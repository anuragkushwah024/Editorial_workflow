from rest_framework import serializers

from accounts.models import User
from accounts.serializers import UserSerializer

from .models import Section, SectionAssignment


class SectionSerializer(serializers.ModelSerializer):
    """Used for listing, creating and editing sections.

    The owner is read as a nested object but written as `owner_id`, so the
    frontend gets names to display and only sends an id back.
    """

    owner = UserSerializer(read_only=True)
    owner_id = serializers.PrimaryKeyRelatedField(
        source="owner",
        queryset=User.objects.filter(role=User.Role.EDITOR, is_active=True),
        write_only=True,
        error_messages={"does_not_exist": "The owner must be an active editor."},
    )
    writer_count = serializers.SerializerMethodField()

    class Meta:
        model = Section
        fields = [
            "id",
            "name",
            "description",
            "owner",
            "owner_id",
            "is_archived",
            "archived_at",
            "writer_count",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["is_archived", "archived_at", "created_at", "updated_at"]

    def get_writer_count(self, section):
        # The list view annotates this in one query. A freshly created or
        # changed section has no annotation, so count it directly.
        annotated = getattr(section, "writer_count", None)
        if annotated is not None:
            return annotated
        return section.assignments.count()

    def validate_name(self, value):
        value = value.strip()
        if value == "":
            raise serializers.ValidationError("Name cannot be empty.")

        # "Tech" and "tech" would confuse everyone, so compare without case.
        # The database UNIQUE constraint is the backstop for exact duplicates.
        clashes = Section.objects.filter(name__iexact=value)
        if self.instance is not None:
            clashes = clashes.exclude(pk=self.instance.pk)
        if clashes.exists():
            raise serializers.ValidationError("A section with this name already exists.")
        return value


class SectionDetailSerializer(SectionSerializer):
    """A single section, with the list of writers assigned to it."""

    writers = serializers.SerializerMethodField()

    class Meta(SectionSerializer.Meta):
        fields = SectionSerializer.Meta.fields + ["writers"]

    def get_writers(self, section):
        assignments = (
            SectionAssignment.objects.filter(section=section)
            .select_related("writer")
            .order_by("writer__full_name")
        )
        result = []
        for assignment in assignments:
            result.append(UserSerializer(assignment.writer).data)
        return result


class AssignWriterSerializer(serializers.Serializer):
    writer_id = serializers.IntegerField()

    def validate_writer_id(self, value):
        writer = User.objects.filter(pk=value, is_active=True).first()
        if writer is None:
            raise serializers.ValidationError("No active user with this id.")
        if not writer.is_writer:
            raise serializers.ValidationError("Only users with the Writer role can be assigned to a section.")
        return value
