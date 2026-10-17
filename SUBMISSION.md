# Submission

## Links

- **GitHub repository:** https://github.com/anuragkushwah024/Editorial_workflow
- **Live application:** https://editorial-workflow-inky.vercel.app

## Notes for the reviewer

- **The backend sleeps.** It runs on Render's free plan, which stops it after about 15 minutes without requests. The first login after that can take up to a minute; if the page says "Could not reach the server", wait a moment and try again.
- **The demo data is already loaded:** 6 people, 5 sections and 40 articles in every status, with about 8 weeks of history behind them, all created through the same lifecycle code as the app, so every timeline is real.
- **Sport is the archived section.** Editors find it under Sections → Archived, with its two articles still there.
- **"Satellite internet trials begin in hill districts" is the overdue article** behind the alerts badge.
- **The history was generated in mid-October 2026.** If you review later, the newest weeks of the chart will be empty, and the other Scheduled articles (set a few days ahead) will have become overdue too. That is the alert working, not a bug.
- Nothing can be deleted, by design: articles and sections are archived or unpublished, and timeline entries are permanent.
- More detail: [docs/architecture.md](docs/architecture.md), [docs/schema.md](docs/schema.md), [docs/decisions.md](docs/decisions.md), [docs/plan.md](docs/plan.md), [docs/ai-prompts.md](docs/ai-prompts.md).

## Demo credentials

Every account uses the same password: `Demo@2026`

| Role | Email | Password | Sections |
|------|-------|----------|----------|
| Editor | asha@newsroom.demo | Demo@2026 | Owns Politics, Culture and Sport (archived) |
| Editor | bina@newsroom.demo | Demo@2026 | Owns Tech and Business |
| Writer | chirag@newsroom.demo | Demo@2026 | Politics, Tech |
| Writer | divya@newsroom.demo | Demo@2026 | Politics, Culture |
| Writer | esha@newsroom.demo | Demo@2026 | Tech, Business |
| Writer | farhan@newsroom.demo | Demo@2026 | Culture, Business, Sport (archived) |

Editors see every section. To see the no-self-approval rule, log in as Bina and open "Editor's note: how we fact-check election claims": she wrote it, so she has no Approve button, while Asha does.

## Stack

| Layer | What you used | Why |
|-------|---------------|-----|
| Frontend | React 19 with Vite, React Router and axios | A separate single-page app keeps every rule on the server and lets me test the rules through the API alone (Decision 2) |
| Backend | Django 5.2, Django REST Framework, JWT login (simplejwt) | Django has login, password hashing, migrations, pagination and PostgreSQL search built in; tokens work across the two domains without cookie trouble (Decisions 1 and 3) |
| Database | PostgreSQL, locally and in production | The rules that must never break rely on PostgreSQL: the trigger that makes the timeline append-only, partial unique indexes and full-text search (Decisions 4, 9 and 26) |
| Hosting | Vercel (frontend), Render (API), Supabase (database), all free plans | Free and deployed straight from GitHub. Supabase instead of Render's database, because Render's free database expires (Decision 12) |

## Goal checklist

| # | Goal | Status | Notes |
|---|------|--------|-------|
| 1 | Accounts and roles | Done | Email and password login, Editor and Writer roles. Every rule is checked on the server: a writer who types the address of an article in another section gets "not found", and the API refuses moves a writer may not make. Log in as a writer to see the reduced menus. |
| 2 | Sections | Done | Sections page: create and edit with name, description and owning editor; Archive and Restore. Archived sections move to the Archived tab and their articles are kept. There is no delete. |
| 3 | Articles inside sections | Done | Opening a section lists its articles. Writers edit their own articles, editors any. The author is always whoever created the article. |
| 4 | Article lifecycle with rules | Done | The article page shows only the moves the user can make now, and the server refuses everything else with a message. No self-approval, even for editors. Editing an Approved or Scheduled article sends it back to In Review ("Review: three budget laptops for students"). Published articles change only through a revision ("Parliament's monsoon session…" has a published one, "Chip shortage pushes phone prices up" an open one). Not built: discarding an abandoned revision. Also, nothing publishes Scheduled articles by itself on the free hosting: the `publish_due` command exists, and editors can use Publish now from the alerts. |
| 5 | Section assignments | Partial | Editors assign and remove writers on a section's page; only assigned writers can create articles there. Writers see their sections on the Sections page and their own articles under Articles → My articles. Partial because a writer removed from a section, or whose section is archived, also loses sight of the articles they wrote there, so "My articles" is not quite every article they have written (Farhan's two Sport articles are missing). I chose one simple visibility rule (Decision 17). |
| 6 | Finding articles | Done | Articles page: full-text search over title and body, filters for section, status and author, sorting by last updated, status or publish time, and pages of 20 with "Showing 1–20 of N". All done in the database query, starting from what the viewer may see. |
| 7 | Acting on many articles at once | Done | Tick articles on the Articles page (editors only), then Schedule or Unpublish. The result lists every article with ✓ or ✗ and the reason; each article is handled on its own. "Export calendar (CSV)" downloads every Scheduled and Published article with section, author and publish time. |
| 8 | Dashboard | Done | The landing page: in review, scheduled this week, published this week and open drafts; by status; by section; published per week for 8 weeks. Weeks run Monday to Sunday in India time. Clicking a number opens the matching article list; "Scheduled this week" opens all Scheduled articles, soonest first, because the list has no date filter. |
| 9 | History you cannot rewrite | Done | Bottom of every article page: created, edits, every status change with old and new status and who made it, revisions opened and published (with the text it replaced), and comments. There is no edit or delete in the API, and a PostgreSQL trigger refuses any change to the table. Comments belong to the article as a whole, not to one revision. |
| 10 | Overdue publish alerts | Done | "Alerts" in the menu, with a count badge refreshed every minute. Editors can Dismiss or Publish now. A dismissal is tied to the exact scheduled time, so after Unpublish and a new schedule that also passes, the alert comes back by itself. |

Backend tests: 229, covering every rule above (`python manage.py test` in `backend/`).

## How much time did you actually spend?

By my notes in plan.md, Phases 1 to 5 (everything except deployment) took about 14–15 hours, and Phase 6 (demo data, deployment and these documents) about 1.5 hours. That is about 16 hours in total, against my 12-hour estimate.

The article page in Phase 3 took the most time beyond the plan: the lifecycle buttons, the revision panel and the timeline were much more frontend work than I expected. Deployment also took longer than its size suggests, mostly because of one Render setting (ai-prompts.md, entry 17).

## What would you do next, with another 12 hours?

1. **Make Scheduled articles publish themselves.** Run `publish_due` every few minutes, from a Render cron job or a GitHub Actions schedule calling a protected endpoint. Today the alerts catch what didn't go out, but the brief's nine o'clock piece should simply go out.
2. **Close the goal 5 gap:** let writers always see the articles they wrote, read-only, even after leaving a section.
3. **Discard a Draft revision**, so an abandoned revision doesn't block new ones.
4. **Browser tests for the main flows** (Playwright): lifecycle buttons, bulk results, the CSV download. One bug, the CSV losing its file name, was only found by clicking.
5. **A date filter on the Articles page**, so "Scheduled this week" opens exactly that week, and a weekly calendar view.
6. **The scaling fixes from schema.md:** a stored search column, a streaming CSV with a date range, and removing the duplicate author index.
7. **A visual diff between revisions.** The timeline already stores the old and new text, so this is mostly frontend work.

## What are you least happy with in this codebase, and why?

That Scheduled articles don't go live on their own. The scenario's last complaint is a piece meant for nine o'clock that sits unpublished until someone notices, and on the free hosting my app still has that problem: nothing runs `publish_due`. What I built makes the problem visible straight away (the overdue alert and its badge) and quick to fix (Publish now), but it doesn't remove it.

Second, the frontend has no automated tests. All 229 tests are backend tests. That's where the rules live, so I put the testing there, but the pages were only checked by hand, and the one bug that reached the browser (the CSV file name) is exactly the kind of thing a browser test would have caught.
