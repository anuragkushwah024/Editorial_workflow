"""
The article lifecycle (goal 4). Every status change goes through this file.

    Draft -> In Review -> Approved -> Scheduled -> Published
                              ^           |            |
                              +-- unpublish -----------+

`transition()` handles the five moves a person asks for (submit, approve,
schedule, publish, unpublish). `edit_content()` handles the one automatic
move: editing an Approved or Scheduled article sends it back to In Review.
Both write the status through `_set_status()`, which also writes the
timeline entry, so a status can never change without a trace.

Rejections are DRF exceptions so the API answers with {"detail": "..."}:
403 when this person may never make the move, 400 when the move is wrong
for the article's current status or input.
"""

from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import APIException, PermissionDenied

from .models import Article, ArticleEvent, Status


class LifecycleError(APIException):
    """A move that is not allowed from the article's current state."""

    status_code = 400
    default_detail = "This change is not allowed."


# Who may make each move, which statuses it starts from, and where it goes.
#   who = "author": only the article's own author
#   who = "editor": any editor
#   who = "other_editor": any editor except the article's author
TRANSITIONS = {
    "submit": {
        "from": [Status.DRAFT],
        "to": Status.IN_REVIEW,
        "who": "author",
        "wrong_status": "Only a Draft article can be submitted for review.",
    },
    "approve": {
        "from": [Status.IN_REVIEW],
        "to": Status.APPROVED,
        "who": "other_editor",
        "wrong_status": "Only an In Review article can be approved.",
    },
    "schedule": {
        "from": [Status.APPROVED],
        "to": Status.SCHEDULED,
        "who": "editor",
        "wrong_status": "Only an Approved article can be scheduled.",
    },
    "publish": {
        "from": [Status.APPROVED],
        "to": Status.PUBLISHED,
        "who": "editor",
        "wrong_status": "Only an Approved article can be published.",
    },
    "unpublish": {
        "from": [Status.SCHEDULED, Status.PUBLISHED],
        "to": Status.APPROVED,
        "who": "editor",
        "wrong_status": "Only a Scheduled or Published article can be unpublished.",
    },
}


def _lock(article):
    """Re-read the article and lock its row until the transaction ends.

    If two editors click "approve" at the same moment, the second one waits
    here and then sees the new status, instead of both moves going through.
    """
    return Article.objects.select_for_update().get(pk=article.pk)


def _check_who(action, rule, article, user):
    if rule["who"] == "author":
        if article.author_id != user.id:
            raise PermissionDenied("Only the article's author can submit it for review.")
        return

    if not user.is_editor:
        raise PermissionDenied("Only editors can " + action + " articles.")

    if rule["who"] == "other_editor" and article.author_id == user.id:
        raise PermissionDenied("You cannot approve an article you wrote. Another editor must approve it.")


def _set_status(article, new_status, user, message="", payload=None):
    """The only place an article's status is written. Always leaves a trace."""
    if payload is None:
        payload = {}
    # The role is copied, not looked up later: if this person's role changes,
    # the timeline still shows what they were when they made the change.
    payload["actor_role"] = user.role

    old_status = article.status
    article.status = new_status
    article.save()
    ArticleEvent.objects.create(
        article=article,
        event_type=ArticleEvent.Type.STATUS_CHANGED,
        from_status=old_status,
        to_status=new_status,
        actor=user,
        message=message,
        payload=payload,
    )


def transition(article, action, user, scheduled_for=None):
    """Make one lifecycle move, or raise an error explaining why it isn't allowed."""
    rule = TRANSITIONS[action]

    with transaction.atomic():
        article = _lock(article)
        _check_who(action, rule, article, user)

        if article.status not in rule["from"]:
            raise LifecycleError(rule["wrong_status"])

        payload = {"action": action}

        if action == "schedule":
            if scheduled_for is None:
                raise LifecycleError("A publish time is required to schedule an article.")
            if scheduled_for <= timezone.now():
                raise LifecycleError("The publish time must be in the future.")
            article.scheduled_for = scheduled_for
            payload["scheduled_for"] = scheduled_for.isoformat()

        elif action == "publish":
            article.published_at = timezone.now()
            payload["published_at"] = article.published_at.isoformat()
            # Keep exactly what went live, so "what did the original say?"
            # can always be answered from the timeline.
            payload["title"] = article.title
            payload["body"] = article.body

        elif action == "unpublish":
            article.scheduled_for = None
            article.published_at = None

        _set_status(article, rule["to"], user, payload=payload)

    return article


def edit_content(article, user, new_values):
    """Change an article's title and/or body, applying the lifecycle's edit rules.

    Who may edit is checked before this is called (CanEditArticle).
    """
    with transaction.atomic():
        article = _lock(article)

        if article.status == Status.PUBLISHED:
            raise LifecycleError("A published article cannot be edited directly. Open a revision instead.")

        changed_fields = []
        for field in ["title", "body"]:
            if field in new_values:
                if new_values[field] != getattr(article, field):
                    setattr(article, field, new_values[field])
                    changed_fields.append(field)

        if len(changed_fields) == 0:
            return article

        article.save()
        ArticleEvent.objects.create(
            article=article,
            event_type=ArticleEvent.Type.EDITED,
            actor=user,
            payload={"fields": changed_fields},
        )

        # Text an editor already signed off on has changed, so it must be
        # reviewed again. A scheduled time no longer applies either.
        if article.status == Status.APPROVED or article.status == Status.SCHEDULED:
            article.scheduled_for = None
            _set_status(
                article,
                Status.IN_REVIEW,
                user,
                message="Content was edited after approval, so it must be reviewed again.",
                payload={"action": "edited_after_approval"},
            )

    return article
