# Assignment 17 — Editorial Workflow

## The scenario

Picture a digital newsroom publishing articles across a handful of sections — Politics, Culture,
Tech, and a few others — staffed by a rotating roster of writers and a small editing desk that has to
sign off before anything goes live. Right now the whole pipeline runs through a shared document and a
messaging channel: a writer pastes a draft into a doc, pings an editor to take a look, and waits for a
reply that may or may not still be relevant by the time the piece is ready to go out.

The result is predictable. A piece runs uncorrected because the only editor who looked at it was also
the person who wrote it. A published piece gets a quiet wording change an hour after it goes live, and
by the time a correction is actually needed nobody can say what the original said. Editors find out
what is supposed to run tomorrow only by scrolling back through the channel, and a piece that was
meant to go out at nine sits unpublished until someone happens to notice.

They want one system: writers draft and submit their work, an editor who did not write a piece signs
off before it goes anywhere, and nothing goes live — or changes after it is live — without leaving a
trace. Anyone should be able to see what is scheduled, what is still waiting on review, and what
already ran without asking around. That is the system you are building.

## What it must do

Everything below is required. Several of the ten spell out exact rules — what happens on an illegal
move, what a bulk action must report back, when a dismissed alert is allowed to reappear — and those
specifics are the actual ask, not just the bold headline in front of them.

1. **Accounts and roles.** People sign in with an email and password, and there are at least two
roles — an editor role and a writer role. Editors create and archive sections, assign writers to them,
and can approve, publish, schedule or unpublish any article, and create or edit any article. Writers
can create articles only in sections they are assigned to, and edit their own articles, but cannot
approve, publish, schedule or unpublish any article, or archive a section, and only see sections they
are assigned to. The difference must be enforced on the server, not just hidden in the interface.

2. **Sections.** Editors create sections with a name, a description, and an owning editor, and can
edit them later. Sections can be archived and restored. Archiving hides a section from the default
views without destroying its data or its articles.

3. **Articles inside sections.** Every article belongs to exactly one section and carries a title, a
body, and an author — the writer who wrote it. A writer creates articles and can edit their own; an
editor can edit any article. Opening a section shows its articles.

4. **An article lifecycle with rules.** An article moves through
*Draft → In Review → Approved → Scheduled → Published*; its writer submits a Draft for review, and
any editor other than the article's own author can then approve it — the author may never approve
their own work. An Approved article can be Scheduled with a future publish time, or published
immediately, which stamps its publish time as now; a Scheduled or Published article can be
unpublished back to Approved. Editing the content of an Approved or Scheduled article sends it back
to In Review. Once Published, an article's content cannot be edited directly — the writer opens a
new revision instead, which starts its own path at Draft and replaces the current content only once
that revision itself reaches Published. Any other move must be rejected by the server with a message
explaining why.

5. **Section assignments.** A section has one owning editor, but any number of writers can be assigned
to it, and only an assigned writer may create articles in that section; a writer can be assigned to
any number of sections. Only an editor can assign or remove a writer from a section. Every writer can
see one list of every section they are assigned to, and one list of every article they have written.

6. **Finding articles.** One list shows articles across every section the viewer can see, with a text
search over title and body, filters for section, status and author, sorting by last updated, status or
publish time, and pagination showing the total number of matches. All of this must happen on the
server — do not load every article into the browser and filter there.

7. **Acting on many articles at once.** Select several articles from the list and either schedule all
of them for the same future publish time or unpublish all of them in one action; because some of those
moves will be illegal for some articles — one still In Review, say — the result must report per
article what succeeded and what was rejected and why, not just fail the whole batch. Separately, export
the editorial calendar — every Scheduled or Published article with its section, author and publish
time — as a CSV file.

8. **A dashboard.** A landing view shows headline numbers — articles in review, articles scheduled to
publish this week, articles published this week, and open drafts. It also breaks articles down by
status and by section, and charts articles published per week over the last eight weeks.

9. **History you cannot rewrite.** Every article has a timeline showing when it was created, every
status change with the old and new status and who made it, every revision opened and whether it was
published, and any comments left on it by an editor or writer. Nothing in this timeline can be edited
or deleted after the fact, including by editors.

10. **Overdue publish alerts.** A Scheduled article whose publish time has passed while it is still not
Published counts as overdue to publish, and appears in an alerts area, with a count badge visible in
the navigation. An editor can dismiss the alert. If the article is unpublished and Scheduled again with
a new publish time that also passes while it is still not Published, the alert returns.

## Stretch ideas (optional)

None of these are required, and none substitute for a goal above. If you finish all ten with time left
over, pick whichever of these sounds most useful and build it:

- A comment thread on specific passages rather than the whole article.
- A visual diff between two revisions of an article.
- A public preview link for an article awaiting approval.
- Word-count and estimated reading-time display.
- A style-guide checklist writers acknowledge before submitting.
- A second required approval for sensitive sections.
- A content calendar view by week or month.
- Freelance payment tracking per published article.
- Cross-section tagging and topic pages.


---

## What we are assessing

A working application is table stakes. Almost every serious candidate will produce something that runs, has a login, and roughly does what was asked. That's the floor, not the differentiator.

What actually separates submissions is the record of thinking behind the app: the decisions you made and why, the trade-offs you weighed, what you built first and what you deliberately left out, and whether you can explain any part of your own system when asked. We are hiring for judgement. The app is the evidence for that judgement, not the deliverable in itself.

We also read the code itself for structure and readability, which counts for a small share of the overall score.

## Time budget

Budget about 12 hours total, spent roughly 2 hours a day across a week.

This is not a race. We are not timing you against other candidates, and submitting early scores nothing extra. Twelve hours is a size guide so you know how much to attempt — pace yourself, stop when you're tired, and spend some of that time thinking and documenting, not only typing code.

## Pick any stack you like

Use any language, any framework, any UI library, any ORM, and any database access approach you want. We have no house stack, and no stack scores better than another — this round is not a test of whether you know particular tools.

Use whatever you are fastest and most confident in. Time spent learning something new to impress us is time not spent on the ten goals above, and it will show.

## Using AI is allowed and encouraged

Use AI tools however you want — to scaffold code, debug a stuck problem, write tests, draft documentation, or anything else that helps you move faster. A few things to know about how we treat it:

- We do not penalise AI use, and we make no attempt to detect it.
- We care about whether you understood, directed and verified the output — not about who or what produced the first draft of it.
- `docs/ai-prompts.md` must contain the prompts you actually used, including the ones that produced bad output and what you changed afterwards. If you used no AI at all, say so here and describe how you worked instead — that is assessed the same way.
- Submitting generated code you cannot explain is the single most common way candidates fail this round.

You are accountable for everything in your submission. If a reviewer points at a piece of code and asks why it's there, or why it works the way it does, "the AI wrote it" is not an answer.

## Use git properly

Publish to a public GitHub repository, and commit incrementally as the work actually happens — after each meaningful step, not in one pass at the end.

A repository whose entire history is a single "initial commit" containing a finished app scores zero on git history, and it colours how we read everything else in your submission, however good the app itself is. Your history is how we see the order you built in, where you got stuck, and how the design changed along the way. If it isn't there, we can't assess it, and we won't assume the best.

## What you must commit

Alongside your code, commit these five files under `docs/`. Your zip includes a stub for each with the questions it needs to answer — fill them in as you go, not from memory at the end.

| File | What it must answer |
|------|----------------------|
| `docs/architecture.md` | What the moving pieces are, how they talk to each other, where each one runs, the request path for one representative user action end to end, and what you decided not to build. |
| `docs/schema.md` | Every table's columns and types, which relationships are one-to-many versus many-to-many, which constraints live in the database versus the application, what you deliberately denormalised, and what would break first at 100x the data. |
| `docs/plan.md` | How you split the work into sessions, what order you built in and why, what you estimated versus what it actually took, and what you cut when you ran short. |
| `docs/decisions.md` | At least five real decisions — what you chose, what you rejected, and why — including at least one you later reversed. |
| `docs/ai-prompts.md` | The prompts you actually used, in order, grouped by what you were trying to do, including at least one that produced something wrong and what you did about it. |

## Host it for free

Deploy the whole thing somewhere reachable by URL, using free tiers only.

One combination that works, if you would rather not decide:

- **Database** — a managed service such as Supabase.
- **Server-side code** — Render.
- **Browser-side code** — Vercel.

Deploy in that order: create the database first, give the server its connection details as environment variables, then point the browser-side part at the server's public URL.

This is one option, not a requirement. Any free host is equally acceptable — everything on a single provider, one virtual machine, a container platform, a static host with serverless functions. The choice earns and loses nothing.

Requirements:

- A working live URL.
- Seeded with enough demo data to show the system doing something, not an empty shell.
- Demo credentials for every role recorded in `SUBMISSION.md`.
- Connection strings, keys and passwords kept in environment variables, never in the repository.
- Free tiers often sleep when idle and can take a minute or more to wake. Note it in `SUBMISSION.md` if yours does, so a slow first load is not read as a broken deployment.
- If you cannot get it hosted, submit anyway and record in `SUBMISSION.md` what you tried and where it broke.

## How to submit

Send us:

- The URL of your public GitHub repository.
- The URL of your live, deployed application.
- Your completed `SUBMISSION.md`, committed to the repository.

That's the whole submission. Nothing else to prepare, no separate form.

## What happens next

If your submission clears the bar, we'll set up a short call. We will ask about specific decisions we can see in your repository and its history — why you modelled something a particular way, what a certain commit was fixing, what you'd change if you kept going.

We're telling you this now because it should change how carefully you document as you go. Write `docs/decisions.md` for a version of yourself who has to explain it three weeks from now.

## Scope

The 10 goals stated in this brief are the cutoff. Meet all 10, solidly, and you have a complete submission.

Stretch ideas are optional. They exist for candidates who finish the 10 with time left and want to keep building — they are never required, and they do not make up for a goal you didn't hit. Doing 8 goals well beats doing 10 goals badly. If time is short, finish fewer goals properly rather than leaving all ten half-done.
