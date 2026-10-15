from rest_framework import serializers

from accounts.serializers import UserSerializer
from sections.models import Section

from .models import Article, ArticleEvent, ArticleRevision


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


class RevisionSerializer(serializers.ModelSerializer):
    """A revision of a published article. Only title and body can be written;
    everything else changes through the lifecycle."""

    created_by = UserSerializer(read_only=True)
    article_id = serializers.IntegerField(read_only=True)

    class Meta:
        model = ArticleRevision
        fields = [
            "id",
            "article_id",
            "number",
            "title",
            "body",
            "status",
            "scheduled_for",
            "published_at",
            "created_by",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "number",
            "status",
            "scheduled_for",
            "published_at",
            "created_at",
            "updated_at",
        ]

    def validate_title(self, value):
        value = value.strip()
        if value == "":
            raise serializers.ValidationError("Title cannot be empty.")
        return value


class OpenRevisionSerializer(serializers.Serializer):
    """Opening a revision: title and body are optional and default to the live text."""

    title = serializers.CharField(required=False, max_length=255)
    body = serializers.CharField(required=False)

    def validate_title(self, value):
        value = value.strip()
        if value == "":
            raise serializers.ValidationError("Title cannot be empty.")
        return value


class EventSerializer(serializers.ModelSerializer):
    """One timeline entry, read-only. There is no serializer that writes events
    from client data: the server writes every entry itself."""

    actor = UserSerializer(read_only=True)
    actor_role = serializers.SerializerMethodField()
    revision = serializers.SerializerMethodField()

    class Meta:
        model = ArticleEvent
        fields = [
            "id",
            "event_type",
            "from_status",
            "to_status",
            "actor",
            "actor_role",
            "revision",
            "message",
            "payload",
            "created_at",
        ]
        read_only_fields = fields

    def get_actor_role(self, event):
        # Status changes store the role the person had at that moment.
        # For other entries, fall back to their current role.
        stored = event.payload.get("actor_role")
        if stored is not None:
            return stored
        return event.actor.role

    def get_revision(self, event):
        if event.revision is None:
            return None
        return {"id": event.revision.id, "number": event.revision.number}


class CommentInputSerializer(serializers.Serializer):
    # The field itself lets blank through, so a missing, empty or spaces-only
    # comment all get the same clear message below.
    message = serializers.CharField(required=False, allow_blank=True, max_length=5000)

    def validate_message(self, value):
        value = value.strip()
        if value == "":
            raise serializers.ValidationError("A comment cannot be empty.")
        return value

    def validate(self, attrs):
        if "message" not in attrs:
            raise serializers.ValidationError({"message": ["A comment cannot be empty."]})
        return attrs
