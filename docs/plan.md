# Plan

## How I split the work into sessions

Six phases over four days:

| Phase | What | Goals | Day |
|---|---|---|---|
| 1 | Foundation: login, roles, all tables, append-only timeline | 1, 9 (database part) | Day 1 |
| 2 | Sections and writer assignments | 1, 2, 5 | Day 2 |
| 3 | Articles, lifecycle, revisions, timeline, comments | 3, 4, 9 | Day 2 |
| 4 | Article list (search, filters, sorting, pages), bulk actions, CSV | 6, 7 | Day 3 |
| 5 | Dashboard and overdue alerts | 8, 10 | Day 3 |
| 6 | Demo data, deployment, docs, SUBMISSION.md | all | Day 4 |

## The order I built in, and why

The foundation came first because it is the expensive part to change later. Django makes the user model very hard to swap after the first migration, and every feature depends on the tables. I designed all seven tables up front, including the ones for later goals (revisions, alerts), so later phases add features without reshaping the database.

Sections come before articles because an article cannot exist without a section, and a writer cannot create one without being assigned to that section.

## Estimated versus actual time

**Day 1 (Phase 1):**
- Phase 1 was built with AI help on Oct 12, from my prompts (see ai-prompts.md).
- On Oct 13 I reviewed it, re-ran the tests, wrote the decisions, architecture and ER diagram, and split it into commits.
- Time: about 2-3 hours.

**Day 2 (Phase 2):**
- Phase 2 (sections and writer assignments) was built with AI help on Oct 12, right after Phase 1, from my prompt (see ai-prompts.md).
- On Oct 14 I reviewed it, ran all 43 tests, checked it in the browser as an editor and as a writer, and committed it in steps: API, tests, pages.
- Time: about 2 hours.

**Day 2 (Phase 3, steps 1-2):**
- Later on Oct 14 I started Phase 3: the articles API (who can create, see and edit), then the lifecycle (submit, approve, schedule, publish, unpublish, and the edit rules).
- Each step: my prompt, then tests (98 passing), then separate commits for code and tests.
- Time: about 2 hours.
- Left for Day 3: revisions, the timeline and comments API, and the article pages. This pushes Phase 4 a little later than planned.

**Day 3 (Phase 3, steps 3-6):**
- Oct 15: revisions, the timeline and comments API, then the article pages (list, forms, and the article page with lifecycle buttons, revisions and timeline).
- Each step: my prompt, then tests (144 passing), checked in the browser, then committed and pushed before the next step.
- Time: about 3 hours.
- Phase 3 took longer than one day, because the article page needed more frontend work than I expected. Phases 4 and 5 (search, bulk actions, CSV, dashboard, alerts) move to Day 4, and deployment to Day 5.

**Day 3 (Phase 4), afternoon:**
- I had time left on Oct 15, so I did Phase 4 (search, filters, pages, bulk actions, calendar CSV) the same day instead of on Day 4.
- I sent all five Phase 4 prompts as one message, but reviewed and committed it in two rounds: backend with tests (186 passing on my laptop), then the frontend, checked in the browser.
- Time: about 2 hours.
- This wins back most of the delay: Phase 5 (dashboard and alerts) is next, on Day 4, followed by demo data and deployment.

**Day 3 (Phase 5), evening:**
- Still on Oct 15 I built Phase 5: the dashboard and overdue alerts, backend first (217 tests passing), then the pages.
- Time: about 2 hours.
- All 10 goals are now built. Left for Phase 6: demo data, deployment, schema.md, architecture.md and SUBMISSION.md.

## What I cut

- **Discarding an open revision.** If a writer abandons a revision, nobody can open a new one. I would add a "discard" move for Draft revisions next.
- **Comments on a specific revision.** Comments belong to the article as a whole.
- **A date filter on the Articles page.** The dashboard's "Scheduled this week" card opens all Scheduled articles, soonest first.
- **An automatic scheduler.** `publish_due` exists, but nothing runs it on the free plan; overdue alerts cover that gap.
