# Decisions

## Decision 1 — Backend framework

- **Chose:** Django 5.2 with Django REST Framework.
- **Rejected:** Node.js with Express.
- **Why:** Django already ships with login, password hashing, an ORM with migrations, pagination and Postgres full-text search. That covers a large part of goals 1, 6 and 9 without extra libraries. With Express I would have picked and wired a separate package for each of those.
- **Later reversed:** my first plan was Node.js and Express. I switched before writing any code because I am more comfortable in Python and Django has far more built in for a 12-hour budget.

## Decision 2 — Separate React frontend

- **Chose:** a Django REST API plus a React single-page app built with Vite.
- **Rejected:** server-rendered Django templates with a little HTMX.
- **Why:** keeping the API separate makes the server the only place where rules live, and lets me test every rule through the API alone. The cost is two deployments, CORS and token auth. Templates would have saved two or three hours, and I accepted losing that time.

## Decision 3 — JWT instead of session cookies

- **Chose:** JWT access tokens (8 hours) and refresh tokens (7 days) using `djangorestframework-simplejwt`, sent in the `Authorization: Bearer` header.
- **Rejected:** Django's session cookies.
- **Why:** the frontend (Vercel) and the API (Render) are on different domains. Cross-site cookies need `SameSite=None`, CSRF handling and careful CORS settings, which break easily on free hosts. A bearer token works across domains with one header.
- **Trade-off:** the token is kept in `localStorage`, so an XSS bug could read it. I accept that for a demo app that loads no third-party scripts.

## Decision 4 — PostgreSQL everywhere, including local development

- **Chose:** PostgreSQL locally and in production, configured through one `DATABASE_URL`.
- **Rejected:** SQLite for local development.
- **Why:** the most important rules depend on Postgres features: the trigger that makes the timeline append-only, partial unique indexes, and full-text search. Testing on SQLite would leave exactly those rules untested.

## Decision 5 — Custom user model from the first migration

- **Chose:** `User(AbstractUser)` with `username` removed, `email` as the login field, and a `role` field (EDITOR or WRITER).
- **Rejected:** Django's default user plus a separate profile table, or Django groups for roles.
- **Why:** the brief requires email login, and Django makes it very hard to swap the user model after the first migration, so it had to be decided on day one. A single `role` column is simpler than groups when there are exactly two roles.

## Decision 6 — Revisions in their own table

- **Chose:** `Article` always holds the live content. Changes to a published article go into `ArticleRevision` rows, each with its own status. Both share an abstract base class (`PublishableContent`) with the same fields.
- **Rejected:** one table holding every version of an article, with a pointer to the live one.
- **Why:** the article list, search and dashboard only need `Article`, with no joins. Because both models have the same fields, one lifecycle function can move either of them.

## Decision 7 — Published text is copied into the timeline

- **Chose:** whenever something is published, the timeline event's `payload` (JSON) stores the exact title and body that went live.
- **Rejected:** relying only on the revisions table to know old versions.
- **Why:** the scenario's main complaint is that nobody can say what the original article said. The timeline is the one place that can never be edited, so it is the safest place to keep that record.

## Decision 8 — Comments are timeline events

- **Chose:** a comment is an `ArticleEvent` with `event_type = COMMENT`.
- **Rejected:** a separate `Comment` table.
- **Why:** goal 9 says comments are part of the timeline and cannot be edited or deleted. One table means one immutability trigger to maintain, and the timeline is a single ordered query instead of a merge of two tables.

## Decision 9 — Immutability enforced by the database

- **Chose:** a PostgreSQL trigger that rejects every UPDATE, DELETE and TRUNCATE on the events table, plus `save()`/`delete()` guards on the model.
- **Rejected:** simply not exposing edit or delete endpoints.
- **Why:** `QuerySet.update()`, bulk deletes, raw SQL and the Django admin all skip model methods. Only the database sees every write, so only the database can guarantee that "not even editors" can change history. Tests confirm that bulk update and delete are refused.

## Decision 10 — Alert dismissal tied to one specific schedule

- **Chose:** an `AlertDismissal` row keyed on (article, revision, `scheduled_for`).
- **Rejected:** a `dismissed` flag on the article.
- **Why:** a flag would have to be reset on every reschedule, and forgetting that would silently hide alerts. With the scheduled time in the key, a new schedule can never match an old dismissal: the new time must be in the future, while the dismissed one is already in the past. The alert comes back on its own, with no extra code.

## Decision 11 — Articles kept out of the Django admin

- **Chose:** article, revision and event models are not registered in the Django admin.
- **Rejected:** registering them to make debugging easier.
- **Why:** an admin edit form would let anyone with admin access skip the lifecycle rules and the timeline entry. Every article change has to go through the API.

## Decision 12 — Supabase for the database host

- **Chose:** Supabase's free PostgreSQL, connected through its Session pooler URL.
- **Rejected:** Render's free PostgreSQL.
- **Why:** Render's free database expires after a limited period, which could be before the review happens. Supabase's direct connection is IPv6-only and Render's free tier cannot reach it, so the pooler connection string is the one to use.
- **Status:** planned; the database will be created on Supabase when I deploy (Day 4).

## Decision 13 — One place decides who sees which sections

- **Chose:** a single helper, `visible_sections(user)` in `sections/access.py`, used by every section query. Editors get all sections. Writers get only sections whose id is in their assignments (a subquery).
- **Rejected:** writing the filter separately in each view, or filtering writers with a join on the assignments table.
- **Why:** the visibility rule is the core of goal 1, so it should live in exactly one place. A join would also limit the writer count on each section to the current writer's own row, so a writer would always see "1 writer". The subquery avoids that.

## Decision 14 — 404, not 403, for sections a writer can't see

- **Chose:** if a writer opens a section they aren't assigned to, or an archived one, the API answers 404 Not Found.
- **Rejected:** 403 Forbidden.
- **Why:** 403 would confirm that the section exists. Writers should only know about their own sections.

## Decision 15 — Sections are archived, never deleted

- **Chose:** no delete endpoint at all. Archive and restore only. Writers can't be added to or removed from an archived section until it is restored.
- **Rejected:** a normal delete.
- **Why:** the brief says archiving must keep the section's data and articles. Deleting would also break the article history. Blocking writer changes on archived sections keeps archived ones frozen.

## Decision 16 — Section names are unique, ignoring capitals

- **Chose:** the serializer rejects a name that matches an existing one in any case ("tech" vs "Tech"). The database also has a UNIQUE constraint as a backstop.
- **Rejected:** relying only on the database's exact-match UNIQUE rule.
- **Why:** two sections called "Tech" and "tech" would confuse everyone. The database check still catches two requests arriving at the same moment.


## Decision 17 — Article visibility follows section visibility

- **Chose:** a writer sees articles only in active sections they are assigned to, including other writers' articles there. Anything else is a 404. A writer removed from a section also loses access to the articles they wrote in it.
- **Rejected:** letting writers always see their own articles, whatever their assignments.
- **Why:** one rule ("you see what's in your sections") is simpler to enforce and explain than two, and it reuses `visible_sections()` from Decision 13. The cost: goal 5 asks for "one list of every article they have written", and a removed writer's list will now be missing those articles. I accepted that, because removing someone from a section should cut their access to it.

## Decision 18 — The author is always the logged-in user

- **Chose:** the server sets the author to whoever creates the article, and ignores any author or status sent by the browser. When an editor creates an article, the editor is its author.
- **Rejected:** letting an editor pick an author when creating.
- **Why:** the no-self-approval rule depends on knowing who really wrote the piece. If the author could be chosen, an editor could name someone else as author and then approve their own work.

## Decision 19 — All lifecycle rules in one file

- **Chose:** `articles/lifecycle.py` holds a table of the five moves (who, from which status, to which status, error message). One function, `_set_status()`, is the only code that writes a status, and it always writes the timeline entry too. The article row is locked during a move (`select_for_update`).
- **Rejected:** checking the rules separately inside each API endpoint.
- **Why:** the lifecycle is the heart of goal 4. With the rules in one table, I can read the whole lifecycle in one place, and a status can never change without a timeline entry. The lock stops two editors approving or publishing the same article at the same moment.

## Decision 20 — No self-approval, even for editors; 403 versus 400

- **Chose:** the approve move needs an editor who is not the article's author. A wrong person gets 403 ("you can never do this"); a wrong status gets 400 ("not from this status").
- **Rejected:** allowing editors to approve their own articles.
- **Why:** the brief's own story is a piece that ran uncorrected because the only editor who looked at it also wrote it. Splitting 403 and 400 tells the user whether to ask someone else or to wait for the right stage.

## Decision 21 — Editing after approval goes back to review; publishing saves the live text

- **Chose:** editing an Approved or Scheduled article moves it back to In Review and clears its scheduled time. A Published article can't be edited at all (revisions come next). When an article is published, the exact title and body that went live are copied into the timeline entry.
- **Rejected:** allowing small edits after approval without a new review.
- **Why:** otherwise text could change after an editor signed it off. Saving the published text answers the brief's "nobody can say what the original said".

## Decision 22 — Revisions reuse the article lifecycle

- **Chose:** the same code in `lifecycle.py` handles an article and a revision. Revisions go Draft → In Review → Approved → Scheduled/Published with the same rules, including no self-approval (whoever opened the revision can't approve it). Only one open revision per article; the database also enforces this.
- **Rejected:** a separate, simpler flow for revisions, or letting editors change published text directly.
- **Why:** the brief says a revision "starts its own path at Draft", so the rules are the same, and one copy of them can't drift apart. Smaller choices where the brief was silent:
  - the article keeps its original publish time when a revision goes live: a correction is not a new publication;
  - a published revision can't be unpublished, because it is already part of the article; to take the piece down, you unpublish the article;
  - a revision can't go live if the article was unpublished in the meantime.

## Decision 23 — The timeline is written only by the server

- **Chose:** the timeline API is read-only, and comments are added through their own POST endpoint that always stores a COMMENT entry from the logged-in user. There is no edit or delete endpoint for any entry; the database trigger from Phase 1 blocks changes underneath as well.
- **Rejected:** a normal create/update/delete API for comments.
- **Why:** goal 9 says nothing in the timeline can change, not even by editors. If the API never offers a way, a bug in the frontend can't create one either. Status changes store the person's role at that moment; other entries show their current role, which is a small trade-off I accepted.

## Decision 24 — The frontend hides buttons; the server decides

- **Chose:** the article page shows only the buttons the user can use right now (no Approve on your own article, no Edit on a published one), and shows the server's own message when it refuses something. After every action the page reloads the article, revisions and timeline from the server.
- **Rejected:** working out the new state in the browser after each click.
- **Why:** goal 1 says the rules must be enforced on the server, so the frontend's checks are only for a clean screen. Reloading from the server means the page never shows a guess.

## Decision 25 — A section's page shows its articles even when archived

- **Chose:** the articles list hides articles from archived sections by default, but asking for one section (`?section=<id>`) includes them, so an editor who opens an archived section still sees its articles. Writers never see archived sections at all.
- **Rejected:** hiding archived sections' articles everywhere.
- **Why:** the brief says archiving hides a section "without destroying its data or its articles", so an editor must still be able to find them.
