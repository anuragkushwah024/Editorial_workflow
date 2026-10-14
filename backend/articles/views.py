from django.db import transaction
from rest_framework import mixins, serializers, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from sections.access import is_assigned

from .access import CanEditArticle, visible_articles
from .lifecycle import edit_content, transition
from .models import ArticleEvent
from .serializers import ArticleSerializer, ArticleUpdateSerializer


class ScheduleInputSerializer(serializers.Serializer):
    # Optional here so the lifecycle can answer with its own clear message
    # (and check who is asking first) when the time is missing.
    scheduled_for = serializers.DateTimeField(required=False)


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

    The lifecycle rules themselves live in lifecycle.py, not here.
    There is no DELETE: an article's timeline must outlive any change to it.
    Search, filters and pagination come in Phase 4.
    """

    http_method_names = ["get", "post", "patch", "head", "options"]
    permission_classes = [IsAuthenticated, CanEditArticle]
    serializer_class = ArticleSerializer

    def get_queryset(self):
        # Anything outside visible_articles() is a 404 for this user, so a
        # writer can't even learn that an article in another section exists.
        queryset = visible_articles(self.request.user).select_related("section", "author")
        if self.action == "list":
            # Archiving a section hides its articles from the default list too.
            queryset = queryset.filter(section__is_archived=False)
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
