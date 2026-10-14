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
- Time: about __ hours.
- Left for Day 3: revisions, the timeline and comments API, and the article pages. This pushes Phase 4 a little later than planned.

## What I cut

Nothing yet.
