# The terminal app

Read this when working on `src/shopper/terminal/cli.py` or `src/shopper/terminal/report_text.py`.

## Keep it simple

The terminal app is a tool for testing and small prototyping. It is not the product: the page
in week 3 is what users see, and this layout will be replaced by it.

- Plain `print` lines and `input`. No colours, tables, column alignment or terminal library.
- No new dependency, no flags beyond `--skip-all`, no retry logic.
- Build what this doc and the task list, and nothing more. Where both are silent, take the
  shortest thing that works and do not design further.
- The detail below fixes words and order so that nobody has to decide them. It is not a call
  for polish.

What does carry over to the page is the fixed wording, which is why every fixed label is a
template in `wording.py` and not a string in the CLI.

## Where the code goes

| Module | Holds |
|---|---|
| `cli.py` | The arguments, the prompts (a question's own lines included) and the printing. Calls the four functions of `graph/` the terminal app uses (`memory_checkpointer` and `build_graph` from `graph.py`, `start_session` and `resume_session` from `sessions.py`), and takes nothing else from them but `ProgressStatus`; it makes each session's id. `run()` takes the agent bundle, `DEFAULT_AGENTS` unless a test passes its own, such as `STUB_AGENTS` |
| `report_text.py` | The report as plain lines: pure functions, one per section, each the text of that section's lines in `report_lines.py`, and one `printed_report(report)` that sets their order. A figure prints as `label: value`; "  " goes before what a lifespan rests on and before "Built from", and "- " before an item of the check list |
| `lines.py` | The lines the API sends, as `Line`s (`docs/adr/0008-api-sends-finished-lines.md`), for a session and a reply: what was understood, each question's source line and the reply's lines. `cli.py` and `report_text.py` print their text (`wording.plain_text`), which leaves out a control such as the `edit` that ends the "Looking for" line (task 3.1.5) |
| `report_lines.py` | The report's lines (task 3.1.4): one `..._lines_of` function per section and `report_lines_of`, every figure of an option a `FigureLine`, its label and its value. It holds the decline and the "From your request" and typical yearly cost lines too, which `lines.py` imports, and imports only `wording.py`, `calc/` and `state.py` |
| `wording.py` | Every fixed label, and `Line` |

Typed input is read through a function passed in, so tests need no terminal. Every number
printed is one `calc/` produced; this code only formats.

Tests: each section is tested on its own lines, and one end-to-end test checks that key lines
are present, not the whole output. A layout change then touches one function and one test.

## Progress

Task 2.5.1. One line as each agent starts, its words from `wording.STARTED`, printed by
`start_session`'s and `resume_session`'s `progress` callback; an agent finishing prints nothing.
The supervisor's line comes first, as the request is read, and is not printed again when it
assembles the report. After the questions, an empty line, then the lines of the TCO, LCA and
second-hand agents (the last two in either order, as they run at once), then the report:

```
Reading your request...
Looking for: frying pan · Budget: €50
Researching what to ask about...

How often will you use it?
...

Finding options and their prices...
Estimating the CO2e of making each option...
Checking for used options...

Lifespan sourced for 0 of 2 options. CO2e to make: not found for 2.
```

## Before the questions

The supervisor's progress line, then the "Looking for" line (`wording.understood`) as soon as
the request is known to run (`start_session`'s `understood` callback), then the brief agent's
progress line while category research runs (when the brief store answers, the questions follow
at once), then any warning, the budget's and the brief agent's alike, then one "From your
request" line per answer the request states, then one line per typical yearly cost of a
consumable (`wording.typical_cost`). There is no line for the scope: it shows through the
caveat and the supervisor's trail entry. A request that does not run, and input that is refused
or a model call that fails, prints the supervisor's progress line and then only its message.

The credits each agent used are logged, one line per agent, on the error stream
(`data_sources.md`, "Rules for every source"); they are not part of the printed output.

## The questions

Above the first question, one line names the keys (`wording.KEYS`). Each
question is shown with its reason and its choices, numbered from 1. Under a question about a
researched decision factor, a source line names the website it came from, and says so when the
manufacturer or a seller is speaking; the usage question has none.

| Typed | Meaning |
|---|---|
| A listed number | That choice |
| `n` | Not sure |
| Enter | Skip this question |
| `skip all` | Skip this question and the rest; answers already given are kept |
| Anything else | The question is asked again, with no limit |

`n` and `skip all` are read without regard to case or surrounding spaces. The end of the input
(piped input that runs out) skips the remaining questions. The `--skip-all` flag asks nothing.

Answers can be piped in from PowerShell, one per line:
`"3","n" | uv run python -m shopper.terminal.cli "I need a new frying pan, budget 50 euro"`.

## The report

Sections, in this order, with an empty line between them. A section with nothing to show
prints nothing, no heading either.

1. The evidence summary line.
2. The caveat.
3. The warnings.
4. The answers the request states, one "From your request" line each, as above the questions;
   then those the reply gave, one "From your reply" line each, a "not sure" included. The
   terminal app sends no reply, so only a report from the API has them.
5. The typical yearly cost of a consumable, one line, as above the questions.
6. One block per option, as labelled lines: name, price (with the size or variant it was quoted
   for and, when it came from a web page, the shipping its offer states and where and when it was
   seen: `wording.price_seen_at`), the link when the option has
   one ("Link: <url>"), the factor values (see "Factor values"), lifespan (marked as a rough estimate when its source is a model estimate
   and the user has not set another, and "(set by you)" when the user set it), what the lifespan rests on (below), the recurring cost
   when it was looked for, cost per year, cost per use, purchases, horizon cost, CO2e (see
   "CO2e"), "Out of stock when the price was seen" and "Sold without a part it needs to work"
   for an option with those marks, and "Over your budget" when `within_budget` is false.
7. The savings lines: one per option that is not the baseline; none when savings are missing
   or zero.
8. The check-before-you-buy list, under the heading "Check before you buy": one line per
   factor, its name and its `why`, grouped under two labels. Under the second label the names
   of the options it concerns are appended. A label with no items is not printed, and an empty
   list prints nothing that reads as "all checked". After the two labels, when any option has a
   price, one line for all of them: "- Confirm the current price: Prices change after the day
   each was seen."
9. The trail, under the heading "Trail", one line per entry: agent, tier and model in brackets
   when it has them, kind, summary, then the reason and the source when present.

**A missing figure keeps its line** and shows its reason from `calc/`. A missing price or
lifespan shows the reason `calc/` gave for the figure it blocks, except that a missing lifespan,
and every figure it blocks, shows "durability evidence could not be read; set a lifespan to see
it" in place of `calc/`'s reason: since task 1.8.3 the evidence read gives every option a
lifespan, so a missing one means the read failed. A lifespan that is not whole years (one read
from months) shows one decimal. An option with no CO2e estimate keeps its CO2e line with the
reason; the `co2e_unavailable` warning says why among the warnings.

The names in front of a figure ("Price", "Cost per year") and the two headings are in `wording.py`
(task 3.1.4). The API sends each name with its figure; the headings are the terminal's, and the
page names its own sections in `web/lib/wording.ts`.

## What a lifespan rests on

Task 1.8.3. Under the lifespan line, one indented line per durability evidence item, labelled
"Warranty", "Wears", "Repairs", "Care" and, for the type-level lifespan, the line in the table
below; each ends with its site and, for a claim of a manufacturer or a seller, the suffix the
question source line uses. A sourced lifespan's own line carries the same suffix. Then the
findings (task 1.8.4, `architecture/option_evidence.md`, "Findings"), tests first and then owner
reports, each ending with its site (its URL is in the trail), and its overall rating when it has one; or the
line for the findings state when there are none. Under a rough estimate with no evidence item
and no findings, "No durability evidence found", in place of the findings line when the reports
were looked up, and followed by "Owner and tester reports not looked up" when they were not.
Then a recurring cost line, only when it was looked for:

```
Lifespan: 10 years (rtings.com)
  Warranty: lifetime (tefal.nl) (the manufacturer states)
  Wears: non-stick coating (consumentenbond.nl)
  Typical for non-stick pans: 2 to 5 years (which.co.uk)
  Test: coating still intact after a year of daily use (rtings.com), overall rating 8.1/10
  Owner report: one owner's handle came loose after about a year (reddit.com)
Recurring cost: €12 a year, replacement filter (site), converted from USD at a fixed rate
```

The labels, the words after them and the words of findings are in `wording.py` (tasks 1.8.3,
1.8.4 and 3.1.4).

## CO2e

Task 1.9.8. The CO2e line shows the range over the horizon with its confidence label, never the
tier number; with no lifespan, the range of making one item. Under it, an indented "Built from:"
line lists the estimate's materials; then, when the option takes less to make over the horizon
than the baseline, one line names the baseline. Factors are never shown. A model estimate's
source is the model: its label says so and the trail names it.

```
CO2e: 12 to 25 kg CO2e to make, over 10 years (AI synthetic estimate)
  Built from: plastic, typical (estimated), 0.6 kg (estimated); stainless steel, recycled, 0.45 kg (estimated)
Against Non-stick pan: About 10 to 40 kg CO2e less to make over 10 years (AI synthetic estimate); for scale, about 100 to 420 km in an average new car in Europe, electric cars included (car figure: EEA, 2025, tailpipe test; real drives emit more)
```

When the model estimated every material, form and mass, the mark follows "Built from" once:

```
  Built from (estimated): stainless steel, typical, 0.72 kg; aluminium, typical, 0.29 kg
```

A published figure or a benchmark names its source after its label, the dataset as words or the
site of a page: "20 to 45 kg CO2e to make, over 10 years (benchmark estimate, pans-dataset, row
12)". The "Against" line names none: its figure comes from two results, each sourced on its own
CO2e line. "CO2e", "Built from" and "Against {baseline}", the words after them, the labels and the
"(estimated)" mark are in `wording.py`; the rounding is `kilograms()` in `calc/display.py`.

## Factor values

Task 1.8.6 (`architecture/option_evidence.md`, "Evidence", "Answers"). After the link line, one
line per factor value of the option, in the order of the decision factors. A value with a source
from the web ends with its site and, for a claim of a manufacturer or a seller, the suffix the
question source line uses:

```
Hob compatibility: works on induction (fonq.nl) (the seller states)
Lid included: could not be confirmed
Care: hand wash only (rtings.com). You said you'd rather avoid this; the lifespan shown assumes it is done.
```

An option removed by an answer has no block: its `excluded` line in the trail is what shows it.
The linked product's mismatch line takes the place of its plain line for that factor:

```
Does not match your answer for Hob compatibility: not suitable for induction (bol.com) (the seller states)
```

Their words are in `wording.py` (`FACTOR_MEETS` and the lines after it; task 1.8.6).

## Wording

The words of the check list, missing figures, prices, savings, the evidence summary, the keys
line and the source lines are in `wording.py`. On the stub agents the evidence summary reads
"Lifespan sourced for 0 of 2 options. CO2e to make: not found for 2."
