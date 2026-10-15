from datetime import timedelta

from django.utils import timezone
from rest_framework.test import APITestCase

from accounts.models import User
from sections.models import Section, SectionAssignment

from .models import Article, ArticleEvent, ArticleRevision, Status


class RevisionTestCase(APITestCase):
    """Shared setup.

    Chirag and Divya are writers in Tech. Esha is a writer with no sections.
    Asha and Bina are editors. Chirag's article is already Published.
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

        self.published_at = timezone.now() - timedelta(days=2)
        self.article = Article.objects.create(
            section=self.tech,
            author=self.writer,
            title="Original title",
            body="Original body",
            status=Status.PUBLISHED,
            published_at=self.published_at,
        )

    def as_user(self, user):
        self.client.force_authenticate(user=user)

    def open_revision(self, data=None):
        if data is None:
            data = {}
        return self.client.post("/api/articles/" + str(self.article.id) + "/revisions/", data, format="json")

    def act(self, revision_id, action_name, data=None):
        if data is None:
            data = {}
        url = "/api/revisions/" + str(revision_id) + "/" + action_name + "/"
        return self.client.post(url, data, format="json")

    def edit(self, revision_id, data):
        return self.client.patch("/api/revisions/" + str(revision_id) + "/", data, format="json")

    def new_revision(self, opened_by, status=Status.DRAFT):
        """Create a revision directly in a given status, to set up a test quickly."""
        scheduled_for = None
        if status == Status.SCHEDULED:
            # Set together with the status: the database refuses a Scheduled row without a time.
            scheduled_for = timezone.now() + timedelta(days=1)
        return ArticleRevision.objects.create(
            article=self.article,
            number=ArticleRevision.objects.filter(article=self.article).count() + 1,
            title="Corrected title",
            body="Corrected body",
            created_by=opened_by,
            status=status,
            scheduled_for=scheduled_for,
        )

    def in_one_day(self):
        return (timezone.now() + timedelta(days=1)).isoformat()


class OpenRevisionTests(RevisionTestCase):
    def test_author_opens_revision_as_a_copy_of_the_live_text(self):
        self.as_user(self.writer)
        response = self.open_revision()
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["number"], 1)
        self.assertEqual(response.data["status"], Status.DRAFT)
        self.assertEqual(response.data["title"], "Original title")
        self.assertEqual(response.data["body"], "Original body")

    def test_opening_is_recorded_in_the_timeline(self):
        self.as_user(self.writer)
        response = self.open_revision()
        event = ArticleEvent.objects.get(article=self.article, event_type=ArticleEvent.Type.REVISION_OPENED)
        self.assertEqual(event.revision_id, response.data["id"])
        self.assertEqual(event.actor, self.writer)

    def test_revision_can_start_with_new_text(self):
        self.as_user(self.writer)
        response = self.open_revision({"title": "Fixed title", "body": "Fixed body"})
        self.assertEqual(response.data["title"], "Fixed title")

    def test_editor_can_open_revision_of_a_writers_article(self):
        self.as_user(self.editor)
        response = self.open_revision()
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["created_by"]["email"], "editor@example.com")

    def test_another_writer_cannot_open_a_revision(self):
        self.as_user(self.other_writer)
        response = self.open_revision()
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.data["detail"], "Only the article's author or an editor can open a revision.")

    def test_writer_outside_the_section_gets_404(self):
        self.as_user(self.outsider)
        self.assertEqual(self.open_revision().status_code, 404)

    def test_only_published_articles_get_revisions(self):
        self.article.status = Status.DRAFT
        self.article.published_at = None
        self.article.save()
        self.as_user(self.writer)
        response = self.open_revision()
        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            response.data["detail"], "Only a published article needs a revision. Edit the article directly instead."
        )

    def test_only_one_open_revision_at_a_time(self):
        self.as_user(self.writer)
        self.open_revision()
        response = self.open_revision()
        self.assertEqual(response.status_code, 400)
        self.assertIn("already has an open revision", response.data["detail"])
        self.assertEqual(ArticleRevision.objects.filter(article=self.article).count(), 1)

    def test_next_revision_can_open_once_the_last_one_is_published(self):
        self.new_revision(self.writer, Status.PUBLISHED)
        self.as_user(self.writer)
        response = self.open_revision()
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["number"], 2)

    def test_revision_list(self):
        self.new_revision(self.writer, Status.PUBLISHED)
        self.new_revision(self.writer)
        self.as_user(self.other_writer)
        response = self.client.get("/api/articles/" + str(self.article.id) + "/revisions/")
        self.assertEqual(response.status_code, 200)
        numbers = []
        for item in response.data:
            numbers.append(item["number"])
        self.assertEqual(numbers, [1, 2])


class RevisionLifecycleTests(RevisionTestCase):
    def test_full_path_replaces_live_text_only_at_publish(self):
        self.as_user(self.writer)
        revision_id = self.open_revision().data["id"]
        self.edit(revision_id, {"body": "Corrected body"})
        self.act(revision_id, "submit")

        self.as_user(self.editor)
        self.act(revision_id, "approve")

        # Approved is not live yet: readers still see the original.
        self.article.refresh_from_db()
        self.assertEqual(self.article.body, "Original body")

        response = self.act(revision_id, "publish")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["status"], Status.PUBLISHED)

        self.article.refresh_from_db()
        self.assertEqual(self.article.body, "Corrected body")
        self.assertEqual(self.article.status, Status.PUBLISHED)

    def test_publishing_records_what_the_original_said(self):
        revision = self.new_revision(self.writer, Status.APPROVED)
        self.as_user(self.editor)
        self.act(revision.id, "publish")
        event = ArticleEvent.objects.get(article=self.article, event_type=ArticleEvent.Type.REVISION_PUBLISHED)
        self.assertEqual(event.revision, revision)
        self.assertEqual(event.payload["previous_title"], "Original title")
        self.assertEqual(event.payload["previous_body"], "Original body")

    def test_article_keeps_its_original_publish_time(self):
        revision = self.new_revision(self.writer, Status.APPROVED)
        self.as_user(self.editor)
        self.act(revision.id, "publish")
        self.article.refresh_from_db()
        self.assertEqual(self.article.published_at, self.published_at)

    def test_revision_status_changes_are_in_the_article_timeline(self):
        self.as_user(self.writer)
        revision_id = self.open_revision().data["id"]
        self.act(revision_id, "submit")
        event = ArticleEvent.objects.get(article=self.article, event_type=ArticleEvent.Type.STATUS_CHANGED)
        self.assertEqual(event.revision_id, revision_id)
        self.assertEqual(event.from_status, Status.DRAFT)
        self.assertEqual(event.to_status, Status.IN_REVIEW)

    def test_scheduled_revision_does_not_change_the_live_text(self):
        revision = self.new_revision(self.writer, Status.APPROVED)
        self.as_user(self.editor)
        response = self.act(revision.id, "schedule", {"scheduled_for": self.in_one_day()})
        self.assertEqual(response.data["status"], Status.SCHEDULED)
        self.article.refresh_from_db()
        self.assertEqual(self.article.title, "Original title")

    def test_scheduled_revision_can_be_unpublished(self):
        revision = self.new_revision(self.writer, Status.SCHEDULED)
        self.as_user(self.editor)
        response = self.act(revision.id, "unpublish")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["status"], Status.APPROVED)

    def test_published_revision_cannot_be_unpublished(self):
        revision = self.new_revision(self.writer, Status.PUBLISHED)
        self.as_user(self.editor)
        response = self.act(revision.id, "unpublish")
        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            response.data["detail"],
            "A published revision is already part of the live article. Unpublish the article instead.",
        )

    def test_revision_cannot_go_live_if_the_article_was_unpublished(self):
        revision = self.new_revision(self.writer, Status.APPROVED)
        self.article.status = Status.APPROVED
        self.article.published_at = None
        self.article.save()
        self.as_user(self.editor)
        response = self.act(revision.id, "publish")
        self.assertEqual(response.status_code, 400)
        self.assertIn("no longer published", response.data["detail"])


class RevisionRuleTests(RevisionTestCase):
    def test_editor_cannot_approve_a_revision_they_opened(self):
        revision = self.new_revision(self.editor, Status.IN_REVIEW)
        self.as_user(self.editor)
        response = self.act(revision.id, "approve")
        self.assertEqual(response.status_code, 403)
        self.assertEqual(
            response.data["detail"], "You cannot approve a revision you wrote. Another editor must approve it."
        )

        self.as_user(self.other_editor)
        self.assertEqual(self.act(revision.id, "approve").status_code, 200)

    def test_writer_cannot_approve_or_publish_a_revision(self):
        revision = self.new_revision(self.writer, Status.IN_REVIEW)
        self.as_user(self.writer)
        response = self.act(revision.id, "approve")
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.data["detail"], "Only editors can approve revisions.")

        revision.status = Status.APPROVED
        revision.save()
        self.assertEqual(self.act(revision.id, "publish").status_code, 403)

    def test_only_the_person_who_opened_it_can_submit(self):
        revision = self.new_revision(self.writer)
        self.as_user(self.editor)
        self.assertEqual(self.act(revision.id, "submit").status_code, 403)

    def test_cannot_skip_review(self):
        revision = self.new_revision(self.writer)
        self.as_user(self.editor)
        response = self.act(revision.id, "publish")
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data["detail"], "Only an Approved or Scheduled revision can be published.")

    def test_editing_approved_revision_sends_it_back_to_review(self):
        revision = self.new_revision(self.writer, Status.APPROVED)
        self.as_user(self.writer)
        response = self.edit(revision.id, {"body": "Another change"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["status"], Status.IN_REVIEW)

    def test_published_revision_cannot_be_edited(self):
        revision = self.new_revision(self.writer, Status.PUBLISHED)
        self.as_user(self.editor)
        response = self.edit(revision.id, {"body": "Sneaky change"})
        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            response.data["detail"], "This revision is already published. Open a new revision instead."
        )

    def test_another_writer_cannot_edit_my_revision(self):
        revision = self.new_revision(self.writer)
        self.as_user(self.other_writer)
        response = self.edit(revision.id, {"body": "Hijacked"})
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.data["detail"], "You can only edit revisions you opened.")

    def test_writer_outside_the_section_cannot_see_revisions(self):
        revision = self.new_revision(self.writer)
        self.as_user(self.outsider)
        self.assertEqual(self.client.get("/api/revisions/" + str(revision.id) + "/").status_code, 404)
