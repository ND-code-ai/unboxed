# Roadmap

Tasks are sized for one working session each. Work top to bottom: the order is the priority
order for the deadline, not the original three weeks. Each task is done on its own branch and
merged through a pull request; tick its box on that branch.

Each task has a "Read" line naming the docs (under `docs/`) to open before starting it, and
nothing more needs loading. Any task that writes code also follows `code_conventions.md`. How to
verify a task is in `building_the_project.md`.

This file holds only the tasks still to do before the submission. The optional layers, for
after it, are in `ROADMAP_OPTIONAL.md`; a task here that calls something "an optional layer"
means a task there. A finished task is moved, ticked and otherwise unchanged, to
`ROADMAP_DONE.md` in the commit that completes it. Task numbers are never reused,
so a number missing here is in that file, or was merged into another task as noted on it.

Each task in this file has a "Prep" line: whether to grill it with its docs
before building, and whether to run `/panel` on the grill's summary. Without a grill, start
with `/task`.

Once 3.5 is done, every later task that changes the app redeploys it, so the public URL always
runs the latest version, until the submission deadline (Fri 30 Oct 2026, 10:00 PT). After it the
submission may not change (Devpost rules, section 5, "Submission Modifications"), and it includes
the hosted app's URL and the public repository: nothing is merged to `main` and nothing is
deployed until the judging period ends (Wed 23 Dec 2026, 12:00 PT). Work goes on in branches whose
pull requests stay open until then.

## Build, in priority order


## Submission

Reserve the last two days for these.

- [ ] **3.8 Demo script and video.** 30 s problem (greenwashing and budgets), 2 min live app
  built around the demo moments that were built, 30 s on how Token Factory and the Nemotron
  models are used, with one line on readiness for Digital Product Passports.
  Prep: no grill.
  Read: `product.md` (Demo moments, Future sources), `eu_market.md`.
  Done when: the video is three minutes or shorter and public on YouTube.
- [ ] **3.9 Devpost submission.** Track (Best Apps and Agents), project description (what, why,
  how), working demo URL, video link, public repository link, and written feedback on Nebius
  Token Factory and the NVIDIA models and tools used.
  The repository must be public with a licence (rules, "Project Requirements"), and a public
  repository shows its whole history, not only `main`'s current files. So, first, before it is
  made public, a check of every branch and every commit (`git log --all`), not a grill; a decision
  is asked only when something turns up:
  - secrets: `.env` or any file with a key or token ever committed, and key-shaped strings in
    the history (Tavily `tvly-`, Firecrawl `fc-`, GitHub `ghp_`, LangSmith `lsv2_`, Nebius and
    Token Factory keys, `Authorization` headers in recorded fixtures under `tests/fixtures/`);
  - saved sessions, caches or logs: `.cache/`, `*.sqlite`, LangSmith exports, and anything with a
    user's typed input or an IP;
  - the private planning notes of the repo's parent folder, or text copied from them (CLAUDE.md);
  - personal details: the e-mail address in commit metadata (GitHub shows it), local paths with a
    user name, and names or addresses in fixtures or findings;
  - the size and kind of the recorded shop pages and search responses in `tests/fixtures/`: they
    are third parties' text, kept as test data; keep them unless one is plainly unsuited.

  Anything found in the history: rotate the key first (a key once pushed is treated as leaked),
  then decide between rewriting the history and publishing a fresh repository with one commit,
  either way before the repository's link goes into the form.
  Then, in order:
  - the testing instructions state the demo's window (30 Nov to 23 Dec 2026, 12:00 PT; task 3.5)
    and that the app runs locally from the README outside it, as the README does;
  - the commit submitted is tagged `submission` and the tag pushed, so the version judged is
    easy to point to after the freeze;
  - submit by about 17:00 in the Netherlands, an hour before the deadline (18:00 there, 10:00
    PT), and after it merge nothing and deploy nothing until 23 Dec 2026, 12:00 PT.
  Prep: no grill; the check above, then the form.
  Read: `product.md`, `eu_market.md`.
  Done when: the check found nothing left to remove, the repository is public with its licence
  shown, and the submission was made before the deadline with every required field filled.
