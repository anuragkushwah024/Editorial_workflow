"""
Who can see which sections.

Every query that lists or opens sections (and later, articles) goes through
these helpers, so the visibility rule from goal 1 lives in exactly one place:
editors see every section, writers see only sections they are assigned to.
"""

from .models import Section, SectionAssignment


def visible_sections(user):
    """Sections this user is allowed to see, archived ones included.

    Callers decide separately whether to hide archived sections.
    """
    if user.is_editor:
        return Section.objects.all()
    # A subquery (id IN ...) rather than a join on assignments: a join would
    # restrict later Count("assignments") annotations to this writer's own row.
    my_section_ids = SectionAssignment.objects.filter(writer=user).values("section_id")
    return Section.objects.filter(id__in=my_section_ids)


def is_assigned(writer, section):
    """True if this writer is assigned to this section."""
    return SectionAssignment.objects.filter(section=section, writer=writer).exists()
