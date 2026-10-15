from django.conf import settings
from django.contrib.postgres.indexes import GinIndex
from django.contrib.postgres.search import SearchVector
from django.db import models
from django.db.models import Q

from sections.models import Section


class Status(models.TextChoices):
    DRAFT = "DRAFT", "Draft"
    IN_REVIEW = "IN_REVIEW", "In Review"
    APPROVED = "APPROVED", "Approved"
    SCHEDULED = "SCHEDULED", "Scheduled"
    PUBLISHED = "PUBLISHED", "Published"


class PublishableContent(models.Model):
    """Fields shared by an Article and an ArticleRevision.

    Both go through exactly the same lifecycle (Draft -> In Review ->
    Approved -> Scheduled -> Published), so the state machine in
    articles/services.py can work on either one.
    """

    title = models.CharField(max_length=255)
    body = models.TextField()
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.DRAFT)
    scheduled_for = models.DateTimeField(null=True, blank=True)
    published_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


# What full-text search looks at: title words (weight A) count more than body
# words (weight B). The GIN index below is built on exactly this expression,
# and listing.py searches with the same one, so PostgreSQL can use the index.
SEARCH_VECTOR = SearchVector("title", weight="A", config="english") + SearchVector(
    "body", weight="B", config="english"
)


class Article(PublishableContent):
    """An article. Its title/body are always the *live* content once it has
    been published. Changes after publishing go through ArticleRevision."""

    section = models.ForeignKey(Section, on_delete=models.PROTECT, related_name="articles")
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="articles",
    )

    class Meta:
        ordering = ["-updated_at"]
        indexes = [
            models.Index(fields=["status"]),
            models.Index(fields=["section", "status"]),
            models.Index(fields=["author"]),
            models.Index(fields=["updated_at"]),
            models.Index(fields=["scheduled_for"]),
            models.Index(fields=["published_at"]),
            GinIndex(SEARCH_VECTOR, name="article_search_idx"),
        ]
        constraints = [
            # A Scheduled article must know when it is going out.
            models.CheckConstraint(
                condition=~Q(status=Status.SCHEDULED) | Q(scheduled_for__isnull=False),
                name="article_scheduled_needs_time",
            ),
            # A Published article must have a publish time.
            models.CheckConstraint(
                condition=~Q(status=Status.PUBLISHED) | Q(published_at__isnull=False),
                name="article_published_needs_time",
            ),
        ]

    def __str__(self):
        return self.title


class ArticleRevision(PublishableContent):
    """A change to an already-published article.

    It starts at Draft and walks the same lifecycle. Only when the revision
    itself reaches Published are its title/body copied onto the Article.
    """

    article = models.ForeignKey(Article, on_delete=models.PROTECT, related_name="revisions")
    number = models.PositiveIntegerField()
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="+",
    )

    class Meta:
        ordering = ["article", "number"]
        constraints = [
            models.UniqueConstraint(fields=["article", "number"], name="unique_revision_number"),
            # At most one revision can be in progress per article at a time.
            models.UniqueConstraint(
                fields=["article"],
                condition=~Q(status=Status.PUBLISHED),
                name="one_open_revision_per_article",
            ),
            models.CheckConstraint(
                condition=~Q(status=Status.SCHEDULED) | Q(scheduled_for__isnull=False),
                name="revision_scheduled_needs_time",
            ),
        ]

    def __str__(self):
        return self.article.title + " (revision " + str(self.number) + ")"


class ArticleEvent(models.Model):
    """One entry in an article's timeline. Append-only.

    Rows can only be inserted. Updates and deletes are blocked twice:
      1. here in save()/delete(), for normal Django code, and
      2. by a PostgreSQL trigger (migration 0002), which also catches
         QuerySet.update(), raw SQL and the Django admin.
    Comments are stored as events too, so they are immutable as well.
    """

    class Type(models.TextChoices):
        CREATED = "CREATED", "Created"
        EDITED = "EDITED", "Content edited"
        STATUS_CHANGED = "STATUS_CHANGED", "Status changed"
        REVISION_OPENED = "REVISION_OPENED", "Revision opened"
        REVISION_PUBLISHED = "REVISION_PUBLISHED", "Revision published"
        COMMENT = "COMMENT", "Comment"

    article = models.ForeignKey(Article, on_delete=models.PROTECT, related_name="events")
    # Set when the event is about a revision rather than the article itself.
    revision = models.ForeignKey(
        ArticleRevision,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="events",
    )
    event_type = models.CharField(max_length=30, choices=Type.choices)
    from_status = models.CharField(max_length=20, choices=Status.choices, blank=True)
    to_status = models.CharField(max_length=20, choices=Status.choices, blank=True)
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="+",
    )
    # Comment text, or a short human-readable note for other event types.
    message = models.TextField(blank=True)
    # Extra facts worth keeping forever, e.g. the exact title/body that went
    # live on publish, or the scheduled time. This is how we can always answer
    # "what did the original say?".
    payload = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at", "id"]
        indexes = [
            models.Index(fields=["article", "created_at"]),
        ]

    def save(self, *args, **kwargs):
        if self.pk is not None:
            raise ValueError("Timeline events cannot be modified.")
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValueError("Timeline events cannot be deleted.")

    def __str__(self):
        return self.event_type + " on article " + str(self.article_id)


class AlertDismissal(models.Model):
    """An editor dismissed the 'overdue to publish' alert for one specific
    scheduling of an article (or of one of its revisions).

    The key includes scheduled_for on purpose. If the article is unpublished
    and scheduled again, the new publish time is necessarily different (it
    must be in the future, the old one already passed), so this dismissal no
    longer matches and the alert comes back by itself.
    """

    article = models.ForeignKey(Article, on_delete=models.CASCADE, related_name="alert_dismissals")
    revision = models.ForeignKey(
        ArticleRevision,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="alert_dismissals",
    )
    scheduled_for = models.DateTimeField()
    dismissed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="+",
    )
    dismissed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["article", "revision", "scheduled_for"],
                name="one_dismissal_per_schedule",
                nulls_distinct=False,
            ),
        ]
