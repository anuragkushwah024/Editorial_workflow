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

