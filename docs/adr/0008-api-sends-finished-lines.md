---
status: accepted
---

# The API sends the page finished lines

The page words and formats nothing it shows: the API sends every line finished, built in Python
by the same functions the terminal app uses, as a `Line` made of parts. The page lays the parts
out, and fills only the words of its own controls from `web/lib/wording.ts`.

Why: the words of a line were already kept in one place (`wording.py`, tested against
`wording.md`), but most of what makes a line right is the logic around them: which template
applies (an answer's status, the factor's kind, the source's kind, where it was stated) and how
each value is written. A TypeScript copy tested against `wording.md` would test the words and not
that logic, so the terminal and the page could show different figures with every test passing:
`euros()` wrote €0.125 as "€0.12" and JavaScript's `toFixed(2)` writes "€0.13". The results
dashboard would also have needed a port of the 579 lines of `terminal/report_text.py`.

Decided in the grill and panel of task 3.1.2 (26 October 2026); built in task 3.1.5 for the
interview and task 3.1.4 for the report.

## The shape

- A `Line` is a list of parts, each tagged `kind`: `text {text}`, `link {text, url}`,
  `confidence {text, basis}` and `control {key}`. No HTML or Markdown in any text.
- A template in `wording.py` fills into a Line: each placeholder's value is a string or a part,
  so a template is chosen in one place. Warnings, error messages and progress lines stay strings:
  finished sentences with no parts.
- The terminal prints a Line by joining its parts' text and dropping control parts, so a control
  part only ends a line, and a sentence that names a control keeps its name as words. Control
  keys are a closed list, each with its words in `wording.ts`.
- A `confidence` part is a figure's confidence label (`basis` `published`, `benchmark` or
  `estimate`). It always shows its text and is styled neutrally: no colour scale, seal or icon,
  which would read as a certification (`eu_market.md`, "Environmental claims").
- Lines travel beside the data, on each stream event and each view of a session. They are built
  when the API answers and never saved, so a change of wording reaches old sessions too.

## Consequences

- The page shows no numeric field of `Report` or `Recalculation`: a figure arrives as a label and
  a value (task 3.1.4). The page may still act on data, such as filtering on the within-budget
  value.
- A chart formats only its axis tick labels. CO2e is drawn as a band from low to high, never as a
  midpoint, and the series names with their confidence label, and any value the chart shows,
  arrive as Lines.
- Display rounding is decided once, in Python (`architecture/calculations.md`).
- One exception, from task 3.10: the page swaps a few of the trail's terms for plainer words
  (`plainTrail`, `TRAIL_PLAIN_WORDS` in `web/lib/wording.ts`), because changing them in Python needed
  a backend redeploy on the submission day. The terminal keeps the API's words. `left_over_tasks.md`
  moves them back.

## Considered options

- **A TypeScript copy of `wording.py`**, tested against `wording.md` as `tests/test_wording.py`
  tests `wording.py`. It would have kept the API pure data and the layout wholly the page's.
  Rejected for the drift above, and because `code_conventions.md` allows no duplication across
  packages.
- **A field of its own for each part a line needs as a control** (the Edit link, a CO2e label, a
  finding's link), beside plain strings. Rejected: a dozen one-off fields, where four kinds of
  part cover them all.
