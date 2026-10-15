"""
Overdue publish alerts (goal 10).

An article, or a revision of one, is overdue when it is still Scheduled and
its publish time has passed.

An editor can dismiss an alert. The dismissal (AlertDismissal, designed on
Day 1) is saved for that exact scheduled time. If the article is unpublished
and scheduled again, the new time is different (it had to be in the future,
the old one is in the past), so the old dismissal no longer matches and the
alert comes back by itself when the new time also passes. No extra code has
to "reset" anything.
"""

from django.db import IntegrityError, transaction
from django.db.models import Exists, OuterRef
from django.utils import timezone
from rest_framework.exceptions import NotFound

from .access import visible_articles, visible_revisions
from .lifecycle import LifecycleError
from .models import AlertDismissal, Status


def _minutes_late(scheduled_for, now):
    return int((now - scheduled_for).total_seconds() // 60)


def overdue_items(user, now=None):
    """Overdue articles and revisions this user can see, not dismissed, most late first."""
    if now is None:
        now = timezone.now()

    # An alert is hidden only by a dismissal for this item AND this exact time.
    article_dismissed = AlertDismissal.objects.filter(
        article=OuterRef("pk"), revision__isnull=True, scheduled_for=OuterRef("scheduled_for")
    )
    articles = (
        visible_articles(user)
        .filter(status=Status.SCHEDULED, scheduled_for__lt=now)
        .exclude(Exists(article_dismissed))
        .select_related("section")
    )

    revision_dismissed = AlertDismissal.objects.filter(
        revision=OuterRef("pk"), scheduled_for=OuterRef("scheduled_for")
    )
    revisions = (
        visible_revisions(user)
        .filter(status=Status.SCHEDULED, scheduled_for__lt=now)
        .exclude(Exists(revision_dismissed))
        .select_related("article__section")
    )

    items = []
    for article in articles:
        items.append({
            "kind": "article",
            "article_id": article.id,
            "revision_id": None,
            "revision_number": None,
            "title": article.title,
            "section": article.section.name,
            "scheduled_for": article.scheduled_for,
            "minutes_late": _minutes_late(article.scheduled_for, now),
        })
    for revision in revisions:
        items.append({
            "kind": "revision",
            "article_id": revision.article_id,
            "revision_id": revision.id,
            "revision_number": revision.number,
            "title": revision.title,
            "section": revision.article.section.name,
            "scheduled_for": revision.scheduled_for,
            "minutes_late": _minutes_late(revision.scheduled_for, now),
        })

    items.sort(key=lambda item: item["scheduled_for"])
    return items


def dismiss(user, article_id, revision_id=None, now=None):
    """Dismiss the alert for one overdue article or revision (editors only;
    the view checks the role)."""
    if now is None:
        now = timezone.now()

    if revision_id is None:
        item = visible_articles(user).filter(pk=article_id).first()
        if item is None:
            raise NotFound("Article not found.")
        article = item
        revision = None
    else:
        item = visible_revisions(user).filter(pk=revision_id, article_id=article_id).first()
        if item is None:
            raise NotFound("Revision not found.")
        article = item.article
        revision = item

    if item.status != Status.SCHEDULED or item.scheduled_for >= now:
        raise LifecycleError("There is no overdue alert to dismiss for this item.")

    try:
        with transaction.atomic():
            AlertDismissal.objects.create(
                article=article, revision=revision, scheduled_for=item.scheduled_for, dismissed_by=user
            )
    except IntegrityError:
        # Already dismissed (maybe by another editor at the same moment): nothing to do.
        pass
