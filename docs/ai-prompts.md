# AI prompts

> Tool: Claude, in one ongoing conversation that could read and write my project folder.
> Prompts are shortened versions of what I actually asked; small follow-ups are left out. Under each one I note what I decided or checked myself.

## Day 1: foundation (Phase 1)

### 1. Understanding the brief and planning

> Read the assignment files and give me the problem statement and a roadmap to build this project.

> Split the work into phases over 4 days and give me the decisions for each phase.

**Result:**
- the 10 goals, with the easy-to-miss rule inside each;
- a 6-phase plan over 4 days;
- three design questions to settle early: how to store revisions, whether Scheduled articles publish themselves, and how a dismissed alert comes back.

**What I decided / checked:**
- I set the order: foundation, then sections, then articles, then search and bulk actions, then dashboard and alerts, then deployment. Each phase depends on the one before it: an article needs a section, and a section needs users and roles.
- I re-read the README myself. The brief says about 12 hours over roughly a week and "commit as the work happens", so I planned several small commits per day instead of one per day.

### 2. Choosing the stack

> Use Django REST Framework with React instead of Node.js.

**Result:** a Django REST API, a React (Vite) frontend and PostgreSQL.

**What I decided / checked:**
- **Django over Node.js:** I'm more comfortable in Python, and Django already has login, password hashing, an ORM, migrations and pagination built in. That's less wiring in a 12-hour budget.
- **DRF + React over Django templates:** templates would have been faster, but I wanted every rule to live in the API, so it can be tested without a browser and can't be skipped by calling the API directly.
- **PostgreSQL everywhere, including locally:** the timeline lock (a trigger) and the search I plan for Phase 4 are Postgres features, so testing on SQLite would leave them untested.

### 3. Building Phase 1

The AI built Phase 1 from the stack choice:
- settings read from environment variables;
- a custom user with email login and Editor/Writer roles;
- JWT login and the `IsEditor` permission;
- all 7 tables with database rules;
- a Postgres trigger that makes the timeline append-only;
- the React login page and protected layout.

**What I decided / checked:**
- **Tables designed up front:** all 7, including the ones for later goals (revisions, alerts), so later phases only add features and never reshape the database.
- **Email login needs a custom user model**, and Django makes that very hard to change after the first migration, so it had to be in Phase 1.
- **I reviewed and tested it in three parts before committing each one:**
  - settings and login: `python manage.py test accounts`;
  - models and trigger: `python manage.py test articles`;
  - frontend: in the browser, with a wrong password, the right password, and staying logged in after a refresh.

**What went wrong:** three trigger tests expected Django's `InternalError`, but the database error arrives as `ProgrammingError`. The tests now expect `DatabaseError`, the parent class of both, so they check "the database refused the write" rather than one exact error type.

### 4. Documentation

> Make a doc of what we built in Phase 1, with block diagrams and the decisions.

> Make an ER diagram of the database and put it in schema.md.

**Result:** diagrams of the architecture, login flow, database and lifecycle; 12 decisions; the ER diagram.

**What I decided / checked:**
- I first asked for the ER diagram in architecture.md, then moved it to schema.md, because that file is about the database design.
- I wrote decisions.md in chosen / rejected / why form, with Node.js → Django as my reversed decision.

### 5. Pushing Phase 1 only

> Help me push only Phase 1 to GitHub, with the decisions and architecture docs.

**What I decided / checked:** I wanted Day 1's history to contain only Phase 1. The Phase 2 code had also changed a few shared files (URL routes, layout), so committing them as they were would have pushed a Phase 1 commit that pointed at missing code. I kept the Phase 2 versions outside the repo, restored the Phase 1 versions, re-ran the 12 tests, and only then committed.

### 6. Running it on my laptop

> I'm new to web development. Guide me step by step to set up and run this project on Windows.

> The database is created. What's next?

> The backend is running but the site can't be reached.

**What went wrong and how I fixed it:**
- **`pip install` failed on the Postgres driver.** My Python was 32-bit, and the driver only ships 64-bit builds for Windows. I installed 64-bit Python 3.12.
- **Tests found 43 instead of 12.** Leftover Phase 2 test files were in the folder without their code. I removed them from the repo; they're backed up outside it.
- **The frontend failed with "Cannot find native binding".** Node 20.18 was too old for Vite 8, so I installed Node 22.
- **"Site can't be reached".** The frontend server wasn't started; I ran `npm run dev`.
- **The first `git push` failed.** There was a typo in the remote URL, which I fixed with `git remote set-url`. My first commit had also picked up two extra files; I removed them before pushing. I now run `git status` before every commit.

## Day 2: sections and writer assignments (Phase 2)

### 7. Sections API and pages

> Start Phase 2: sections and writer assignments.

**Result:**
- a sections API: list, create, edit, archive, restore, assign a writer, remove a writer;
- 31 tests;
- a sections list page and a section detail page.

This was built on Oct 12, right after Phase 1, and I reviewed and committed it on Oct 14.

**What I decided / checked:**
- **One helper decides which sections a user can see** (editors: all; writers: only their assigned ones), so the goal 1 rule lives in one place.
- **A writer opening someone else's section gets 404, not 403**, so they can't tell the section exists.
- **No delete, only archive and restore**, because the brief says archiving must keep the data. Writers can't be changed on an archived section until it's restored.
- **Section names are unique ignoring capitals**, so "Tech" and "tech" can't both exist.
- **I committed it in steps after checking each one:**
  - the API;
  - then the tests (43 passing);
  - then the pages, checked in the browser as an editor (create, assign, archive) and as a writer (sees only their section, with no edit buttons).

**What went wrong:** after assigning a writer, the API response still showed the old writer count (0 instead of 1). The section and its count were loaded before the change, so the response used a stale number. The fix reloads the section after every change. A test caught this before it reached the browser.

## Day 2 (continued): articles (Phase 3)

### 8. Articles API

> Start Phase 3, step 1: the articles API. Writers can create articles only in the sections they are assigned to. A writer can edit only their own articles. Editors can see and edit all articles. A writer must not see articles from sections they aren't assigned to. Also add tests.

**Result:** create, list, view and edit for articles, with 25 tests (68 in total).

**What I decided / checked:**
- I set the four access rules myself. The last one means a writer removed from a section loses access to their own articles there too. I kept it, and wrote down the trade-off in Decision 17.
- The author always comes from the login, never from the request (Decision 18).
- I committed the API and the tests separately.

**What went wrong:** my first `git add` failed with "not a git repository", because the terminal was open in my home folder, not the project folder. I now `cd` into the project before running git.

### 9. Article lifecycle

> Phase 3, step 2: the article lifecycle. Put all status changes inside a single central function so that all lifecycle rules reside in one place.
> - Submit: the author moves Draft to In Review. Approve: an editor moves In Review to Approved, but never their own article. Schedule: an editor moves Approved to Scheduled with a future time. Publish now: Approved to Published, publish time = now. Unpublish: Scheduled or Published back to Approved. Writers can't approve, schedule, publish or unpublish.
> - Editing an Approved or Scheduled article sends it back to In Review. A Published article can't be edited directly.
> - Illegal moves are rejected with a clear message. Every status change goes in the timeline with old status, new status and who made it.
> - Tests for every allowed move, the edit rules, and the important illegal moves (self-approval, writers making editor moves, scheduling in the past, skipping steps).

**Result:** `lifecycle.py` with the five moves, the edit rules, and 30 tests (98 in total).

**What I decided / checked:**
- I asked for one central function so the rules can be read in one place (Decision 19).
- The timeline also stores the person's role at that moment, so the history stays correct if their role changes later.
- I committed the lifecycle code and its tests separately.

## Day 3: finishing articles (Phase 3, steps 3-6)

### 10. Revisions

> Phase 3, step 3: revisions. A Published article's content can't be edited directly, so the author (or an editor) opens a revision instead. A revision starts at Draft and goes through the same lifecycle and the same rules as an article. The live article keeps its current text until the revision itself is published; then the revision's title and body replace it. Only one open revision per article at a time. Record "revision opened" and "revision published" in the timeline. Add tests.

**Result:** revisions on top of the existing lifecycle code, with 26 tests (124 in total).

**What I decided / checked:** see Decision 22. The AI pointed out one gap: an abandoned open revision can't be discarded yet, so no new one can be opened. I left it out for now (see plan.md, "What I cut").

**What went wrong:** one test failed at first. The test setup created a Scheduled revision without a publish time, and the database refused it ("Scheduled needs a time", a rule from Phase 1). The rule did its job; the test setup was fixed.

### 11. Timeline and comments API

> Phase 3, step 4: the article timeline and comments. An endpoint that returns the full timeline, oldest first, with who did what and when, and which revision an entry belongs to. Anyone who can see the article can see its timeline; a writer outside the section gets 404. Editors and writers who can see the article can comment; comments are timeline entries, so nobody can edit or delete them. No edit or delete endpoint at all. Empty comments rejected. Add tests.

**Result:** a read-only timeline endpoint and a comments endpoint, with 16 tests (140 in total).

**What I decided / checked:** Decision 23. The tests also try PATCH, PUT and DELETE on the timeline and comments, and posting a fake status change as a comment.

**What went wrong:** the timeline code ended up inside the "Revisions" commit. The files for this step were updated before I had committed step 3.3, so that commit picked up both. The commit was already pushed, so I left the history as it is instead of force-pushing; the timeline tests are in their own commit. Since then I commit and push each step before asking for the next one.

### 12. Article list and forms

> Phase 3, step 5: article pages, part 1. An Articles page with title, section, author, status and last updated. Opening a section shows its articles (add a simple section filter to the API). A New article form where a writer can only pick their assigned sections and an editor any active section. An edit form for title and body. Show the server's error messages. The frontend only hides buttons; the server enforces the rules.

**Result:** the Articles page, the section's article list, new and edit forms, a simple article page, and a `?section=` filter with 4 tests (144 in total).

**What I decided / checked:** Decision 25 for archived sections.

**What went wrong:** my prompt used "editing an article that's under review" as an example of a server error, but my own lifecycle allows editing an In Review article. The real case is editing a Published article, which the server refuses. I also sent the next prompt before pushing this step; the AI checked GitHub, saw it wasn't there, and I committed and pushed first.

### 13. Article page

> Phase 3, step 6: article pages, part 2. An article page with title, body, section, author, status and publish time. Only the lifecycle buttons this user can use right now, with a date and time picker for scheduling. Show the server's message when a move is rejected. For a published article, an "Open revision" button and a revision panel with the same buttons, with the live text above it until the revision is published. The timeline and a comment box at the bottom. I'll test it as a writer and two different editors.

**Result:** the full article page: lifecycle buttons with a short hint when there is nothing to do, the revision panel, and the timeline with comments.

**What I decided / checked:** Decision 24. The test story: a writer drafts and submits; editor 1 approves, tries a past schedule time (refused with the server's message), schedules, unpublishes and publishes; the writer opens a revision; editor 1 approves and publishes it; an editor's own article can only be approved by editor 2.

## Day 3 (continued): finding articles and bulk actions (Phase 4)

### 14. All of Phase 4 in one prompt

I wrote five prompts for Phase 4 (search and filters API, the Articles page, bulk actions API, calendar CSV, bulk actions on the page) and sent them together as one message to save time. I asked for the work to be handed over in two rounds, backend first and then frontend, and I tested and committed each round before the next.

> Phase 4: finding articles and acting on many at once.
> - Search over title and body with PostgreSQL full-text search; filters by section, status and author, plus "my articles"; sorting by last updated, status or publish time in both directions; page numbers with the total count. Everything in the database query, visibility first. Bad input gets a clear error, never a crash.
> - The Articles page: search box, dropdowns, sort, Previous/Next with "Showing 21–40 of 57"; choices kept in the page address; "My articles" for writers.
> - Bulk schedule and unpublish: one endpoint for editors; each article through the same lifecycle function, handled separately; a result for every article; writers get 403; a limit on how many at once. Tests with a mixed batch.
> - Calendar CSV: every Scheduled or Published article the user can see, sorted by publish time, as a dated .csv; titles with commas, quotes or line breaks must not break it.
> - Bulk actions on the page: checkboxes, select all on this page, an action bar, a ✓/✗ result list, and an Export button that sends the login token.

**Result:** `listing.py`, `bulk.py` and `calendar_export.py` with a search index and 42 tests (186 in total), then the new Articles page.

**What I decided / checked:** Decisions 26–29. I ran the full test suite on my own laptop before committing round 1, and checked the page in the browser before committing round 2.

**What went wrong:**
- **A test passed on Linux but failed on my Windows laptop.** The sort test created four articles within a millisecond. Windows' clock is coarser, so several got exactly the same "last updated" time, and the tie-breaker always put the newest id first, even when sorting oldest first. The fix was in both places: the tie-breaker now follows the sort direction, and the test gives each article a clearly different time. There is a new test for the tie case.
- **One search test expected the wrong order.** It assumed "Budget phones" would rank first for "phones", but "Phone review" has the word in its title *and* body, so it ranks higher. The code was right; the test now checks what matters: a body-only match comes after title matches.
- **The CSV downloaded without its dated file name.** The browser hides response headers from another domain, so the page couldn't read the file name. One setting (`CORS_EXPOSE_HEADERS`) fixed it. This was found while testing in the browser; the backend tests couldn't catch it.

## Day 3 (continued): dashboard and alerts (Phase 5)

### 15. Dashboard and alerts

I sent Phase 5 as two messages: the backend (steps 5.1 and 5.2), then the frontend (5.3 and 5.4) after the backend was pushed.

> Phase 5, steps 1-2 (backend): one dashboard endpoint with in review, scheduled this week, published this week and open drafts, a breakdown by status and by section, and published per week for 8 weeks including zeros. Weeks run Monday to Sunday in IST. Only articles the user can see; counted in the database. Tests including Sunday 23:59 vs Monday 00:00 IST.
> Overdue alerts: Scheduled and past its time, for articles and revisions; a list with how late, and a count for the badge. Only editors dismiss, saved for that exact scheduled time, so the alert comes back after a reschedule. Let an editor publish a Scheduled article now, and add a `publish_due` command. Tests for detection, dismiss, the alert coming back, writers can't dismiss, and the command.

> Phase 5, steps 3-4 (frontend): the dashboard page with four number cards, the breakdowns and a simple bar chart without a chart library; clicking a number or a row opens the Articles page with that filter. An Alerts link with a count badge refreshed every minute and after any action; an Alerts page with how late each item is; Publish now and Dismiss for editors only; the server's message if something is refused.

**Result:** `dashboard.py`, `alerts.py` and the `publish_due` command with 31 tests (217 in total), then the dashboard page, the alerts page and the badge.

**What I decided / checked:**
- Decisions 30–33.
- Two choices the AI made where my prompt didn't say, which I kept: the timeline names the section's owning editor when `publish_due` publishes something, and dismissing an alert is not written to the timeline (the brief's list doesn't include it, and the dismissal row records who and when).
- I ran `publish_due --dry-run` once on my own data.

**What went wrong / what I noticed:** the "Scheduled this week" card opens the Articles page filtered to Scheduled, but that page has no date filter, so it shows all scheduled articles, soonest first. I left it and labelled the card honestly rather than adding a date filter this late.

## Day 3 (continued): demo data, deployment and docs (Phase 6)

### 16. Demo data and production settings

I sent Phase 6 steps 1 and 2 as two prompts, and committed each one separately.

> Phase 6, step 1: a command that fills an empty database with demo data: two editors and four writers with one shared password, five sections (one archived), about 40 articles in every status spread over the last 8 weeks, a published revision, an open revision, comments, and one overdue scheduled article. Everything through the same lifecycle functions as the API, so every timeline is real. Add tests.

> Phase 6, step 2: get the project ready to deploy on Supabase, Render and Vercel. All secrets from environment variables, a build script for Render that runs the migrations (and the demo data once), static files, and an example environment file for the backend and the frontend. Nothing secret in the repository.

**Result:** the `seed_demo` command with 12 tests (229 in total), then the production settings, `build.sh` and the `.env.example` files.

**What I decided / checked:**
- Decisions 34–37, and the finished Decision 12.
- Before I deployed, the AI ran `build.sh`, the seed and gunicorn against a fresh database in its own workspace and called the API: the trigger and the search index were created, the chart had bars in all 8 weeks, alerts showed 1, and the app refused to start on "Render" with the development secret key.
- I ran the full test suite on my laptop before committing.

**What went wrong:** after adding logging for production, my test run on the laptop was full of "Forbidden" and "Unauthorized" lines. Nothing was failing; those were the tests' own refused requests being logged. Decision 37 fixed it.

### 17. Deploying

There was no code prompt for this part: I created the Supabase project (Mumbai region), the Render web service and the Vercel project, and set the environment variables, asking the AI step by step when I got stuck.

**Result:**
- Site: https://editorial-workflow-inky.vercel.app
- API: https://editorial-api-1lb1.onrender.com

**What went wrong:**
- **Render failed twice with "bash: build.sh: No such file or directory".** Render runs the build from the top of the repository, and `build.sh` is inside `backend/`. The fix is the service's **Root Directory** setting: `backend`.
  - The first time, I hadn't set it at all.
  - The second time, I had typed `backend/` while a list of folder suggestions was open, and the deploy started before the setting was saved. It used the same commit and the same empty Root Directory, so it failed the same way.
  - After the setting was saved as `backend`, the next deploy's log showed `Running build command 'bash build.sh'` and the service went live.
- **The database was already set up.** The successful deploy's log said `No migrations to apply.` and the seed printed "Demo data already exists ... Skipping." The demo is created in one transaction, so it is either all there or not at all, and after logging in the dashboard matched the demo exactly.
- **CORS.** The site can't call the API until Render lists the Vercel address in `CORS_ALLOWED_ORIGINS`, so that came last, after Vercel gave me the address, followed by another Render deploy.
- **"Not Found" on the API address.** I first opened the Render address in the browser and got Django's "Not Found". That is expected: the API has nothing at its bare address, only under `/api/`. The site people use is the Vercel address.

**What I checked:** logged in as Asha (editor): 38 articles in the four active sections (Sport is archived), a bar in each of the 8 weeks, and 1 overdue alert.

### 18. Schema and architecture docs

> Start Phase 6, step 3: the schema and architecture docs. Fill in docs/schema.md and docs/architecture.md from the actual code, not from memory. schema.md: every table with its fields, the constraints and indexes (including the timeline trigger, the search index and the alert-dismissal unique rule), and why each rule exists. architecture.md: how the pieces connect (React on Vercel → Django API on Render → PostgreSQL on Supabase), where the main rules live (lifecycle.py, access.py, listing.py, bulk.py), how a request flows from button click to database, and the deployment setup. The live site is https://editorial-workflow-inky.vercel.app and the API is https://editorial-api-1lb1.onrender.com. Also add the Phase 6 entries to decisions.md and ai-prompts.md, including the Render root-directory problem and how it was fixed.

**Result:** schema.md filled in (relationships, database rules versus application rules, what I denormalised, what would break first at 100x, and a table of every rule and index with its reason); architecture.md updated for the deployed app, with the rules-by-file table and the "Approve" request path.

**What I decided / checked:** the constraints, indexes and triggers in schema.md were listed from a freshly migrated database, not from the model code. That showed one thing I hadn't planned: two identical indexes on the article's author. I wrote it down in schema.md rather than changing the database this late.

