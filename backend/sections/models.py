from django.conf import settings
from django.db import models


class Section(models.Model):
    """A newsroom section such as Politics, Culture or Tech.

    Archiving is a soft delete: the row and all of its articles stay in the
    database, the section is just hidden from default views.
    """

    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True)
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="owned_sections",
    )
    writers = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        through="SectionAssignment",
        through_fields=("section", "writer"),
        related_name="assigned_sections",
        blank=True,
    )
    is_archived = models.BooleanField(default=False)
    archived_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class SectionAssignment(models.Model):
    """Many-to-many link between writers and sections.

    An explicit model (instead of a plain ManyToManyField) so we can record
    who made the assignment and when.
    """

    section = models.ForeignKey(Section, on_delete=models.CASCADE, related_name="assignments")
    writer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="section_assignments",
    )
    assigned_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="+",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["section", "writer"], name="unique_writer_per_section"),
        ]

    def __str__(self):
        return str(self.writer) + " -> " + str(self.section)
