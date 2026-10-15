from datetime import timedelta
from io import StringIO

from django.core.management import call_command
from django.utils import timezone
from rest_framework.test import APITestCase

from accounts.models import User
from sections.models import Section, SectionAssignment

from .alerts import overdue_items
from .models import AlertDismissal, Article, ArticleEvent, ArticleRevision, Status


class AlertTestCase(APITestCase):
    """Shared setup: a writer in Tech, an outsider writer, and one overdue
    article (scheduled an hour ago, still not published)."""

    def setUp(self):
        self.editor = User.objects.create_user(
            email="editor@example.com", password="x", full_name="Asha Editor", role=User.Role.EDITOR
        )
        self.writer = User.objects.create_user(
            email="writer@example.com", password="x", full_name="Chirag Writer", role=User.Role.WRITER
        )
        self.outsider = User.objects.create_user(
            email="writer3@example.com", password="x", full_name="Esha Writer", role=User.Role.WRITER
        )
        self.tech = Section.objects.create(name="Tech", owner=self.editor)
        SectionAssignment.objects.create(section=self.tech, writer=self.writer, assigned_by=self.editor)

        self.now = timezone.now()
        self.overdue = Article.objects.create(
            section=self.tech, author=self.writer, title="Late piece", body="b",
            status=Status.SCHEDULED, scheduled_for=self.now - timedelta(hours=1),
        )

    def titles(self, items):
        result = []
        for item in items:
            result.append(item["title"])
        return result

    def get_alerts(self, user):
        self.client.force_authenticate(user=user)
        return self.client.get("/api/alerts/")

    def dismiss(self, user, article, revision=None):
        self.client.force_authenticate(user=user)
        data = {"article_id": article.id}
        if revision is not None:
            data["revision_id"] = revision.id
        return self.client.post("/api/alerts/dismiss/", data, format="json")


class OverdueDetectionTests(AlertTestCase):
    def test_overdue_article_is_listed_with_how_late(self):
        response = self.get_alerts(self.editor)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["count"], 1)
        item = response.data["results"][0]
        self.assertEqual(item["title"], "Late piece")
        self.assertEqual(item["section"], "Tech")
        self.assertGreaterEqual(item["minutes_late"], 59)

    def test_future_published_and_approved_articles_are_not_overdue(self):
        Article.objects.create(section=self.tech, author=self.writer, title="Future", body="b",
                               status=Status.SCHEDULED, scheduled_for=self.now + timedelta(hours=1))
        Article.objects.create(section=self.tech, author=self.writer, title="Live", body="b",
                               status=Status.PUBLISHED, published_at=self.now - timedelta(hours=2))
        Article.objects.create(section=self.tech, author=self.writer, title="Waiting", body="b",
                               status=Status.APPROVED)
        self.assertEqual(self.titles(overdue_items(self.editor)), ["Late piece"])

    def test_overdue_revision_is_listed(self):
        live = Article.objects.create(section=self.tech, author=self.writer, title="Live", body="b",
                                      status=Status.PUBLISHED, published_at=self.now - timedelta(days=1))
        ArticleRevision.objects.create(article=live, number=1, title="Live (fixed)", body="b2",
                                       created_by=self.writer, status=Status.SCHEDULED,
                                       scheduled_for=self.now - timedelta(minutes=10))
        items = overdue_items(self.editor)
        self.assertEqual(self.titles(items), ["Late piece", "Live (fixed)"])
        self.assertEqual(items[1]["kind"], "revision")
        self.assertEqual(items[1]["revision_number"], 1)

    def test_writers_see_alerts_only_for_their_sections(self):
        self.assertEqual(self.get_alerts(self.writer).data["count"], 1)
        self.assertEqual(self.get_alerts(self.outsider).data["count"], 0)

    def test_login_required(self):
        self.assertEqual(self.client.get("/api/alerts/").status_code, 401)


class DismissTests(AlertTestCase):
    def test_editor_dismisses_and_it_disappears(self):
        response = self.dismiss(self.editor, self.overdue)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["count"], 0)
        dismissal = AlertDismissal.objects.get(article=self.overdue)
        self.assertEqual(dismissal.scheduled_for, self.overdue.scheduled_for)
        self.assertEqual(dismissal.dismissed_by, self.editor)

    def test_dismissal_hides_it_for_everyone(self):
        self.dismiss(self.editor, self.overdue)
        self.assertEqual(self.get_alerts(self.writer).data["count"], 0)

    def test_writers_cannot_dismiss(self):
        response = self.dismiss(self.writer, self.overdue)
        self.assertEqual(response.status_code, 403)
        self.assertEqual(self.get_alerts(self.editor).data["count"], 1)

    def test_dismissing_twice_is_harmless(self):
        self.dismiss(self.editor, self.overdue)
        self.assertEqual(self.dismiss(self.editor, self.overdue).status_code, 200)
        self.assertEqual(AlertDismissal.objects.count(), 1)

    def test_cannot_dismiss_something_not_overdue(self):
        on_time = Article.objects.create(section=self.tech, author=self.writer, title="Future", body="b",
                                         status=Status.SCHEDULED, scheduled_for=self.now + timedelta(hours=1))
        response = self.dismiss(self.editor, on_time)
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data["detail"], "There is no overdue alert to dismiss for this item.")

    def test_dismiss_a_revision_alert(self):
        live = Article.objects.create(section=self.tech, author=self.writer, title="Live", body="b",
                                      status=Status.PUBLISHED, published_at=self.now - timedelta(days=1))
        revision = ArticleRevision.objects.create(article=live, number=1, title="Live (fixed)", body="b2",
                                                  created_by=self.writer, status=Status.SCHEDULED,
                                                  scheduled_for=self.now - timedelta(minutes=10))
        self.dismiss(self.editor, live, revision)
        self.assertEqual(self.titles(overdue_items(self.editor)), ["Late piece"])


class AlertComesBackTests(AlertTestCase):
    def test_alert_returns_after_unpublish_and_new_schedule_passes(self):
        # 1. Dismissed.
        self.dismiss(self.editor, self.overdue)
        self.assertEqual(overdue_items(self.editor), [])

        # 2. Unpublished and scheduled again for a new time, two hours from now.
        self.client.force_authenticate(user=self.editor)
        self.client.post("/api/articles/" + str(self.overdue.id) + "/unpublish/")
        new_time = self.now + timedelta(hours=2)
        response = self.client.post("/api/articles/" + str(self.overdue.id) + "/schedule/",
                                    {"scheduled_for": new_time.isoformat()}, format="json")
        self.assertEqual(response.data["status"], Status.SCHEDULED)

        # 3. Not overdue yet...
        self.assertEqual(overdue_items(self.editor), [])
        # 4. ...but once the new time has passed (checked "three hours from now"),
        #    the old dismissal doesn't match the new time, so the alert is back.
        later = self.now + timedelta(hours=3)
        self.assertEqual(self.titles(overdue_items(self.editor, now=later)), ["Late piece"])


class PublishScheduledTests(AlertTestCase):
    def test_editor_can_publish_a_scheduled_article_now(self):
        self.client.force_authenticate(user=self.editor)
        response = self.client.post("/api/articles/" + str(self.overdue.id) + "/publish/")
        self.assertEqual(response.status_code, 200)
        self.overdue.refresh_from_db()
        self.assertEqual(self.overdue.status, Status.PUBLISHED)
        self.assertIsNone(self.overdue.scheduled_for)
        event = ArticleEvent.objects.get(article=self.overdue, event_type=ArticleEvent.Type.STATUS_CHANGED)
        self.assertEqual(event.from_status, Status.SCHEDULED)
        self.assertIn("was_scheduled_for", event.payload)
        # And it is no longer an alert.
        self.assertEqual(overdue_items(self.editor), [])

    def test_writer_still_cannot_publish(self):
        self.client.force_authenticate(user=self.writer)
        response = self.client.post("/api/articles/" + str(self.overdue.id) + "/publish/")
        self.assertEqual(response.status_code, 403)


class PublishDueCommandTests(AlertTestCase):
    def run_command(self, *args):
        out = StringIO()
        call_command("publish_due", *args, stdout=out)
        return out.getvalue()

    def test_publishes_due_article_and_revision_but_not_future_ones(self):
        future = Article.objects.create(section=self.tech, author=self.writer, title="Future", body="b",
                                        status=Status.SCHEDULED, scheduled_for=self.now + timedelta(hours=1))
        live = Article.objects.create(section=self.tech, author=self.writer, title="Live", body="old text",
                                      status=Status.PUBLISHED, published_at=self.now - timedelta(days=1))
        revision = ArticleRevision.objects.create(article=live, number=1, title="Live", body="new text",
                                                  created_by=self.writer, status=Status.SCHEDULED,
                                                  scheduled_for=self.now - timedelta(minutes=5))

        output = self.run_command()
        self.assertIn("Done: 2 published, 0 skipped.", output)

        self.overdue.refresh_from_db()
        future.refresh_from_db()
        live.refresh_from_db()
        revision.refresh_from_db()
        self.assertEqual(self.overdue.status, Status.PUBLISHED)
        self.assertEqual(future.status, Status.SCHEDULED)
        self.assertEqual(revision.status, Status.PUBLISHED)
        self.assertEqual(live.body, "new text")

    def test_timeline_names_the_section_owner_and_says_automatic(self):
        self.run_command()
        event = ArticleEvent.objects.get(article=self.overdue, event_type=ArticleEvent.Type.STATUS_CHANGED)
        self.assertEqual(event.actor, self.editor)
        self.assertEqual(event.message, "Published automatically at its scheduled time (publish_due).")

    def test_dry_run_changes_nothing(self):
        output = self.run_command("--dry-run")
        self.assertIn("Would publish: Late piece", output)
        self.overdue.refresh_from_db()
        self.assertEqual(self.overdue.status, Status.SCHEDULED)

    def test_item_that_cannot_be_published_is_skipped_and_stays_an_alert(self):
        # The section owner is no longer an editor, so the lifecycle refuses.
        self.editor.role = User.Role.WRITER
        self.editor.save()
        output = self.run_command()
        self.assertIn("Skipped: Late piece", output)
        self.overdue.refresh_from_db()
        self.assertEqual(self.overdue.status, Status.SCHEDULED)
