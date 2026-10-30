# Findings from task 1.14: the temperature of the extracting reads

Run on 24 October 2026 against Nebius only (`scripts/temperature_check.py`). Each read ran through
the app's own code: the real model, and searches and pages recorded earlier, so no Tavily or
Firecrawl credit was spent. The cost was **662 medium-tier calls**: 630 measured, 27 for a trial
run and 5 to record the replay. That is about 4.3 million input and 0.5 million output tokens,
roughly $1.85 at the prices in `models.md`.

**Result:** none of the three reads gains from a low temperature. All three keep the default:
no temperature is sent, so Nebius uses its own, 1.0, which the model cards recommend
(`docs/findings/task_1.11.md`). `config.py` gets no setting. The page read's real fault was its
prompt, not its temperature. An empty quote dropped 23 of 135 reads, and the trimmed prompt
drops 3.

## Design, decided before spending credits

- **Settings.** The default: no temperature sent. Low: 0, the value the supervisor already sends,
  so a winner would add no new number, and the strongest form of the change. If 0 did not make
  the reads steadier, a value between would not either. If it repeated itself, the findings
  would say so.
- **Reads.** Five per input at each setting.
- **Inputs.** Product-page read: the 27 product pages the live run of task 1.15 fetched that
  day, still in `.cache/live/firecrawl/`, read with the local terms of that run's briefs.
  Brief read: the two template searches of each tuned category (`tests/fixtures/tavily/`).
  Evidence read: the six evidence searches of task 1.15 that found a result. The three with
  none (Inventum, Severin, Powerplus) give the read nothing to extract, only an estimate.
- **What counts.** The outcome as code keeps it. For a page: the item and its price, or the
  reason it is left out. For the brief: the kept factors, as kind and cited URL, since the model
  words a factor's name differently each time. For the evidence: the lifespan, the warranty,
  the other kinds of evidence and the recurring cost. A read "differs" when its outcome is not
  its input's most common one. Also counted: calls cut off at `max_tokens` (finish reason
  `length`), completion tokens, and reads asked again after invalid output.
- **Rule.** Set a temperature in `config.py` only if fewer reads differ at the low setting with
  nothing worse: no cut-off, no repetition, nothing kept that is plainly wrong.

## Counts

| Read | Reads | Differ at default | Differ at 0 | Cut off | Asked again |
|---|---|---|---|---|---|
| Brief | 15 per setting | 4 | 5 | 0 / 0 | 0 / 0 |
| Evidence | 30 per setting | 14 | 11 | 0 / 0 | 0 / 0 |
| Product page, prompt of task 1.13 | 135 per setting | 23 | 24 | 0 / 0 | 0 / 0 |
| Product page, trimmed prompt | 135 per setting | 5 | 8 | 0 / 0 | 0 / 0 |

Completion tokens were alike at both settings. Medians at the default and at 0: brief 1,054 and
862, evidence 1,585 and 1,520, trimmed page read 465 and 454. Maxima stayed far under the limits:
3,675 of 24,000 for the evidence, 3,701 of 16,000 for a page. No read repeated itself until it
was cut off.

**Brief.** Temperature 0 changed one read more. It kept more factors for the drill: 4 to 5 per
read, against 2, 3, 5, 2 and 2 at the default. In the app, a read that keeps fewer than three
runs the follow-up search. Over all three categories it kept 83 factors against 73. That
points the other way, but it rests on one category and five reads, and the count it was
measured on did not improve. Left to task 1.10 to watch (`left_over_tasks.md`).

**Evidence.** Three fewer reads changed at 0, but not in what the read extracts. Of the six
inputs, the extracted fields varied in about as many at both settings: the warranty in 2 at the
default and 1 at 0, the wear material in 2 and 4, the repairability in 1 and 0. The lifespan
estimate, which comes from the model's own knowledge rather than from extraction, varied in 4
inputs at each. At 0 it also gave estimates that are plainly wrong. Five of 30 reads put the WMF
Profi Resist, a stainless-steel pan, and the Einhell Power X-Change drill at **1 year**. No
default read did; the default gave 3 to 5 years.

**Product page.** No gain at 0 with either prompt, and fewer pages kept: 74 of 135 against 81
with the old prompt, 93 against 95 with the trimmed one.

**Repetition.** The script's check for a line written three or more times flagged 0 to 15
calls per run: brief 3 at the default and 0 at 0, evidence 4 and 0, page 9 and 10 with the old
prompt and 15 and 15 with the trimmed one. On inspection these were JSON replies citing the same
quote for several factors or amounts, not runaway text. Neither setting cut off or ballooned a
call, so no repetition showed.

**Identical replies.** At both settings many replies matched an earlier read of the same input
byte for byte: 61 of 135 trimmed page reads at the default against 54 at 0, and 7 of 15 brief
reads against 5. A check with a fake transport confirmed that the low runs sent
`"temperature": 0.0` and the default runs none. So Nebius, or the model's sampling, repeats an
answer whatever the temperature, and the default is already about as repeatable as 0.

## The page read's prompt, trimmed (left-over items of tasks 1.12 and 1.15)

With the prompt of task 1.13, "what the page sells is not quoted from the page" dropped 23 of 135
reads at the default and 27 at 0. These are the drops task 1.15 saw live in 4 of the kettle's 8
reads. There were two causes. In 12 reads every `sells_quote` came back empty, 11 of them for
`the_item` and one for `unclear`: the prompt gave example quotes only for sets, parts and
missing parts. In 11 the model returned no amount at all, though the 12,000 characters each of
those pages shows the read hold 12 to 28 euro signs.

`PAGE_PROMPT` and `PageReading` were cut to the fields code reads: `page_kind`,
`lists_several_products`, `variant`, `stock_quote` and `flags` are gone. Two instructions were
added: list the amounts of the product the title names first, and never leave `sells_quote`
empty, giving the product's name when the page sells the item itself. The amount's own quote
stays, as the anchor of each entry.

Over the same 27 pages at the default:

| | Prompt of task 1.13 | Trimmed |
|---|---|---|
| Reads that differ | 23 | 5 |
| Not quoted | 23 | 3 |
| Kept (the item, or incomplete) | 81 | 95 |

On four pages the most common outcome changed:

- The Midea kettle went from not quoted to the item at €27.99.
- The Makita DHP458Z went from "names no boormachine" to incomplete at €101.18. That is right:
  it is a body sold without a battery.
- The Power X-Change went from not quoted to "names no boormachine". It is still left out, now
  for its name (the compound name of task 1.15).
- The wok went from "names no koekenpan" to "another kind of product". It is still left out.

The three drops left are the Rommelsbacher travel immersion heater (`reisdompelaar`). It is
still read as the item in 1 or 2 of 5 reads, though it is no kettle.

**Replay test.** The braadpan, hapjespan and wok pages of task 1.15, plus the WMF (beslist.nl)
and GreenChef pages recorded again with their text from that day's live cache, were read once
each with the trimmed prompt at the default. The replies are stored with their prompt and input
(`tests/fixtures/nebius/page-read-frying-pan-*.json`). `tests/agents/tco/test_tco_pages.py`
("The recorded page reads of task 1.14, replayed") runs the TCO analyzer on them. It checks
three things. The prompt and the input sent are the ones recorded, so a change asks for a new
recording. The WMF and the GreenChef are kept at their pages' offers, €44.99 and €23.99. The
three other pans are left out as naming no koekenpan. With the old prompt, the WMF was dropped
as not quoted in the trial run. The replay was recorded with the trimmed prompt only, so the old
and the trimmed classification were compared on the 27 pages above, five reads each, rather than
on one recorded reply per page.

## Decided

- The brief read, the product-page read and the evidence read send no temperature. `models.md`
  ("The client") says so and points here.
- The product-page read uses the trimmed prompt.
