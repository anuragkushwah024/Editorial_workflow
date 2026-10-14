from rest_framework.test import APITestCase

from accounts.models import User
from sections.models import Section, SectionAssignment

from .models import Article, ArticleEvent, Status


class ArticleApiTestCase(APITestCase):
    """Shared setup.

    Tech has two writers (Chirag and Divya); Politics has only Divya.
    Esha is a writer with no sections at all.
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
        self.politics = Section.objects.create(name="Politics", owner=self.editor)
        SectionAssignment.objects.create(section=self.tech, writer=self.writer, assigned_by=self.editor)
        SectionAssignment.objects.create(section=self.tech, writer=self.other_writer, assigned_by=self.editor)
        SectionAssignment.objects.create(section=self.politics, writer=self.other_writer, assigned_by=self.editor)

        self.tech_article = Article.objects.create(
            section=self.tech, author=self.writer, title="New phones", body="Draft text"
        )
        self.politics_article = Article.objects.create(
            section=self.politics, author=self.other_writer, title="Election", body="Draft text"
        )

    def as_user(self, user):
        self.client.force_authenticate(user=user)

    def url(self, article):
        return "/api/articles/" + str(article.id) + "/"

    def create(self, section, title="A title", body="A body"):
        return self.client.post(
            "/api/articles/", {"section_id": section.id, "title": title, "body": body}, format="json"
        )

    def titles(self, response):
        result = []
        for item in response.data:
            result.append(item["title"])
        return sorted(result)


class CreateTests(ArticleApiTestCase):
    def test_writer_creates_article_in_assigned_section(self):
        self.as_user(self.writer)
        response = self.create(self.tech, title="Chip shortage")
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["author"]["email"], "writer@example.com")
        self.assertEqual(response.data["section"]["name"], "Tech")
        self.assertEqual(response.data["status"], Status.DRAFT)

    def test_creating_records_a_created_event(self):
        self.as_user(self.writer)
        response = self.create(self.tech)
        events = ArticleEvent.objects.filter(article_id=response.data["id"])
        self.assertEqual(events.count(), 1)
        self.assertEqual(events[0].event_type, ArticleEvent.Type.CREATED)
        self.assertEqual(events[0].actor, self.writer)

    def test_writer_cannot_create_in_unassigned_section(self):
        self.as_user(self.writer)
        response = self.create(self.politics, title="Sneaky")
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.data["detail"], "You can only create articles in sections you are assigned to.")
        self.assertFalse(Article.objects.filter(title="Sneaky").exists())

    def test_writer_with_no_sections_cannot_create(self):
        self.as_user(self.outsider)
        self.assertEqual(self.create(self.tech).status_code, 403)

    def test_editor_creates_in_any_section_and_is_the_author(self):
        self.as_user(self.editor)
        response = self.create(self.politics)
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["author"]["email"], "editor@example.com")

    def test_cannot_create_in_archived_section(self):
        self.tech.is_archived = True
        self.tech.save()
        self.as_user(self.editor)
        response = self.create(self.tech)
        self.assertEqual(response.status_code, 400)
        self.assertIn("section_id", response.data)

    def test_client_cannot_choose_author_or_status(self):
        self.as_user(self.writer)
        response = self.client.post(
            "/api/articles/",
            {
                "section_id": self.tech.id,
                "title": "t",
                "body": "b",
                "status": Status.PUBLISHED,
                "author": self.editor.id,
            },
            format="json",
        )
        self.assertEqual(response.status_code, 201)
        article = Article.objects.get(pk=response.data["id"])
        self.assertEqual(article.status, Status.DRAFT)
        self.assertEqual(article.author, self.writer)

    def test_title_cannot_be_blank(self):
        self.as_user(self.writer)
        response = self.create(self.tech, title="   ")
        self.assertEqual(response.status_code, 400)
        self.assertIn("title", response.data)

    def test_unknown_section_is_rejected(self):
        self.as_user(self.editor)
        response = self.client.post(
            "/api/articles/", {"section_id": 99999, "title": "t", "body": "b"}, format="json"
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("section_id", response.data)


class VisibilityTests(ArticleApiTestCase):
    def test_login_required(self):
        self.assertEqual(self.client.get("/api/articles/").status_code, 401)

    def test_editor_sees_all_articles(self):
        self.as_user(self.editor)
        response = self.client.get("/api/articles/")
        self.assertEqual(self.titles(response), ["Election", "New phones"])

    def test_writer_sees_only_articles_in_assigned_sections(self):
        self.as_user(self.writer)
        response = self.client.get("/api/articles/")
        self.assertEqual(self.titles(response), ["New phones"])

    def test_writer_sees_other_writers_articles_in_shared_section(self):
        self.as_user(self.other_writer)
        response = self.client.get("/api/articles/")
        self.assertEqual(self.titles(response), ["Election", "New phones"])

    def test_writer_with_no_sections_sees_nothing(self):
        self.as_user(self.outsider)
        self.assertEqual(self.client.get("/api/articles/").data, [])

    def test_writer_cannot_open_article_in_unassigned_section(self):
        self.as_user(self.writer)
        self.assertEqual(self.client.get(self.url(self.politics_article)).status_code, 404)

    def test_writer_removed_from_section_loses_its_articles(self):
        SectionAssignment.objects.filter(section=self.tech, writer=self.writer).delete()
        self.as_user(self.writer)
        self.assertEqual(self.client.get("/api/articles/").data, [])
        # Even the article they wrote themselves.
        self.assertEqual(self.client.get(self.url(self.tech_article)).status_code, 404)

    def test_archived_section_articles_are_hidden(self):
        self.tech.is_archived = True
        self.tech.save()

        self.as_user(self.editor)
        self.assertEqual(self.titles(self.client.get("/api/articles/")), ["Election"])
        # The data is still there: an editor can still open it.
        self.assertEqual(self.client.get(self.url(self.tech_article)).status_code, 200)

        self.as_user(self.writer)
        self.assertEqual(self.client.get(self.url(self.tech_article)).status_code, 404)


class EditTests(ArticleApiTestCase):
    def test_writer_edits_own_article(self):
        self.as_user(self.writer)
        response = self.client.patch(self.url(self.tech_article), {"title": "Newer phones"}, format="json")
        self.assertEqual(response.status_code, 200)
        self.tech_article.refresh_from_db()
        self.assertEqual(self.tech_article.title, "Newer phones")

    def test_edit_records_which_fields_changed(self):
        self.as_user(self.writer)
        self.client.patch(self.url(self.tech_article), {"title": "Newer phones", "body": "Draft text"}, format="json")
        event = ArticleEvent.objects.get(article=self.tech_article, event_type=ArticleEvent.Type.EDITED)
        self.assertEqual(event.payload, {"fields": ["title"]})
        self.assertEqual(event.actor, self.writer)

    def test_saving_without_changes_records_nothing(self):
        self.as_user(self.writer)
        self.client.patch(self.url(self.tech_article), {"title": "New phones"}, format="json")
        self.assertFalse(ArticleEvent.objects.filter(event_type=ArticleEvent.Type.EDITED).exists())

    def test_writer_cannot_edit_another_writers_article(self):
        # Divya can see Chirag's article (same section) but not edit it.
        self.as_user(self.other_writer)
        response = self.client.patch(self.url(self.tech_article), {"title": "Hijacked"}, format="json")
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.data["detail"], "You can only edit articles you wrote.")
        self.tech_article.refresh_from_db()
        self.assertEqual(self.tech_article.title, "New phones")

    def test_writer_cannot_edit_article_in_unassigned_section(self):
        self.as_user(self.writer)
        response = self.client.patch(self.url(self.politics_article), {"title": "Hijacked"}, format="json")
        self.assertEqual(response.status_code, 404)

    def test_editor_edits_any_article_and_author_stays(self):
        self.as_user(self.editor)
        response = self.client.patch(self.url(self.politics_article), {"body": "Edited by desk"}, format="json")
        self.assertEqual(response.status_code, 200)
        self.politics_article.refresh_from_db()
        self.assertEqual(self.politics_article.body, "Edited by desk")
        self.assertEqual(self.politics_article.author, self.other_writer)

    def test_edit_cannot_move_article_to_another_section(self):
        self.as_user(self.editor)
        self.client.patch(self.url(self.tech_article), {"section_id": self.politics.id}, format="json")
        self.tech_article.refresh_from_db()
        self.assertEqual(self.tech_article.section, self.tech)

    def test_articles_cannot_be_deleted(self):
        self.as_user(self.editor)
        response = self.client.delete(self.url(self.tech_article))
        self.assertEqual(response.status_code, 405)
        self.assertTrue(Article.objects.filter(pk=self.tech_article.pk).exists())
