"""
python manage.py seed_demo [--password PASSWORD] [--skip-if-exists]

Fills an empty database with demo data for reviewers:
  - 2 editors and 4 writers (all with the same demo password),
  - 5 sections with different owners and writers (one archived at the end),
  - 40 articles in every status, published over the last 8 weeks,
  - a published revision (so a timeline shows "what it said before"),
    an open revision, comments, and one overdue Scheduled article.

Everything goes through the same functions the API uses (lifecycle.py), so
every rule is applied and every timeline entry is real. To make the history
look like 8 weeks of work, each step runs with the clock set back to the
moment it "happened": timeline dates, publish times and the dashboard chart
then all agree.

Timeline entries can never be deleted (a database trigger blocks it), so this
command cannot clean up and start again. It refuses to run a second time.
"""

from contextlib import contextmanager
from datetime import timedelta
from unittest import mock

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from accounts.models import User
from articles.lifecycle import add_comment, create_article, edit_content, open_revision, transition
from articles.models import Status
from sections.models import Section, SectionAssignment

DEMO_DOMAIN = "@newsroom.demo"
DEFAULT_PASSWORD = "Demo@2026"

PEOPLE = [
    # key, name, role
    ("asha", "Asha Rao", User.Role.EDITOR),
    ("bina", "Bina Shah", User.Role.EDITOR),
    ("chirag", "Chirag Mehta", User.Role.WRITER),
    ("divya", "Divya Iyer", User.Role.WRITER),
    ("esha", "Esha Kapoor", User.Role.WRITER),
    ("farhan", "Farhan Ali", User.Role.WRITER),
]

SECTIONS = [
    # name, description, owner, writers
    ("Politics", "Parliament, elections and city government.", "asha", ["chirag", "divya"]),
    ("Tech", "Gadgets, apps, startups and the internet.", "bina", ["chirag", "esha"]),
    ("Culture", "Film, music, books and heritage.", "asha", ["divya", "farhan"]),
    ("Business", "Markets, money and small business.", "bina", ["esha", "farhan"]),
    ("Sport", "Local leagues and big events.", "asha", ["farhan"]),
]

# section, author, title, final status, days ago it was written, extra
# For Published, it went live one day after it was written.
# For Scheduled, "extra" is the publish time in days from now (negative = overdue).
ARTICLES = [
    ("Politics", "chirag", "Parliament's monsoon session opens with a crowded agenda", Status.PUBLISHED, 30, "revision"),
    ("Politics", "divya", "State budget sets aside more money for rural roads", Status.PUBLISHED, 45, None),
    ("Politics", "chirag", "Opposition parties meet to plan a joint campaign", Status.PUBLISHED, 16, None),
    ("Politics", "divya", "Election commission announces dates for by-polls", Status.SCHEDULED, 4, 2),
    ("Politics", "chirag", "What the new data protection rules mean for voters", Status.IN_REVIEW, 2, "comments"),
    ("Politics", "divya", "Ward councillors push for better street lighting", Status.DRAFT, 1, None),
    ("Politics", "chirag", "Explainer: how a bill becomes law", Status.APPROVED, 3, None),
    ("Politics", "divya", "City council approves new bus routes", Status.PUBLISHED, 6, None),
    ("Politics", "chirag", "How to read an exit poll", Status.PUBLISHED, 10, None),
    ("Politics", "divya", "Monsoon preparedness: what the city has done so far", Status.DRAFT, 2, None),
    ("Politics", "bina", "Editor's note: how we fact-check election claims", Status.IN_REVIEW, 2, None),
    ("Tech", "esha", "Chip shortage pushes phone prices up", Status.PUBLISHED, 9, "open_revision"),
    ("Tech", "chirag", "UPI payments cross a new monthly record", Status.PUBLISHED, 23, None),
    ("Tech", "esha", "Startups bet on regional-language AI assistants", Status.PUBLISHED, 38, None),
    ("Tech", "chirag", "Review: three budget laptops for students", Status.IN_REVIEW, 4, "edited_after_approval"),
    ("Tech", "esha", "How to spot a fake delivery SMS", Status.PUBLISHED, 3, None),
    ("Tech", "chirag", "Satellite internet trials begin in hill districts", Status.SCHEDULED, 2, "overdue"),
    ("Tech", "esha", "Data centres and the summer power crunch", Status.DRAFT, 1, None),
    ("Tech", "chirag", "Open-source maps help flood rescue teams", Status.APPROVED, 3, None),
    ("Tech", "esha", "Smartwatch makers add blood-oxygen alerts", Status.SCHEDULED, 3, 4),
    ("Culture", "divya", "Film festival opens with a record number of debut directors", Status.PUBLISHED, 12, None),
    ("Culture", "farhan", "The old city's stepwells get a second life", Status.PUBLISHED, 27, None),
    ("Culture", "divya", "A classical music app finds a young audience", Status.PUBLISHED, 49, None),
    ("Culture", "farhan", "The book fair returns after two years", Status.IN_REVIEW, 2, "comments"),
    ("Culture", "divya", "Street food vendors win heritage recognition", Status.DRAFT, 1, None),
    ("Culture", "farhan", "Regional theatre groups go online", Status.PUBLISHED, 35, None),
    ("Culture", "divya", "A museum of everyday objects", Status.APPROVED, 4, None),
    ("Culture", "farhan", "Folk musicians tour college campuses", Status.SCHEDULED, 3, 1),
    ("Business", "esha", "Small exporters struggle with shipping costs", Status.PUBLISHED, 20, None),
    ("Business", "farhan", "Gold prices rise ahead of the wedding season", Status.PUBLISHED, 1.5, None),
    ("Business", "esha", "Electric two-wheeler sales double in a year", Status.PUBLISHED, 42, None),
    ("Business", "farhan", "Why tomato prices swing so much", Status.IN_REVIEW, 2, "comments"),
    ("Business", "esha", "Co-operative banks get new lending rules", Status.DRAFT, 1, None),
    ("Business", "farhan", "Coffee growers try selling directly to buyers", Status.PUBLISHED, 31, None),
    ("Business", "esha", "Interview: running a family textile business", Status.IN_REVIEW, 3, None),
    ("Business", "farhan", "New freight corridor cuts delivery times", Status.APPROVED, 5, None),
    ("Business", "esha", "Monthly GST collections, explained", Status.DRAFT, 2, None),
    ("Business", "farhan", "Handloom weavers find buyers online", Status.PUBLISHED, 53, None),
    ("Sport", "farhan", "Local cricket league crowns its first champions", Status.PUBLISHED, 25, None),
    ("Sport", "farhan", "City marathon draws runners from twelve states", Status.PUBLISHED, 15, None),
]

COMMENTS = {
    "What the new data protection rules mean for voters": [
        ("asha", "Please add a source for the figures in the third paragraph."),
        ("chirag", "Added the ministry's notification as the source."),
    ],
    "The book fair returns after two years": [
        ("asha", "Good piece. Can we get a quote from one of the publishers?"),
    ],
    "Why tomato prices swing so much": [
        ("bina", "The chart description needs the months spelled out."),
        ("farhan", "Fixed, and added last year's numbers for comparison."),
    ],
}


@contextmanager
def clock(moment):
    """Run the code inside as if it were `moment` (for timestamps and rules)."""
    with mock.patch("django.utils.timezone.now", return_value=moment):
        yield


def body_for(title):
    return (
        title + ".\n\n"
        "This is a demo article written for the Editorial Workflow take-home. "
        "It exists so the dashboard, the article list, search and the timeline have something to show.\n\n"
        "Reporters filed this from the city desk. Editors checked the facts before it moved on."
    )


class Command(BaseCommand):
    help = "Create demo users, sections and articles in an empty database (can only run once)."

    def add_arguments(self, parser):
        parser.add_argument("--password", default=DEFAULT_PASSWORD, help="Password for every demo user.")
        parser.add_argument(
            "--skip-if-exists",
            action="store_true",
            help="Exit quietly (instead of with an error) if the demo data is already there. For build scripts.",
        )

    def handle(self, *args, **options):
        if User.objects.filter(email__endswith=DEMO_DOMAIN).exists():
            message = (
                "Demo data already exists. Timeline entries can never be deleted, so the demo "
                "cannot be removed and created again. Use a fresh database to seed again."
            )
            if options["skip_if_exists"]:
                self.stdout.write(message + " Skipping.")
                return
            raise CommandError(message)

        self.now = timezone.now()
        # All or nothing: if anything fails, no half-built demo is left behind.
        with transaction.atomic():
            self.create_people(options["password"])
            self.create_sections()
            for row in ARTICLES:
                self.create_article(*row)
            self.archive_sport()

        self.stdout.write(self.style.SUCCESS(
            "Created " + str(len(PEOPLE)) + " users, " + str(len(SECTIONS)) + " sections and "
            + str(len(ARTICLES)) + " articles. Log in as asha" + DEMO_DOMAIN + " (editor) or chirag"
            + DEMO_DOMAIN + " (writer)."
        ))

    # --- helpers ------------------------------------------------------------

    def ago(self, days, hours=0):
        return self.now - timedelta(days=days, hours=hours)

    def create_people(self, password):
        self.people = {}
        for key, name, role in PEOPLE:
            self.people[key] = User.objects.create_user(
                email=key + DEMO_DOMAIN, password=password, full_name=name, role=role
            )

    def create_sections(self):
        self.sections = {}
        with clock(self.ago(60)):
            for name, description, owner_key, writer_keys in SECTIONS:
                owner = self.people[owner_key]
                section = Section.objects.create(name=name, description=description, owner=owner)
                for writer_key in writer_keys:
                    SectionAssignment.objects.create(section=section, writer=self.people[writer_key], assigned_by=owner)
                self.sections[name] = section

    def other_editor(self, person):
        """An editor who is not this person (nobody approves their own work)."""
        if person.id == self.people["asha"].id:
            return self.people["bina"]
        return self.people["asha"]

    def create_article(self, section_name, author_key, title, final, days_ago, extra):
        section = self.sections[section_name]
        author = self.people[author_key]
        approver = self.other_editor(author)
        publisher = section.owner
        start = self.ago(days_ago)

        with clock(start):
            article = create_article(author, section, title, body_for(title))
        if final == Status.DRAFT:
            return

        with clock(start + timedelta(hours=2)):
            transition(article, "submit", author)
        if final == Status.IN_REVIEW and extra != "edited_after_approval":
            self.add_comments(article, start + timedelta(hours=3))
            return

        with clock(start + timedelta(hours=5)):
            transition(article, "approve", approver)

        if extra == "edited_after_approval":
            # The author changes the text after approval, so it goes back to review.
            with clock(start + timedelta(hours=7)):
                edit_content(article, author, {"body": body_for(title) + "\n\nUpdated with prices from this week."})
            return
        if final == Status.APPROVED:
            return

        if final == Status.SCHEDULED:
            if extra == "overdue":
                # Scheduled for two hours ago and never published: shows in Alerts.
                publish_at = self.now - timedelta(hours=2)
            else:
                publish_at = self.now + timedelta(days=extra)
            with clock(start + timedelta(days=1)):
                transition(article, "schedule", publisher, scheduled_for=publish_at)
            return

        # Published one day after it was written.
        published_on = start + timedelta(days=1)
        with clock(published_on):
            transition(article, "publish", publisher)

        if extra == "revision":
            self.published_revision(article, author, approver, publisher, published_on)
        if extra == "open_revision":
            with clock(self.ago(1)):
                revision = open_revision(article, author)
                edit_content(revision, author, {"title": title + " (updated)"})
            with clock(self.ago(1) + timedelta(hours=1)):
                transition(revision, "submit", author)

    def published_revision(self, article, author, approver, publisher, published_on):
        """A correction after publishing: the timeline keeps the old text."""
        start = published_on + timedelta(days=9)
        with clock(start):
            revision = open_revision(article, author)
            edit_content(revision, author, {
                "body": article.body.replace("Reporters filed this", "Corrected: the session opens on Monday, not Tuesday. Reporters filed this"),
            })
        with clock(start + timedelta(hours=1)):
            transition(revision, "submit", author)
        with clock(start + timedelta(hours=3)):
            transition(revision, "approve", approver)
        with clock(start + timedelta(hours=4)):
            transition(revision, "publish", publisher)
            add_comment(article, publisher, "Correction published. Thanks for flagging the date.")

    def add_comments(self, article, moment):
        for index, (person_key, message) in enumerate(COMMENTS.get(article.title, [])):
            with clock(moment + timedelta(minutes=30 * index)):
                add_comment(article, self.people[person_key], message)

    def archive_sport(self):
        # Archived at the end, so its articles exist but are hidden by default.
        section = self.sections["Sport"]
        section.is_archived = True
        section.archived_at = self.ago(5)
        section.save(update_fields=["is_archived", "archived_at", "updated_at"])
