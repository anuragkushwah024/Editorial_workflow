"""
Acting on many articles at once (goal 7): bulk schedule and bulk unpublish.

Each article goes through lifecycle.transition(), exactly like a single
move, so every rule still applies. Each one also runs in its own
transaction (inside transition()), so a rejected article never stops or
undoes the others. The result lists every article: what happened, or why not.
"""

from rest_framework.exceptions import APIException

from .access import visible_articles
from .lifecycle import transition

BULK_ACTIONS = ["schedule", "unpublish"]
MAX_ARTICLES = 100


def run_bulk(user, action, article_ids, scheduled_for=None):
    results = []
    for article_id in article_ids:
        article = visible_articles(user).filter(pk=article_id).first()
        if article is None:
            # Not found and "not yours to see" look the same on purpose.
            results.append({"id": article_id, "title": None, "ok": False, "status": None,
                            "error": "Article not found."})
            continue

        try:
            article = transition(article, action, user, scheduled_for)
        except APIException as error:
            # The lifecycle's own message, e.g. "Only an Approved article can be scheduled."
            results.append({"id": article.id, "title": article.title, "ok": False, "status": article.status,
                            "error": str(error.detail)})
            continue

        results.append({"id": article.id, "title": article.title, "ok": True, "status": article.status,
                        "error": None})

    succeeded = 0
    for result in results:
        if result["ok"]:
            succeeded = succeeded + 1

    return {
        "action": action,
        "succeeded": succeeded,
        "rejected": len(results) - succeeded,
        "results": results,
    }
