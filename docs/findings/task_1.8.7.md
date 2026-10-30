# Findings from task 1.8.7: fewer lost options

The live check of task 1.8.7: `uv run python -m shopper.cli --skip-all "<request>"` on the three
tuned categories, with the requests of task 1.8.3 ("I need a new frying pan, I cook every day",
"I need a new kettle, I use it every day", "I need a cordless drill, I use it a few times a
year"). Run twice on 18 October 2026: once before the review fixes of this task, and once on the
final code; the second run is the proof.

## What was measured

"Done when" asks for three options wherever three priced candidates survive "Confirm". So for
each category: the candidates the shortlist kept, those with an accepted price, those that
survived "Confirm" (confirmed or kept unconfirmed), and the options. A surviving priced
candidate left out of the options would fail the line; fewer than three survivors cannot give
three options.

## The proof: the run on the final code

| Category | Kept | Priced | Survived "Confirm" | Options |
|---|---|---|---|---|
| Frying pan | 5 | 1 | 0 | 0 (`no_options_found`) |
| Kettle | 5 | 1 | 1 | 1 (`one_option_only`) |
| Drill | 6 | 3 | 1 | 1 (`one_option_only`) |

The line holds: no surviving priced candidate was left out, and each slot left empty says "no
priced candidate is left". It holds thinly. No category had three survivors, in this run or the
first, so three options were never possible, and this run gave fewer than the first: the
shortlist call reasons afresh on every run (its searches came from the cache), and named
candidates whose price searches found less.

- **Frying pan.** Only the Demeyere Atlantis Proline was priced: €218 from a klarna.com category
  page (`/cl/`), dropped at "Confirm" as holding no product offer, with no other accepted price.
  The Fissler, Staub, Le Creuset and M&S found no accepted euro price.
- **Kettle.** The Cuisinart CPK-17P1 was dropped at a beslist.nl listing and kept at its next
  price, €234.17 at amazon.nl, unconfirmed: the one option. Without the next price the kettle
  would have had none.
- **Drill.** The DeWalt DCD801QQ2 (amazon.com.be, unconfirmed) is the option. The Bosch PSB 1800
  was `Discontinued` at gamma.nl, and the Festool T18+3 at €507.51 came from a beslist.be
  category page; neither had another accepted price.

**Judgements in this run.** 16 candidates: 8 `long`, 8 `medium`, none `short` or `unknown`, every
reason passing the check. One reason praised ("traditional nonstick coating with excellent
durability in abrasive tests", the Le Creuset); the check on model text finds digits, currency
and generic environmental terms, not praise (`left_over_tasks.md`, 1.10). Between the runs the
same product moved by one step (the Demeyere `unknown` then `medium`, the Russell Hobbs `short`
then `medium`), so the judgement is a coarse tie-break, as intended, and not a measure.

## The first run, before the review fixes

| Category | Kept | Priced | Survived "Confirm" | Options |
|---|---|---|---|---|
| Frying pan | 5 | 2 | 1 | 1 |
| Kettle | 6 | 3 | 2 | 2 |
| Drill | 4 | 2 | 1 | 1 |

Every surviving priced candidate became an option. No category had three survivors, so the
fill of an empty slot never ran live; it is shown offline (`tests/agents/tco/test_tco_selection.py`,
on pools rebuilt from the trails of task 1.8.3).

**The next price ran live three times:**

- The Demeyere Atlantis Proline (frying pan), dropped at bestsale-shop.se (a brand-filtered
  category page), tried €299 at bestsale.be, another listing, and stayed dropped: "its next price
  was tried already".
- The Cuisinart CPK-17P1 (kettle), dropped at a beslist.nl listing, took its next price, €234.17
  at amazon.nl, kept unconfirmed.
- The Fellow Stagg EKG (kettle), dropped at blommers.coffee (no JSON-LD offer), tried €159 at
  klarna.com, whose page gave €178.96 in stock, sold by Galaxus: confirmed. Without these two
  next prices the kettle would have had no option at all.

The Russell Hobbs Structure (a beslist.nl listing) and the Bosch PSB 1800 (gamma.nl,
`Discontinued`) had no other accepted price.

**The durability judgement.** 15 candidates were judged: 7 `long`, 2 `medium`, 4 `short`, 2
`unknown`. One reason failed the check: the Demeyere's held a digit (most likely a steel grade
such as "18/10"), so it counted as `unknown` (`left_over_tasks.md`, 1.10). The reasons named a
make each time ("stainless steel body, concealed heating element", "brushed motor with carbon
brushes that wear out"); none gave years or praise. Four kettles were judged `long` on the same
"stainless steel" reason, so the judgement separates a coated pan from a steel one better than
one steel kettle from another.

## What limits the count now

Not selection: in both runs no priced candidate that survived "Confirm" was left out. The
candidates are lost before it, as in task 1.8.3: US models with no euro price (Kobalt, Secura,
Amazon Basics, Titan), price reads whose results list several products (Fissler, Staub), and
shop results that are listings, dropped at "Confirm" with no second shop in the same read. Those
are the two ways to widen the search that `left_over_tasks.md` keeps for task 1.10.

## Cost

**7 Tavily credits** on 18 October 2026: 4 for the first run and 3 for the second. The
discovery, brief and most price searches were still in the cache from task 1.8.3, so the 20
credits the roadmap estimated were not needed; only follow-up and new price searches were paid.
**2 Firecrawl credits** (the bestsale pages of the first frying-pan run); every other price page
was still in the day-long page cache from task 1.8.3. Time was not measured.
