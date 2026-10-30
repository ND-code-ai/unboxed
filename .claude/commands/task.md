---
description: Work on one roadmap task, using only the docs that task names
argument-hint: "[task number, e.g. 1.4 — empty for the first task in the roadmap]"
---

Work on exactly one task from `docs/ROADMAP.md`, or from `docs/ROADMAP_OPTIONAL.md` when the
task is an optional layer. Wherever this command says the roadmap, it means the file that holds
the task.

Task: $ARGUMENTS

If no task number is given above, use the first task in `docs/ROADMAP.md`. If the given task is not in
the roadmap because it is finished (it is then in `docs/ROADMAP_DONE.md`), or a task it depends
on is still in the roadmap above it, say so and stop.

Work happens on a branch and ends in a pull request, as `docs/building_the_project.md` ("Git")
describes. Never commit task work to `main`.

Follow these steps in order.

1. **Find the task.** Do not read the whole roadmap. In two steps:
   - Search `docs/ROADMAP.md` for the pattern `^- \[|^## |^Goal:` with line numbers. That returns
     one line per task, heading and goal: an outline, not the task texts.
   - From the outline take the line number of this task (the first task when no number was
     given) and of the entry or heading that follows it, and read only the lines between the
     two.

   The week's goal is already in the outline. State the task's number, title and "Done when"
   line back to me in one or two sentences.
2. **Check the left-over items.** Read `left_over_tasks.md` at the repo root. If it has items
   under this task's heading, list them and ask me, for each, whether to include it in this task,
   defer it (to which task) or drop it, and wait for my answer. Included items become part of the
   work and the verification; the "Done when" line is not changed. If there are no items, say so
   in one line and continue.
3. **Load only what it names.** Open the docs on the task's "Read" line, and only the sections
   named in brackets where given. If the task writes code, also open `docs/code_conventions.md`
   (shared principles plus the section for the language in use). Do not open other docs unless
   something in the task cannot be done without them; if so, say which and why.
4. **Prepare the branch.** Switch to `main` and pull. If the working tree is not clean, or an
   earlier task's pull request is still open, stop and tell me. Otherwise create
   `task/<number>-<short-name>`.
5. **Look at the existing code the task touches**, and no more than that.
6. **Ask before starting** if the task depends on an open decision (listed in
   `docs/service_architecture.md` and at the end of `docs/architecture/calculations.md`) or if
   the "Done when" line is ambiguous. Otherwise start without asking.
7. **Do the work.** Stay inside this task. If it writes code, use the `tdd` skill, and read its
   linked `tests.md` and `mocking.md` before the first test. The test points are agreed in
   `docs/code_conventions.md` ("Tests"); do not ask about them. For an unfamiliar or
   fast-changing library or API, ask the `docs-researcher` subagent. Note anything that belongs
   to another task for step 11 and leave it alone.
8. **Review and refactor.** If the task wrote code, use the `code-review` skill with `main` as
   the fixed point, this task's roadmap entry and the docs on its "Read" line as the spec, and
   `CLAUDE.md` and `docs/code_conventions.md` as the standards. Fix the hard violations and the
   spec findings. For each judgement call, refactor only if it stays inside this task's code;
   otherwise note it for step 11. Keep the tests green throughout.
9. **Verify** as `docs/building_the_project.md` ("Verifying a task") describes: show the command
   and output that proves the "Done when" line, and run the tests and the linter. If the task
   changed `web/`, open the pages it touched on the dev server in the browser at 390 px and
   1280 px, check the console for errors and failed requests, and run `impeccable detect` on each
   page's URL at both widths (`--viewport 390x844`, `--viewport 1280x800`); fix layout faults,
   console errors and failing findings before going on.
10. **Get an independent check.** Hand the task number to the `task-verifier` subagent. If the
    task changed CO2e estimates, emission-factor data, lifespan assumptions or the LCA agent, also
    ask the `lca-reviewer` subagent to review that change. On FAIL, PARTIAL or NEEDS CHANGES, fix
    the problems and run the check again. If a problem cannot be fixed inside this task, do not
    tick the box; report it.
11. **Update the left-over items.** In `left_over_tasks.md`: delete the items this task
    resolved, and move or delete the ones I deferred or dropped in step 2. Add anything this task
    leaves open, and anything you noticed for other tasks, under the heading of the task that
    should act on it (`## For task <number>`, created in roadmap order if missing), each ending
    with `(from <this task>)`. Use `## Unassigned` only when no task fits. One or two sentences
    per item, naming the file or model concerned.
12. **Commit.** Correct any doc the change made untrue, tick the task's checkbox, move its
    entry unchanged from `docs/ROADMAP.md` to the end of its week in `docs/ROADMAP_DONE.md`, and
    commit on the branch, including `left_over_tasks.md`, with a message that starts with the task number.
13. **Open the pull request.** Push the branch and run `gh pr create`. Title: the task number and
    title. Body: the "Done when" line, the proof, the verifier's verdict, and anything left open.
    Then watch the checks with `gh pr checks --watch`; if one fails, fix it on the branch, push,
    and watch again.
14. **Report and stop.** Give me the pull request link, what was done, what the proof was, and
    what you added to or removed from `left_over_tasks.md`. Do not merge and do not start
    the next task. Merge only when I say so, with `gh pr merge --squash --delete-branch`, then
    switch back to `main` and pull.

If the "Done when" line cannot be met, do not tick the box and do not weaken the line. Push the
branch so the work is not lost, open the pull request as a draft, explain what blocks it and stop.
