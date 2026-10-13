# Articles, revisions and timeline events are deliberately NOT registered in
# the Django admin. Every change to an article must go through the API so the
# lifecycle rules (articles/services.py) and the timeline are always applied.
# An admin edit form would be a back door around both.
