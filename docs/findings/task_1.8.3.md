# Findings from task 1.8.3: the evidence template and snippets

Run with `scripts/evidence_check.py` (its docstring lists the commands). The runs are in
`.cache/live/check_1_8_3/`, one file per category; the fixtures the tests use are trimmed
copies in `tests/fixtures/tavily/`.

## Design, fixed before the first search

**What runs.** The TCO analyzer as the graph calls it after a skip-all interview, on the live
sources and the real model, with the category's cached brief, so a recurring cost is looked for
exactly when the app would look for one (the kettle and the drill have a factor of kind
`recurring_cost`; the frying pan has none). The first run selects the options with the first
template; the second template reruns only the evidence step on the same options, so both
templates are measured on the same products. The read is the app's own (medium tier, reasoning
in full) and every value passes the app's own checks: this measures what survives, not what the
results hold.

**Templates**, both with the evidence parameters (English, Netherlands boost):

| Label | Search query |
|---|---|
| A | "{product} durability lifespan warranty" |
| B | "{product} review how long does it last" |

**Measures, per category and template.** Options with any durability evidence (a sourced
lifespan, a type-level lifespan, or one of warranty, wear material, repairability, care);
options with a sourced lifespan; options with a recurring cost found, for the kettle and the
drill.

**Decision rule.**

1. The template with more options with any durability evidence, over the three categories.
2. On a tie, more sourced lifespans.
3. On a tie, template A (named first, and the words it holds are the ones the read looks for).

**Full page text** (`data_sources.md`, "Tavily") is switched on for the evidence purpose when the
chosen template gives fewer than one option in three any durability evidence, or no option a
recurring cost in the kettle or the drill. Each template ran once, so a margin of one option is
noise; a choice that rests on it is marked tentative.

**Amended after the first run.** The first run measured only the selected options, and option
research selected 0, 1 and 1 (frying pan, kettle, drill; see "Option research was thin" below):
two products cannot choose a template. The evidence step does not depend on a price, so the
check was widened before any template was compared: both templates run on the first four
candidates of each shortlist, priced or not, plus every selected option. The decision rule is
unchanged. That first run also found two faults, fixed before the widened run: the lifespan
reader did not read numbers in words ("three to five years"), and the read took one owner's
"20+ years old" set as a lifespan of the line, which the prompt now rules out.

## Results

Run on 17 October 2026. Credits are in "Cost" below.

### Snippets: the two templates

Twelve products, four per category, each read once per template. "Evidence" is any durability
evidence that passed the checks; "sourced" a sourced lifespan.

| Category | Products | A: evidence | A: sourced | B: evidence | B: sourced |
|---|---|---|---|---|---|
| Frying pan | Demeyere Atlantis Proline, Le Creuset Toughened Nonstick PRO, Tramontina Professional (10-inch), Kyocera Ceramic Coated | 4 | 3 | 4 | 4 |
| Kettle | Amazon Basics Electric, Bonavita 1.0L Gooseneck, Cuisinart CPK-17P1, Russell Hobbs Structure | 2 | 1 | 1 | 0 |
| Drill | DeWalt DCD801QQ2, Makita GFD02D, Kobalt KXDD 1424A-03, Bosch PSB 1800 | 2 | 0 | 3 | 0 |
| **Total** | 12 | **8** | **4** | **8** | **4** |

**Template A is chosen, tentatively**: the rule ties on both measures (8 and 4 each) and falls
to its third step. B found more review pages, and with them two 30-year lifespans that are doubtful
for the reader: the Demeyere's from a UK shop's buying guide (stated by a seller, so it passes
only because no tester or owner quote competes), and the Le Creuset Toughened Nonstick's from a
review site about the line, high for a non-stick coating. A found more warranty and material
pages.

**Recurring costs: none found** by either template, in the kettle or the drill. The kettle reads
named consumables ("water filters", "descaling agents") but no result gave a price with an
interval in one place; the drill reads named none. By the rule, full page text is switched on
for the evidence purpose (`include_raw_content`, cut to `RAW_CONTENT_MAX_CHARACTERS`).

**Who the evidence is about.** Kettle and drill evidence is thin: 4 of 8 products got none with
either template, and US models (Kobalt at Lowe's, the Cuisinart) dominate the drill and kettle
results. Wear material and care are the kinds that pass most often; a warranty passes only when
the result names the product, and two-year warranties are dropped as the legal guarantee.

### Faults found and fixed during the check

- **Numbers in words.** "your pan should last three to five years" and "a three- to five-year
  lifespan" gave no years; the lifespan reader in `calc/lifespans.py` now reads number words and
  a hyphen before the unit.
- **One unit's age read as a lifespan.** "pots and pans that are 20+ years old" was returned as
  a lifespan of the line; the prompt now names that case as not a lifespan.
- **An estimate of zero.** With no evidence the read answered `estimated_years: 0` in 13 of the 24
  reads of the snippet run, which code raised to the floor of one year, so the drill's options
  showed a lifespan of 1 year. The prompt now asks for at least one year, from how long such a
  product typically lasts when the results say nothing.

### Option research was thin

Not this task's step, but it limits what the evidence step gets. With the shortlist on full
reasoning (as `option_research.md` settled), the runs of this check selected 0, 1 and 1 options
in the first run and 2, 2 and 1 in the widened one (frying pan, kettle, drill). The shortlist
named US models, whose price searches found no euro price; the price name check refused real
euro prices ("Green Pan" against the shops' "GreenPan", English material words against Dutch shop
names), though not for the category's words ("The 10-inch Tramontina Professional Nonstick Fry
Pan" was priced); "Confirm" dropped listing pages (beslist.nl, supersales.nl) and an out-of-stock
offer; and the role-based selection left a priced Demeyere out. Task
1.8.2 measured 1, 3 and 2 with little reasoning, so this is not new; it is in
`left_over_tasks.md` for task 1.10.

### Full page text, on the chosen template

The recheck ran template A with `include_raw_content="text"` on a fresh option search, so its
products differ from the snippet run in part (14 products: the first four candidates of each
shortlist and the selected options).

| Category | Products | Evidence | Sourced lifespan | Recurring cost |
|---|---|---|---|---|
| Frying pan | Staub Enameled Cast Iron, Le Creuset Toughened Nonstick PRO, Kyocera Ceramic Coated, T-fal Initiatives | 4 | 0 | not looked for |
| Kettle | Russell Hobbs Structure, Amazon Basics Electric, OXO Variable Temperature, Cuisinart CPK-17P1, Fellow Stagg EKG | 2 | 1 | 0 of 5 |
| Drill | DeWalt Atomic 20-Volt Max, Bosch PSB 1800, Festool T18+3, DeWALT DCD980L2, DeWalt DCD801QQ2 | 4 | 0 | 0 of 5 |
| **Total** | 14 | **10** | **1** | **0 of 10** |

Most results came back with no full text (`raw_content` empty); the pages that had it were
manuals, review articles and FAQ pages. The estimate floor no longer bites: the reads gave 2 to
20 years, none zero. Full page text stays on: it costs no credit, and the rule asks for it. It
found no recurring cost either.

**Why no recurring cost is found.** Searches made by hand while looking for a result to test
the conversion on (5 credits, not part of the rule): spares shops state the interval ("It is
recommended to change the filter every 6 months") with no price in the snippet, the price sits
on the product page, and running-cost articles give ranges ("between $30 and $60 every 6 to 12
months", in a Facebook post the evidence search now excludes). A price and an interval rarely
stand in one result.

### The recurring cost in dollars, on a recorded reply

No live run found a recurring cost, so the conversion is proved the way the roadmap allows: a
test with a recorded model reply over a real result. Three more searches by hand (air purifier,
shaver heads) found one result that states both: levoit.com's page for the Core 300
replacement filter 2-pack ("Regular price$54.99", "Recommended replacement every 6–8 months").
The app's own evidence search for "Levoit Core 300" (1 credit) did not return that page, so it
is not a live find. The result is kept, trimmed, under the search query that found it
(`tests/fixtures/tavily/air-purifier-evidence-levoit-filter.json`), and the real evidence read
over it is recorded in `tests/fixtures/nebius/evidence-levoit-core-300.json`. Code reads $54.99
as a bare "$" (US dollars, with a trail entry), converts it at 1.1253 per euro to €48.87, takes
half for the 2-pack and 1.5 replacements a year from the long end of "every 6–8 months": €36.65
a year, labelled "converted from USD at a fixed rate" (`test_tco_evidence.py`).

**A fault found while recording.** The read cited that lone result as `result: 0` twice, also
after the prompt said results are numbered from [1]; code refused the cost both times
("it cites no search result that was shown"). The evidence read's schema now bounds `result` at
1 (`ResultNumber` in `agents/tco/models.py`), so a zero fails validation and is asked again; the
third recording cited `result: 1`.

**A domain the search let through.** `config.py` excluded only video, Pinterest and three eBay
domains from the evidence search, where `data_sources.md` excludes social sites, marketplaces and
every eBay domain; ebay.co.uk and a Facebook post came back. The evidence search now excludes
both; the other purposes keep their lists, so their cached searches stay valid.

### The proof: the terminal app on three categories

`uv run python -m shopper.cli --skip-all "<request>"` with usage stated in the request, so cost
per use is filled: "I need a new frying pan, I cook every day", "I need a new kettle, I use it
every day", "I need a cordless drill, I use it a few times a year". Run twice: once before the
review fixes and once on the final code; the second run, below, is the proof.

| Category | Options | Lifespans | Recurring cost |
|---|---|---|---|
| Frying pan | Tramontina Professional Fusion 10-Inch (€86, cost per year €86, per use €0.24), GreenPan Valencia Pro Ceramic Nonstick (€459.90, €153.30, €0.42) | both rough estimates; the GreenPan's with a lifetime warranty, wear material and care under it, the Tramontina's with "No durability evidence found" | not looked for |
| Kettle | Bonavita 1.0L Gooseneck (€57.31, €57.31, €0.16), Cuisinart CPK-17P1 (€234.17, €58.54, €0.16) | rough estimates; the Cuisinart's with a 3-year warranty | "recurring costs not found" |
| Drill | DeWalt DCD801QQ2 (€447.67, €89.53, €22.38), with `one_option_only` | rough estimate with a 3-year warranty, stated by the manufacturer | "recurring costs not found" |

The first run, on the code before the review, gave the one sourced lifespan of the day: the
Tramontina's 3 years from Wirecutter, a tester.

**One-year estimates.** In the final run the read estimated the Tramontina and the Bonavita at 1
year with no evidence, which put the pan's cost per year at its full price. The read still
treated "never add a fact from what you know" as forbidding an estimate. Rule 1 of the prompt now
names the estimate as its one exception, and the schema bounds `estimated_years` at 1. The
evidence step run again on those two products, on their cached searches, gave 3 years for each.

## Cost

**109 Tavily credits** on 17 October 2026 (31 to 140 on the day's ledger; the local ceiling was
raised to 140 for this task, with the developer's agreement): 81 for the template and
full-text checks with their option research, 9 for the searches made by hand while looking for a
dollar cost (the Levoit evidence search included), and 19 for the two rounds of terminal-app
runs. Firecrawl credits and the read's time were not measured.

## The LCA review

The `lca-reviewer` read the code and these runs and asked for five changes, made in this task
and tested offline (not re-run live: the day's credits were used):

- the name check of a lifespan, a warranty and a recurring cost runs on the passage of its quote,
  the title and the line or snippet that holds it, not the whole result (the Demeyere's 30 years
  came from a shop's worked example for a saucepan on a buying guide);
- a word for a material, a finish or a tier ("nonstick", "pro") names no line (the Le Creuset's
  30 years passed on "nonstick"), and the prompt rules out "how long some people keep one", the
  brand in general and a worked example for another product;
- "limited lifetime warranty" stays limited and shows as "limited lifetime";
- "up to N years" is no lifespan whoever states it;
- the typical range shows the kind of product its quote names ("Typical for Non-stick pans")
  when that name stands in the quote, else "this kind of product", never the category, which may
  be wider than the quote (asked for on the second round of the review).

Its other findings are in `left_over_tasks.md` for tasks 1.10 and 3.2.
