import csv
import io
from datetime import timedelta

from django.utils import timezone
from rest_framework.test import APITestCase

from accounts.models import User
from sections.models import Section, SectionAssignment

from .models import Article, Status


class CalendarTests(APITestCase):
    def setUp(self):
        self.editor = User.objects.create_user(
            email="editor@example.com", password="x", full_name="Asha Editor", role=User.Role.EDITOR
        )
        self.writer = User.objects.create_user(
            email="writer@example.com", password="x", full_name="Chirag Writer", role=User.Role.WRITER
        )
        self.tech = Section.objects.create(name="Tech", owner=self.editor)
        self.politics = Section.objects.create(name="Politics", owner=self.editor)
        SectionAssignment.objects.create(section=self.tech, writer=self.writer, assigned_by=self.editor)

        now = timezone.now()
        self.published_at = now - timedelta(days=2)
        self.scheduled_for = now + timedelta(days=1)
        Article.objects.create(
            section=self.tech, author=self.writer, title='Phones, "cheap" ones\nand more', body="x",
            status=Status.SCHEDULED, scheduled_for=self.scheduled_for,
        )
        Article.objects.create(
            section=self.tech, author=self.writer, title="Rupee falls", body="x",
            status=Status.PUBLISHED, published_at=self.published_at,
        )
        Article.objects.create(section=self.tech, author=self.writer, title="Just a draft", body="x")
        Article.objects.create(
            section=self.politics, author=self.editor, title="Election day", body="x",
            status=Status.SCHEDULED, scheduled_for=now + timedelta(days=5),
        )

    def download(self, user):
        self.client.force_authenticate(user=user)
        return self.client.get("/api/articles/calendar/")

    def rows(self, response):
        text = response.content.decode("utf-8-sig")  # -sig drops the byte-order mark
        return list(csv.reader(io.StringIO(text)))

    def test_is_a_csv_download_with_the_date_in_the_name(self):
        response = self.download(self.editor)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response["Content-Type"].startswith("text/csv"))
        expected = 'attachment; filename="editorial-calendar-' + timezone.now().date().isoformat() + '.csv"'
        self.assertEqual(response["Content-Disposition"], expected)

    def test_scheduled_and_published_only_sorted_by_publish_time(self):
        rows = self.rows(self.download(self.editor))
        self.assertEqual(rows[0], ["Title", "Section", "Author", "Author email", "Status", "Publish time (UTC)"])
        titles = []
        for row in rows[1:]:
            titles.append(row[0])
        # Published two days ago, then scheduled tomorrow, then in five days. No draft.
        self.assertEqual(titles, ["Rupee falls", 'Phones, "cheap" ones\nand more', "Election day"])

    def test_publish_time_is_the_right_one_for_each_status(self):
        rows = self.rows(self.download(self.editor))
        self.assertEqual(rows[1][4], "Published")
        self.assertEqual(rows[1][5], self.published_at.isoformat())
        self.assertEqual(rows[2][4], "Scheduled")
        self.assertEqual(rows[2][5], self.scheduled_for.isoformat())

    def test_commas_quotes_and_line_breaks_survive(self):
        rows = self.rows(self.download(self.editor))
        # Read back as exactly one row with the full title, so nothing broke.
        self.assertEqual(len(rows), 4)
        self.assertEqual(rows[2][0], 'Phones, "cheap" ones\nand more')
        self.assertEqual(rows[2][1], "Tech")

    def test_writer_only_gets_their_sections(self):
        rows = self.rows(self.download(self.writer))
        titles = []
        for row in rows[1:]:
            titles.append(row[0])
        self.assertNotIn("Election day", titles)
        self.assertEqual(len(titles), 2)

    def test_formula_like_titles_are_made_harmless(self):
        Article.objects.create(
            section=self.tech, author=self.writer, title="=HYPERLINK(\"http://evil\")", body="x",
            status=Status.PUBLISHED, published_at=timezone.now() - timedelta(days=9),
        )
        rows = self.rows(self.download(self.editor))
        self.assertEqual(rows[1][0], "'=HYPERLINK(\"http://evil\")")

    def test_login_required(self):
        self.assertEqual(self.client.get("/api/articles/calendar/").status_code, 401)
