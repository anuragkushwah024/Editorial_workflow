from django.db import IntegrityError
from django.db.models import Count
from django.utils import timezone
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from accounts.permissions import IsEditor

from .access import visible_sections
from .models import SectionAssignment
from .serializers import AssignWriterSerializer, SectionDetailSerializer, SectionSerializer


def error(message, http_status=status.HTTP_400_BAD_REQUEST):
    """A rejected request always answers with a human-readable reason."""
    return Response({"detail": message}, status=http_status)


class SectionViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.CreateModelMixin,
    mixins.UpdateModelMixin,
    viewsets.GenericViewSet,
):
    """
    /api/sections/                        GET list, POST create (editor)
    /api/sections/{id}/                   GET one, PATCH edit (editor)
    /api/sections/{id}/archive/           POST (editor)
    /api/sections/{id}/restore/           POST (editor)
    /api/sections/{id}/writers/           POST assign a writer (editor)
    /api/sections/{id}/writers/{user_id}/ DELETE remove a writer (editor)

    There is deliberately no DELETE on a section: archiving is the only way
    to retire one, so its articles and history are never destroyed.
    """

    http_method_names = ["get", "post", "patch", "delete", "head", "options"]

    def get_permissions(self):
        if self.action == "list" or self.action == "retrieve":
            return [IsAuthenticated()]
        return [IsEditor()]

    def get_serializer_class(self):
        if self.action == "list":
            return SectionSerializer
        return SectionDetailSerializer

    def get_queryset(self):
        user = self.request.user
        queryset = visible_sections(user).select_related("owner")
        queryset = queryset.annotate(writer_count=Count("assignments", distinct=True))

        if self.action == "list":
            # Archived sections are hidden from the default view (goal 2).
            # Editors can ask for them explicitly; writers never see them.
            show_archived = self.request.query_params.get("archived") == "true"
            if user.is_editor and show_archived:
                queryset = queryset.filter(is_archived=True)
            else:
                queryset = queryset.filter(is_archived=False)
        elif not user.is_editor:
            # A writer opening an archived section by id gets a 404 too.
            queryset = queryset.filter(is_archived=False)

        return queryset.order_by("name")

    def fresh_detail(self, response_status=status.HTTP_200_OK):
        """Re-read the section after a change so counts in the response are current.

        The object loaded before the change still carries its old annotated
        writer_count, which would report the number from before the change.
        """
        section = self.get_object()
        return Response(SectionDetailSerializer(section).data, status=response_status)

    @action(detail=True, methods=["post"])
    def archive(self, request, pk=None):
        section = self.get_object()
        if section.is_archived:
            return error("This section is already archived.")
        section.is_archived = True
        section.archived_at = timezone.now()
        section.save(update_fields=["is_archived", "archived_at", "updated_at"])
        return self.fresh_detail()

    @action(detail=True, methods=["post"])
    def restore(self, request, pk=None):
        section = self.get_object()
        if not section.is_archived:
            return error("This section is not archived.")
        section.is_archived = False
        section.archived_at = None
        section.save(update_fields=["is_archived", "archived_at", "updated_at"])
        return self.fresh_detail()

    @action(detail=True, methods=["post"], url_path="writers")
    def assign_writer(self, request, pk=None):
        section = self.get_object()
        if section.is_archived:
            return error("Writers cannot be changed on an archived section. Restore it first.")

        input_serializer = AssignWriterSerializer(data=request.data)
        input_serializer.is_valid(raise_exception=True)
        writer_id = input_serializer.validated_data["writer_id"]

        if SectionAssignment.objects.filter(section=section, writer_id=writer_id).exists():
            return error("This writer is already assigned to this section.")

        try:
            SectionAssignment.objects.create(section=section, writer_id=writer_id, assigned_by=request.user)
        except IntegrityError:
            # Two editors clicked at the same moment; the unique constraint caught it.
            return error("This writer is already assigned to this section.")

        return self.fresh_detail(status.HTTP_201_CREATED)

    @action(detail=True, methods=["delete"], url_path=r"writers/(?P<user_id>\d+)")
    def remove_writer(self, request, pk=None, user_id=None):
        section = self.get_object()
        if section.is_archived:
            return error("Writers cannot be changed on an archived section. Restore it first.")

        deleted_count, _ = SectionAssignment.objects.filter(section=section, writer_id=user_id).delete()
        if deleted_count == 0:
            return error("This writer is not assigned to this section.", status.HTTP_404_NOT_FOUND)

        return self.fresh_detail()
