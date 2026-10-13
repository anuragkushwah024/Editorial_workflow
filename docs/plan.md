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
- Time: about 2 hours .

## What I cut

Nothing yet.
