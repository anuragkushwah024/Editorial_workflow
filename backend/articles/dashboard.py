"""
The dashboard numbers (goal 8).

Every number is counted by the database (COUNT ... GROUP BY), so the work
does not grow with the number of articles loaded into Python. Everything
starts from visible_articles(user), so a writer's dashboard only covers
their own sections. Like the default article list, archived sections are
left out.

Weeks run Monday 00:00 to Sunday 23:59 in India time (IST). In UTC a week
would start at 05:30 on Monday morning IST, so an article published at
02:00 on a Monday would land in the wrong week.
"""

from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo

from django.db.models import Count, Q
from django.db.models.functions import TruncWeek
from django.utils import timezone

from sections.access import visible_sections

from .access import visible_articles
from .models import Status

NEWSROOM_TIMEZONE = ZoneInfo("Asia/Kolkata")
WEEKS_IN_CHART = 8

STATUS_ORDER = [Status.DRAFT, Status.IN_REVIEW, Status.APPROVED, Status.SCHEDULED, Status.PUBLISHED]


def week_start(moment):
    """Monday 00:00 IST of the week that contains `moment`."""
    local = moment.astimezone(NEWSROOM_TIMEZONE)
    monday = local.date() - timedelta(days=local.weekday())
    return datetime.combine(monday, time(0, 0), tzinfo=NEWSROOM_TIMEZONE)


def dashboard_data(user, now=None):
    if now is None:
        now = timezone.now()

    this_week_start = week_start(now)
    this_week_end = this_week_start + timedelta(days=7)
    articles = visible_articles(user).filter(section__is_archived=False)

    # --- headline numbers: one query with four filtered counts ---
    headline = articles.aggregate(
        in_review=Count("id", filter=Q(status=Status.IN_REVIEW)),
        scheduled_this_week=Count(
            "id",
            filter=Q(
                status=Status.SCHEDULED,
                scheduled_for__gte=this_week_start,
                scheduled_for__lt=this_week_end,
            ),
        ),
        published_this_week=Count(
            "id",
            filter=Q(
                status=Status.PUBLISHED,
                published_at__gte=this_week_start,
                published_at__lt=this_week_end,
            ),
        ),
        open_drafts=Count("id", filter=Q(status=Status.DRAFT)),
    )

    # --- by status: one GROUP BY, then every status listed, zeros included ---
    counts_by_status = {}
    for row in articles.values("status").annotate(count=Count("id")):
        counts_by_status[row["status"]] = row["count"]
    by_status = []
    for status in STATUS_ORDER:
        by_status.append({"status": status, "label": status.label, "count": counts_by_status.get(status, 0)})

    # --- by section: every section this user sees, with a count per status ---
    article_ids = articles.values("id")
    status_counts = {}
    for status in STATUS_ORDER:
        status_counts[status.lower()] = Count(
            "articles", filter=Q(articles__id__in=article_ids, articles__status=status)
        )
    sections = (
        visible_sections(user)
        .filter(is_archived=False)
        .annotate(total=Count("articles", filter=Q(articles__id__in=article_ids)), **status_counts)
        .order_by("name")
    )
    by_section = []
    for section in sections:
        row = {"id": section.id, "name": section.name, "total": section.total}
        for status in STATUS_ORDER:
            row[status.lower()] = getattr(section, status.lower())
        by_section.append(row)

    # --- published per week, last 8 weeks (this week included) ---
    first_week = this_week_start - timedelta(weeks=WEEKS_IN_CHART - 1)
    per_week = {}
    published = (
        articles.filter(status=Status.PUBLISHED, published_at__gte=first_week, published_at__lt=this_week_end)
        # date_trunc('week') in PostgreSQL starts weeks on Monday; tzinfo makes
        # it cut at Monday 00:00 IST instead of UTC.
        .annotate(week=TruncWeek("published_at", tzinfo=NEWSROOM_TIMEZONE))
        .values("week")
        .annotate(count=Count("id"))
    )
    for row in published:
        per_week[row["week"].date()] = row["count"]

    published_per_week = []
    for index in range(WEEKS_IN_CHART):
        start = first_week + timedelta(weeks=index)
        # Weeks with nothing published are still listed, with 0.
        published_per_week.append({"week_start": start.date().isoformat(), "count": per_week.get(start.date(), 0)})

    return {
        "week": {
            "start": this_week_start.isoformat(),
            "end": this_week_end.isoformat(),
            "timezone": "Asia/Kolkata",
        },
        "headline": headline,
        "by_status": by_status,
        "by_section": by_section,
        "published_per_week": published_per_week,
    }
