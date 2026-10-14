from rest_framework import serializers

from accounts.serializers import UserSerializer
from sections.models import Section

from .models import Article


class SectionSummarySerializer(serializers.ModelSerializer):
    """Just enough about the section to show it next to an article."""

    class Meta:
        model = Section
        fields = ["id", "name", "is_archived"]


class ArticleSerializer(serializers.ModelSerializer):
    """Used to list, open and create articles.

    The section is read as a small nested object but written as `section_id`.
    The author is never sent by the client: it is always the logged-in user.
    Status and publish times are read-only here; they change only through the
    lifecycle actions (Phase 3, step 2).
    """

    section = SectionSummarySerializer(read_only=True)
    section_id = serializers.PrimaryKeyRelatedField(
        source="section",
        queryset=Section.objects.all(),
        write_only=True,
        error_messages={"does_not_exist": "No section with this id."},
    )
    author = UserSerializer(read_only=True)

    class Meta:
        model = Article
        fields = [
            "id",
            "title",
            "body",
            "section",
            "section_id",
            "author",
            "status",
            "scheduled_for",
            "published_at",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["status", "scheduled_for", "published_at", "created_at", "updated_at"]

    def validate_title(self, value):
        value = value.strip()
        if value == "":
            raise serializers.ValidationError("Title cannot be empty.")
        return value


class ArticleUpdateSerializer(ArticleSerializer):
    """Editing an article changes its title and body only.

    Moving an article to another section is not supported, so section_id is
    left out; if a client sends it anyway, it is ignored.
    """

    class Meta(ArticleSerializer.Meta):
        fields = [
            "id",
            "title",
            "body",
            "section",
            "author",
            "status",
            "scheduled_for",
            "published_at",
            "created_at",
            "updated_at",
        ]
