# Findings from task 1.10: the first end-to-end run

Run on 2026-10-21 with the terminal app, live sources and live models, tracing on (LangSmith
project `true-cost-copilot`, EU region). Answers were piped in, one line per question; each
transcript in `tests/transcripts/` starts with its query, its duration and what was typed. The
credits per agent below are from the error stream.

The first run (below, up to "Order") left task 1.10 not done; its transcripts stayed on the
closed branch `task/1.10-end-to-end-tone`. The rerun of 24 October 2026, after tasks 1.11 to
1.15, is at the end ("The rerun"); its transcripts are the ones in `tests/transcripts/`.

## The five runs

| Transcript | Query | Time | Tavily / Firecrawl credits | Outcome |
|---|---|---|---|---|
| `1_cookware_frying_pan.txt` | I need a new frying pan, budget 50 euro | 254 s | 0 / 0 (all cached) | 1 option, over budget |
| `2_appliance_kettle.txt` | a kettle that boils quickly, around 60 euros | 372 s | 4 / 0 | 0 options |
| `3_tools_drill.txt` | a cordless drill for occasional DIY at home, max 120 euro | 127 s | 7 / 1 | 1 option, brief lost |
| `4_unusual_sewing_machine.txt` | a sewing machine for a beginner, budget 250 euro | 248 s | 17 / 5 | 2 options |
| `5_not_a_product.txt` | I want a gym membership in Utrecht, budget 40 euro a month | 22 s | 0 / 0 | Declined, correct |

## Why the "Done when" line fails

1. **Every product report holds a "Stub:" trail entry.** `second_hand decided: Stub: used
   listings are not searched yet` (`agents/stubs.py`) is the last trail line of runs 1 to 4. The
   second-hand agent is task 2.3, which the deadline reorder put after 1.10, so this part of
   the line cannot hold before 2.3 unless the roadmap changes.
2. **The unusual product is tuned.** A sewing machine is a portable plug-in household appliance,
   which `supervisor.md` scopes `tuned`, so no "not tuned" caveat is right. The query was a poor
   choice; the rerun needs a clearly `general` product (an office chair, a bicycle).
3. **Three of four product reports are wrong**, below.

## What went wrong, run by run

**Frying pan.** Only one option, and it is over budget.
- Oxo Ceramic Professional Non-Stick priced at €183.72 on amazon.nl, kept unconfirmed (Amazon
  publishes no offer data, ADR 0004). A single pan of that line sells far below that, so the
  page is likely a set or another product (left-over item 7).
- GreenPan Stanley Tucci priced at €799 on allesduurzaam.nl, then dropped at "Confirm" as a
  listing page.
- Only two candidates were named, both from US roundups.
- A model-written reason says "The pan size should match..." (item 34).

**Kettle.** No options at all.
- The follow-up shortlist call timed out.
- Four of five candidates found no euro price (US or roundup names: "Amazon Basics Electric",
  "Oxo's Variable Temperature Electric").
- The one priced, the Cuisinart CPK-17P1 at €234.17 on amazon.nl, is likely another product's
  page (item 7), and was then excluded because "1.7-Liter capacity" was judged to fail the
  answer "A few cups" (item 15: the model judges whether a value meets an answer).

**Drill.** One option; the interview was lost.
- **New bug.** The brief's first read kept 8 factors; the follow-up search's read ("Read 24
  search results: 0 cited, 0 factors kept") replaced them, so the brief ended with none and the
  `research_unavailable` warning showed. A follow-up read should add to the first read's
  factors, not replace them.
- Five of six candidates found no euro price (US models: DeWalt Atomic 20-Volt Max, Kobalt).
- The Bosch PSB 1800 at €114.27 on beslist.nl is plausible.

**Sewing machine.** Two options, one resting on a doubtful lifespan.
- Singer Start 1304: "Lifespan: 55 years (walmart.com) (the seller states)" (item 11). With it,
  the cheap machine costs €0.99 a year and drives "Brother innov-is A16 costs €384.67 more than
  Singer Start 1304" (item 19).
- Brother XM2701 priced at €21.39 on a kieskeurig.nl sewing-pattern page (item 7).
- "for a beginner: suitable for beginners (sewingmachinefun.com)" reads oddly as a factor line
  (item 14).
- Singer Heavy Duty 4423 was excluded on "for a beginner" from a bobbinhub.com table quote,
  "Intermediate+, heavy fabrics WIN": a defensible reading.

**Gym membership.** "It can't help with gym membership." Correct; the singular category reads
acceptably here (item 40).

## What held

- The supervisor understood every query: category, budget and scope; the decline was right.
- The interview questions were on topic and sourced. No preachy wording and no generic
  environmental claim appeared in any transcript.
- The cache, the trail, the warnings, the LCA and the report layout all worked; every figure
  printed was computed in `calc/`.

## The pattern: option research loses its candidates

Since task 1.8.3 every live run has given 0 to 3 options per category, and tasks 1.8.3, 1.8.4
and 1.8.7 each patched one step without moving that. The steps run in this order:

1. Discover products in English "best X tested" roundups, mostly US sites.
2. Search a price for each name ("{name} prijs").
3. Have the model read a price from the results.
4. Confirm the price on the shop page.

Each step drops what the step before thought was good: US models have no euro price, a wrong
page gives a wrong price, and shop pages are out of stock or listing pages. Most candidates are
gone before durability is judged.

## Proposal: option research from what is sold here

Grilled since; what was decided, and the measurement's pass rule and credits, are in "Decided"
below. The proposal as first written: turn the order around:

1. Find in-stock, euro-priced products for the category within the budget on Dutch and EU
   shops or comparison sites. Their product pages carry name, price and stock in JSON-LD, which
   code reads.
2. Judge durability only for those: evidence, findings, the user's answers.
3. Keep the roundups as evidence for a product that is already priced, not as the source of
   candidates.

This would remove the wrong-product price pages, the US-only models, the out-of-stock losses
and most of the model's price reading in one step, and move the price into code. The
supervisor, the brief and interview, `calc/`, the LCA and the report are untouched. Most of
group 1 of the left-over items would be answered by the design rather than one by one. ADR 0004
(Firecrawl confirms shop prices) would be revisited.

**Measure first.** For the three tuned categories, search Dutch comparison sites and shops for
in-stock product pages within budget, read them with Firecrawl, and count the usable priced
products: five or more per category argues for the rework, fewer kills it before any design.
Roughly 10 Tavily and 10 Firecrawl credits; no new service.

Kept apart from the rework:
- Loose model judgements (1.7 L against "a few cups", a seller's 55 years) belong to group 2:
  compare amounts in code; drop or cap seller-stated lifespans.
- The drill brief losing its factors is a plain bug.

## Improvement matrix: smaller changes

Changes that are not too hard and need no new service, each tied to what these runs showed. Effort:
**S** is a few lines plus a test, **M** a function or a prompt change with a live check. Impact on
quality (right figures and options), consistency (the same input gives the same result) and recall
(how many good options and factors survive): ●●● high, ●● some, ● little, blank none. Every
item is a proposal, measured on a rerun before it stays.

| # | Change | Where | Seen in | Quality | Consistency | Recall | Effort | Left-over |
|---|---|---|---|---|---|---|---|---|
| 1 | A follow-up read replaces the first only when it cites at least as many factors | `_follow_up`, `agents/brief/agent.py` | Drill: 8 factors to 0 | ●● | ●● | ●●● | S | new (group 3) |
| 2 | Let a follow-up query hold a digit; keep refusing prices and currencies only | `follow_up_fault`, `agents/shared/research.py` | 3 of 4 shortlists discarded their follow-up for a digit | | ● | ●● | S | — |
| 3 | Strip a trailing category word from a candidate's name before its price search | `PRICE_TEMPLATE` use, `agents/tco/price.py` | "Cordless Electric", "Non-Stick" in price queries | | ● | ●● | S | 29 |
| 4 | Add a Dutch discovery template next to the English ones ("beste {category} getest") | `DISCOVERY_TEMPLATES`, `config.py` | US models with no euro price: 4 of 6 kettles, 5 of 6 drills | ● | | ●●● | S | 9 |
| 5 | Ask the shortlist for models sold in the EU, and to leave out US-only lines | `SHORTLIST_PROMPT`, `agents/tco/prompt.py` | Kobalt, DeWalt Atomic 20-Volt, Amazon Basics | ● | ● | ●● | S | 9 |
| 6 | Drop a price far from the other candidates' prices (over 3 times or under a third of their median), as the per-candidate outlier rule already does within one candidate | `calc/prices.py` | GreenPan €799, Brother XM2701 €21.39 | ●●● | ●● | | S | 7 |
| 7 | Rank an Amazon search price last: take it only when no other shop's price was accepted | `chosen_price`, `calc/prices.py` | Oxo €183.72, Cuisinart €234.17, both unconfirmed amazon.nl | ●●● | ● | | S | 7 |
| 8 | A seller's or manufacturer's lifespan is evidence, not the lifespan; or cap it at the type range | `lifespans`, `agents/tco/durability.py` | Singer Start 1304: 55 years from walmart.com | ●●● | ● | | S | 11 |
| 9 | A `fails` on a requirement marks the option instead of removing it; only a compatibility `fails` removes | `agents/tco/answers.py` | Kettle: the only priced option removed on 1.7 L against "A few cups" | ●● | ● | ●●● | S | 13, 15 |
| 10 | Retry a model call once on timeout | `_ask`, `llm.py` (it retries invalid output already) | Kettle: the follow-up shortlist timed out | ● | ●●● | ●● | S | — |
| 11 | A low temperature on the reads that extract (brief, shortlist, price, evidence), as the supervisor has | the read calls; one setting in `config.py` | Factors and prices differ from run to run (items 3, 31, and the LCA's factors) | ● | ●●● | | S | — |
| 12 | Say in the savings line when a lifespan behind it is a rough estimate or a seller's claim | `savings_lines`, `report_text.py`; `wording.py` | "Brother ... costs €384.67 more" on a 55-year seller claim | ●● | | | S | 19 |
| 13 | Refuse "should" and "must" in model-written questions and reasons, as generic claims are refused | `fault_in`, `agents/shared/model_text.py` | "The pan size should match the food type" | ● (tone) | ● | | S | 34 |
| 14 | A factor of the user's own quotes the phrase: "You asked for "for a beginner": suitable for beginners" | `FACTOR_MEETS` use, `report_text.py`; `wording.md` | "for a beginner: suitable for beginners" | ● (tone) | | | S | 14 |
| 15 | Warm the brief and search caches for the demo categories before the demo | a script over `cli.py` | The frying pan run, all cached, was the only one with no failed call | | ●●● | | S | — |
| 16 | Price searches on comparison sites' product pages (beslist.nl, kieskeurig.nl, Tweakers Pricewatch) first | `SEARCH_PURPOSE_PARAMETERS`, `config.py`; a second price template | One priced candidate per category; listing pages dropped at "Confirm" | ●● | ● | ●●● | M | 9 |
| 17 | Compare a stated quantity in code (litres, cm, watts) against the answer, not by the model | `agents/tco/answers.py`, a `calc/` helper | 1.7 L judged against "A few cups" | ●● | ●● | ● | M | 15 |

**A first batch.** Changes 1, 6, 7, 8, 9 and 10, all S, would have changed three of the four
product reports here: the drill keeps its questions, the frying pan and kettle lose their wrong
Amazon prices instead of being priced out, the kettle keeps its option, and the sewing machine
loses its 55 years. Changes 2 to 5 then raise recall before the larger rework is decided. Change
16 is the cheap half of the rework above, and its measurement is the same one.

**What these do not fix.** None of them changes the order of option research, so the count of
priced candidates per category stays the bottleneck; that is what the proposal above is for.

## Decided: option research direction (grill, 22 October 2026)

Grilled on this file, `option_research.md`, `data_sources.md`, `eu_market.md` and ADR 0004, then
reviewed by the panel (product, implementation, data). The work is tasks 1.11 to 1.13 in
`docs/ROADMAP.md`; 1.10 stays open until its reruns. Not settled here: the "Stub:" part of
1.10's "Done when" line, left-over groups 2 to 4, and the matrix rows not named below.

**Direction**

1. **The measurement is a prototype** of the new first step (task 1.12), written with the
   existing tools, cache and fixtures. On a pass it is the rework's first commit, with fixtures
   recorded for every search and page it used.
2. **The pass rule, fixed before credits are spent.** Pass when, in at least 2 of the 3 tuned
   categories, the restricted listing search and product-page reads give at least 5 **buyable
   candidates** (`GLOSSARY.md`) within the budget, from at least 3 distinct brands, each checked
   by hand. Otherwise the rework is killed. Ceiling: 15 Tavily and 35 Firecrawl credits; at the
   ceiling, stop and judge on what was read.
3. **Recorded, not deciding:** buyable candidates per domain; per domain, whether its listing
   pages hold an `ItemList` with URLs and its product pages nested offers or only a `lowPrice`,
   and whether Firecrawl can fetch it; reads per category needed to reach 5; the open control
   search against the restricted one; how often the page classification (item 9) was right;
   how many buyable candidates a roundup names, and how many have at least one quoted hint, and
   whether a durable pick with a quoted hint exists; whether the chosen offer matches the
   variant, whether shipping is stated, and whether foreign sellers appear; the supervisor's
   Dutch term for each category against the hand-written one; credits used. With fewer than 2
   candidates holding a quoted hint in 2 of 3 categories, a durable pick ranked by the model's
   judgement comes back to the developer as a product decision; it does not kill the rework.

**Finding products**

4. **Listing pages give names; product pages give prices.** A comparison site's listing page
   names candidates; its lowest price only skips a product when it is over 3 times the budget
   (the durable pick may be over the budget). Every price shown comes from a product page's
   offer. A product page whose offer has only a `lowPrice` drops its candidate, recorded per
   domain; following its link to the shop is a 1.13 decision, with the data.
5. **Dutch search term.** The supervisor returns the category's Dutch search term, checked like
   any string a model writes, used in search queries only and never shown as the category.
   Hand-written in the prototype; added to the request in 1.13; task 2.3 reuses it.
6. **Domains.** The listing search is restricted to a fixed list of comparison sites
   (beslist.nl, kieskeurig.nl, tweakers.net, klarna.com/nl to start); shops are reached through
   their nested offers. One open control search per category, judged from its result URLs with
   no page reads: a domain giving product pages in 2 or more categories is added, and if the
   open search finds more than the restricted one, the restriction is dropped.
7. **Firecrawl.** Its use widens from 5 to at most 12 reads per analysis, one page per request
   and never a crawl. Task 1.12 may lower that cap, not raise it; ADR 0007 and
   `data_sources.md` record it.
8. **Durability.** The two roundup searches stay: a read attaches cited, quote-checked hints to
   the buyable candidates the roundups name. A lifespan or warranty hint needs the full name
   check, model number included; wear material, repairability and care match at line level, as
   in "Evidence". The durability judgement is the fallback; a pick resting on it alone shows
   "rough estimate", and the judgement is never shown as evidence.

**Identifying the product and its price**

9. **What the page sells.** For each amount the price read answers a closed question: the item
   itself, a set or bundle, a part or accessory, another kind of product, or unclear, with a
   quote code finds in the result. Code keeps only the item itself, or a set when a set is
   asked for (`set_requested` passed to the read); unclear counts as not the item. The linked
   product is never dropped by it. Ships in task 1.11, in the current order.
10. **A stale price is accepted; a wrong product's price never.** An out-of-stock candidate is
    marked, not dropped: it ranks after every in-stock one in each slot, takes a slot only when
    no in-stock candidate is left, is never the baseline and never counts as within the budget.
    The linked product gets the same mark when its page says it is out of stock. "Confirm" is
    no longer a step of its own. Task 1.13.
11. **Wording** (to `wording.md` in 1.13): beside the price "price seen at {shop} via
    {comparison site} on 22 Oct 2026", or "price seen at {shop} on …" when the shop's own page
    gave it; "Prices change" once per report, in the "Confirm the current price" item, which
    then stands for every option; "shipping €4.95" when the offer states it, else "shipping not
    stated".

**Matrix rows**

12. Row 6 ships in 1.11, reworked by the panel: only a low outlier is dropped (under a third of
    the median of the other priced candidates), and only with at least 3 others; a high price is
    left to item 9, since a durable product can cost several times a coated one. Row 1's rule
    (keep the read with more cited items; a tie goes to the second) applies to both follow-up
    reads, the brief's and the shortlist's. Row 10 (retry a model call once on timeout) ships
    in 1.11 too, and so do row 2 (a follow-up query may hold a digit, never a price or
    currency) and row 11 (a low temperature on the extracting reads), all added after the grill;
    row 3 joins the fallback. Row 7 ships only if the rework is killed, with rows
    3, 4, 5 and 16.
    Changed in task 1.11 (`docs/findings/task_1.11.md`): row 6 was dropped by the developer,
    because on the recorded prices it removes real cheap candidates (the Russell Hobbs
    Structure at €40.95); row 10 was already in place (the `openai` client retries a timeout
    once); row 11 moved to task 1.14, since the models' cards recommend temperature 1.0.

**Roadmap and records**

13. Tasks 1.11 (batch), 1.12 (measurement, results in `docs/findings/task_1.12.md`) and 1.13
    (on a pass the rework, on a fail rows 3, 4, 5, 7 and 16) come before the 1.10 reruns.
14. Task 1.13 has at most two sessions; then it falls back to rows 3, 4, 5, 7 and 16 on top of what
    is finished.
15. On a pass, a new ADR 0007, "Option research starts from what is sold here", supersedes the
    step order of ADR 0004. On a fail, a note in `docs/findings/task_1.12.md` says why the rework
    was killed.

## Order

1. Task 1.11, then 1.12, then 1.13 (`docs/ROADMAP.md`).
2. Grill left-over group 2, then groups 3 and 4.
3. Rerun the five 1.10 queries, with an office chair as the unusual product, and settle the
   "Stub:" part of the line with the roadmap.

## The rerun (24 October 2026)

Run with the terminal app on live services and models, tracing on. The three tuned requests are
those of task 1.15 (`tests/test_cli.py`, "OPTIONS"); the unusual product is an office chair
(scope `general`); the request that is not a product is a gym membership. Each run was timed with
PowerShell's `Measure-Command`; credits are from the error stream. The transcripts were made
last, on the final code, and most of what they read was cached by the first runs, so the first
runs' figures are given too.

| Transcript | Typed | First run | Transcript run |
|---|---|---|---|
| `1_cookware_frying_pan.txt` | answers: no coating, every day | 98 s, Tavily 2, Firecrawl 1 | 93 s, Tavily 0, Firecrawl 0 |
| `2_appliance_kettle.txt` | `--skip-all` | 91 s, Tavily 7, Firecrawl 0 | 65 s, 0, 0 |
| `3_tools_cordless_drill.txt` | `--skip-all` | 125 s, Tavily 3 (+3 for the brief), Firecrawl 0 | 123 s, 0, 0 |
| `4_unusual_office_chair.txt` | `--skip-all` | 126 s, Tavily 9, Firecrawl 8 | 73 s, 0, 0 |
| `5_not_a_product_gym_membership.txt` | `--skip-all` | 16 s | 12 s |

In all, about 30 Tavily and 14 Firecrawl credits (two for the drill pages recorded as
fixtures), and four runs of the live supervisor evaluation. The temperature stayed as task
1.14 left it.

**Outcome.** Every product run gives two or three options priced from a product page's offer;
the office chair shows the "not tuned" caveat and the gym membership the decline. No transcript
holds preachy wording or a generic environmental claim, and the only "Stub:" entry is the
second-hand agent's. In the frying pan run, "No coating" excluded the GreenChef, and the Tefal
Renew ON that refilled its slot, each with its quote and site: the first live run of the answer
exclusion and the refill. In two of the drill reruns the LCA check turned down the model's
inputs for two drills ("lithium-ion battery pack points at fixed input 1", with no fixed input
given), so their CO2e showed as not estimated; the transcript's run estimated all three.

**Traces.** 162 model calls of these runs, all finished with `stop`, none above 70% of its
`max_tokens`. Medians: the LCA estimate 12.2 s, the judgement by name 18.8 s, the evidence read
9.7 s, the supervisor 11.0 s (at most 18.8 s), the page read 2.9 s.

### Fixed in this task

1. **"Cordless" stays in the category** (the developer's choice over a requirement): the
   supervisor's rule 3 keeps "cordless", "corded" and "petrol" (`supervisor.md`, "Category").
   Live, "cordless drill" gave the term "accuboormachine", and the Aerotec pneumatic drill, the
   POWXBOX screwdriver and corded drills were left out by the term check. A first, longer
   wording of the rule failed the evaluation's "3d printer" and German tumble dryer cases; the
   short one passed 2 of 3 runs, the third failing on the Dutch e-bike's scope (`general` or
   `tuned`), as `main`'s prompt did not in one run.
2. **Compound local terms** (`names_kind`, `agents/tco/checks.py`): a term stands written apart
   or with a hyphen, inside a longer word, with a shared last part ("klopboor-/schroefmachine")
   and after its first word ("Accu Klopboormachine"). "accuboormachine" now stands in 21 of the
   69 recorded drill names, against 2. A name with only "Schroefmachine" still does not stand.
3. **The shop's plural category is no name**: "Rommelsbacher - Reisdompelaar Type 343 -
   Waterkokers" no longer passes the term check. It was not read live in the rerun.
4. **Colours name no product** (`COLOUR_WORDS`): the Tefal braadpan and So Expert stay apart.
5. **"Ø24 cm" is a size**: the GreenChef lost its "states no size or variant" note live.
6. **A name that says it is bare is incomplete**: the Makita DHP458Z "(Body)" was read as the
   item live; now both bare Makitas are marked and lose their slots to complete drills.
7. **Prompts that name no output key returned empty lists.** The frying pan's phrasing call
   (task 1.15) and every judgement by name in this task's first frying pan run planned their
   own JSON shape and returned `[]` under the schema. `PHRASING_PROMPT`, `JUDGE_NAMES_PROMPT` and
   `JUDGE_PAGES_PROMPT` now name their keys; the frying pan has questions again and the
   judgement by name works (1 unknown of 34). The page judgement's reasons were in Dutch; the
   prompt now asks for English.
8. **Tone and wording**: "should" and "must" refused in model-written factors, questions,
   reasons and care statements; the category quoted in the decline and the two brief warnings
   (`It can't help with "gym membership".`); "CO2e to make" in place of "Footprint" in the
   evidence summary; a savings line resting on a rough estimate says so; a factor of the user's
   own reads `You asked for "boils quickly": …`; a candidate that takes no slot names the step
   that decided it; the no-brand trail reason no longer speaks of "your link" for a listed
   product.

### Judged on the transcripts, not changed

- **Group 1.** No follow-up query held a size or model number. "Recurring costs not found"
   stands on every kettle, and the kettle's filter factor got no yearly cost. The So Expert's
   name states its coating ("Antiaanbaklaag"); one run judged it `unverified`, another `fails`
   on its title. No `ProductGroup` page and no model number one letter short came up.
- **Group 2.** Every lifespan but one was a rough estimate. The one sourced lifespan, the SIHOO
  chair's "3 years (techbits.cc)", is an owner's time of use, not a lifespan: the doubtful sourced
  lifespan of task 1.8.3. A seller's "lifetime" warranty (interfixpro.com) showed for a Makita in
  a first drill run. In one frying pan run the Demeyere Proline 7's page judgement was lost to a
  digit in its reason. No option of the four transcripts got a finding from an owner or a tester.
  The CO2e figures are with the `lca-reviewer` (below).
- **Group 3.** The supervisor's call is 11 s at the median, so a cached run cannot show its
   questions within 12 s. The kettle brief kept stovetop factors (induction hob, copper
   polishing, olive-oil polishing) from kitchenaid.com's page on kettle types. The stated-answers
   call read "occasional DIY at home" as usage in two drill runs, and in one as the answer to
   the tasks question alone (whose factor is named "Voltage and amp hours"), so the usage was
   lost. `STATED_PROMPT` now says a phrase about how often always gives the usage factor its
   frequency, also when it answers another factor; both drill reruns after it stated the usage.
   It read "boils quickly" as a factor of the user's own. The drill's brief kept 6 factors after its
   follow-up. The frying pan's size choices are in inches ("8 inches", copied from a US source),
   though the market is metric.
- **Group 4.** No preachy wording in any transcript. When a refilled slot's candidate also
   fails an answer, no entry says the slot ended empty (frying pan, final run).

**LCA review.** The `lca-reviewer` found "CO2e to make" accurate for every figure tier 3 gives
(cradle to gate) and the transcripts free of generic claims. For later tasks it found the
drill's tier 3 range moving between runs on cached inputs (about 25 to 55 kg against 47 to
100 kg per unit for the GSR 120-LI, with masses about twice the maker's), a stainless kettle
given a plastic kettle's materials, no rough mark on the CO2e over 10 years, and the label to
follow the result's boundary once a published figure can be cradle to grave. The office chairs
fall inside published EPDs (32 to 197 kg per chair). All are in `left_over_tasks.md`.
