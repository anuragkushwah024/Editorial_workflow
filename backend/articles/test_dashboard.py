from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from django.db import connection
from django.test.utils import CaptureQueriesContext
from rest_framework.test import APITestCase

from accounts.models import User
from sections.models import Section, SectionAssignment

from .dashboard import dashboard_data, week_start
from .models import Article, Status

IST = ZoneInfo("Asia/Kolkata")
UTC = ZoneInfo("UTC")

# A fixed "now" so the tests don't depend on today's date:
# Wednesday 15 Oct 2026, 14:00 IST. Its week runs Mon 12 Oct to Sun 18 Oct.
NOW = datetime(2026, 10, 15, 14, 0, tzinfo=IST)


class DashboardTestCase(APITestCase):
    def setUp(self):
        self.editor = User.objects.create_user(
            email="editor@example.com", password="x", full_name="Asha Editor", role=User.Role.EDITOR
        )
        self.writer = User.objects.create_user(
            email="writer@example.com", password="x", full_name="Chirag Writer", role=User.Role.WRITER
        )
        self.tech = Section.objects.create(name="Tech", owner=self.editor)
        self.politics = Section.objects.create(name="Politics", owner=self.editor)
        self.empty = Section.objects.create(name="Culture", owner=self.editor)
        SectionAssignment.objects.create(section=self.tech, writer=self.writer, assigned_by=self.editor)

    def make(self, section, status, published_at=None, scheduled_for=None):
        return Article.objects.create(
            section=section, author=self.writer, title="t", body="b", status=status,
            published_at=published_at, scheduled_for=scheduled_for,
        )

    def week_counts(self, data):
        result = []
        for week in data["published_per_week"]:
            result.append(week["count"])
        return result


class WeekBoundaryTests(DashboardTestCase):
    def test_week_starts_monday_midnight_ist(self):
        self.assertEqual(week_start(NOW), datetime(2026, 10, 12, 0, 0, tzinfo=IST))

    def test_sunday_2359_and_monday_0000_ist_are_different_weeks(self):
        sunday_night = datetime(2026, 10, 11, 23, 59, tzinfo=IST)
        monday_midnight = datetime(2026, 10, 12, 0, 0, tzinfo=IST)
        self.make(self.tech, Status.PUBLISHED, published_at=sunday_night)
        self.make(self.tech, Status.PUBLISHED, published_at=monday_midnight)

        data = dashboard_data(self.editor, now=NOW)
        self.assertEqual(data["headline"]["published_this_week"], 1)
        # Last bar = this week, the one before = last week.
        self.assertEqual(self.week_counts(data)[-2:], [1, 1])

    def test_monday_morning_ist_is_not_last_week_in_utc_terms(self):
        # 02:00 Monday IST is still Sunday 20:30 in UTC. A UTC week would put
        # it in last week; an IST week puts it in this week.
        early_monday = datetime(2026, 10, 12, 2, 0, tzinfo=IST)
        self.assertEqual(early_monday.astimezone(UTC).weekday(), 6)  # Sunday in UTC
        self.make(self.tech, Status.PUBLISHED, published_at=early_monday)
        self.assertEqual(dashboard_data(self.editor, now=NOW)["headline"]["published_this_week"], 1)


class HeadlineTests(DashboardTestCase):
    def test_the_four_numbers(self):
        self.make(self.tech, Status.IN_REVIEW)
        self.make(self.tech, Status.IN_REVIEW)
        self.make(self.tech, Status.DRAFT)
        self.make(self.tech, Status.SCHEDULED, scheduled_for=NOW + timedelta(days=2))   # Friday: this week
        self.make(self.tech, Status.SCHEDULED, scheduled_for=NOW + timedelta(days=6))   # next Tuesday: not
        self.make(self.tech, Status.PUBLISHED, published_at=NOW - timedelta(days=1))
        self.make(self.tech, Status.PUBLISHED, published_at=NOW - timedelta(days=10))  # last week

        headline = dashboard_data(self.editor, now=NOW)["headline"]
        self.assertEqual(headline, {
            "in_review": 2, "scheduled_this_week": 1, "published_this_week": 1, "open_drafts": 1,
        })

    def test_unpublished_article_is_not_counted_as_published(self):
        # Currently Approved: it was published once, but isn't now.
        self.make(self.tech, Status.APPROVED)
        self.assertEqual(dashboard_data(self.editor, now=NOW)["headline"]["published_this_week"], 0)


class BreakdownTests(DashboardTestCase):
    def test_by_status_lists_every_status_in_lifecycle_order(self):
        self.make(self.tech, Status.DRAFT)
        self.make(self.politics, Status.DRAFT)
        statuses = []
        counts = []
        for row in dashboard_data(self.editor, now=NOW)["by_status"]:
            statuses.append(row["status"])
            counts.append(row["count"])
        self.assertEqual(statuses, ["DRAFT", "IN_REVIEW", "APPROVED", "SCHEDULED", "PUBLISHED"])
        self.assertEqual(counts, [2, 0, 0, 0, 0])

    def test_by_section_includes_empty_sections_and_status_split(self):
        self.make(self.tech, Status.DRAFT)
        self.make(self.tech, Status.PUBLISHED, published_at=NOW)
        rows = dashboard_data(self.editor, now=NOW)["by_section"]
        names = []
        for row in rows:
            names.append(row["name"])
        self.assertEqual(names, ["Culture", "Politics", "Tech"])
        tech = rows[2]
        self.assertEqual(tech["total"], 2)
        self.assertEqual(tech["draft"], 1)
        self.assertEqual(tech["published"], 1)
        self.assertEqual(rows[0]["total"], 0)

    def test_chart_has_eight_weeks_with_zeros_and_ignores_older(self):
        self.make(self.tech, Status.PUBLISHED, published_at=NOW - timedelta(weeks=3))
        self.make(self.tech, Status.PUBLISHED, published_at=NOW - timedelta(weeks=9))  # too old
        data = dashboard_data(self.editor, now=NOW)
        self.assertEqual(len(data["published_per_week"]), 8)
        self.assertEqual(self.week_counts(data), [0, 0, 0, 0, 1, 0, 0, 0])
        self.assertEqual(data["published_per_week"][-1]["week_start"], "2026-10-12")
        self.assertEqual(data["published_per_week"][0]["week_start"], "2026-08-24")

    def test_archived_sections_are_left_out(self):
        self.make(self.politics, Status.DRAFT)
        self.politics.is_archived = True
        self.politics.save()
        data = dashboard_data(self.editor, now=NOW)
        self.assertEqual(data["headline"]["open_drafts"], 0)
        for row in data["by_section"]:
            self.assertNotEqual(row["name"], "Politics")


class VisibilityAndQueryTests(DashboardTestCase):
    def test_writer_only_counts_their_sections(self):
        self.make(self.tech, Status.DRAFT)
        self.make(self.politics, Status.DRAFT)
        data = dashboard_data(self.writer, now=NOW)
        self.assertEqual(data["headline"]["open_drafts"], 1)
        names = []
        for row in data["by_section"]:
            names.append(row["name"])
        self.assertEqual(names, ["Tech"])

    def test_number_of_queries_does_not_grow_with_articles(self):
        self.make(self.tech, Status.DRAFT)
        with CaptureQueriesContext(connection) as few:
            dashboard_data(self.editor, now=NOW)
        for number in range(30):
            self.make(self.tech, Status.PUBLISHED, published_at=NOW - timedelta(days=number))
        with CaptureQueriesContext(connection) as many:
            dashboard_data(self.editor, now=NOW)
        self.assertEqual(len(few), len(many))

    def test_api_endpoint(self):
        self.client.force_authenticate(user=self.writer)
        response = self.client.get("/api/dashboard/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["week"]["timezone"], "Asia/Kolkata")
        self.assertIn("headline", response.data)

    def test_login_required(self):
        self.assertEqual(self.client.get("/api/dashboard/").status_code, 401)
