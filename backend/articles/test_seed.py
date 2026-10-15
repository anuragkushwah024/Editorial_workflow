from io import StringIO

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase
from django.utils import timezone

from accounts.models import User
from sections.models import Section

from .alerts import overdue_items
from .dashboard import dashboard_data
from .models import Article, ArticleEvent, ArticleRevision, Status


class SeedDemoTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        # Seeding is slow-ish, so it runs once for all the tests in this class.
        call_command("seed_demo", stdout=StringIO())

    def test_users_and_roles(self):
        users = User.objects.filter(email__endswith="@newsroom.demo")
        self.assertEqual(users.filter(role=User.Role.EDITOR).count(), 2)
        self.assertEqual(users.filter(role=User.Role.WRITER).count(), 4)
        self.assertTrue(User.objects.get(email="asha@newsroom.demo").check_password("Demo@2026"))

    def test_sections_one_archived(self):
        self.assertEqual(Section.objects.count(), 5)
        self.assertEqual(list(Section.objects.filter(is_archived=True).values_list("name", flat=True)), ["Sport"])

    def test_about_forty_articles_in_every_status(self):
        self.assertEqual(Article.objects.count(), 40)
        for status in Status.values:
            with self.subTest(status=status):
                self.assertTrue(Article.objects.filter(status=status).exists())

    def test_every_article_has_a_real_timeline(self):
        for article in Article.objects.all():
            self.assertTrue(ArticleEvent.objects.filter(article=article, event_type=ArticleEvent.Type.CREATED).exists())
        published = Article.objects.filter(status=Status.PUBLISHED).first()
        moves = ArticleEvent.objects.filter(article=published, event_type=ArticleEvent.Type.STATUS_CHANGED)
        self.assertGreaterEqual(moves.count(), 3)  # submit, approve, publish

    def test_published_revision_keeps_what_it_said_before(self):
        event = ArticleEvent.objects.get(event_type=ArticleEvent.Type.REVISION_PUBLISHED)
        self.assertIn("previous_body", event.payload)
        self.assertNotEqual(event.payload["previous_body"], event.article.body)

    def test_one_open_revision(self):
        self.assertEqual(ArticleRevision.objects.exclude(status=Status.PUBLISHED).count(), 1)

    def test_comments_exist(self):
        self.assertGreaterEqual(ArticleEvent.objects.filter(event_type=ArticleEvent.Type.COMMENT).count(), 5)

    def test_one_overdue_article_for_the_alerts(self):
        editor = User.objects.get(email="asha@newsroom.demo")
        items = overdue_items(editor)
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["title"], "Satellite internet trials begin in hill districts")

    def test_dashboard_chart_has_real_bars(self):
        editor = User.objects.get(email="asha@newsroom.demo")
        weeks_with_articles = 0
        for week in dashboard_data(editor)["published_per_week"]:
            if week["count"] > 0:
                weeks_with_articles = weeks_with_articles + 1
        self.assertGreaterEqual(weeks_with_articles, 6)

    def test_history_is_in_the_past_and_in_order(self):
        now = timezone.now()
        self.assertFalse(ArticleEvent.objects.filter(created_at__gt=now).exists())
        article = Article.objects.get(title="Parliament's monsoon session opens with a crowded agenda")
        times = list(article.events.order_by("id").values_list("created_at", flat=True))
        self.assertEqual(times, sorted(times))

    def test_refuses_to_run_twice(self):
        with self.assertRaises(CommandError) as raised:
            call_command("seed_demo", stdout=StringIO())
        self.assertIn("cannot be removed and created again", str(raised.exception))
        self.assertEqual(Article.objects.count(), 40)

    def test_skip_if_exists_is_quiet(self):
        out = StringIO()
        call_command("seed_demo", "--skip-if-exists", stdout=out)
        self.assertIn("Skipping", out.getvalue())
