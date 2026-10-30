# Findings from task 1.13: option research from comparison sites, on fixtures

Built on 23 and 24 October 2026, as decided in task 1.12 (`docs/findings/task_1.12.md`,
"Decided", items 1 to 14) and in `docs/adr/0007-options-from-comparison-site-product-pages.md`.
Nothing here was run against live models: every model reply in the tests is written by hand,
from what the recorded pages say. The live run, with the real judgements and page reads, is
task 1.15's.

**Result:** offline, with the fixture twin, each tuned category gives three product options in
the terminal app, each priced from an offer on a comparison site's product page
(`tests/test_cli.py`, `test_each_category_prints_its_options_priced_from_a_product_pages_offer`).

| Category | Request | Options |
|---|---|---|
| frying pan | "I need a new frying pan, budget 50 euro" | GreenChef €23.99, de Buyer €51.95, Tefal Renew ON €35.99 |
| kettle | "a kettle that boils quickly, around 60 euros" | Midea €27.99, Inventum €28.95, Severin €29.95 |
| drill | "a cordless drill for occasional DIY at home, max 120 euro" | Aerotec €48.99, EasyDrill €49.99, Metabo €63.27 |

The de Buyer is the durable pick over the budget (judged `long`, under 3 times the budget). The
kettle's slots are filled by price, because the hand-written judgement tells no kettle apart.
The drill's five bare tool bodies on the recorded pages ("Basic Body", "Solo", "Body": sold
without battery and charger) are marked `incomplete` and fill no slot while buyable drills are
left.

**Credits:** 19 Tavily, 0 Firecrawl, 0 Nebius. The roadmap estimated 6 to 10 Tavily credits; the
developer chose to record both the evidence and the findings search of every option (18), and
one listing search for the drill's fallback. The listing pages and product pages are the ones
task 1.12 recorded.

## The drill's local term is in too few listed names

The hand-written term of task 1.12, "accuboormachine", stands in 2 of the 34 names on the drill's
two listing pages, under `MIN_NAMES_WITH_TERM` (3). So the listing search runs again with the
category, "drill kopen" (recorded as `tests/fixtures/tavily/drill-listing-pages-category.json`,
1 credit). It gives no listing page: its beslist.nl results are a product page (`/p/`, added to
beslist.nl's `not_listing` rules for it), a search page (`/r/`) and a page filtered on a brand
(`merk~`), and its kieskeurig.nl results are all product pages (`/product/`). The first list
stands, with a `decided` trail entry saying so. Which term the model gives live, and whether it
stands in enough names, is task 1.15's to see.

## Most evidence searches find nothing for a product page's name

The evidence and findings searches fill their templates with the option's name, which is now the
product page's JSON-LD name: long, with sizes, colours and selling words.

| Option | Evidence results | Findings results |
|---|---|---|
| GreenChef Diamond Inductie Koekenpan - Ø24 cm - Zwart - PFAS-vrij | 0 | 8 |
| de Buyer Mineral B Element Koekenpan - Ø 26 cm | 8 | 8 |
| Tefal Renew ON Keramische Koekenpan - 24 cm - Inductie - Grijs | 2 | 8 |
| Midea - Roestvrijstalen waterkoker - Wit - 1,5 liter - 2200 W - Met temperatuurinstelling en veiligheidsfuncties | 0 | 1 |
| Inventum HW817D Waterkoker - 1.7L - RVS/Zwart - 2200W - Met Warmhoudfunctie | 0 | 8 |
| Severin WK 9342 Waterkoker - 1L - 2400W - Zwart/RVS | 0 | 8 |
| Aerotec Pneumatische boormachine 6.3 bar | 0 | 8 |
| Bosch - EasyDrill 18V-38 - Accu-schroefboormachine - 18 V - 2.5 Ah Li-ion | 0 | 1 |
| Metabo SBE 650 Klopboormachine - Kartonnen tandwielhouder - 1 stuk | 0 | 8 |

 7 of the 9 evidence searches
(`"{product} durability lifespan warranty"`, with the Netherlands boost) returned nothing; the
findings searches, worded the same way, mostly did. An option with no evidence keeps a lifespan
of kind `model_estimate`, so the report still has its figures, but rests on less. Searching with
the brand and model only (from the JSON-LD brand and the model-number words `checks.py` already
finds) is the likely fix; it changes the search queries, so it belongs with task 1.15's live run
and its fixtures recorded again.

## The outlier rule drops the WMF's two lowest offers

On the recorded WMF frying pan page, two offers at €44.99 stand beside nine at €76.95 or more.
Both are under 60% (`PRICE_OUTLIER_SHARE`) of the median of all the page's offers, so both are
dropped as the decided rule says, and the cheapest offer left is chosen. Whether €44.99 was a
real sale or a wrong listing cannot be told from the recording; the live run should look at the
page.

The rule first took the median of the *other* offers. A pair of offers at one low price was then
each judged against a median without itself, which on a page of few offers can put both under
the line where counting them would not. The median now counts every usable offer, itself
included, and needs at least `MIN_OTHER_OFFERS` (3) others (`calc/offers.py`, with a test).

## Two lists merged two different products

The lists are merged by `same_product` (one name names the other, by brand). On the recorded
kettle lists two products were merged that are not the same:

1. **Demeyere Proline 7 and Demeyere Apollo 7** shared only "7" and the size "1.7 L". Sizes (a
   measure or a word in `SIZE_UNITS`) no longer count as name words.
2. **The same two again, on "waterkoker",** when the listing search ran with the English
   category: only the category's words were left out of the comparison, so the local term's word
   counted as a name word. The words of both the category and the local term are now left out.

And left-over item 7 of task 1.12: "Makita DHP 490 Z" matched "Makita DHP 482 Z" on their other
words. A model number written in parts now counts as one word (`_joined` in `checks.py`): runs of
two or three short words or numbers, one of them a number of at least three digits.

## For task 1.15

- The live run sees what the hand-written replies stand in for: the local term the model gives,
  both durability judgements, and the page read's `sells`, `incomplete` and piece count.
- The evidence search query for a long product name (above).
- The WMF page's €44.99 offers (above).
- The report does not yet show shipping, the marks, or where and when a price was seen in the
  decided words; "Confirm the current price" stays only for a linked product until the single
  "Prices change" line replaces it.
