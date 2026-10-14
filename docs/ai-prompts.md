# AI prompts

> Tool: Claude, in one ongoing conversation that could read and write my project folder.
> Prompts are shortened versions of what I actually asked. Small follow-up questions are left out.

## Day 1

### 1. Understanding the brief

> Read the assignment files and give me the problem statement and a roadmap to build this project.

**Result:** the 10 goals, the easy-to-miss rule inside each, and a 6-session roadmap. It also flagged three design questions to settle early: how to store revisions, whether Scheduled articles publish themselves, and how a dismissed alert comes back.

> Split the work into phases over 4 days and give me the decisions for each phase.

**Result:** 6 phases over 4 days, with the commits and decisions for each day.

### 2. Choosing the stack

> Use Django REST Framework with React instead of Node.js.

**Result:** a Django REST API, a React (Vite) frontend and PostgreSQL. I chose this over Django templates, which would have been faster, so that all the rules live in the API and can be tested there (decisions.md, Decisions 1 and 2).

### 3. Building Phase 1

The AI built Phase 1 from that choice:
- settings read from environment variables;
- a custom user with email login and Editor/Writer roles;
- JWT login and the `IsEditor` permission;
- all 7 tables with database rules;
- a Postgres trigger that makes the timeline append-only;
- the React login page and protected layout.

I reviewed and tested it part by part on my laptop before committing each part.

**What went wrong:** three trigger tests expected Django's `InternalError`, but the database error arrives as `ProgrammingError`. The tests now expect `DatabaseError`, the parent class of both.

### 4. Documentation

> Make a doc of what we built in Phase 1, with block diagrams and the decisions.

**Result:** diagrams of the architecture, login flow, database and article lifecycle, plus 12 decisions. I used them for decisions.md and architecture.md.

> Make an ER diagram of the database and put it in schema.md.

**Result:** the ER diagram is in schema.md. I first had it in architecture.md, then moved it, because schema.md is the file about the database.

### 5. Pushing Phase 1 only

> Help me push only Phase 1 to GitHub, with the decisions and architecture docs.

**What was tricky:** Phase 2 code had also changed a few Phase 1 files (routes, layout). Those files were restored to their Phase 1 versions and re-tested on their own, and the Phase 2 versions were kept outside the repo until Day 2.

### 6. Running it on my laptop

> I'm new to web development. Guide me step by step to set up and run this project on Windows.

> The database is created. What's next?

> The backend is running but the site can't be reached.

**What went wrong:**
- **`pip install` failed on the Postgres driver** because my Python was 32-bit. I installed 64-bit Python 3.12.
- **Tests found 43 instead of 12**, because leftover Phase 2 test files were in the folder. I removed them from the repo, and they are backed up outside it.
- **The frontend failed with "Cannot find native binding"**, because Node 20.18 was too old for Vite 8. I installed Node 22.
- **"Site can't be reached"** was because the frontend server wasn't started. I ran `npm run dev`.
- **The first `git push` failed** because of a typo in the remote URL. I fixed it with `git remote set-url`.
