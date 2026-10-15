from django.db import transaction
from django.utils import timezone
from rest_framework import mixins, serializers, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from sections.access import is_assigned

from accounts.permissions import IsEditor

from .access import CanEditArticle, CanEditRevision, visible_articles, visible_revisions
from .bulk import BULK_ACTIONS, MAX_ARTICLES, run_bulk
from .calendar_export import calendar_csv_response
from .lifecycle import edit_content, open_revision, transition
from .listing import ArticlePagination, filter_articles
from .models import ArticleEvent
from .serializers import (
    ArticleSerializer,
    ArticleUpdateSerializer,
    CommentInputSerializer,
    EventSerializer,
    OpenRevisionSerializer,
    RevisionSerializer,
)


class ScheduleInputSerializer(serializers.Serializer):
    # Optional here so the lifecycle can answer with its own clear message
    # (and check who is asking first) when the time is missing.
    scheduled_for = serializers.DateTimeField(required=False)


class BulkInputSerializer(serializers.Serializer):
    action = serializers.ChoiceField(
        choices=BULK_ACTIONS, error_messages={"invalid_choice": "Action must be schedule or unpublish."}
    )
    ids = serializers.ListField(
        child=serializers.IntegerField(min_value=1),
        min_length=1,
        max_length=MAX_ARTICLES,
        error_messages={
            "min_length": "Select at least one article.",
            "max_length": "At most " + str(MAX_ARTICLES) + " articles can be changed at once.",
        },
    )
    scheduled_for = serializers.DateTimeField(required=False)

    def validate(self, attrs):
        # One check for the whole batch, instead of the same rejection on every article.
        if attrs["action"] == "schedule":
            scheduled_for = attrs.get("scheduled_for")
            if scheduled_for is None:
                raise serializers.ValidationError({"scheduled_for": ["A publish time is required to schedule."]})
            if scheduled_for <= timezone.now():
                raise serializers.ValidationError({"scheduled_for": ["The publish time must be in the future."]})

        # The same id twice would be tried twice; keep the first one only.
        unique_ids = []
        for article_id in attrs["ids"]:
            if article_id not in unique_ids:
                unique_ids.append(article_id)
        attrs["ids"] = unique_ids
        return attrs


class ArticleViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.CreateModelMixin,
    viewsets.GenericViewSet,
):
    """
    /api/articles/                  GET list, POST create
    /api/articles/{id}/             GET one, PATCH edit title/body
    /api/articles/{id}/submit/      POST  author: Draft -> In Review
    /api/articles/{id}/approve/     POST  another editor: In Review -> Approved
    /api/articles/{id}/schedule/    POST  editor: Approved -> Scheduled ({"scheduled_for": ...})
    /api/articles/{id}/publish/     POST  editor: Approved -> Published now
    /api/articles/{id}/unpublish/   POST  editor: Scheduled/Published -> Approved
    /api/articles/{id}/revisions/   GET list, POST open a revision of a published article
    /api/articles/{id}/timeline/    GET the full history, oldest first
    /api/articles/{id}/comments/    POST add a comment (anyone who can see the article)

    The lifecycle rules themselves live in lifecycle.py, not here.
    There is no DELETE: an article's timeline must outlive any change to it.
    /api/articles/?q=&section=&status=&author=&sort=&page=   search, filters, pages (listing.py)
    /api/articles/bulk/             POST  editor: schedule or unpublish many articles (bulk.py)
    /api/articles/calendar/         GET   Scheduled and Published articles as CSV (calendar_export.py)
    """

    http_method_names = ["get", "post", "patch", "head", "options"]
    permission_classes = [IsAuthenticated, CanEditArticle]
    serializer_class = ArticleSerializer
    pagination_class = ArticlePagination

    def get_queryset(self):
        # Anything outside visible_articles() is a 404 for this user, so a
        # writer can't even learn that an article in another section exists.
        queryset = visible_articles(self.request.user).select_related("section", "author")
        if self.action == "list":
            # Search, filters and sorting (listing.py). Archived sections stay
            # hidden unless one section is asked for.
            return filter_articles(queryset, self.request.query_params, self.request.user)
        return queryset.order_by("-updated_at")

    def perform_create(self, serializer):
        user = self.request.user
        section = serializer.validated_data["section"]

        if user.is_writer and not is_assigned(user, section):
            raise PermissionDenied("You can only create articles in sections you are assigned to.")
        if section.is_archived:
            raise ValidationError({"section_id": ["This section is archived. Restore it first."]})

        # The article and its first timeline entry are saved together or not at all.
        with transaction.atomic():
            article = serializer.save(author=user)
            ArticleEvent.objects.create(
                article=article,
                event_type=ArticleEvent.Type.CREATED,
                to_status=article.status,
                actor=user,
            )

    def partial_update(self, request, pk=None):
        # get_object() checks visibility (404) and CanEditArticle (403).
        article = self.get_object()
        input_serializer = ArticleUpdateSerializer(article, data=request.data, partial=True)
        input_serializer.is_valid(raise_exception=True)
        article = edit_content(article, request.user, input_serializer.validated_data)
        return Response(ArticleSerializer(article).data)

    # --- lifecycle moves -------------------------------------------------
    # These use IsAuthenticated only: CanEditArticle is about editing content,
    # while who may make each move is decided by lifecycle.transition().

    def move(self, action_name, scheduled_for=None):
        article = self.get_object()
        article = transition(article, action_name, self.request.user, scheduled_for)
        return Response(ArticleSerializer(article).data)

    @action(detail=True, methods=["post"], permission_classes=[IsAuthenticated])
    def submit(self, request, pk=None):
        return self.move("submit")

    @action(detail=True, methods=["post"], permission_classes=[IsAuthenticated])
    def approve(self, request, pk=None):
        return self.move("approve")

    @action(detail=True, methods=["post"], permission_classes=[IsAuthenticated])
    def schedule(self, request, pk=None):
        input_serializer = ScheduleInputSerializer(data=request.data)
        input_serializer.is_valid(raise_exception=True)
        scheduled_for = input_serializer.validated_data.get("scheduled_for")
        return self.move("schedule", scheduled_for)

    @action(detail=True, methods=["post"], permission_classes=[IsAuthenticated])
    def publish(self, request, pk=None):
        return self.move("publish")

    @action(detail=True, methods=["post"], permission_classes=[IsAuthenticated])
    def unpublish(self, request, pk=None):
        return self.move("unpublish")

    # --- many articles at once ---------------------------------------------

    @action(detail=False, methods=["post"], permission_classes=[IsEditor])
    def bulk(self, request):
        input_serializer = BulkInputSerializer(data=request.data)
        input_serializer.is_valid(raise_exception=True)
        data = input_serializer.validated_data
        result = run_bulk(request.user, data["action"], data["ids"], data.get("scheduled_for"))
        return Response(result)

    @action(detail=False, methods=["get"], permission_classes=[IsAuthenticated])
    def calendar(self, request):
        return calendar_csv_response(request.user)

    # --- timeline and comments --------------------------------------------
    # Both are POST/GET only on purpose: there is no way through the API to
    # change or delete a timeline entry, and the database trigger from
    # Phase 1 blocks it underneath as well.

    @action(detail=True, methods=["get"], permission_classes=[IsAuthenticated])
    def timeline(self, request, pk=None):
        article = self.get_object()
        events = article.events.select_related("actor", "revision").order_by("created_at", "id")
        return Response(EventSerializer(events, many=True).data)

    @action(detail=True, methods=["post"], permission_classes=[IsAuthenticated])
    def comments(self, request, pk=None):
        # get_object() is the access check: seeing the article is enough to comment.
        article = self.get_object()
        input_serializer = CommentInputSerializer(data=request.data)
        input_serializer.is_valid(raise_exception=True)
        event = ArticleEvent.objects.create(
            article=article,
            event_type=ArticleEvent.Type.COMMENT,
            actor=request.user,
            message=input_serializer.validated_data["message"],
        )
        return Response(EventSerializer(event).data, status=201)

    # --- revisions -------------------------------------------------------

    @action(detail=True, methods=["get", "post"], permission_classes=[IsAuthenticated])
    def revisions(self, request, pk=None):
        article = self.get_object()

        if request.method == "GET":
            revisions = article.revisions.select_related("created_by").order_by("number")
            return Response(RevisionSerializer(revisions, many=True).data)

        input_serializer = OpenRevisionSerializer(data=request.data)
        input_serializer.is_valid(raise_exception=True)
        revision = open_revision(
            article,
            request.user,
            title=input_serializer.validated_data.get("title"),
            body=input_serializer.validated_data.get("body"),
        )
        return Response(RevisionSerializer(revision).data, status=201)


class RevisionViewSet(mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    """
    /api/revisions/{id}/             GET one, PATCH edit title/body
    /api/revisions/{id}/submit/      POST  (and approve/, schedule/, publish/, unpublish/)

    A revision follows exactly the same lifecycle as an article; the rules
    are the same code in lifecycle.py. Publishing it replaces the article's
    live text.
    """

    http_method_names = ["get", "post", "patch", "head", "options"]
    permission_classes = [IsAuthenticated, CanEditRevision]
    serializer_class = RevisionSerializer

    def get_queryset(self):
        # Revisions of articles this user can't see are a 404.
        return visible_revisions(self.request.user).select_related("article", "created_by")

    def partial_update(self, request, pk=None):
        revision = self.get_object()
        input_serializer = RevisionSerializer(revision, data=request.data, partial=True)
        input_serializer.is_valid(raise_exception=True)
        revision = edit_content(revision, request.user, input_serializer.validated_data)
        return Response(RevisionSerializer(revision).data)

    def move(self, action_name, scheduled_for=None):
        revision = self.get_object()
        revision = transition(revision, action_name, self.request.user, scheduled_for)
        return Response(RevisionSerializer(revision).data)

    @action(detail=True, methods=["post"], permission_classes=[IsAuthenticated])
    def submit(self, request, pk=None):
        return self.move("submit")

    @action(detail=True, methods=["post"], permission_classes=[IsAuthenticated])
    def approve(self, request, pk=None):
        return self.move("approve")

    @action(detail=True, methods=["post"], permission_classes=[IsAuthenticated])
    def schedule(self, request, pk=None):
        input_serializer = ScheduleInputSerializer(data=request.data)
        input_serializer.is_valid(raise_exception=True)
        return self.move("schedule", input_serializer.validated_data.get("scheduled_for"))

    @action(detail=True, methods=["post"], permission_classes=[IsAuthenticated])
    def publish(self, request, pk=None):
        return self.move("publish")

    @action(detail=True, methods=["post"], permission_classes=[IsAuthenticated])
    def unpublish(self, request, pk=None):
        return self.move("unpublish")
