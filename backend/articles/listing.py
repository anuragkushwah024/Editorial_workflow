"""
Finding articles (goal 6): search, filters, sorting and pages.

Everything here only adds conditions to a database query. The query always
starts from visible_articles(user), so search and filters can never reach an
article this user isn't allowed to see.

Query parameters of GET /api/articles/:
    q        text to search for in title and body (PostgreSQL full-text search)
    section  a section id
    status   DRAFT, IN_REVIEW, APPROVED, SCHEDULED or PUBLISHED
    author   a user id, or "me" for the logged-in user's own articles
    sort     updated, status or publish_time; a leading "-" means descending
             (default: -updated, newest first; with a search: best match first)
    page     page number, 20 articles per page
"""

from django.contrib.postgres.search import SearchQuery, SearchRank
from django.db.models import Case, F, IntegerField, Value, When
from django.db.models.functions import Coalesce
from rest_framework.exceptions import NotFound, ValidationError
from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response

# SEARCH_VECTOR lives next to the model because the GIN index (migration 0003)
# is built on it. Title words count more than body words when ranking.
from .models import SEARCH_VECTOR, Status

# Sorting by status follows the lifecycle, not the alphabet.
STATUS_ORDER = Case(
    When(status=Status.DRAFT, then=Value(1)),
    When(status=Status.IN_REVIEW, then=Value(2)),
    When(status=Status.APPROVED, then=Value(3)),
    When(status=Status.SCHEDULED, then=Value(4)),
    When(status=Status.PUBLISHED, then=Value(5)),
    output_field=IntegerField(),
)

# "Publish time" is the time it went live, or the time it is scheduled for.
PUBLISH_TIME = Coalesce("published_at", "scheduled_for")

SORT_FIELDS = {
    "updated": "updated_at",
    "status": "status_order",
    "publish_time": "publish_time",
}


def _parse_id(value, name):
    if not value.isdigit():
        raise ValidationError({name: ["Must be a number."]})
    return int(value)


def filter_articles(queryset, params, user):
    """Apply search, filters and sorting from the query string."""
    # --- section (archived sections are hidden unless one is asked for) ---
    section = params.get("section")
    if section:
        queryset = queryset.filter(section_id=_parse_id(section, "section"))
    else:
        queryset = queryset.filter(section__is_archived=False)

    # --- status ---
    status = params.get("status")
    if status:
        if status not in Status.values:
            raise ValidationError({"status": ["Unknown status. Use one of: " + ", ".join(Status.values) + "."]})
        queryset = queryset.filter(status=status)

    # --- author ("me" = my own articles, for goal 5) ---
    author = params.get("author")
    if author:
        if author == "me":
            queryset = queryset.filter(author=user)
        else:
            queryset = queryset.filter(author_id=_parse_id(author, "author"))

    # --- search ---
    text = params.get("q", "").strip()
    searching = text != ""
    if searching:
        # "websearch" understands what people type into search boxes:
        # several words, "quoted phrases" and -excluded words.
        query = SearchQuery(text, search_type="websearch", config="english")
        queryset = queryset.annotate(search=SEARCH_VECTOR, rank=SearchRank(SEARCH_VECTOR, query))
        queryset = queryset.filter(search=query)

    # --- sorting ---
    sort = params.get("sort", "")
    queryset = queryset.annotate(status_order=STATUS_ORDER, publish_time=PUBLISH_TIME)

    if sort == "" and searching:
        # With a search and no chosen order, the best matches come first.
        return queryset.order_by("-rank", "-updated_at", "-id")
    if sort == "":
        sort = "-updated"

    descending = sort.startswith("-")
    key = sort.lstrip("-")
    if key not in SORT_FIELDS:
        raise ValidationError({"sort": ["Unknown sort. Use updated, status or publish_time, with - for descending."]})

    # The id breaks ties (two articles saved in the same instant), in the same
    # direction as the sort, so the order is always the same and pages never
    # repeat or skip an article.
    field = F(SORT_FIELDS[key])
    if descending:
        return queryset.order_by(field.desc(nulls_last=True), "-id")
    return queryset.order_by(field.asc(nulls_last=True), "id")


class ArticlePagination(PageNumberPagination):
    """20 articles per page, and the total number of matches (goal 6)."""

    page_size = 20

    def paginate_queryset(self, queryset, request, view=None):
        try:
            return super().paginate_queryset(queryset, request, view)
        except NotFound:
            raise NotFound("This page does not exist. Go back to page 1.")

    def get_paginated_response(self, data):
        return Response(
            {
                "count": self.page.paginator.count,
                "page": self.page.number,
                "page_size": self.page_size,
                "total_pages": self.page.paginator.num_pages,
                "results": data,
            }
        )
