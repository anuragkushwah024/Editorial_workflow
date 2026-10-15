from datetime import timedelta

from django.utils import timezone
from rest_framework.test import APITestCase

from accounts.models import User
from sections.models import Section, SectionAssignment

from .models import Article, ArticleEvent, Status


class BulkTestCase(APITestCase):
    """Shared setup: two Approved, one In Review, one Scheduled and one
    Published article in Tech; Chirag is a writer in Tech."""

    def setUp(self):
        self.editor = User.objects.create_user(
            email="editor@example.com", password="x", full_name="Asha Editor", role=User.Role.EDITOR
        )
        self.writer = User.objects.create_user(
            email="writer@example.com", password="x", full_name="Chirag Writer", role=User.Role.WRITER
        )
        self.tech = Section.objects.create(name="Tech", owner=self.editor)
        SectionAssignment.objects.create(section=self.tech, writer=self.writer, assigned_by=self.editor)

        now = timezone.now()
        self.approved_1 = self.make("Approved one", Status.APPROVED)
        self.approved_2 = self.make("Approved two", Status.APPROVED)
        self.in_review = self.make("Still in review", Status.IN_REVIEW)
        self.scheduled = self.make("Already scheduled", Status.SCHEDULED, scheduled_for=now + timedelta(days=3))
        self.published = self.make("Already live", Status.PUBLISHED, published_at=now - timedelta(days=1))

    def make(self, title, status, scheduled_for=None, published_at=None):
        return Article.objects.create(
            section=self.tech, author=self.writer, title=title, body="text", status=status,
            scheduled_for=scheduled_for, published_at=published_at,
        )

    def bulk(self, data):
        return self.client.post("/api/articles/bulk/", data, format="json")

    def in_one_day(self):
        return (timezone.now() + timedelta(days=1)).isoformat()

    def result_for(self, response, article):
        for result in response.data["results"]:
            if result["id"] == article.id:
                return result
        return None


class BulkScheduleTests(BulkTestCase):
    def test_mixed_batch_reports_each_article(self):
        self.client.force_authenticate(user=self.editor)
        response = self.bulk({
            "action": "schedule",
            "ids": [self.approved_1.id, self.in_review.id, self.approved_2.id, self.published.id],
            "scheduled_for": self.in_one_day(),
        })
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["succeeded"], 2)
        self.assertEqual(response.data["rejected"], 2)

        ok = self.result_for(response, self.approved_1)
        self.assertTrue(ok["ok"])
        self.assertEqual(ok["status"], Status.SCHEDULED)

        rejected = self.result_for(response, self.in_review)
        self.assertFalse(rejected["ok"])
        self.assertEqual(rejected["error"], "Only an Approved article can be scheduled.")
        self.assertEqual(rejected["status"], Status.IN_REVIEW)

    def test_successful_ones_stay_saved_after_a_rejection(self):
        self.client.force_authenticate(user=self.editor)
        self.bulk({
            "action": "schedule",
            "ids": [self.approved_1.id, self.in_review.id, self.approved_2.id],
            "scheduled_for": self.in_one_day(),
        })
        self.approved_1.refresh_from_db()
        self.approved_2.refresh_from_db()
        self.in_review.refresh_from_db()
        self.assertEqual(self.approved_1.status, Status.SCHEDULED)
        self.assertEqual(self.approved_2.status, Status.SCHEDULED)
        self.assertEqual(self.in_review.status, Status.IN_REVIEW)

    def test_each_success_is_in_its_articles_timeline(self):
        self.client.force_authenticate(user=self.editor)
        self.bulk({"action": "schedule", "ids": [self.approved_1.id, self.in_review.id],
                   "scheduled_for": self.in_one_day()})
        self.assertEqual(
            ArticleEvent.objects.filter(article=self.approved_1, event_type=ArticleEvent.Type.STATUS_CHANGED).count(), 1
        )
        self.assertEqual(
            ArticleEvent.objects.filter(article=self.in_review, event_type=ArticleEvent.Type.STATUS_CHANGED).count(), 0
        )

    def test_results_keep_the_order_sent_and_skip_repeats(self):
        self.client.force_authenticate(user=self.editor)
        response = self.bulk({"action": "schedule", "ids": [self.approved_2.id, self.approved_1.id, self.approved_2.id],
                              "scheduled_for": self.in_one_day()})
        ids = []
        for result in response.data["results"]:
            ids.append(result["id"])
        self.assertEqual(ids, [self.approved_2.id, self.approved_1.id])

    def test_past_time_rejects_the_whole_request(self):
        self.client.force_authenticate(user=self.editor)
        past = (timezone.now() - timedelta(hours=1)).isoformat()
        response = self.bulk({"action": "schedule", "ids": [self.approved_1.id], "scheduled_for": past})
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data["scheduled_for"], ["The publish time must be in the future."])
        self.approved_1.refresh_from_db()
        self.assertEqual(self.approved_1.status, Status.APPROVED)

    def test_schedule_needs_a_time(self):
        self.client.force_authenticate(user=self.editor)
        response = self.bulk({"action": "schedule", "ids": [self.approved_1.id]})
        self.assertEqual(response.status_code, 400)
        self.assertIn("scheduled_for", response.data)


class BulkUnpublishTests(BulkTestCase):
    def test_unpublish_scheduled_and_published_but_not_approved(self):
        self.client.force_authenticate(user=self.editor)
        response = self.bulk({"action": "unpublish", "ids": [self.scheduled.id, self.published.id, self.approved_1.id]})
        self.assertEqual(response.data["succeeded"], 2)
        self.assertEqual(self.result_for(response, self.scheduled)["status"], Status.APPROVED)
        self.assertEqual(self.result_for(response, self.published)["status"], Status.APPROVED)
        self.assertEqual(
            self.result_for(response, self.approved_1)["error"],
            "Only a Scheduled or Published article can be unpublished.",
        )


class BulkInputTests(BulkTestCase):
    def test_writers_get_403(self):
        self.client.force_authenticate(user=self.writer)
        response = self.bulk({"action": "unpublish", "ids": [self.published.id]})
        self.assertEqual(response.status_code, 403)
        self.published.refresh_from_db()
        self.assertEqual(self.published.status, Status.PUBLISHED)

    def test_unknown_ids_are_reported_not_fatal(self):
        self.client.force_authenticate(user=self.editor)
        response = self.bulk({"action": "unpublish", "ids": [999999, self.published.id]})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["results"][0], {
            "id": 999999, "title": None, "ok": False, "status": None, "error": "Article not found.",
        })
        self.assertTrue(response.data["results"][1]["ok"])

    def test_unknown_action_is_rejected(self):
        self.client.force_authenticate(user=self.editor)
        response = self.bulk({"action": "publish", "ids": [self.approved_1.id]})
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data["action"], ["Action must be schedule or unpublish."])

    def test_empty_and_too_long_lists_are_rejected(self):
        self.client.force_authenticate(user=self.editor)
        self.assertEqual(self.bulk({"action": "unpublish", "ids": []}).data["ids"], ["Select at least one article."])
        too_many = list(range(1, 102))
        response = self.bulk({"action": "unpublish", "ids": too_many})
        self.assertEqual(response.data["ids"], ["At most 100 articles can be changed at once."])
