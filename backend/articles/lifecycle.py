"""
The article lifecycle (goal 4). Every status change goes through this file.

    Draft -> In Review -> Approved -> Scheduled -> Published
                              ^           |            |
                              +-- unpublish -----------+

The same rules apply to an Article and to an ArticleRevision (a change to an
article that is already published). In this file both are called an "item".

`transition()` handles the five moves a person asks for (submit, approve,
schedule, publish, unpublish). `edit_content()` handles the one automatic
move: editing an Approved or Scheduled item sends it back to In Review.
`open_revision()` starts a revision of a published article.
Status is only ever written by `_set_status()`, which also writes the
timeline entry, so a status can never change without a trace.

Rejections are DRF exceptions so the API answers with {"detail": "..."}:
403 when this person may never make the move, 400 when the move is wrong
for the item's current status or input.
"""

from django.db import IntegrityError, transaction
from django.db.models import Max
from django.utils import timezone
from rest_framework.exceptions import APIException, PermissionDenied, ValidationError

from .models import Article, ArticleEvent, ArticleRevision, Status


class LifecycleError(APIException):
    """A move that is not allowed from the item's current state."""

    status_code = 400
    default_detail = "This change is not allowed."


# Who may make each move, which statuses it starts from, and where it goes.
#   who = "author": only the item's own author
#   who = "editor": any editor
#   who = "other_editor": any editor except the item's author
# "{thing}" in a message becomes "article" or "revision".
TRANSITIONS = {
    "submit": {
        "from": [Status.DRAFT],
        "to": Status.IN_REVIEW,
        "who": "author",
        "wrong_status": "Only a Draft {thing} can be submitted for review.",
    },
    "approve": {
        "from": [Status.IN_REVIEW],
        "to": Status.APPROVED,
        "who": "other_editor",
        "wrong_status": "Only an In Review {thing} can be approved.",
    },
    "schedule": {
        "from": [Status.APPROVED],
        "to": Status.SCHEDULED,
        "who": "editor",
        "wrong_status": "Only an Approved {thing} can be scheduled.",
    },
    "publish": {
        # From Scheduled too: that is how a scheduled article goes live, either
        # by an editor (e.g. from an overdue alert) or by the publish_due command.
        "from": [Status.APPROVED, Status.SCHEDULED],
        "to": Status.PUBLISHED,
        "who": "editor",
        "wrong_status": "Only an Approved or Scheduled {thing} can be published.",
    },
    "unpublish": {
        "from": [Status.SCHEDULED, Status.PUBLISHED],
        "to": Status.APPROVED,
        "who": "editor",
        "wrong_status": "Only a Scheduled or Published {thing} can be unpublished.",
    },
}


# --- small helpers so the same code works on articles and revisions -------

def _is_revision(item):
    return isinstance(item, ArticleRevision)


def _thing(item):
    if _is_revision(item):
        return "revision"
    return "article"


def _a_thing(item):
    if _is_revision(item):
        return "a revision"
    return "an article"


def _author_id(item):
    """The person who wrote this item: the article's author, or whoever opened the revision."""
    if _is_revision(item):
        return item.created_by_id
    return item.author_id


def _article_of(item):
    if _is_revision(item):
        return item.article
    return item


def _lock(item):
    """Re-read the item and lock its row(s) until the transaction ends.

    If two editors click "approve" at the same moment, the second one waits
    here and then sees the new status, instead of both moves going through.
    For a revision the article is locked too (always article first, so two
    requests can never wait on each other), because publishing a revision
    changes the article.
    """
    if _is_revision(item):
        article = Article.objects.select_for_update().get(pk=item.article_id)
        revision = ArticleRevision.objects.select_for_update().get(pk=item.pk)
        revision.article = article
        return revision
    return Article.objects.select_for_update().get(pk=item.pk)


def _check_who(action, rule, item, user):
    thing = _thing(item)

    if rule["who"] == "author":
        if _author_id(item) != user.id:
            raise PermissionDenied("Only the " + thing + "'s author can submit it for review.")
        return

    if not user.is_editor:
        raise PermissionDenied("Only editors can " + action + " " + thing + "s.")

    if rule["who"] == "other_editor" and _author_id(item) == user.id:
        raise PermissionDenied(
            "You cannot approve " + _a_thing(item) + " you wrote. Another editor must approve it."
        )


def _record(item, event_type, user, from_status="", to_status="", message="", payload=None):
    """Write one timeline entry for this item."""
    if payload is None:
        payload = {}
    revision = None
    if _is_revision(item):
        revision = item
    ArticleEvent.objects.create(
        article=_article_of(item),
        revision=revision,
        event_type=event_type,
        from_status=from_status,
        to_status=to_status,
        actor=user,
        message=message,
        payload=payload,
    )


def _set_status(item, new_status, user, message="", payload=None):
    """The only place a status is written. Always leaves a trace."""
    if payload is None:
        payload = {}
    # The role is copied, not looked up later: if this person's role changes,
    # the timeline still shows what they were when they made the change.
    payload["actor_role"] = user.role

    old_status = item.status
    item.status = new_status
    item.save()
    _record(
        item,
        ArticleEvent.Type.STATUS_CHANGED,
        user,
        from_status=old_status,
        to_status=new_status,
        message=message,
        payload=payload,
    )


# --- the public functions --------------------------------------------------

def create_article(user, section, title, body):
    """Create a Draft article with its first timeline entry.

    Used by the API and by the seed_demo command, so both follow the same rules.
    """
    if user.is_writer and not section.assignments.filter(writer=user).exists():
        raise PermissionDenied("You can only create articles in sections you are assigned to.")
    if section.is_archived:
        raise ValidationError({"section_id": ["This section is archived. Restore it first."]})

    # The article and its first timeline entry are saved together or not at all.
    with transaction.atomic():
        article = Article.objects.create(section=section, author=user, title=title, body=body)
        _record(article, ArticleEvent.Type.CREATED, user, to_status=article.status)
    return article


def add_comment(article, user, message):
    """Add a comment. Comments are timeline entries, so they can never change."""
    event = ArticleEvent.objects.create(
        article=article,
        event_type=ArticleEvent.Type.COMMENT,
        actor=user,
        message=message,
    )
    return event


def transition(item, action, user, scheduled_for=None, message=""):
    """Make one lifecycle move, or raise an error explaining why it isn't allowed.

    `message` is an optional note for the timeline entry, e.g. when the
    publish_due command publishes something automatically.
    """
    rule = TRANSITIONS[action]

    with transaction.atomic():
        item = _lock(item)
        _check_who(action, rule, item, user)

        if _is_revision(item) and action == "unpublish" and item.status == Status.PUBLISHED:
            raise LifecycleError(
                "A published revision is already part of the live article. Unpublish the article instead."
            )

        if item.status not in rule["from"]:
            raise LifecycleError(rule["wrong_status"].replace("{thing}", _thing(item)))

        if _is_revision(item) and (action == "schedule" or action == "publish"):
            if item.article.status != Status.PUBLISHED:
                raise LifecycleError(
                    "The article is no longer published, so this revision can't go live. "
                    "Edit the article directly instead."
                )

        payload = {"action": action}

        if action == "schedule":
            if scheduled_for is None:
                raise LifecycleError("A publish time is required to schedule " + _a_thing(item) + ".")
            if scheduled_for <= timezone.now():
                raise LifecycleError("The publish time must be in the future.")
            item.scheduled_for = scheduled_for
            payload["scheduled_for"] = scheduled_for.isoformat()

        elif action == "publish":
            item.published_at = timezone.now()
            payload["published_at"] = item.published_at.isoformat()
            if item.scheduled_for is not None:
                # It was scheduled; keep the planned time in the history, and
                # clear it on the item, because published_at is now the truth.
                payload["was_scheduled_for"] = item.scheduled_for.isoformat()
                item.scheduled_for = None
            # Keep exactly what went live, so "what did the original say?"
            # can always be answered from the timeline.
            payload["title"] = item.title
            payload["body"] = item.body

        elif action == "unpublish":
            item.scheduled_for = None
            item.published_at = None

        _set_status(item, rule["to"], user, message=message, payload=payload)

        if _is_revision(item) and action == "publish":
            _apply_revision(item, user)

    return item


def _apply_revision(revision, user):
    """A revision just reached Published: its text replaces the live article's.

    The article keeps its original publish time; this is a correction, not a
    new publication.
    """
    article = revision.article
    previous_title = article.title
    previous_body = article.body

    article.title = revision.title
    article.body = revision.body
    article.save()

    _record(
        revision,
        ArticleEvent.Type.REVISION_PUBLISHED,
        user,
        message="Revision " + str(revision.number) + " replaced the live text.",
        payload={
            "number": revision.number,
            "previous_title": previous_title,
            "previous_body": previous_body,
        },
    )


def edit_content(item, user, new_values):
    """Change an item's title and/or body, applying the lifecycle's edit rules.

    Who may edit is checked before this is called (CanEditArticle / CanEditRevision).
    """
    with transaction.atomic():
        item = _lock(item)

        if item.status == Status.PUBLISHED:
            if _is_revision(item):
                raise LifecycleError("This revision is already published. Open a new revision instead.")
            raise LifecycleError("A published article cannot be edited directly. Open a revision instead.")

        changed_fields = []
        for field in ["title", "body"]:
            if field in new_values:
                if new_values[field] != getattr(item, field):
                    setattr(item, field, new_values[field])
                    changed_fields.append(field)

        if len(changed_fields) == 0:
            return item

        item.save()
        _record(item, ArticleEvent.Type.EDITED, user, payload={"fields": changed_fields})

        # Text an editor already signed off on has changed, so it must be
        # reviewed again. A scheduled time no longer applies either.
        if item.status == Status.APPROVED or item.status == Status.SCHEDULED:
            item.scheduled_for = None
            _set_status(
                item,
                Status.IN_REVIEW,
                user,
                message="Content was edited after approval, so it must be reviewed again.",
                payload={"action": "edited_after_approval"},
            )

    return item


def open_revision(article, user, title=None, body=None):
    """Start a revision of a published article.

    The revision starts at Draft with a copy of the live text (or the text
    given). The live article does not change until the revision is published.
    """
    if not user.is_editor and article.author_id != user.id:
        raise PermissionDenied("Only the article's author or an editor can open a revision.")

    with transaction.atomic():
        article = _lock(article)

        if article.status != Status.PUBLISHED:
            raise LifecycleError("Only a published article needs a revision. Edit the article directly instead.")

        open_one = article.revisions.exclude(status=Status.PUBLISHED).first()
        if open_one is not None:
            raise LifecycleError(
                "This article already has an open revision (number " + str(open_one.number) + "). "
                "It must be published before another one is opened."
            )

        highest = article.revisions.aggregate(highest=Max("number"))["highest"]
        number = 1
        if highest is not None:
            number = highest + 1

        if title is None:
            title = article.title
        if body is None:
            body = article.body

        try:
            # A savepoint, so a clash with the database rule (two people opening
            # a revision at the same moment) can be turned into a clear message.
            with transaction.atomic():
                revision = ArticleRevision.objects.create(
                    article=article, number=number, title=title, body=body, created_by=user
                )
        except IntegrityError:
            raise LifecycleError("This article already has an open revision.")

        _record(
            revision,
            ArticleEvent.Type.REVISION_OPENED,
            user,
            to_status=revision.status,
            payload={"number": number},
        )

    return revision
