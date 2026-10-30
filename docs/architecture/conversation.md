# Conversation

Read this when working on the conversation agent, follow-up questions about a report, reruns
triggered from the chat, report versions, or the chat panel.

- [Purpose](#purpose)
- [When the conversation is open](#when-the-conversation-is-open)
- [Kinds of message](#kinds-of-message)
- [Routing](#routing)
- [What a rerun runs](#what-a-rerun-runs)
- [Report versions](#report-versions)
- [Rules for every answer](#rules-for-every-answer)
- [Data model](#data-model)
- [Limits](#limits)
- [Open questions](#open-questions)

## Purpose

The first pass (parse, interview, analysis, report) is a fixed pipeline, because that is what
makes the numbers trustworthy. After the report, the user can talk to the system: ask why, try a
what-if, add a requirement, or push back on budget. A conversation agent reads each message,
decides what kind of request it is, and hands the work to the specialist agent that owns it.
This is where the agents visibly collaborate on one goal: the user's purchase.

Deterministic where the numbers have to be right; conversational where the user wants control.

## When the conversation is open

- From the moment the first report exists until the session ends.
- Not during the interview: the questions are the conversation at that stage. Not before the
  report: a correction to the request itself is a new session (see `supervisor.md`).
- A request that does not run (declined, `several_products` or `unclear`) has no conversation; it has the decline or rephrase message.

## Kinds of message

| Kind | Example | Handled by | What runs |
|---|---|---|---|
| `explain` | "Why does the steel pan last so much longer?" | Conversation agent | Nothing new: the answer comes from the report, its trail and its sources |
| `what_if` | "What if I only cook twice a week?" | `calc/` | Recalculation with changed assumptions, as the recalculate endpoint does; no agent |
| `refine` | "I don't want to season a pan." | The specialists that own the change | A new stated answer, then the reruns in the table below |
| `negotiate` | "Can you find something under €40?" | The specialists that own the change | A new budget or trade-off, then the reruns below |
| `new_topic` | "Actually, I need a kettle." | Conversation agent | Nothing: offer to start a new session with the text pre-filled |
| `off_topic` | Anything unrelated to this purchase | Conversation agent | Nothing: one friendly line saying what the chat can help with |

`refine` changes what the product must be (a requirement). `negotiate` changes what the user is
willing to trade (budget, new or used, a higher price for a longer life). Both end in a rerun;
the difference is which agents rerun.

## Routing

1. The conversation agent classifies the message into one kind and extracts the change it asks
   for, as structured output: for `what_if` the changed assumption; for `refine` the factor and
   its stated value; for `negotiate` the new budget or preference.
2. **Code dispatches**, not the model. The kind decides which function or agents run. The
   conversation agent never calls another agent directly and never chooses agents freely.
3. If the classification is unsure, the agent asks one clarifying question instead of guessing.
4. The answer to the user is written after the work is done, from its results.

## What a rerun runs

Reruns reuse the session's cache, so research already done is not repeated.

| Change | Reruns |
|---|---|
| Assumption (lifespan, horizon, uses per year) | `calc/` only |
| Requirement (`refine`) | TCO analyzer with the new stated answer, the LCA agent for options it has not seen, the second-hand agent, then `calc/` and assembly |
| Budget (`negotiate`) | Second-hand agent and `calc/`; the TCO analyzer too when no option was within the new budget |
| Preference for used or new (`negotiate`) | Second-hand agent and `calc/` |

A rerun should not re-estimate an option whose CO2e it already has: the LCA agent makes one
large-tier call for every option it is given, with one factor table for all of them (task
1.9.7), so passing it the unchanged options again costs the most expensive call and can give the
same option a different figure in the new version. Keep the earlier results and pass only the
new options; the conversation tasks decide how the new options share the earlier factor table.

## Report versions

- A rerun produces a new report version; it never edits the previous one. Version 1 is the first
  report.
- Each version records the turn that caused it and a "what changed" summary computed in code by
  comparing it with the previous version: options added or removed, and figures that changed.
- The previous versions stay available, so the user can go back.
- A `what_if` recalculation is not a new version; it is the same report with different
  assumptions, as with the sliders.
- A what-if lives only in the browser until the chat tasks decide otherwise:
  `POST /sessions/{id}/recalculate` saves nothing, and the saved report keeps its own
  assumptions.

## Rules for every answer

- **No invented numbers.** An answer may only contain figures that appear in the current report
  version or in a result just returned by `calc/`. Code checks every number in the answer before
  it is shown. If one fails, the answer is regenerated once; if it fails again, a plain answer
  built in code from the report is shown instead.
- **Cite.** Every factual statement points to a source or trail entry in the report. If the
  report does not contain the answer, say so plainly, and offer a `refine` if more research could
  find it.
- **The budget stays a hard constraint.** Negotiation can make the user aware of a trade-off
  ("€60 new lasts 30 years; €45 used is within budget"); it never pushes them over the budget
  they set.
- **Tone and claims.** `product.md` (Tone) and `eu_market.md` (Environmental claims) apply to
  every chat answer. Free text is where generic environmental claims slip in most easily.
- **No personal data** in prompts, answers or logs, as everywhere else.
- **Every turn is in the trail**: the kind, what was dispatched, and the tier and model used.

## Data model

Added to `src/shopper/state.py` with the first conversation task, as frozen models like the
rest.

| Model | Key fields |
|---|---|
| Turn | id, role (`user` or `assistant`), text, kind (for user turns), the sources and trail entries an answer cites, the report version it refers to |
| Report version | number, the turn that caused it (none for version 1), the report, the "what changed" summary |
| Change summary | options added, options removed, and per remaining option the figures that changed (from and to) |

## Limits

Proposed defaults, to keep cost and latency predictable:

- At most 20 turns per session and at most 5 reruns per session. After that, the agent says so
  and offers a new session.
- Classification is small-tier work; writing the answer is medium tier; the large tier is never
  used in the conversation itself (a rerun may still reach LCA tier 3).

## Open questions

Ask before deciding.

- Whether the chat should also be available during the interview, for questions about a question.
- Whether a third pause, after the options are proposed and before the footprint and used
  listings are researched, is worth the extra wait.
- The turn and rerun limits above.
- How a user steers the research. There is no general "stricter" or "more lenient" setting,
  because nobody can say what it changes. "Be more lenient on X" is already a `refine`: that
  factor's answer becomes not sure, so no option is excluded on it. Two further controls are
  not built: a list of source domains the user wants left out for the session, added to the
  excluded domains on a rerun; and counting only findings of one kind (`test` or
  `owner_report`).
