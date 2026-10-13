from django.db import DatabaseError, IntegrityError, transaction
from django.test import TestCase

from accounts.models import User
from sections.models import Section

from .models import Article, ArticleEvent, Status


class ImmutableTimelineTests(TestCase):
    """Goal 9: nothing in the timeline can be edited or deleted."""

    def setUp(self):
        self.editor = User.objects.create_user(
            email="ed@example.com", password="x", full_name="Ed", role=User.Role.EDITOR
        )
        self.section = Section.objects.create(name="Tech", owner=self.editor)
        self.article = Article.objects.create(
            section=self.section, author=self.editor, title="Hello", body="World"
        )
        self.event = ArticleEvent.objects.create(
            article=self.article,
            event_type=ArticleEvent.Type.COMMENT,
            actor=self.editor,
            message="original comment",
        )

    def test_model_save_on_existing_event_is_blocked(self):
        self.event.message = "rewritten"
        with self.assertRaises(ValueError):
            self.event.save()

    def test_model_delete_is_blocked(self):
        with self.assertRaises(ValueError):
            self.event.delete()

    def test_database_blocks_queryset_update(self):
        # QuerySet.update() skips save(), so only the Postgres trigger stops it.
        with self.assertRaises(DatabaseError):
            with transaction.atomic():
                ArticleEvent.objects.filter(pk=self.event.pk).update(message="rewritten")

    def test_database_blocks_queryset_delete(self):
        with self.assertRaises(DatabaseError):
            with transaction.atomic():
                ArticleEvent.objects.filter(pk=self.event.pk).delete()

    def test_event_is_unchanged_after_attempts(self):
        try:
            with transaction.atomic():
                ArticleEvent.objects.filter(pk=self.event.pk).update(message="rewritten")
        except DatabaseError:
            pass
        fresh = ArticleEvent.objects.get(pk=self.event.pk)
        self.assertEqual(fresh.message, "original comment")


class ArticleConstraintTests(TestCase):
    def setUp(self):
        self.editor = User.objects.create_user(
            email="ed@example.com", password="x", full_name="Ed", role=User.Role.EDITOR
        )
        self.section = Section.objects.create(name="Tech", owner=self.editor)

    def test_scheduled_article_needs_a_time(self):
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Article.objects.create(
                    section=self.section,
                    author=self.editor,
                    title="t",
                    body="b",
                    status=Status.SCHEDULED,
                )
