# Option research

Read this when working on the TCO analyzer: how candidates are found, priced and selected, and
what a product option carries. The rules every search and read follows (templates, citations,
quotes, `stated_by`, money) are in `data_sources.md` ("Research rules"); the search purposes and
call limits are there too. Terms are in `GLOSSARY.md`.

Built in task 1.13 from the prototype of task 1.12, as decided in its grill and panel
(`docs/findings/task_1.12.md`, "Decided", items 1 to 16;
`docs/adr/0007-options-from-comparison-site-product-pages.md`). Evidence (task 1.8.3, factor
values 1.8.6) and Findings (task 1.8.4) are older and run as before; they are in
`option_evidence.md`. The steps run in order, except that Evidence and Findings run at the same
time.

## The steps

1. **Listing pages.** One listing search with the local category term, and per comparison site
   the listing page of the whole category in its results; the lists are merged into the
   candidates (see "Listing pages").
2. **Judgement by name.** One medium-tier call judges each candidate's durability from its
   listed name, before any product page is read, and says whether a set is asked for (see
   "Durability judgement").
3. **Product pages.** The candidates' product pages are read in order: the offer is read in code
   and the model says what the page sells (see "Product pages", "The offer on a product page",
   "What a product page sells").
4. **Judgement by page.** One medium-tier call judges the candidates read again from their
   product pages; this judgement orders the slots.
5. **Select.** Code keeps up to three product options (see "Selection").
6. **Evidence.** One search per product option for durability evidence and recurring costs, and
   one read of its results (`option_evidence.md`, "Evidence").
7. **Findings.** One search per product option for what testers and owners report, and one read
   of its results, at the same time as step 6 (`option_evidence.md`, "Findings").

## Listing pages

**The search.** One search, purpose `listing_pages` (`data_sources.md`, "Search purposes"),
"{term} kopen" with the local category term category research found (`category_brief.md`, "How
the brief is researched"), restricted to the comparison sites with the Netherlands boost. The term is
a model's, so the search is a model's query: the fixture twin answers it only when it was
recorded.

**The comparison sites** are beslist.nl and kieskeurig.nl (`COMPARISON_SITES` in `config.py`);
tweakers.net and klarna.com gave no listing page in task 1.12. Per site, its results are tried
in result order, leaving out a URL that is no listing page of the whole category: a product page
(beslist.nl's `/p/`, kieskeurig.nl's `/product/`), an information page (`/informatie`) or a list
filtered on a search word or a brand (beslist.nl's `/r/` and `merk~`). A beslist.nl list filtered
that way stands for the listing of its category, its URL cut before `/r/` or `/c/`
(`category_cut`): in task 1.15 the live kettle search found only such lists, every one under
`…/huishoudelijke_apparatuur_19968034_19970345`. A kieskeurig.nl product page is not cut, since
its path names the category of whatever matched ("drill kopen" found `/voetbal` and
`/speelgoedgereedschap`). Of the rest, the first
whose page holds a non-empty `ItemList` is the site's listing page, read with Firecrawl; a page
that lists nothing gets a trail entry and the next result is tried. Each site tries at most an
equal share of the 12 pages of an analysis, the pages read before taken off (6 each on the first
search), so the listing pages alone never pass the 12 ("When the reads stop"). On the recorded
drill searches the first beslist.nl result is a list filtered on a search word, so both read
beslist.nl's drill category (`…/klussen_486173_4468902`, recorded in task 1.15).

**The candidates.** The two lists are merged in turn, the list found first in the results
leading: its first product, the other's first, its second, and so on. A product of one list that
names the same product as one already kept from the other is that product, and the first kept
stands, with a `decided` entry; a list names each of its products once, so two products of one
list are never merged. Two names are the same product when each holds the brand either listing
names (kieskeurig.nl names one, beslist.nl none) and passes the name check of the other
("What a product page sells", "The name check"); with no brand they are two products. The words
of the category and of the local term name no product.

**The term check.** The local term has to stand in at least 3 of the product names the listing
pages list, as a compound stands (`names_kind`, "What a product page sells"). When it stands in
fewer, or category research found no term, the listing search runs once more with the English
category ("drill kopen"), a page read before is not read again, the name check on the product
pages is skipped, and a `decided` entry says why. When that search names no product, the
candidates of the first search stand, with the name check still skipped. On the recorded searches
"accuboormachine" stands in 21 of the 69 names on the two drill listing pages (in 2 before task
1.10 read compounds), so its candidates stand, and kieskeurig.nl's corded and pneumatic drills are
left out by the name check.

**The linked product** holds the first place: a candidate whose name is the same product as the
linked product (by the same test as the merge) is left out, with a trail entry.

## Durability judgement

Two medium-tier calls, reasoning in full, give each candidate a judgement, always measured
against most products of the same kind, from the model's own knowledge of how it is made. The
schema and the prompts describe each value:

| Value | Meaning | Reason, for example |
|---|---|---|
| `long` | Built to outlast most products of its kind: no part known to wear out early, or the wearing part can be replaced | "multi-ply stainless steel, no coating to wear out"; "brushless motor, replaceable battery" |
| `medium` | About as long as a typical product of its kind; nothing in its make points either way | "stainless body, standard heating element" |
| `short` | Likely to wear out sooner than most of its kind: a part known to wear out early that cannot be replaced, or a build known to be light | "PTFE coating, wears out within a few years"; "sealed battery" |
| `unknown` | The model does not know how this product is made | none needed |

The reason is one line that names the make (a material, a part, a build), never a number of
years and never praise; it needs no quote, and its text is checked like every string a model
writes. A missing judgement, one for a number not shown, or one whose reason fails the check,
counts as `unknown`, with the reason on its trail entry.

- **By name**, before any page is read: over the numbered listed names, it also returns
  `set_requested` (true only when the category itself is a set of several pieces). It decides
  only which product over the budget is read (see "Product pages"). A failed call leaves every
  judgement `unknown` and no set asked for.
- **By page**, after the reads: over the candidates read, each with its name and the start of
  its product page. This judgement orders the slots. A failed call leaves every judgement
  `unknown`, so the slots are filled by price.

The judgement is never a lifespan and never on the report, only in the trail, worded there as
the model's judgement, not a sourced figure; the lifespan shown comes from "Evidence" (`option_evidence.md`). The fixed
words are in `wording.py` (`JUDGED` and the lines after it).

## Product pages

**The order.** With a budget, up to one candidate over it comes first: the first in the listing
judged `long` by name and listed at most 3 times the budget. Then every candidate within the
budget, by its listed lowest price, in listing order. A candidate the listing gives no price for
is not read. With no budget every candidate counts as within it, in listing order, and no
over-budget read is made. A `decided` entry says how many are to be read.

**When the reads stop.** At 5 buyable candidates, or at 12 pages read in all, the listing pages
among them and cached pages counted too (`ENOUGH_BUYABLE`, `TCO_FETCH_LIMIT`); the page fetch's
own call limit, which counts only calls to Firecrawl, stays apart. At most 3 pages are read at
once (`MAX_READS_AT_ONCE`). Their results are taken in listing order, not as they finish, and no
read starts once the reads in flight and the buyable candidates together reach 5, so a run reads
the same pages each time. A `decided` entry says why products were left unread.

**A page that cannot be used** leaves its candidate out, with a trail entry: the fetch failed (a
429 retried once and answered 429 again is skipped, counted in the 12; `data_sources.md`,
"Firecrawl"), the page holds no product offer, its offer is an `AggregateOffer` with only a
`lowPrice` (a lowest price is no offer; its shop link is not followed), no new offer in euro
stands (below), the page read failed, or the page does not sell the item.

**Name and brand** are the product page's JSON-LD name and brand, else the listing's. A brand
whose words do not all stand in the name is cut to those that do ("Bosch Home and Garden" for a
"Bosch EasyDrill" is "Bosch"); a brand none of whose words stand there is kept whole.

**Size.** When at least half of the listed names state a size, a capacity or a power ("24 cm",
"1.7L", "18V"; `SIZE_UNITS`) and the page's name states none, a `decided` entry says the page
states no size or variant. On the recorded pages beslist.nl's WMF Profi Resist names none.

## The offer on a product page

The offers are read in code, with no model, from the page's JSON-LD (`tools/json_ld.py`): every
offer of the page's product, with its price, its shipping rate, its availability, its condition
and its seller. Which one stands is `chosen_offer` in `calc/offers.py`:

- Only a new offer with a euro price counts. Used and refurbished offers are skipped; an offer
  that states no condition counts as new only on a site recorded as listing new items only
  (beslist.nl, `new_only`).
- kieskeurig.nl's price is the item price plus its shipping rate (checked on three pages in task
  1.12; `price_includes_shipping`), so code takes the shipping off; an offer there with no euro
  shipping rate is passed over. beslist.nl's price is the item price.
- An offer in stock that costs under 50% of the median of the page's offers, itself included, is
  dropped when the page has at least 3 others (`PRICE_OUTLIER_SHARE`, `MIN_OTHER_OFFERS`), with
  a trail entry: the Metabo SBE 650's €32.95 against €63.27 to €114.94 in task 1.12, 37% of the
  median. Counting the offer itself lets a pair at one low price stand where the median of the
  others alone would drop both (the GreenChef at bol. and Amazon, €26.98 each, beside €52.94 and
  €77.90). The share was 60% until task 1.15 (below).
- Of the rest, the cheapest in stock wins, counted with its stated shipping (or its price alone
  when it states none); with none in stock, the cheapest, and the candidate is out of stock. Ties
  go to the earlier offer.

The option's price is the item price without shipping, and the figures use it; the shipping the
offer states is kept beside it (`shipping`, missing when not stated). The "Over your budget"
mark, the "nothing within budget" warning and selection count the price with its shipping
(`calculations.md`, "Definitions"). The price is seen on the day the page was read, and its
source is the product page, labelled with the seller the offer names; a comparison site speaks
for no one, so `stated_by` stays empty. The report shows it as "price seen at {shop} via {site}
on {date}", after the shipping ("plus €4.95 shipping", "free shipping", "shipping not stated";
`wording.py`).

beslist.nl's WMF Profi Resist page offers €44.99 twice (bol.com and Joybuy.nl) and €76.95 to
€95.90 nine times, all under one EAN, on the page task 1.13 recorded and again live two days
later in task 1.15: a sale by a real shop, 58% of the median. At 60% the report dropped it and
showed the WMF at €76.95, over the frying pan's budget; at 50% it stands at €44.99, and the
Metabo's 37% is still dropped.

## What a product page sells

The page read is the price read of tasks 1.8.2 and 1.11, which task 1.12 measured on product
pages: medium tier, little reasoning, given the page as one numbered result (its JSON-LD name as
the title and the start of its text), the category as the product named, the page's brand, and
whether a set is asked for. For each euro amount the page states, those for the product its
title names first, it returns the amount as quoted, the name of the product the amount is for,
what that product's page sells, a quote that shows it (the product's name when the page sells
the item itself; never empty), and for a set the piece count with its quote. Task 1.14 cut the
price read's other fields, which code did not read, and asked for the quote always: an empty
one, or no amount at all, dropped 23 of 135 reads as not quoted, and the trimmed prompt 3
(`docs/findings/task_1.14.md`). What it sells is a closed question:
`the_item`, `set_or_bundle`, `incomplete` (task 1.13: the item sold without a part it needs to
work, a battery, a charger, a lid, a base), `part_or_accessory`, `other_kind` or `unclear`.

Code decides (`page_sells` in `agents/tco/checks.py`):

- An amount counts only when its quote of what the page sells stands in the page.
- The amounts for the page's own product decide, its JSON-LD name compared case, spaces and
  punctuation aside; all amounts only when none is for it, since a page shows other products
  too. Taking every amount turned the Makita DF330DWE away in task 1.12, by the similar
  products below it. What most of the deciding amounts sell is the answer; a tie, or `unclear`,
  is not the item.
- `the_item` stands when the page's name holds the local term, or a deciding quote does
  (`names_kind`: a Dutch compound also stands written with a hyphen or apart, with its last part
  shared, "klopboor-/schroefmachine", and after its first word, "Accu Klopboormachine" for
  "accuboormachine"; a last part shorter than six letters only as written). A part of the
  name between dashes that is only the term in the plural is the shop's category and does not
  count: "Rommelsbacher - Reisdompelaar Type 343 - Waterkokers" is a travel immersion heater;
  otherwise the page is dropped (the Tefal Trattoria braadpan, the hapjespan and the wok of task
  1.12). The check is skipped when the term check sent the search to the English category.
- `incomplete` stands only when a deciding quote holds a missing-part word ("zonder accu",
  "solo", "body", "basic body", "zonder lader"; `MISSING_PART_WORDS`). An item read as the item
  itself whose own name says it is bare is `incomplete` too: a missing-part word of several
  words anywhere in the name, a single word only as its own part, between dashes or in brackets
  ("Makita DHP458Z - … (Body)", read as the item live in task 1.10). Otherwise the page is not
  the item.
- `set_or_bundle` stands only when a set is asked for, with a piece count quoted from the page
  that holds its number; otherwise the page is dropped. `part_or_accessory` and `other_kind` are
  not the item.

**The name check** (`names_product`), shared with the merge, the linked product, Evidence and
Findings: a text names a product when it holds its brand and at least one other word of its name
that is not a word of the category. When the name has a model number (a word with a digit that
is not a measure), that word is one of its model numbers, because a neighbouring model shares
the rest. A model number a shop writes in parts ("DHP 490 Z", "WK 9342": short words and a
number of at least three digits) counts as one word, so its parts alone name nothing (left-over
item 7 of task 1.12). A size names nothing either: a number, a measure or a unit ("7", "28",
"cm"); nor does a colour ("zwart", `COLOUR_WORDS`), which two pans of one brand shared in task
1.15. A word with a digit, or of fewer than six letters, has to stand as written; a longer word
counts in another spelling of its last two letters.

**A buyable candidate** sells the item (or a set when one is asked for), with an offer in stock.
A candidate sold `incomplete`, or with no offer in stock, is a candidate but not buyable: it does
not count toward the 5, and it carries its mark onto the option (`incomplete`, `out_of_stock`).
The linked product is never read here; it is marked out of stock when its own page says so.

## Selection

Pure code (`select` in `agents/tco/selection.py`), at most three product options in total,
filled in this order, each slot choosing only from candidates no earlier slot took:

| Slot | Without a linked product | With a linked product |
|---|---|---|
| 1 | The cheapest | The linked product |
| 2 | The durable pick | The durable pick |
| 3 | The durable pick within budget | The durable pick within budget |

- **The cheapest**: the lowest price with its stated shipping.
- **The durable pick**: by the judgement by page, `long`, `medium`, `unknown`, `short`; a
  candidate over the budget may take it only when judged `long`.
- **The durable pick within budget**: by the same judgement, within the budget only.
- **In every slot** a buyable candidate comes first, then one sold incomplete, then one out of
  stock; ties go to the lower price with its shipping, then the earlier in the listing. So an
  incomplete candidate takes a slot only when no buyable one is left, and one out of stock comes
  last.
- **Within the budget** is the price with its stated shipping at most the budget; with no budget
  every candidate is within it.

Each slot gets a `decided` entry: the price with its shipping for the cheapest, the judgement for
a durable pick, or, for a candidate with a mark, that no buyable candidate was left. When no
durable pick was decided by the judgement (it ranks no candidate the slot could take, with the
pick's standing, below the pick, so the price alone chose it), one more `decided` entry says the
slots were filled by price. A slot whose own rule finds no candidate
stays empty, with the reason. A candidate read that takes no slot gets an `excluded` entry
naming the step that decided it (task 1.10): over the budget and not judged long, out of stock
or sold incomplete while buyable candidates filled the slots, or else each slot went to a
cheaper candidate or to one the model judged to last longer.

The slot names are internal: they appear in trail entries, never as a label on the report. The
report shows each option by name. The baseline of the comparison is the cheapest option by
sticker price that is neither out of stock nor sold incomplete (`calculations.md`).

**A slot refilled after an answer.** When "Evidence" (`option_evidence.md`) removes an option for an
answer, its slot is refilled once from the buyable candidates left, by that slot's own rule, and the new
option gets its own Evidence and Findings (two more searches). A refilled option that fails an
answer too stays removed; a slot with no buyable candidate left stays empty, with a `decided`
entry.

## Warnings

Both are worked out after "Evidence" and any refill, and count the options shown, marked ones
included. `one_option_only` when exactly one product option is left, the linked product included,
whatever the reason. `no_options_found` when none is left; the first that applies chooses its
wording:

1. every listing search failed or every listing page fetch failed, or every product page fetch
   failed: the searches did not work;
2. any option was removed by an answer at "Evidence": none met the answers, where `{n}` counts
   the candidates whose product page was read and offered them;
3. otherwise: nothing with a euro price was found.

A candidate out of stock still takes a slot, last in its order, so no run ends with no options
for that reason; task 1.15 dropped the wording for "none in stock".

The words are in `wording.py`. The check-before-you-buy list has an item of reason `price` for
every option with a price, shown as one line for all of them ("Confirm the current price: Prices
change after the day each was seen.").

## What a product option carries from these steps

Name and brand (from the product page, else the listing), link (the product page), `price`
(the offer's price without shipping), `price_source` and `price_seen_on` (the day the page was
read, also on a cache hit), all three given together or not at all, `shipping` (the offer's, missing when it states none), the marks
`out_of_stock` and `incomplete`, and a set's `piece_count`. The source is the product page,
labelled with the seller the offer names (none when it names none), with `stated_by` left empty
for a comparison site.
Everything else (lifespan, durability evidence, recurring cost, factor values, findings) is
added by steps 6 and 7.

**The linked product** gets its price, source and date from the pasted page when the page
states a euro price, and the mark `out_of_stock` when its offer says so. With no price it keeps
slot 1, counts as an option for the warnings, and the trail says why it has no price; the
baseline is then the cheapest priced option that carries no mark.

Lifespan, durability evidence and recurring cost are added by "Evidence"; findings by
"Findings" (both in `option_evidence.md`).
