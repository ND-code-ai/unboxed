# Findings from task 1.12: option research from what is sold here, measured

Run on 22 October 2026 with `scripts/listing_prototype.py`, live sources and live models. The
design, the pass rule and what is recorded were fixed before any credit was spent
(`docs/findings/task_1.10.md`, "Decided", items 1 to 3) and were not changed here.

**Verdict: pass.** Two of the three tuned categories hold at least 5 buyable candidates within the
budget from at least 3 brands, checked by hand, and the third holds them too when a drill sold
without battery and charger counts. The rework goes ahead in task 1.13.

**Credits:** 6 Tavily (ceiling 15) and 33 Firecrawl (ceiling 35). Nebius: 27 medium-tier price
reads for the page classification and 9 calls for the Dutch term probe. The roundup searches are
the six recorded in task 1.8 (`.cache/live/experiment_1_8/`), so they cost nothing.

## What the prototype does

For each category, with the budget the 1.10 runs asked for:

1. **Listing search.** One Tavily search, `"{Dutch term} kopen"`, restricted to beslist.nl,
   kieskeurig.nl, tweakers.net and klarna.com with the Netherlands boost (the new search purpose
   `listing_pages` in `config.py`). The Dutch term is written by hand: koekenpan, waterkoker,
   accuboormachine.
2. **Listing pages.** The general listing page of each comparison site in the results is read
   with Firecrawl. Code reads its `ItemList` (`listed` on the fetched page, `tools/json_ld.py`):
   each product's name, link and lowest price.
3. **Product pages.** Listed products are read in listing order, those whose lowest price is
   within the budget first. A product over 3 times the budget would be skipped; none was read.
   Code reads the offer from the JSON-LD as it does for a price page.
4. **Page classification.** The price read of task 1.11 runs over each product page, with the
   category as the product named, so `sells` says whether the page sells the category's item. The
   page counts what the amounts for its own product name say (see "The classification").
5. **Buyable by code:** a product offer in euro, in stock, and `sells` = `the_item`. Then every
   page is checked by hand against `GLOSSARY.md` ("Buyable candidate").

Also recorded: the open control search (the same query with the price search's domains, judged
from its URLs, no page reads), the roundup match, and the supervisor's Dutch term.

Every search and page is a fixture: `tests/fixtures/tavily/{category}-listing-pages.json` and
`-control.json`, and `tests/fixtures/firecrawl/{category}-{read number}-{site}-…-page.json`,
trimmed to the JSON-LD product data (shoppers' reviews and pictures left out) and the page text's
first heading and stock lines. Each trimmed page fixture gives the same product, offer and
listed products as its live page, and each search fixture the same result URLs (checked for all
33 pages and 6 searches); the page text is cut, so the classification cannot be replayed from
them. The model replies stay in `.cache/live/prototype_1_12/reads/`,
not committed: a replay test needs the page text the read saw, which the trimmed fixtures drop.

## The counts by hand

| Category (budget) | Reads (listing + product) | Buyable within budget, by hand | Brands | Pass |
|---|---|---|---|---|
| Kettle (€60) | 2 + 6 | 6: Midea €27.99, Severin WK 9342 €29.95, Philips HD9350/90 €35.99, Tefal Subito Mini €34.99, Inventum HW817D €28.95, Russell Hobbs Colours Plus+ €38.42 | 6 | Yes; 5 reached at read 7 |
| Frying pan (€50) | 2 + 9 | 5: WMF Profi Resist 24 cm €44.99, GreenChef Diamond 24 cm €26.98, Tefal Renew ON 24 cm €35.99, Tefal Jamie Oliver keramisch 28 cm €39.99, Tefal Jamie Oliver Cook Smart 28 cm €37.99 | 3 | Yes, at the edge; 5 reached at read 11 |
| Drill (€120) | 2 + 12 | 10 by the glossary, 5 of them sold without battery and charger; 4 complete electric drills (Bosch EasyDrill 18V-38 €49.99, Makita DF330DWE €113.85, Metabo SBE 650 €32.95 corded, Black+Decker KR911K €70.98 corded), 2 of them cordless | 6; 4 complete | Yes by the glossary (5 reached at read 7); no if a drill without battery does not count |

Left out by hand: in frying pan, a Tefal Trattoria braadpan (a casserole), a Tefal Renew hapjespan
(a sauté pan) and a Tefal XL Force wok, each another kind of pan, and the de Buyer Mineral B at
€51.95, over the budget (its listing said €47.83). In drill, a Roughneck soil auger and a Rotec
core drill bit; the Aerotec pneumatic drill counts as a drill but needs a compressor.

Two drill prices are doubtful, though they are offers on the page: the EasyDrill's €49.99
(Joybuy.nl and Amazon Partners, against €65.83 to €100.42 elsewhere) and the Metabo's €32.95
(Amazon, against €63.27 to €114.94, and a listed lowest price of €63.27). Neither changes the
verdict.

The frying pan passes only just: exactly 5, exactly 3 brands, three of them Tefal. Its two
listing pages were thin for the budget. beslist.nl's `ItemList` held 10 products, 9 of them
Demeyere or WMF over €50; kieskeurig.nl's `/pan/beste` mixed pan sets, casseroles, woks, a
pressure cooker, a bread maker and a crêpe maker among its 24.

**Reads per analysis.** Five buyable candidates took 7, 11 and 7 reads, listing pages included.
That is within the cap of 12 reads per analysis ("Decided", item 7), so the cap is not lowered;
the frying pan's 11 leaves it little room. The drill's reads 8 to 14 went past its fifth
candidate, to count complete drills and the classification; an analysis would not make them, and
the Black+Decker at read 14 is past the cap.

## Per domain

| Domain | Listing pages | Product pages | Firecrawl | Page kind the read gave (product pages) | Buyable within budget, by hand |
|---|---|---|---|---|---|
| beslist.nl | `ItemList` of 10 products with relative links and a lowest price only, no brand (3 of 3) | `AggregateOffer` with nested offers: seller, price, stock, shipping; no condition stated; the price excludes shipping (checked on two pages); 7 of 7 | 10 of 10 read | `comparison_site` 6, `shop` 1 | 7: 1 kettle, 1 frying pan, 5 drills |
| kieskeurig.nl | `ItemList` of 24 products with full links, brand and 1 or 2 nested offers each (3 of 3) | Nested offers with seller, price, stock, `NewCondition`, shipping; the price **includes** shipping (checked on three pages); 20 of 20 | 23 of 23 read | `comparison_site` 17, `shop` 3, `other` 0 | 14: 5 kettles, 4 frying pans, 5 drills |
| tweakers.net | None in the listing search (one forum thread on gathering.tweakers.net) | A Pricewatch page read by an earlier task holds no JSON-LD | Read before | — | — |
| klarna.com/nl | None in the listing search | Two of the three product pages read by earlier tasks nest their offers (the third is a `ProductGroup`); a category page read then has no `ItemList` | Read before | — | — |

No product page had only a `lowPrice`, so none was dropped for it, and following a `lowPrice`
page's shop link (an open point for 1.13) had no case here. In 2 of 27 product pages the offer
differed from the listed lowest price (the de Buyer and the Metabo above).

kieskeurig.nl's offer price is the item price plus shipping: GreenChef at bol. is €23.99 plus
€2.99 shipping in the page text, and €26.98 with a `shippingRate` of €2.99 in the JSON-LD; Tefal
Subito and Philips HD9350 at MediaMarkt.nl are €34.99 and €35.99 plus €2.99, and €37.98 and
€38.98 in the JSON-LD. beslist.nl's is not (Midea at Joybuy.nl: €27.99, with €3.99 shipping stated
apart). So "shipping €2.99" beside a kieskeurig.nl price counts it twice, and the cheapest offer
there is the cheapest with shipping, while on beslist.nl it is not.

The left-over item from task 1.11 (kieskeurig.nl read as `other`) did not recur: no product page
of either site came back as `other`. Five reads returned a second, empty entry `other` for the one
page they were given.

**Rate limit.** Firecrawl answered 429 after nine reads in a row within about a minute. The four
failed reads cost nothing and were repeated after a pause. At up to 12 reads per analysis
(item 7), the reads need pacing or a retry after a pause.

## Variant, shipping and sellers

- **Variant.** Each kieskeurig.nl product page is one product with its size or capacity in the
  name, and its offers are for that product. beslist.nl's WMF page names no size; its
  specifications say 24 cm, which fits the €44.99 offers (Joybuy.nl and bol.com). No chosen offer
  was found to be for another variant.
- **Shipping** is stated in every offer of both sites, as `shippingDetails` (above for what the
  price includes).
- **Foreign sellers.** None among the chosen offers: every seller is a Dutch-facing shop (bol.,
  Coolblue.nl, Amazon.nl, Wehkamp, EP.nl, Toolstation.nl, Proshop.nl, Joybuy.nl and others).
  Marketplaces stand among them (bol. Plaza, Amazon Marketplace, Kaufland), whose actual seller
  the page does not name; 2 of the 26 offers chosen within budget are bol. Plaza.

## The classification (left-over item from task 1.11)

The price read, asked against the category, on each product page read:

| Category | Right | Wrong |
|---|---|---|
| Frying pan | 7 of 9 | Tefal Trattoria braadpan and Tefal Renew hapjespan read as `the_item`; the wok was caught (`other_kind`) |
| Kettle | 6 of 6 | — |
| Drill | 10 of 12 | Roughneck soil auger and Rotec core drill bit read as `the_item`; kieskeurig.nl's own specifications call the auger an "Accuboormachine" |
| All | 23 of 27 | 4, all a page of another kind or an accessory let through; none of the item turned away |

It errs the same way as in task 1.11 (a saucepan and a grill pan let through): it lets a near
kind of product through, and it is not to be relied on alone. It has no answer for a drill sold
without battery and charger: all five came back `the_item`, right by the closed question. The
supervisor's category for the 1.10 drill run was "drill", not "cordless drill", so a corded or a
pneumatic drill is the item too.

How the page's answer is taken matters. A product page also shows other products, and the read
gives an amount for each. Taking what most amounts sell turned the Makita DF330DWE away
(`other_kind`, from the similar products below it); taking the amounts for the page's own product
name gives `the_item`. The counts above use the page's own name.

## The open control search

Judged from the result URLs only, as decided. The open search is the same query with the price
search's domains, so bol.com and social sites cannot appear in it either:

| Category | Restricted: product / listing / other | Open: product / listing / other |
|---|---|---|
| Frying pan | 0 / 7 / 1 forum thread | 0 / 7 shops' listing pages / 1 blog |
| Kettle | 0 / 7 / 1 guide | 0 / 7 shops' listing pages / 1 blog |
| Drill | 1 / 7 / 0 | 0 / 5 shops' listing pages / 3 guides and reviews |

The open search found no product page and no comparison site's listing page; it found shops' own
listing pages (Coolblue, MediaMarkt, Gamma, Praxis and others), as many as the restricted search
found in two categories. No domain gave product pages in 2
or more categories, so none is added, and the open search did not find more than the restricted
one, so the restriction stays. Whether the shops' listing pages hold an `ItemList` was not read.

## The roundup match

The two roundup searches per category (`best {category} tested`, `best budget {category}`) name
**none** of the 27 products read, checked by hand at model level. They are US and UK roundups:
the brands overlap (Russell Hobbs, Bosch, Makita, DeWalt, Black+Decker, T-fal) but the models do
not (Russell Hobbs Structure, Bosch EasyImpact, Makita DHP482). So no buyable candidate has a
quoted hint, and no durable pick with a quoted hint exists among those read. That is fewer than
2 in 2 of 3 categories: by the decided rule, a durable pick ranked by the model's judgement comes
back to the developer as a product decision (an open point of task 1.13), and it does not kill
the rework.

The app's name check (`names_product` in `agents/tco/checks.py`) matched the Makita "DHP 490 Z
… Solo (Without Battery/Charger)" in three roundups, on "without" and "battery": a model number
split into short parts is no model number to it, so any other word of the name counts.

## The supervisor's Dutch term

A probe with its own prompt (the shopper's 1.10 words and the category; no brand, budget or
size), since the supervisor does not return the term until task 1.13:

| Category | By hand | Small tier (the supervisor's), two runs at temperature 0 | Medium tier |
|---|---|---|---|
| Frying pan | koekenpan | bakpan; bakpan | koekenpan |
| Kettle | waterkoker | sneldampketel; sneldampende waterkoker | snelkokende waterkoter |
| Drill | accuboormachine | accuboore; accu boormachine | accuboormachine |

The small tier gave the hand-written term in none of six answers, two of them not Dutch words,
and two runs differed (every run is in `.cache/live/prototype_1_12/terms.json`; the first run was
kept from the file as it stood before the script stored every run). The medium tier gave it twice, and misspelt the third. No check of a
model's string would catch "sneldampketel". Task 1.13 decides where the term comes from.

## For task 1.13

- The pass holds on two comparison sites; tweakers.net and klarna.com gave nothing through the
  search, and beslist.nl's listing holds only 10 products.
- The classification lets a near kind or an accessory through (4 of 27); it needs help before it
  decides alone, and it should classify the page's own product, not every amount on the page.
- kieskeurig.nl's price includes shipping; the shipping wording of item 11 needs the site's rule.
- A drill without battery and charger, and the category losing "cordless", are product decisions.
- The Dutch term from the small tier is not usable as it is.
- Firecrawl's rate limit needs pacing at 12 reads per analysis.

## Decided: the rework of task 1.13 (grill and panel, 23 October 2026)

Grilled on this file, `docs/findings/task_1.10.md` ("Decided"), `option_research.md`,
`data_sources.md`, `eu_market.md` and ADR 0004, then reviewed by the panel (product,
implementation, data). Where an item here differs from the 1.10 "Decided" list, this one holds.
Terms are in `GLOSSARY.md`, updated in the same commit.

**Finding products**

1. **Local category term.** A medium-tier call in category research writes it, cached with the
   brief; it is no longer the supervisor's. Code checks it stands in at least 3 product names of
   the listing pages' `ItemList`. If not, the listing search runs once more with the English
   category, the name check of item 9 is skipped, and the trail says so. A failed call leaves the
   brief unstored, as for its other calls; stored briefs are rebuilt.
2. **Comparison sites.** Only beslist.nl and kieskeurig.nl; tweakers.net and klarna.com are dropped
   (nothing from them in this task). At most one listing page per domain, the first result whose
   page holds a non-empty `ItemList`, in result order. The two lists are merged alternately; a
   product `names_product` matches to one already kept is the same product, the first kept.
3. **Removed:** the two roundup searches (they named none of the 27 products), discovery, the
   shortlist, the `"{product} prijs"` price search and "Confirm"; the search purposes `discovery`
   and `price` go, and `check_sources.py` moves to another purpose. No search-price fallback: too
   few candidates give the existing warnings. Durability hints go with the roundups.
4. **Durability judgement.** One medium-tier call over the listing names, before any product page
   is read, gives each candidate a judgement and returns `set_requested`. After the reads, a second
   medium-tier call judges the read candidates again from their product pages, and that judgement
   decides the slots. The trail wording is fixed in `wording.md`: ordered by the model's judgement,
   not a sourced figure.
5. **Read order.** Up to one over-budget product judged `long` from its name (at most 3 times the
   budget), then within-budget products in listing order. The reads stop at 5 buyable candidates or
   12 pages, listing pages included, counted cached or not (the credit limit stays apart). Results
   are taken in listing order, not as they finish, and no read starts once the reads in flight plus
   the buyable candidates reach 5. With no budget, every product counts as within it and the
   over-budget read is skipped.
6. **Firecrawl.** At most 3 reads at once. A 429 is retried once after `Retry-After` or a pause, a
   Firecrawl-only setting in `config.py` (the shared rule in `tools/http.py` waits at most 5 s);
   after a second 429 the page is skipped, counted in the 12, with a trail entry.
7. **A product page whose offer has only a `lowPrice`** drops its candidate, with a trail entry;
   its shop link is not followed (no case in this task).

**Price and identity**

8. **Offer price and shipping.** The figures use the item price without shipping; kieskeurig.nl's
   offer includes its `shippingRate`, which code in `calc/` takes off. The offer chosen on a page,
   and the "Over your budget" mark, use the item price plus the stated shipping; with no shipping
   stated, the item price alone, and the report says "shipping not stated". A kieskeurig.nl offer
   with no euro `shippingRate` is dropped for another offer on the page. On one page, an in-stock
   new offer under 60% of the median of at least 3 other offers is dropped, with a trail entry (the
   Metabo's €32.95). An offer with no `itemCondition` counts as new only on a domain recorded as
   offering new items only (beslist.nl); used and refurbished offers are skipped. When the page
   states no size or variant and the category has one, the trail says so.
9. **What the page sells.** The amounts whose name is the page's own JSON-LD product name decide
   (all amounts only when none is); `unclear` or a tie is not the item. When that is `the_item` but
   the product name lacks the local category term, the `sells` quote must hold it, or the page is
   dropped. On these pages the rule drops the braadpan, the hapjespan and the wok (2 errors of the
   classification and one it had caught) and nothing right in frying pan and kettle; for drill it
   changes nothing. Session 2 records those three pages with their text, so a test replays it.
10. **`incomplete`**, a new value of the closed question: the item sold without a part it needs to
    work (a battery, a charger, a lid, a base). Code needs a missing-part word in its quote ("zonder
    accu", "solo", "body only", "zonder lader"), else the existing rules apply. It is a candidate,
    not buyable: it does not count toward the 5, takes a slot only when no buyable candidate is
    left, and shows its savings and CO2e avoided as missing, with a fixed line in `wording.md`.
11. **Out of stock.** A candidate with no in-stock offer takes its cheapest offer and is marked:
    not buyable, last in each slot, never the baseline. Its own label, never "Over your budget";
    `within_budget` stays a price test. The linked product gets the mark when its page says so.
    `ProductOption` carries both marks, and the baseline rule in `calc/` leaves a marked option out.
    `one_option_only` and `no_options_found` count the options shown.
12. **Names and answers.** An option's name and brand come from the product page's JSON-LD, else the
    listing; a sub-brand ("Bosch Home and Garden") is cut to the words that stand in the product
    name. Evidence loses the cited discovery result. Piece counts are read from the product page,
    checked by quote. The early drop for an answer goes; when Evidence removes an option for an
    answer, its slot is refilled once from the buyable candidates left, with Evidence and Findings
    for that one (2 Tavily searches).

**Selection and the report**

13. **Slots.** 1: the cheapest buyable candidate, or the linked product (a listed product that
    `names_product` matches to it is dropped). 2: the durable pick, over the budget only when judged
    `long`. 3: the durable pick within budget. Each slot leaves out candidates already taken; order
    `long`, `medium`, `unknown`, `short`; ties to the lower price, then listing order. When no
    judgement decides, a `decided` entry says the slots were filled by price.
14. **Warnings and wording.** `no_options_found` chooses its words from: the searches or every page
    fetch failed; none met the answers (`{n}` counting candidates read); none in stock; nothing with a
    euro price. "Confirm the current price" ("Prices change") stands once, for every option, and
    "price seen at {shop} via {comparison site} on {date}" stands beside each price.

**Tasks**

15. **Two roadmap tasks, one session each**, since `/task` takes one task to its "Done when", its
    box and one pull request. **Task 1.13:** items 1 to 14 on fixtures, with the evidence and
    findings searches for these product names recorded (about 6 to 10 Tavily credits), and
    `option_research.md`, `data_sources.md` and ADR 0007 rewritten for what landed; merged only when
    green. **Task 1.15:** the words in `wording.md` and on the report, the live run of the three
    tuned categories and the fixtures recorded again. If task 1.13 ends without a green pipeline,
    its branch is closed with a note here, and task 1.15 does rows 3, 4, 5, 7 and 16 of
    `docs/findings/task_1.10.md` from `main` instead. This replaces the "at most two sessions" of
    the 1.10 "Decided" item 14.
16. **Unchanged or left over:** the linked product's own path, except the stock mark; ADR 0007 also
    records dropping the roundups and the Firecrawl cap of 12. The supervisor's category losing
    "cordless" is added to `left_over_tasks.md` under task 1.10 by task 1.13 (its step 11).
