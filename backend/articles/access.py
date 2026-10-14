"""
Who can see and edit which articles.

Article visibility follows section visibility, so the rule from goal 1 is
still decided in one place (sections/access.py):
  - editors see every article;
  - writers see articles only in active sections they are assigned to,
    including articles written by other writers in those sections.
"""

from rest_framework.permissions import SAFE_METHODS, BasePermission

from sections.access import visible_sections

from .models import Article


def visible_articles(user):
    """Articles this user is allowed to open."""
    if user.is_editor:
        return Article.objects.all()
    my_sections = visible_sections(user).filter(is_archived=False)
    return Article.objects.filter(section__in=my_sections)


class CanEditArticle(BasePermission):
    """Editors can edit any article; a writer can edit only articles they wrote.

    DRF runs this when the view loads the article, before the request body is
    validated, so a writer touching someone else's article always gets 403.
    """

    message = "You can only edit articles you wrote."

    def has_object_permission(self, request, view, article):
        if request.method in SAFE_METHODS:
            return True
        if request.user.is_editor:
            return True
        return article.author_id == request.user.id
