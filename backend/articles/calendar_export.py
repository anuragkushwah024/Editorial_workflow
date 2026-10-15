"""
The editorial calendar as a CSV file (goal 7): every Scheduled or Published
article the user can see, with its section, author and publish time.
"""

import csv
import io

from django.db.models.functions import Coalesce
from django.http import HttpResponse
from django.utils import timezone

from .access import visible_articles
from .models import Status

HEADER = ["Title", "Section", "Author", "Author email", "Status", "Publish time (UTC)"]


def _safe_cell(value):
    """Stop a spreadsheet from running a title as a formula.

    A cell starting with = + - or @ is treated as a formula by Excel and
    Google Sheets (so-called CSV injection), so such values get a leading '.
    """
    text = str(value)
    if text != "" and text[0] in "=+-@":
        return "'" + text
    return text


def calendar_rows(user):
    """The articles in the calendar, earliest publish time first.

    Like the default article list, articles in archived sections are left out.
    """
    articles = (
        visible_articles(user)
        .filter(status__in=[Status.SCHEDULED, Status.PUBLISHED], section__is_archived=False)
        .select_related("section", "author")
        .annotate(publish_time=Coalesce("published_at", "scheduled_for"))
        .order_by("publish_time", "id")
    )
    rows = []
    for article in articles:
        rows.append(
            [
                _safe_cell(article.title),
                _safe_cell(article.section.name),
                _safe_cell(article.author.full_name),
                article.author.email,
                article.get_status_display(),
                article.publish_time.isoformat(),
            ]
        )
    return rows


def calendar_csv_response(user):
    # The csv module puts quotes around any value with a comma, quote or line
    # break, and doubles quotes inside it, so such titles can't break the file.
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(HEADER)
    for row in calendar_rows(user):
        writer.writerow(row)

    filename = "editorial-calendar-" + timezone.now().date().isoformat() + ".csv"
    # A byte-order mark at the start makes Excel read the file as UTF-8,
    # so names with accents or Indian scripts show correctly.
    response = HttpResponse("﻿" + buffer.getvalue(), content_type="text/csv; charset=utf-8")
    response["Content-Disposition"] = 'attachment; filename="' + filename + '"'
    return response
