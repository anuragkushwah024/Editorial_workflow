from rest_framework.test import APITestCase

from accounts.models import User
from sections.models import Section, SectionAssignment

from .models import ArticleEvent, Status


class TimelineTestCase(APITestCase):
    """Shared setup.

    Chirag and Divya are writers in Tech. Esha is a writer with no sections.
    Asha is an editor. Chirag writes an article through the API in each test,
    so the timeline is built by the real code, not inserted by hand.
    """

    def setUp(self):
        self.editor = User.objects.create_user(
            email="editor@example.com", password="x", full_name="Asha Editor", role=User.Role.EDITOR
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

        self.as_user(self.writer)
        response = self.client.post(
            "/api/articles/", {"section_id": self.tech.id, "title": "New phones", "body": "Draft"}, format="json"
        )
        self.article_id = response.data["id"]
        self.base = "/api/articles/" + str(self.article_id) + "/"

    def as_user(self, user):
        self.client.force_authenticate(user=user)

    def timeline(self):
        return self.client.get(self.base + "timeline/")

    def comment(self, message):
        return self.client.post(self.base + "comments/", {"message": message}, format="json")

    def types(self, response):
        result = []
        for entry in response.data:
            result.append(entry["event_type"])
        return result


class TimelineContentTests(TimelineTestCase):
    def test_timeline_lists_everything_oldest_first(self):
        self.client.patch(self.base, {"body": "Better draft"}, format="json")
        self.client.post(self.base + "submit/")
        self.as_user(self.editor)
        self.client.post(self.base + "approve/")
        self.comment("Looks good.")

        response = self.timeline()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            self.types(response),
            ["CREATED", "EDITED", "STATUS_CHANGED", "STATUS_CHANGED", "COMMENT"],
        )

    def test_status_change_entry_has_old_new_who_role_and_when(self):
        self.client.post(self.base + "submit/")
        entry = self.timeline().data[1]
        self.assertEqual(entry["from_status"], Status.DRAFT)
        self.assertEqual(entry["to_status"], Status.IN_REVIEW)
        self.assertEqual(entry["actor"]["email"], "writer@example.com")
        self.assertEqual(entry["actor_role"], User.Role.WRITER)
        self.assertIsNotNone(entry["created_at"])

    def test_revision_entries_say_which_revision(self):
        self.client.post(self.base + "submit/")
        self.as_user(self.editor)
        self.client.post(self.base + "approve/")
        self.client.post(self.base + "publish/")
        self.as_user(self.writer)
        revision = self.client.post(self.base + "revisions/", {}, format="json").data

        last = self.timeline().data[-1]
        self.assertEqual(last["event_type"], ArticleEvent.Type.REVISION_OPENED)
        self.assertEqual(last["revision"], {"id": revision["id"], "number": 1})

    def test_article_entries_have_no_revision(self):
        entry = self.timeline().data[0]
        self.assertEqual(entry["event_type"], ArticleEvent.Type.CREATED)
        self.assertIsNone(entry["revision"])


class TimelineAccessTests(TimelineTestCase):
    def test_other_writer_in_the_section_can_see_it(self):
        self.as_user(self.other_writer)
        self.assertEqual(self.timeline().status_code, 200)

    def test_editor_can_see_it(self):
        self.as_user(self.editor)
        self.assertEqual(self.timeline().status_code, 200)

    def test_writer_outside_the_section_gets_404(self):
        self.as_user(self.outsider)
        self.assertEqual(self.timeline().status_code, 404)

    def test_login_required(self):
        self.client.force_authenticate(user=None)
        self.assertEqual(self.timeline().status_code, 401)


class CommentTests(TimelineTestCase):
    def test_writer_and_editor_can_comment(self):
        self.as_user(self.other_writer)
        response = self.comment("Can you add a source?")
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["event_type"], ArticleEvent.Type.COMMENT)
        self.assertEqual(response.data["actor"]["email"], "writer2@example.com")

        self.as_user(self.editor)
        self.assertEqual(self.comment("Agreed.").status_code, 201)

        comments = ArticleEvent.objects.filter(article_id=self.article_id, event_type=ArticleEvent.Type.COMMENT)
        self.assertEqual(comments.count(), 2)

    def test_comment_text_is_kept_without_surrounding_spaces(self):
        response = self.comment("  Needs a quote.  ")
        self.assertEqual(response.data["message"], "Needs a quote.")

    def test_writer_outside_the_section_cannot_comment(self):
        self.as_user(self.outsider)
        self.assertEqual(self.comment("Hello").status_code, 404)

    def test_empty_comment_is_rejected(self):
        for message in ["", "   "]:
            with self.subTest(message=message):
                response = self.comment(message)
                self.assertEqual(response.status_code, 400)
                self.assertEqual(response.data["message"], ["A comment cannot be empty."])

    def test_missing_comment_is_rejected(self):
        response = self.client.post(self.base + "comments/", {}, format="json")
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data["message"], ["A comment cannot be empty."])


class CannotRewriteHistoryTests(TimelineTestCase):
    def test_comments_and_timeline_cannot_be_edited_or_deleted_through_the_api(self):
        self.as_user(self.editor)
        comment = self.comment("Original comment").data

        attempts = [
            ("patch", self.base + "timeline/"),
            ("put", self.base + "timeline/"),
            ("delete", self.base + "timeline/"),
            ("patch", self.base + "comments/"),
            ("put", self.base + "comments/"),
            ("delete", self.base + "comments/"),
        ]
        for method, url in attempts:
            with self.subTest(method=method, url=url):
                response = getattr(self.client, method)(url, {"message": "Rewritten"}, format="json")
                self.assertEqual(response.status_code, 405)

        stored = ArticleEvent.objects.get(pk=comment["id"])
        self.assertEqual(stored.message, "Original comment")

    def test_there_is_no_address_for_a_single_timeline_entry(self):
        self.as_user(self.editor)
        comment = self.comment("Original comment").data
        for url in ["/api/events/" + str(comment["id"]) + "/", self.base + "comments/" + str(comment["id"]) + "/"]:
            with self.subTest(url=url):
                self.assertEqual(self.client.delete(url).status_code, 404)
        self.assertTrue(ArticleEvent.objects.filter(pk=comment["id"]).exists())

    def test_client_cannot_fake_an_entry_type_or_author(self):
        self.as_user(self.writer)
        response = self.client.post(
            self.base + "comments/",
            {"message": "Hi", "event_type": "STATUS_CHANGED", "actor": self.editor.id, "to_status": "PUBLISHED"},
            format="json",
        )
        self.assertEqual(response.data["event_type"], ArticleEvent.Type.COMMENT)
        self.assertEqual(response.data["actor"]["email"], "writer@example.com")
        self.assertEqual(response.data["to_status"], "")
