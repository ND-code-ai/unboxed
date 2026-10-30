# Option evidence

Read this when working on what the TCO analyzer reads for each product option once the options
are chosen: its lifespan, durability evidence, recurring cost and factor values ("Evidence"), and
how it held up for testers and owners ("Findings"). How the options are found, priced and chosen
is in `option_research.md`; the rules every search and read follows are in `data_sources.md`
("Research rules").

Evidence (task 1.8.3, factor values 1.8.6) and Findings (task 1.8.4) run at the same time, as
steps 6 and 7 of `option_research.md` ("The steps").

## Evidence

Built in task 1.8.3; factor values from the same read in task 1.8.6. It runs after selection,
for every product option, the linked product included, also when the request has no category
(the template is then filled with the linked product's name alone, and no recurring cost is
looked for). It runs on the product options, each carrying its brand for the name check
(`brand` on the product option: its product page's, else its listing's, for a candidate; the
JSON-LD `brand` for the linked product).

**The search.** One per option, purpose `evidence` (`data_sources.md`, "Search purposes"),
filled with the words that name the option (`search_name` in `agents/tco/checks.py`): the first
part of its name, cut at " - ", that says more than the brand, with the brand in front when that
part lacks it, and without sizes ("Inventum HW817D Waterkoker - 1.7L - RVS/Zwart - 2200W" is
"Inventum HW817D Waterkoker"; a bare number is a size only before a unit, so "Metabo SBE 650"
keeps its model). The name is the product page's JSON-LD name ("Decided", item 12), or for the
linked product its name as JSON-LD gives it; task 1.13 found 7 of 9 searches with the whole name
empty, and task 1.15 changed this. No
follow-up: the three calls are one per option, and gaps go to the trail. The template,
"{product} durability lifespan warranty", was chosen in the live check of task 1.8.3, tentatively
(`docs/findings/task_1.8.3.md`), and the search asks for full page text (`data_sources.md`,
"Tavily"). The query is a name a model or
a page wrote, so the fixture twin answers it only when recorded; `not_recorded` is a failed
search, below.

**The read.** One per option, in parallel, medium tier reasoning in full. It sees the evidence
search's results and, as one more numbered result, the option's own page cut to the same text
limit: for a candidate the product page read in "Product pages" (`option_research.md`), for the linked product its own
page, which code fetches again through the page fetch, answered by the cache (`with_page` in
`agents/tco/evidence.py`). Both were read before, so they cost no credit, and a page often lists
what an answer asks ("Geschikt voor inductie: Ja"). A page with no text is left out. Since task
1.13 the read no longer sees a discovery result. It returns, each with its cited result, a quote
and `stated_by`:

- lifespan quotes, each marked `about`: `product`, `line` or `type`;
- at most one item per kind of durability evidence: warranty, repairability, wear material,
  care. Each value names a material, a part or an action ("PTFE coating", "spare blades sold",
  "hand wash only"), never a judgement of the product;
- when the category has consumables, the main one: its name, an amount quote, an interval quote
  and an optional pack-count quote; other consumables only by name, for the trail;
- an estimated lifespan in whole years with the evidence items it rests on;
- a fit for each answered factor it is given (see "Answers");
- gaps, for the trail.

**What must name the product.** The passage of the quote must pass the name check of "What a
product page sells" (`names_product`) for a lifespan `about` the product, for a warranty and for a
recurring cost. The passage is the cited result's title and the line, or the snippet between two
"[...]", that holds the quote (`passage` in `agents/tco/evidence_checks.py`): a buying guide that
names many products names the product of a quote only near it (the LCA review of task 1.8.3
found a shop's worked example for a Demeyere saucepan taken as the frying pan's lifespan). A
lifespan `about` the line passes with the brand and one other word of the name that is not a
category word, without the model-number rule, since a line spans models; a word for a material,
a finish or a tier ("nonstick", "ceramic", "pro") names no line (`LINE_GENERIC_WORDS`).
Wear material, repairability and care are accepted from any cited result. The linked product
has a brand only when its JSON-LD names one; with none, it gets no sourced lifespan, warranty
or recurring cost, and the trail says why.

**The quote check** is the one in `data_sources.md` ("Research rules"). A quote may join parts
with an ellipsis, each found in order, for a text value only; a quote that code reads a number
from (years, a warranty, an amount, an interval, a pack count) holds that number and its unit in
one part.

**Sourced lifespan.** Code reads the years from the quote with its own reader, which takes the
low end of a range. Each form is unit-tested:

| The quote says | Years |
|---|---|
| "2 to 5 years", "2-5 years", "between 2 and 5 years", "2 or 3 years", "two to five years", "tussen 2 en 5 jaar" | the low end, 2 |
| "at least 5 years", "over 5 years", "5+ years" | 5 |
| "18 months" | 1.5 |
| "up to 10 years", "up to about 10 years", whoever states it | not sourced |
| hours or cycles ("500 hours of use") | not sourced |
| "a lifetime", "for generations" | not sourced |

Only a statement of how long the product typically lasts or is expected to last counts. One owner's
report of one unit failing, how long some people keep one, a statement about the brand's
products in general and a seller's worked example for another product are not lifespans; the
first feeds the estimate. Findings (step 7) run at the same time as this read and feed nothing:
not the estimate, not the lifespan, not any figure. A quote `about` the type ("non-stick
pans last 2 to 5 years") is never sourced: it becomes a type-level evidence item when it states
a range (a single number is left out), shown as typical for the kind of product the quote names
when that name stands in the quote ("Typical for Non-stick pans"), else for "this kind of
product", since the category may be wider than the quote. When several sourced
quotes remain, a tester's or owner's wins over a manufacturer's or seller's, then the lowest.

**Estimated lifespan.** With no sourced lifespan, the option takes the read's estimate: whole
years, kept between 1 and 50 by code and, when there is a type-level item, inside its range.
The prompt says the estimate never copies the warranty. Its source has the kind
`model_estimate`, the model ID as reference and the label "rough estimate"; the evidence it rests
on goes on its trail entry. A read with no evidence still gives one, shown with "No durability
evidence found" under it.

**Durability evidence** (`DurabilityEvidence` in `state.py`) holds one item per kind, each
`Sourced` with `stated_by`, plus the type-level lifespan item. A warranty is years or a lifetime
(`WarrantyTerm`), marked limited when its quote says so ("limited lifetime warranty", which
covers defects and not wear, so it shows as "limited lifetime"), kept only when it is a lifetime
or longer than two years: two years is the EU
legal guarantee (`docs/eu_market.md`), which says nothing about this product, so it goes to the
trail. Text values are checked like every string a model writes (`model_text.py`), except that a
number is allowed when it stands in the quote.

**Recurring cost.** Looked for only when the brief has a factor of kind `recurring_cost`, or the
brief has no researched factor at all (`research_unavailable`), at no extra call. Otherwise it is
"not looked for": no value and no flag. The reading below is shared with the brief's typical
yearly cost (`agents/shared/yearly_cost.py`). Code reads the amount with `calc/amounts.py`, the pack
count from its quote, and the interval with a parser in `calc/`: every N days, weeks, months or
years, "yearly", "annually", "annual", "monthly", "twice a year", "per year" or "each month"
(once), and their Dutch forms; a money amount in the quote, with a currency marker or code before
it or a currency word after it, decimals or not, is taken out first, so it is never read as a count
("€12.50 a month" is once a month); a range of
intervals takes its long end. The yearly cost is the amount divided by the pack count, times the
replacements a year. A quote that shows a pack with no readable count, an interval in uses
("every 50 uses") or one the parser cannot read leaves the cost not found, with a trail entry.
An amount in USD or GBP is converted at the fixed rate (`docs/adr/0002-fixed-rate-conversion-recurring-costs.md`);
a bare "$" counts as USD, with a trail entry; any other currency is dropped. When the read names
other consumables, the option's recurring cost is marked as leaving them out.

**Answers** (task 1.8.6). The read writes the option's factor values, the only step that does.

- **Which factors.** One of kind `compatibility`, `requirement` or `care`, or a factor of the
  user's own, whose answer is `chosen` or `stated`; a care factor only when the answer is
  `care-avoid`, since nothing hangs on `care-fine`. A factor answered `not_sure` or `skipped` is
  on the check-before-you-buy list already and gets no value; neither does the factor of kind
  `usage`, nor one of kind `recurring_cost`, which is never asked about (`category_brief.md`,
  "Recurring costs are factors"); the option's own recurring cost is its line on the report.
- **What the read is told.** The factors numbered (code maps the numbers back to ids), each
  with its name, its question and the answer as text: the choice's text, the
  stated value, or, for a factor of the user's own, the user's phrase. A care factor also gets
  its care statement, and is judged as "does this option need that care": `fails` when it does,
  `meets` when it does not.
- **What it returns** per factor: the fit (`meets`, `fails` or `unverified`), a short value in
  plain words ("works on induction", "hand wash only"), the cited result and a quote. A factor it
  leaves out is `unverified`.
- **The check.** A `meets` or a `fails` stands only when code finds its quote in the cited result
  and the quote's passage passes `names_product`, as a warranty's does (see "What must name the
  product"). Otherwise the value becomes `unverified`, and the trail says why ("its quote is not
  in the result", "the result does not name the product"). The value is checked like every
  string a model writes, a number allowed when it stands in the quote; one that fails makes the
  fit `unverified` too. A linked product with no brand gets only `unverified` values, and the
  trail says why.
- **Its source.** A `meets` or `fails` has the cited result as its source, with the read's
  `stated_by` (`seller` for a shop's page, such as the linked product's). An `unverified` value
  has no value text and the factor's own source; it goes on the check-before-you-buy list.
- **What a fit does.** A `fails` on a factor of kind `compatibility` or `requirement`, or on a
  factor of the user's own, removes the option, and its slot is refilled once from the buyable
  candidates left, with their own Evidence and Findings (`option_research.md`, "Selection"; task 1.13). The trail
  gets an `excluded` entry naming the factor, the quote and its site, and the warnings are
  worked out after this (`option_research.md`, "Warnings"). The early drop for an answer at the shortlist is gone
  with it. A `fails` on a
  care factor marks the option and removes nothing: a line on the report, with no change to the
  lifespan, the selection or any figure.
- **The linked product** is never removed: a `fails` gives it a mismatch line beside the product,
  with its source, and it stays first. A care factor it fails gives it the care mark, not the
  mismatch line.
- **The trail** gets one `found` entry per option listing its fits with their sites
  ("hob compatibility: meets (fonq.nl); care: unverified"), with the reason of each value the
  check turned `unverified`.

**Failures.** A failed or empty search, or one `not_recorded` by the fixture twin, still gets a
read of what is left, so the option still gets an estimate. A read that fails twice leaves the
lifespan missing and every factor value `unverified`; the trail says why ("durability evidence
could not be read"), the lifespan line points to setting one, and no warning is raised.

## Findings

Task 1.8.4; settled in an interview before the task, with why the quote is never shown in
`docs/adr/0005-findings-summarised-quote-logged.md`. Up to three short reports per product
option of how it held up for a tester or an owner (`docs/product.md`, "Durability evidence").
Findings are shown and feed nothing: no lifespan, no estimate, no selection, no figure.

**When it runs.** At the same time as "Evidence", for every product option, the linked product
included, and also when the request has no category. Both return their part and code merges
them after both finish, so neither overwrites the other's. An option that "Evidence" removes for
an answer loses its findings and their trail entries: it has no block on the report. A linked
product with no brand gets no search (its name cannot be checked); the trail says why.

**The search.** One per option, purpose `findings` (`data_sources.md`, "Search purposes"),
filled with the option's name; English, no country. No follow-up. The template, "{product} long
term review durability", and snippets only (no full page text) were chosen in the live check of
task 1.8.4, tentatively (below). The query is a name a model or a page wrote, so the fixture twin
answers it only when recorded.

**The read.** One per option, medium tier with little reasoning (chosen in the live check). It
sees only the findings search's results. The prompt names the preferred testers
(`PREFERRED_TESTER_DOMAINS`) and asks for a mix of tests and owner reports. It returns, for each
finding, the cited result, whether that result is a shop's page, a quote, a summary, `stated_by`
and an optional rating quote; and gaps, for the trail.

- **Durability only**: a part that failed or wore, how long the product or one owner's unit
  lasted, a repair, a warranty claim. Performance ("heats evenly", "loud"), a forecast ("will
  last a lifetime"), what the product is made of, what could go wrong, and what owners in
  general say ("some buyers reported") are not findings; the prompt names each, after the live
  check found them kept.
- **Not from a shop's page.** The read judges whether a result is a page of a shop that sells
  the product, its customer reviews included, and code leaves out a finding from one: retailer
  review pages are not used (`docs/product.md`). `SHOP_DOMAINS` are excluded from the search as
  well; the read's judgement covers the shops no list names (the live check found target.com,
  homedepot.com and walmart.com).
- **Who is speaking** sets the kind, in code: `tester` gives a test, `owner` an owner report. The
  prompt gives `tester` to a reviewer or a test site that says it used or tested the product,
  also over weeks or months; a roundup that did not is no test. A statement by a manufacturer or a seller is never a finding, and a shop's
  page is the seller's. Owner reviews on a forum or a comparison site (Reddit, Tweakers) are
  `owner`.
- **The quote** is one piece, with no ellipsis, found in the cited result, and its passage
  (`passage` in `agents/tco/evidence_checks.py`) names the product's line: the brand and one
  other word of the name that is not a category word, as for a lifespan `about` the line. When
  the passage names only the line and not the product, the trail entry says so. After the
  checks the quote is written to a debug log line on the `shopper.findings` logger and dropped:
  it is not on the product option or the trail.
- **The summary** is English whatever the source's language, at most 25 words, about one unit
  or one test ("One owner's pan lost its coating after 8 months"). It passes the check every
  string a model writes gets (`model_text.py`); a number, and a generalising word ("many",
  "most", "often", "always", "owners", "commonly"), stand in it only when they stand in the
  quote. It may not share a run of 6 or more words with the text the read saw, compared after
  the normalisation of `plain`, leaving out runs made only of the option's name and brand words.
- **The rating**, when the read gives one, comes from its own rating quote in the same result,
  checked on its own: it stands in the result in one piece, its passage passes `names_product`
  (the model-number rule included, since a star rating for a neighbouring model misleads), and it
  holds a value with a scale ("4.5/5", "4.5 out of 5", "8/10", "4,5 van 5"), not for one aspect:
  a quote that names durability, longevity, lifespan or build quality ("Durability: 5/5") scores
  an aspect and is no overall rating. The rating is kept as the quote writes it. A test's rating needs no review count. An owner report's rating is kept
  only with one: the number before a word for reviews ("reviews", "ratings", "beoordelingen",
  "recensies", "Bewertungen"), read by a function in `calc/` that handles thousands separators
  ("1.234 beoordelingen" is 1234) and never takes the scale of the rating for it ("4.5/5
  rating" has no count). A rating is shown as the source's overall rating, never as a
  durability score.
- **One finding per cited result**, at most three per option: the first three that pass the
  checks, in the order the read named them. A finding that fails a check goes to the trail with
  its reason.

A finding (`Finding` in `state.py`) holds its kind, the summary, its source (with `stated_by`),
the rating and review count, and the result's published date when the search gives one (stored,
not shown). Durability evidence holds the findings and a findings state:

| Findings state | When | Shown as |
|---|---|---|
| `found` | At least one finding passed the checks | The findings |
| `none_found` | The search found nothing (`not_found`, no read), or the read kept none | "No owner or tester reports found" |
| `not_searched` | The search or the read failed, the fixture twin had no recording (`not_recorded`), the daily limit was reached, or a linked product with no brand was not searched | "Owner and tester reports not looked up" |

The words are in `wording.py`. Under a rough estimate with no evidence item and no finding,
"No durability evidence found" stands for both lines when the reports were looked up
(`none_found`); when they were not (`not_searched`), the "not looked up" line follows it, since
nothing was looked at.

**The live check of task 1.8.4.** Before the template is fixed, two templates are run on the
three tuned categories, each with full page text and without, and the reads compared with little
and full reasoning on the same recorded results. The rule is fixed before credits are spent:
count the options with at least one finding checked by hand as correct (the right product, the
right kind, a summary faithful to its quote, about durability), and the findings dropped per
cause (quote, name, overlap, `model_text`, kind). Full page text, and full reasoning, are taken
only when they add correct findings, not more findings. The check also records how many kept
findings came from EU or Dutch sites per template. Results in `docs/findings/task_1.8.4.md`;
the same run records the fixtures. Run on 18 October 2026: template A, snippets and little
reasoning, each by a margin of one correct finding, so the choice is tentative. A first round of
reads chose template B with full page text; the prompt was then corrected for the faults that
round found, and the reads run again on the same stored searches gave this choice. Correct findings
were few (a GreenPan, a Hario and, among the products recorded after the choice, an OXO kettle)
and none came from an EU or Dutch site.
