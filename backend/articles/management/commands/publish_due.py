"""
python manage.py publish_due [--dry-run]

Publishes every Scheduled article and revision whose publish time has come.
It can be run by hand or by a scheduler (for example every few minutes).
On the free hosting plan there is no scheduler, so the overdue alerts are
the safety net: anything not published on time shows up there.

Each item goes through lifecycle.transition(), like an editor's click, so
the same rules apply and the timeline gets its entry. The timeline names
the section's owning editor as the one who published, with a note that it
happened automatically.
"""

from django.core.management.base import BaseCommand
from django.utils import timezone
from rest_framework.exceptions import APIException

from articles.lifecycle import transition
from articles.models import Article, ArticleRevision, Status

AUTOMATIC_NOTE = "Published automatically at its scheduled time (publish_due)."


class Command(BaseCommand):
    help = "Publish Scheduled articles and revisions whose publish time has passed."

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true", help="Only list what would be published.")

    def handle(self, *args, **options):
        now = timezone.now()
        dry_run = options["dry_run"]

        due = []
        for article in Article.objects.filter(status=Status.SCHEDULED, scheduled_for__lte=now).select_related(
            "section__owner"
        ):
            due.append(article)
        for revision in ArticleRevision.objects.filter(status=Status.SCHEDULED, scheduled_for__lte=now).select_related(
            "article__section__owner"
        ):
            due.append(revision)

        published = 0
        skipped = 0
        for item in due:
            if isinstance(item, ArticleRevision):
                label = item.article.title + " (revision " + str(item.number) + ")"
                owner = item.article.section.owner
            else:
                label = item.title
                owner = item.section.owner

            if dry_run:
                self.stdout.write("Would publish: " + label)
                continue

            try:
                transition(item, "publish", owner, message=AUTOMATIC_NOTE)
            except APIException as error:
                # e.g. the section owner is no longer an editor, or the article
                # of a revision was unpublished. It stays overdue, so it stays
                # in the alerts for a person to deal with.
                skipped = skipped + 1
                self.stdout.write("Skipped: " + label + " (" + str(error.detail) + ")")
                continue

            published = published + 1
            self.stdout.write("Published: " + label)

        if dry_run:
            self.stdout.write(str(len(due)) + " item(s) due.")
        else:
            self.stdout.write("Done: " + str(published) + " published, " + str(skipped) + " skipped.")
