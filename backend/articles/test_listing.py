from datetime import timedelta

from django.utils import timezone
from rest_framework.test import APITestCase

from accounts.models import User
from sections.models import Section, SectionAssignment

from .models import Article, Status


class ListingTestCase(APITestCase):
    """Shared setup.

    Tech: Chirag's "Rupee falls" (Published), Chirag's "Budget phones" (Draft),
          Divya's "Phone review" (In Review).
    Politics: Asha's "Rupee and the election" (Scheduled). Only editors see it.
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
        self.tech = Section.objects.create(name="Tech", owner=self.editor)
        self.politics = Section.objects.create(name="Politics", owner=self.editor)
        SectionAssignment.objects.create(section=self.tech, writer=self.writer, assigned_by=self.editor)
        SectionAssignment.objects.create(section=self.tech, writer=self.other_writer, assigned_by=self.editor)

        now = timezone.now()
        self.rupee = Article.objects.create(
            section=self.tech, author=self.writer, title="Rupee falls",
            body="The rupee fell against the dollar.", status=Status.PUBLISHED,
            published_at=now - timedelta(days=1),
        )
        self.budget = Article.objects.create(
            section=self.tech, author=self.writer, title="Budget phones",
            body="Cheap phones are getting better.",
        )
        self.review = Article.objects.create(
            section=self.tech, author=self.other_writer, title="Phone review",
            body="A long review of one phone.", status=Status.IN_REVIEW,
        )
        self.election = Article.objects.create(
            section=self.politics, author=self.editor, title="Rupee and the election",
            body="Parties promise to protect the rupee.", status=Status.SCHEDULED,
            scheduled_for=now + timedelta(days=2),
        )

        # Give each article a clearly different "last updated" time. Created a
        # few microseconds apart, they can get the same time on Windows, whose
        # clock is coarser, and the sort tests would depend on luck.
        # .update() is used because save() would overwrite updated_at with now.
        hours_ago = 4
        for article in [self.rupee, self.budget, self.review, self.election]:
            Article.objects.filter(pk=article.pk).update(updated_at=now - timedelta(hours=hours_ago))
            hours_ago = hours_ago - 1

    def as_user(self, user):
        self.client.force_authenticate(user=user)

    def get(self, query=""):
        return self.client.get("/api/articles/" + query)

    def titles(self, response):
        result = []
        for item in response.data["results"]:
            result.append(item["title"])
        return result


class SearchTests(ListingTestCase):
    def test_search_matches_title_and_body(self):
        self.as_user(self.editor)
        response = self.get("?q=rupee")
        self.assertEqual(sorted(self.titles(response)), ["Rupee and the election", "Rupee falls"])

    def test_search_matches_word_forms(self):
        # "falling" and "fell" share no letters-in-a-row with "falls", but the
        # English stemmer reduces "falling" and "falls" to the same word.
        self.as_user(self.editor)
        self.assertEqual(self.titles(self.get("?q=falling")), ["Rupee falls"])

    def test_title_match_ranks_above_body_match(self):
        Article.objects.create(
            section=self.tech, author=self.writer, title="Markets today",
            body="Shares rose. The phones sector was quiet.",
        )
        self.as_user(self.editor)
        titles = self.titles(self.get("?q=phones"))
        # "Markets today" only has the word in its body, so both articles with
        # it in the title ("Phone review", "Budget phones") rank above it.
        self.assertEqual(titles[-1], "Markets today")
        self.assertEqual(sorted(titles[:2]), ["Budget phones", "Phone review"])

    def test_search_with_no_match_is_empty(self):
        self.as_user(self.editor)
        response = self.get("?q=cricket")
        self.assertEqual(response.data["count"], 0)
        self.assertEqual(response.data["results"], [])

    def test_writer_cannot_find_other_sections_through_search(self):
        self.as_user(self.writer)
        # "Rupee and the election" is in Politics, which Chirag can't see.
        self.assertEqual(self.titles(self.get("?q=election")), [])
        self.assertEqual(self.titles(self.get("?q=rupee")), ["Rupee falls"])

    def test_search_combined_with_filters(self):
        self.as_user(self.editor)
        response = self.get("?q=phone&status=DRAFT&section=" + str(self.tech.id))
        self.assertEqual(self.titles(response), ["Budget phones"])

    def test_search_symbols_do_not_crash(self):
        self.as_user(self.editor)
        for text in ['"', "-", "a & b | !", "''", "rupee -election"]:
            with self.subTest(text=text):
                self.assertEqual(self.get("?q=" + text).status_code, 200)
        self.assertEqual(self.titles(self.get("?q=rupee -election")), ["Rupee falls"])


class FilterTests(ListingTestCase):
    def test_filter_by_status(self):
        self.as_user(self.editor)
        self.assertEqual(self.titles(self.get("?status=IN_REVIEW")), ["Phone review"])

    def test_filter_by_section(self):
        self.as_user(self.editor)
        self.assertEqual(self.titles(self.get("?section=" + str(self.politics.id))), ["Rupee and the election"])

    def test_filter_by_author(self):
        self.as_user(self.editor)
        response = self.get("?author=" + str(self.other_writer.id))
        self.assertEqual(self.titles(response), ["Phone review"])

    def test_my_articles(self):
        self.as_user(self.writer)
        self.assertEqual(sorted(self.titles(self.get("?author=me"))), ["Budget phones", "Rupee falls"])

    def test_unknown_status_is_a_clear_error(self):
        self.as_user(self.editor)
        response = self.get("?status=LIVE")
        self.assertEqual(response.status_code, 400)
        self.assertIn("Unknown status", response.data["status"][0])

    def test_non_number_ids_are_a_clear_error(self):
        self.as_user(self.editor)
        self.assertEqual(self.get("?author=asha").status_code, 400)
        self.assertEqual(self.get("?section=tech").status_code, 400)

    def test_archived_sections_hidden_unless_asked_for(self):
        self.politics.is_archived = True
        self.politics.save()
        self.as_user(self.editor)
        self.assertNotIn("Rupee and the election", self.titles(self.get()))
        self.assertEqual(self.titles(self.get("?section=" + str(self.politics.id))), ["Rupee and the election"])


class SortTests(ListingTestCase):
    def test_default_is_newest_updated_first(self):
        self.as_user(self.editor)
        self.assertEqual(self.titles(self.get())[0], "Rupee and the election")

    def test_sort_by_updated_oldest_first(self):
        self.as_user(self.editor)
        self.assertEqual(self.titles(self.get("?sort=updated"))[0], "Rupee falls")

    def test_sort_by_status_follows_the_lifecycle(self):
        self.as_user(self.editor)
        self.assertEqual(
            self.titles(self.get("?sort=status")),
            ["Budget phones", "Phone review", "Rupee and the election", "Rupee falls"],
        )
        self.assertEqual(self.titles(self.get("?sort=-status"))[0], "Rupee falls")

    def test_sort_by_publish_time_puts_unpublished_last(self):
        self.as_user(self.editor)
        titles = self.titles(self.get("?sort=publish_time"))
        self.assertEqual(titles[:2], ["Rupee falls", "Rupee and the election"])
        titles = self.titles(self.get("?sort=-publish_time"))
        self.assertEqual(titles[:2], ["Rupee and the election", "Rupee falls"])

    def test_ties_follow_the_sort_direction(self):
        # Same updated time for all: oldest-first lists the lowest id first.
        Article.objects.all().update(updated_at=timezone.now())
        self.as_user(self.editor)
        self.assertEqual(self.titles(self.get("?sort=updated"))[0], "Rupee falls")
        self.assertEqual(self.titles(self.get("?sort=-updated"))[0], "Rupee and the election")

    def test_unknown_sort_is_a_clear_error(self):
        self.as_user(self.editor)
        response = self.get("?sort=title")
        self.assertEqual(response.status_code, 400)
        self.assertIn("sort", response.data)


class PageTests(ListingTestCase):
    def setUp(self):
        super().setUp()
        for number in range(1, 22):
            Article.objects.create(section=self.tech, author=self.writer, title="Filler " + str(number), body="x")

    def test_first_page_has_twenty_and_the_total(self):
        self.as_user(self.editor)
        response = self.get()
        self.assertEqual(response.data["count"], 25)
        self.assertEqual(response.data["page"], 1)
        self.assertEqual(response.data["total_pages"], 2)
        self.assertEqual(len(response.data["results"]), 20)

    def test_second_page_has_the_rest_without_repeats(self):
        self.as_user(self.editor)
        first = self.titles(self.get("?page=1"))
        second = self.titles(self.get("?page=2"))
        self.assertEqual(len(second), 5)
        for title in second:
            self.assertNotIn(title, first)

    def test_page_out_of_range_is_a_clear_error(self):
        self.as_user(self.editor)
        response = self.get("?page=999")
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.data["detail"], "This page does not exist. Go back to page 1.")

    def test_count_respects_filters(self):
        self.as_user(self.editor)
        self.assertEqual(self.get("?q=filler").data["count"], 21)
