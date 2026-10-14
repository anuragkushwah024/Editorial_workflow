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
