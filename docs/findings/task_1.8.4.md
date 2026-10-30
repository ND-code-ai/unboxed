# Findings from task 1.8.4: the findings template, full page text and reasoning

Run with `scripts/findings_check.py` (its docstring lists the commands). The searches and reads
are in `.cache/live/check_1_8_4/`; the fixtures the tests and the terminal app use are trimmed
copies in `tests/fixtures/tavily/` and `tests/fixtures/nebius/`.

## Design, fixed before the first search

**Products.** Three per tuned category, from the products whose price searches are recorded
(`tests/fixtures/tavily/*-price-*.json`): with the fixture twin these are the only product
options option research can produce, so they are the ones the findings fixtures must cover.
Each is given the brand of its name.

| Category | Products |
|---|---|
| Frying pan | Demeyere Atlantis, GreenPan Valencia Pro, Tramontina Professional |
| Kettle | Fellow Corvo EKG, Hario Buono, Russell Hobbs Structure |
| Drill | DeWalt DCD801QQ2, Makita GFD02D, Ryobi R18PD3-215GZ |

**Templates**, both with the findings parameters (English, no country, video, Pinterest,
marketplaces and `SHOP_DOMAINS` excluded):

| Label | Search query |
|---|---|
| A | "{product} long term review durability" |
| B | "{product} owner review problems" |

Each search is made once, asking for full page text (`include_raw_content`, no extra credit),
so the snippets and the full text are compared on the same results: 2 templates by 9 products,
18 credits.

**Reads.** The app's own findings read and checks (`agents/tco/findings.py`), medium tier, in
three stages, each on the stored searches:

1. both templates, snippets only, little reasoning (18 reads): chooses the template;
2. the chosen template with full page text, little reasoning (9 reads): chooses the text;
3. the chosen template and text with full reasoning (9 reads): chooses the reasoning.

**Measures**, per template, text and reasoning: the products with at least one finding checked
by hand as correct (the right product, the right kind, a summary faithful to its quote, about
durability); the findings kept and the correct ones among them; the findings dropped per cause
(quote, name, overlap, `model_text`, kind, other); and, per template, how many kept findings
came from EU or Dutch sites.

**Decision rule.**

1. Template: the one with more products with a correct finding over the three categories; on a
   tie, more correct findings; on a tie, A (named first).
2. Full page text is taken only when it gives more products with a correct finding, or, on a
   tie, more correct findings, than snippets on the chosen template. Otherwise snippets.
3. Full reasoning is taken by the same rule against little reasoning.

Each read runs once, so a margin of one product is noise; a choice that rests on it is marked
tentative.

**After the choice.** The other nine recorded products are searched once with the chosen
template and read with the chosen settings (9 credits), so every product option a fixture run
can produce has its findings search recorded; the replies of the chosen settings are recorded
too.

## Results

Run on 18 October 2026 on the developer's machine (the cloud session's network policy refused
Tavily and Nebius). 18 Tavily credits. All eight combinations of template, text and reasoning
were read at once, to save round trips; the choice still follows the staged rule above, on the
same stored searches.

### Checked by hand

A kept finding counts as correct when it is about the right product (its line is enough, as the
name check allows), has the right kind, a summary that adds nothing to its quote, and reports
how the product held up. Kept findings that failed the hand check, and why:

- a forecast or a construction note, not a report: "These pans will last you a lifetime"
  (centurylife.org), "hard-anodized aluminum core, making it highly durable" (foodnetwork.com),
  "increases the number of components that can age or fail" (techkith.com), "400-series steel
  is not as corrosion-resistant" (centurylife.org), "Long-term electronic reliability unknown"
  (galaxus.at);
- a summary that adds to its quote: "over hours of use" summarised as "during extended use"
  (eater.com, in five of the eight runs), "I love it" as "without any problems";
- the wrong kind: a reviewer's eight months of daily use labelled `owner` (nontoxiclab.com); a
  shop's product text labelled `owner` (walmart.com);
- many owners, not one: "Some Reddit discussions note", "some guests have reported ... many
  still recommend" (organicauthority.com, target.com). The generalising words stand in those
  quotes, so the summary check lets them through;
- a durability sub-score kept as the overall rating: "Durability: 5/5" (centurylife.org).

| Template, text, reasoning | Kept | Correct | Products with a correct finding | Dropped: name, quote, `model_text`, overlap, kind |
|---|---|---|---|---|
| A, snippets, little | 6 | 2 | 1 (GreenPan) | 3, 0, 0, 0, 1 |
| A, snippets, full | 4 | 2 | 1 (GreenPan) | 10, 0, 2, 1, 0 |
| A, full text, little | 0 | 0 | 0 | 4, 1, 0, 0, 0 |
| A, full text, full | 3 | 1 | 1 (GreenPan) | 9, 0, 0, 0, 0 |
| B, snippets, little | 2 | 2 | 2 (Demeyere, GreenPan) | 2, 0, 0, 0, 0 |
| B, snippets, full | 7 | 3 | 2 (Demeyere, GreenPan) | 3, 0, 0, 0, 0 |
| B, full text, little | 3 | 3 | 2 (Demeyere, GreenPan) | 2, 1, 1, 0, 1 |
| B, full text, full | 5 | 2 | 2 (Demeyere, GreenPan) | 6, 0, 2, 0, 0 |

(The script's own drop count put name and summary drops under "quote", because their reasons
also say "its quote"; the counts above are by hand, and the script is fixed.)

**EU or Dutch sites** among the kept findings: one with template A (galaxus.at, not a correct
finding), none with B. Every correct finding came from a US or UK site.

### The choice, by the rule

1. **Template B** ("{product} owner review problems"): 2 products with a correct finding against
   1 for A, on snippets with little reasoning.
2. **Full page text**, tentatively: on B with little reasoning it ties on products (2 and 2) and
   adds one correct finding (3 against 2), a margin of one.
3. **Little reasoning**: full reasoning on B with full text gives the same 2 products and fewer
   correct findings (2 against 3).

### What the check shows

- **Thin outside the frying pan.** No correct finding for a kettle or a drill in any run; the
  drills got no finding at all. Every correct finding is a Demeyere Atlantis or a GreenPan
  Valencia Pro.
- **The name check drops most.** Tramontina Professional, Fellow Corvo EKG and the Ryobi lost
  every finding to it; the results name another model or no brand near the quote.
- **Retailer review pages come through.** target.com, homedepot.com, walmart.com and galaxus.at
  are not in `SHOP_DOMAINS`, which lists Dutch and German shops only, so their review pages
  reach the read: two correct owner reports (target.com, homedepot.com) and one shop text
  taken for an owner (walmart.com).

### Changed after the first reads

The developer chose to keep the shop exclusion to `SHOP_DOMAINS` and to let the read judge the
rest: a finding now carries `on_shop_page`, the read's judgement of whether its result is a
page of a shop that sells the product, its customer reviews included, and code leaves such a
finding out. A rating that scores one aspect ("Durability: 5/5") is no longer taken for the
overall rating. The prompt now names the faults the hand check found: a forecast, what the
product is made of, what could go wrong and what owners in general say are no findings; a
reviewer who used the product over weeks is a tester; a summary adds nothing to its quote.

The reads were run again on the same stored searches, with no credit spent, so the choice
rests on the prompt the app ships with.

### The second reads, checked by hand

The shops' review pages are gone: the read returned no finding from target.com, homedepot.com
or walmart.com, so none had to be dropped as a shop's page. The durability score of
centurylife.org was dropped as a rating ("it scores durability"). Kept findings that still
failed the hand check: the eater.com kettle test summarised as "extended use" in five runs
(once it said "hours of use", which counts); a forecast or a material note (centurylife.org,
techkith.com, consumerreports.org's "has a 3 year warranty"); nontoxiclab.com's projected
"18-24 months" told as observed; "I love it" told as "without issue"; a handle that stays cool,
which is performance.

| Template, text, reasoning | Kept | Correct | Products with a correct finding | Dropped: name, quote, `model_text`, overlap, kind |
|---|---|---|---|---|
| A, snippets, little | 5 | 2 | 1 (GreenPan) | 3, 0, 0, 0, 0 |
| A, snippets, full | 4 | 1 | 1 (GreenPan) | 7, 0, 1, 0, 0 |
| A, full text, little | 1 | 1 | 1 (GreenPan) | 8, 0, 1, 0, 0 |
| A, full text, full | 2 | 2 | 2 (GreenPan, Hario) | 8, 0, 0, 0, 0 |
| B, snippets, little | 2 | 1 | 1 (GreenPan) | 3, 0, 0, 1, 0 |
| B, snippets, full | 5 | 1 | 1 (GreenPan) | 4, 0, 0, 0, 0 |
| B, full text, little | 1 | 1 | 1 (GreenPan) | 2, 0, 0, 0, 0 |
| B, full text, full | 4 | 1 | 1 (GreenPan) | 7, 0, 0, 0, 0 |

No kept finding came from an EU or Dutch site with either template.

### The choice, on the second reads

The first choice (B, full text, little reasoning) is replaced by this one, made by the same
rule on the prompt the app ships with:

1. **Template A** ("{product} long term review durability"): on snippets with little reasoning
   both templates give 1 product with a correct finding; A gives 2 correct findings against 1.
2. **Snippets**: full page text on A with little reasoning gives 1 product and 1 correct
   finding against 1 and 2.
3. **Little reasoning**: full reasoning on A with snippets gives 1 product and 1 correct finding
   against 1 and 2.

Every step rests on a margin of one correct finding, so the choice is tentative. The staged rule
never reaches A with full text and full reasoning, the one run with 2 products; with one read
per run that is within the noise. Two correct findings for nine products is thin: the findings
are worth checking again in task 1.10, with more products.

### The other nine products, and the fixtures

The other nine recorded products were searched with template A and read with snippets and
little reasoning (9 credits), and `scripts/findings_check.py fixtures` wrote the 18 findings
searches (snippets only) and the 18 replies as fixtures. Kept findings, checked by hand:

| Product | Kept | Correct |
|---|---|---|
| GreenPan Stanley Tucci | 1: a steel-wool test of the coating (consumerreports.org) | 1 |
| OXO Brew Adjustable Temperature Kettle | 1: five years of daily use, still accurate (coffeegeek.com) | 1 |
| The other seven | 0 (five findings dropped by the name check, one by its summary) | 0 |

Over all eighteen products, with the chosen settings: 7 findings kept, 4 correct, on 3 products
(GreenPan Valencia Pro, GreenPan Stanley Tucci, OXO Brew); none from an EU or Dutch site; 9
dropped by the name check, 1 by its summary, and one rating by its aspect.

### The terminal app on the recordings

`uv run python -m shopper.cli` with `SHOPPER_SOURCES=fixtures` gave no option in any tuned
category: with the real model the shortlist names products differently from the recorded price
searches ("Demeyere Atlantis Proline", "Tramontina Professional Fusion 10-Inch"), so their price
searches are `not_recorded`; one kettle run that named "Russell Hobbs Structure" raised
`FixtureMissingError` on a price page no fixture holds. Neither is this task's; both are in
`left_over_tasks.md` for task 1.10.

The proof is therefore the terminal app's own tests on the recordings (`tests/test_cli.py`): the
CLI end to end, with the shortlist and price reads written by hand from the recorded searches as
before, and the findings read answered by the recorded replies of this check. A drill option has
no recorded euro price that passes the price rule, so the drill is shown by a live run.

## The proof: the terminal app, live

`uv run python -m shopper.cli --skip-all "<request>"` on 18 October 2026, on the final code,
with the usage stated in the request:

| Request | Options | Findings lines |
|---|---|---|
| "I need a new frying pan, I cook every day" | Staub Enameled Cast Iron (`one_option_only`) | "No owner or tester reports found", under its wear and care items |
| "I need a new kettle, I use it every day" | Russell Hobbs Structure, Cuisinart CPK-17P1 PerfecTemp, OXO Variable Temperature | the Cuisinart: "Owner report: Owner reports the open button became less responsive over time. (oolongowl.com) https://oolongowl.com/cuisinart-cpk-17-perfectemp-variable-temperature-kettle-review", its trail saying the passage names the line, not the product; the OXO: "No owner or tester reports found"; the Russell Hobbs: "No durability evidence found", standing for both |
| "I need a cordless drill, I use it a few times a year" | none: "none is in stock where it was priced" | none, since no option reached the findings step |

**The drill.** Option research ended with no option: of six candidates only the Bosch PSB 1800
got a euro price, and "Confirm" dropped it, out of stock at gamma.nl (as in tasks 1.8.3 and
1.8.7; `left_over_tasks.md`, task 1.10). The findings step only runs for an option that survives
"Confirm", so the drill was run again with that product's page pasted as a link: a linked product
is never removed and gets the same `option_findings` call as a selected option. **The drill was
therefore run through a pasted link, not a typed request.**

The run (`uv run python -m shopper.cli --skip-all
"https://www.gamma.nl/assortiment/bosch-accuklopboormachine-psb-1800-li-2-incl-2-accu-s/p/B128022"`,
11 Tavily and 2 Firecrawl credits) understood the category as "hammer drill" (tuned) and gave two
options:

- the linked Bosch PSB 1800 LI-2 (€149 at gamma.nl): a rough estimate with no evidence item, its
  findings search found and read, none kept, so "No durability evidence found" stands for both;
- the Makita HR4013C (€702.97, confirmed at bouwchemie24.nl), chosen by selection, not linked:
  "Wears: brushes", "Repairs: brush replacement", "Care: clean dust …" and then
  "No owner or tester reports found".

So the drill's findings line comes from an option that option research selected; the link only
gave option research a drill category whose candidates survived "Confirm".

## Cost

27 Tavily credits on 18 October 2026: 18 for the two templates on nine products, 9 for the other
nine products. The reads (72 for the comparison, 9 for the rest) cost model calls only.

After the check, the code review moved the prompt's limits to `config.py`, so the prompt now
writes them in digits ("up to 5 findings", "at most 25 words", "never 5 or more words in a
row") where the recorded run had them in words; the rules are unchanged.
