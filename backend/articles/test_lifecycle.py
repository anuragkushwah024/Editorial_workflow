from datetime import timedelta

from django.utils import timezone
from rest_framework.test import APITestCase

from accounts.models import User
from sections.models import Section, SectionAssignment

from .models import Article, ArticleEvent, Status


class LifecycleTestCase(APITestCase):
    """Shared setup.

    Chirag and Divya are writers in Tech. Esha is a writer with no sections.
    Asha and Bina are editors. Chirag wrote one article; Asha wrote another.
    """

    def setUp(self):
        self.editor = User.objects.create_user(
            email="editor@example.com", password="x", full_name="Asha Editor", role=User.Role.EDITOR
        )
        self.other_editor = User.objects.create_user(
            email="editor2@example.com", password="x", full_name="Bina Editor", role=User.Role.EDITOR
        )
        self.writer = User.objects.create_user(
            email="writer@example.com", password="x", full_name="Chirag Writer", role=User.Role.WRITER
        )
        self.other_writer = User.objects.create_user(
            email="writer2@example.com", password="x", full_name="Divya Writer", role=User.Role.WRITER
        )
        self.outsider = User.objects.create_user(
            email="writer3@example.com", password="x", full_name="Esha Writer", role=User.Role.WRITER
        )
        self.tech = Section.objects.create(name="Tech", owner=self.editor)
        SectionAssignment.objects.create(section=self.tech, writer=self.writer, assigned_by=self.editor)
        SectionAssignment.objects.create(section=self.tech, writer=self.other_writer, assigned_by=self.editor)

        self.article = Article.objects.create(
            section=self.tech, author=self.writer, title="New phones", body="Draft text"
        )
        self.editors_article = Article.objects.create(
            section=self.tech, author=self.editor, title="Editor's piece", body="Text"
        )

    def as_user(self, user):
        self.client.force_authenticate(user=user)

    def act(self, article, action_name, data=None):
        url = "/api/articles/" + str(article.id) + "/" + action_name + "/"
        if data is None:
            data = {}
        return self.client.post(url, data, format="json")

    def edit(self, article, data):
        return self.client.patch("/api/articles/" + str(article.id) + "/", data, format="json")

    def put_in(self, article, status):
        """Jump an article straight to a status, to set up a test quickly."""
        article.status = status
        article.scheduled_for = None
        article.published_at = None
        if status == Status.SCHEDULED:
            article.scheduled_for = timezone.now() + timedelta(days=1)
        if status == Status.PUBLISHED:
            article.published_at = timezone.now()
        article.save()

    def in_one_day(self):
        return (timezone.now() + timedelta(days=1)).isoformat()

    def status_events(self, article):
        return ArticleEvent.objects.filter(article=article, event_type=ArticleEvent.Type.STATUS_CHANGED)


class AllowedMoveTests(LifecycleTestCase):
    def test_author_submits_draft_for_review(self):
        self.as_user(self.writer)
        response = self.act(self.article, "submit")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["status"], Status.IN_REVIEW)

    def test_status_change_is_recorded_with_old_new_and_who(self):
        self.as_user(self.writer)
        self.act(self.article, "submit")
        event = self.status_events(self.article).get()
        self.assertEqual(event.from_status, Status.DRAFT)
        self.assertEqual(event.to_status, Status.IN_REVIEW)
        self.assertEqual(event.actor, self.writer)
        self.assertEqual(event.payload["actor_role"], User.Role.WRITER)

    def test_editor_approves_article_in_review(self):
        self.put_in(self.article, Status.IN_REVIEW)
        self.as_user(self.editor)
        response = self.act(self.article, "approve")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["status"], Status.APPROVED)

    def test_editor_schedules_approved_article_for_the_future(self):
        self.put_in(self.article, Status.APPROVED)
        self.as_user(self.editor)
        response = self.act(self.article, "schedule", {"scheduled_for": self.in_one_day()})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["status"], Status.SCHEDULED)
        self.article.refresh_from_db()
        self.assertIsNotNone(self.article.scheduled_for)

    def test_editor_publishes_approved_article_now(self):
        self.put_in(self.article, Status.APPROVED)
        self.as_user(self.editor)
        before = timezone.now()
        response = self.act(self.article, "publish")
        self.assertEqual(response.status_code, 200)
        self.article.refresh_from_db()
        self.assertEqual(self.article.status, Status.PUBLISHED)
        self.assertGreaterEqual(self.article.published_at, before)

    def test_publishing_keeps_the_text_that_went_live(self):
        self.put_in(self.article, Status.APPROVED)
        self.as_user(self.editor)
        self.act(self.article, "publish")
        event = self.status_events(self.article).get()
        self.assertEqual(event.payload["title"], "New phones")
        self.assertEqual(event.payload["body"], "Draft text")

    def test_unpublish_scheduled_article(self):
        self.put_in(self.article, Status.SCHEDULED)
        self.as_user(self.editor)
        response = self.act(self.article, "unpublish")
        self.assertEqual(response.status_code, 200)
        self.article.refresh_from_db()
        self.assertEqual(self.article.status, Status.APPROVED)
        self.assertIsNone(self.article.scheduled_for)

    def test_unpublish_published_article(self):
        self.put_in(self.article, Status.PUBLISHED)
        self.as_user(self.editor)
        response = self.act(self.article, "unpublish")
        self.assertEqual(response.status_code, 200)
        self.article.refresh_from_db()
        self.assertEqual(self.article.status, Status.APPROVED)
        self.assertIsNone(self.article.published_at)

    def test_full_path_is_recorded_in_order(self):
        self.as_user(self.writer)
        self.act(self.article, "submit")
        self.as_user(self.editor)
        self.act(self.article, "approve")
        self.act(self.article, "schedule", {"scheduled_for": self.in_one_day()})
        self.act(self.article, "unpublish")
        self.act(self.article, "publish")

        steps = []
        for event in self.status_events(self.article):
            steps.append(event.from_status + " -> " + event.to_status)
        self.assertEqual(
            steps,
            [
                "DRAFT -> IN_REVIEW",
                "IN_REVIEW -> APPROVED",
                "APPROVED -> SCHEDULED",
                "SCHEDULED -> APPROVED",
                "APPROVED -> PUBLISHED",
            ],
        )


class WhoCanMoveTests(LifecycleTestCase):
    def test_author_cannot_approve_own_article_even_as_editor(self):
        self.put_in(self.editors_article, Status.IN_REVIEW)
        self.as_user(self.editor)
        response = self.act(self.editors_article, "approve")
        self.assertEqual(response.status_code, 403)
        self.assertEqual(
            response.data["detail"], "You cannot approve an article you wrote. Another editor must approve it."
        )
        self.editors_article.refresh_from_db()
        self.assertEqual(self.editors_article.status, Status.IN_REVIEW)

    def test_another_editor_can_approve_an_editors_article(self):
        self.put_in(self.editors_article, Status.IN_REVIEW)
        self.as_user(self.other_editor)
        self.assertEqual(self.act(self.editors_article, "approve").status_code, 200)

    def test_writer_cannot_make_editor_moves(self):
        # Each move is tried from the one status where it would otherwise be legal.
        cases = [
            ("approve", Status.IN_REVIEW),
            ("schedule", Status.APPROVED),
            ("publish", Status.APPROVED),
            ("unpublish", Status.PUBLISHED),
        ]
        self.as_user(self.writer)
        for action_name, status in cases:
            with self.subTest(action=action_name):
                self.put_in(self.article, status)
                response = self.act(self.article, action_name, {"scheduled_for": self.in_one_day()})
                self.assertEqual(response.status_code, 403)
                self.assertEqual(response.data["detail"], "Only editors can " + action_name + " articles.")
                self.article.refresh_from_db()
                self.assertEqual(self.article.status, status)

    def test_another_writer_cannot_submit_my_draft(self):
        self.as_user(self.other_writer)
        response = self.act(self.article, "submit")
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.data["detail"], "Only the article's author can submit it for review.")

    def test_editor_cannot_submit_a_writers_draft(self):
        self.as_user(self.editor)
        self.assertEqual(self.act(self.article, "submit").status_code, 403)

    def test_writer_outside_the_section_gets_404(self):
        self.as_user(self.outsider)
        self.assertEqual(self.act(self.article, "submit").status_code, 404)

    def test_login_required(self):
        self.assertEqual(self.act(self.article, "submit").status_code, 401)


class IllegalMoveTests(LifecycleTestCase):
    def test_cannot_approve_a_draft(self):
        self.as_user(self.editor)
        response = self.act(self.article, "approve")
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data["detail"], "Only an In Review article can be approved.")

    def test_cannot_jump_from_draft_to_published(self):
        self.as_user(self.editor)
        response = self.act(self.article, "publish")
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data["detail"], "Only an Approved article can be published.")

    def test_cannot_schedule_an_article_in_review(self):
        self.put_in(self.article, Status.IN_REVIEW)
        self.as_user(self.editor)
        response = self.act(self.article, "schedule", {"scheduled_for": self.in_one_day()})
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data["detail"], "Only an Approved article can be scheduled.")

    def test_cannot_submit_twice(self):
        self.as_user(self.writer)
        self.act(self.article, "submit")
        response = self.act(self.article, "submit")
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data["detail"], "Only a Draft article can be submitted for review.")

    def test_cannot_unpublish_an_approved_article(self):
        self.put_in(self.article, Status.APPROVED)
        self.as_user(self.editor)
        response = self.act(self.article, "unpublish")
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data["detail"], "Only a Scheduled or Published article can be unpublished.")

    def test_cannot_schedule_in_the_past(self):
        self.put_in(self.article, Status.APPROVED)
        self.as_user(self.editor)
        an_hour_ago = (timezone.now() - timedelta(hours=1)).isoformat()
        response = self.act(self.article, "schedule", {"scheduled_for": an_hour_ago})
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data["detail"], "The publish time must be in the future.")
        self.article.refresh_from_db()
        self.assertEqual(self.article.status, Status.APPROVED)

    def test_cannot_schedule_without_a_time(self):
        self.put_in(self.article, Status.APPROVED)
        self.as_user(self.editor)
        response = self.act(self.article, "schedule")
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data["detail"], "A publish time is required to schedule an article.")

    def test_rejected_move_leaves_no_trace(self):
        self.as_user(self.editor)
        self.act(self.article, "approve")
        self.assertEqual(self.status_events(self.article).count(), 0)

    def test_status_cannot_be_changed_by_editing(self):
        # PATCHing "status" directly must not skip the lifecycle.
        self.as_user(self.editor)
        self.edit(self.article, {"status": Status.PUBLISHED})
        self.article.refresh_from_db()
        self.assertEqual(self.article.status, Status.DRAFT)


class EditRuleTests(LifecycleTestCase):
    def test_editing_approved_article_sends_it_back_to_review(self):
        self.put_in(self.article, Status.APPROVED)
        self.as_user(self.writer)
        response = self.edit(self.article, {"body": "Changed after approval"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["status"], Status.IN_REVIEW)

        event = self.status_events(self.article).get()
        self.assertEqual(event.from_status, Status.APPROVED)
        self.assertEqual(event.to_status, Status.IN_REVIEW)
        self.assertEqual(event.actor, self.writer)

    def test_editing_scheduled_article_sends_it_back_and_clears_the_time(self):
        self.put_in(self.article, Status.SCHEDULED)
        self.as_user(self.editor)
        self.edit(self.article, {"title": "Fixed headline"})
        self.article.refresh_from_db()
        self.assertEqual(self.article.status, Status.IN_REVIEW)
        self.assertIsNone(self.article.scheduled_for)

    def test_published_article_cannot_be_edited(self):
        self.put_in(self.article, Status.PUBLISHED)
        self.as_user(self.editor)
        response = self.edit(self.article, {"body": "Quiet change"})
        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            response.data["detail"], "A published article cannot be edited directly. Open a revision instead."
        )
        self.article.refresh_from_db()
        self.assertEqual(self.article.body, "Draft text")

    def test_editing_draft_or_in_review_keeps_status(self):
        self.as_user(self.writer)
        for status in [Status.DRAFT, Status.IN_REVIEW]:
            with self.subTest(status=status):
                self.put_in(self.article, status)
                response = self.edit(self.article, {"body": "Text for " + status})
                self.assertEqual(response.data["status"], status)

    def test_saving_approved_article_without_changes_keeps_it_approved(self):
        self.put_in(self.article, Status.APPROVED)
        self.as_user(self.writer)
        response = self.edit(self.article, {"title": "New phones"})
        self.assertEqual(response.data["status"], Status.APPROVED)
