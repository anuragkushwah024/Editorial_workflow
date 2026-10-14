from django.db import transaction
from rest_framework import mixins, viewsets
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.permissions import IsAuthenticated

from sections.access import is_assigned

from .access import CanEditArticle, visible_articles
from .models import ArticleEvent
from .serializers import ArticleSerializer, ArticleUpdateSerializer


class ArticleViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.CreateModelMixin,
    mixins.UpdateModelMixin,
    viewsets.GenericViewSet,
):
    """
    /api/articles/       GET list, POST create
    /api/articles/{id}/  GET one, PATCH edit title/body

    There is no DELETE: an article's timeline must outlive any change to it.
    Search, filters and pagination come in Phase 4.
    """

    http_method_names = ["get", "post", "patch", "head", "options"]
    permission_classes = [IsAuthenticated, CanEditArticle]

    def get_serializer_class(self):
        if self.action == "partial_update":
            return ArticleUpdateSerializer
        return ArticleSerializer

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

    def perform_update(self, serializer):
        # Who may edit was already checked by CanEditArticle.
        # Which statuses allow editing comes with the lifecycle (Phase 3, step 2).
        article = serializer.instance
        changed_fields = []
        for field in ["title", "body"]:
            if field in serializer.validated_data:
                if serializer.validated_data[field] != getattr(article, field):
                    changed_fields.append(field)

        with transaction.atomic():
            serializer.save()
            if len(changed_fields) > 0:
                ArticleEvent.objects.create(
                    article=article,
                    event_type=ArticleEvent.Type.EDITED,
                    actor=self.request.user,
                    payload={"fields": changed_fields},
                )
