---
status: superseded by 0007
---

> Superseded in task 1.13 by `docs/adr/0007-options-from-comparison-site-product-pages.md`:
> option research now prices every candidate from its comparison site's product page before
> selection, and "Confirm" is gone. The reasons below for reading the offer in code still hold.

# Firecrawl confirms the price of a selected option on its shop page

Option research selects on prices read from Tavily search results, then reads each selected
option's price page once with Firecrawl to confirm the price and the stock. Until now Firecrawl
read only a link the user pasted; this is the one other use, and it stays narrow: only the
pages of selected options, at most 5 per analysis, cached per URL for a day, never a crawl.

Why: a search result holds the parts of a page that match the query, not its stock or its
current offer. In task 1.8 bol.com's Fellow Corvo EKG passed every price check at €86,98
while the page said "Niet leverbaar" and other shops asked €175 to €200, and a scraped page
that was not a shop (show63.ru) passed too. A wrong price decides the baseline, the budget mark
and every figure in `calc/`. The page's JSON-LD offer gives the price, the availability and
often the seller, read by code with no model, for one credit.

The steps are in `docs/architecture/option_research.md`; the work is task 1.8.5.

## Amendment: bol.com and Amazon (before task 1.8.5)

The live check before task 1.8.5 (`docs/findings/task_1.8.5.md`) found that the two sites that
priced most options in task 1.8.2 cannot be confirmed this way:

- **bol.com refuses Firecrawl** on every page tried, also with its stealth engine. Its JSON-LD,
  seen in a browser, is a `ProductGroup` whose `AggregateOffer` has only a `lowPrice`, with no
  availability and no seller, while the page says "Niet leverbaar".
- **Amazon pages are read but hold no JSON-LD.** Stock and seller stand only in the page text,
  next to review text and bundle totals.

A comparison site such as beslist.nl does work: its `AggregateOffer` lists each shop's offer
with its price, availability and seller.

So:

- **bol.com is excluded from the price search.** Its prices cannot be confirmed, and its
  snippets gave the two worst prices of task 1.8.2 (the Corvo, and a body-only drill at €25,95).
- **Shops that publish no offer data (`amazon.*`) are not read.** Their search price is kept
  and stays unconfirmed, with "Confirm the current price" on the check-before-you-buy list.
- **A comparison site confirms through its nested offers**: the cheapest new offer in stock.
  An aggregate with only a `lowPrice` confirms nothing, because a "lowest price" is rejected in
  search results too.

## Amendment: a page with no offer is still dropped; the next price is tried (task 1.8.7)

The live runs of task 1.8.3 dropped three priced candidates whose price pages held no JSON-LD
`Product` offer (beslist.nl, supersales.nl, grizzlytools.shop), among them the only cheap drill.
Keeping such a page at its search price was considered and rejected: the cached pages show all
three were listing or search pages (a brand-filtered category on beslist.nl and supersales.nl,
"Artikel gevonden 1 - 20" on grizzlytools.shop), and the drill's €18,69 was the price of a
drill chuck on that search page. The drop was right each time; the fault is that a listing
reached selection.

So, in task 1.8.7:

- **A dropped candidate tries its next price once.** The price rule runs again on the same
  read's accepted amounts without that site; the new price page is read like any other, within
  the 5 reads.
- **An Amazon price must come from a product page** (`/dp/` or `/gp/product/`), or it is refused
  at price acceptance: Amazon pages are never read, so a search page's price (the Fissler at
  €16,99 on amazon.de in task 1.8.2) would otherwise reach the report unchecked. No general list
  of listing-URL patterns: it cannot cover every shop, and "Confirm" already catches a listing
  on every page it reads.

## Considered options

- **Search prices only, with stricter checks.** Rejected: no check on a snippet can see the
  stock, and the outlier rule needs at least two other prices in the same results.
- **Confirm every priced candidate.** Rejected: up to six page reads where three decide the
  report; confirming after selection and selecting again costs 3 to 5.
- **A screenshot of the page.** Rejected as a source: the price would be read by a model. It
  may be shown as evidence beside the price (`ROADMAP_OPTIONAL.md`, "A screenshot of the shop
  page as evidence").
- **Wait for the eBay task.** eBay becomes the first choice for a new price, but most products
  will still be priced from search, so the fallback needs the check too.
- **Keep bol.com and Amazon as they come** (amendment). Rejected: a failed bol.com read keeps
  the unconfirmed price, so the Corvo stays at €86,98, and every Amazon page would be dropped
  as holding no offer.
- **Read Amazon's stock and seller from fixed phrases in its text** (amendment). Rejected: no
  price is published as data, and review text gives false hits.
- **Confirm every option on a comparison site** (amendment): one more search per option to
  find its beslist.nl or kieskeurig.nl page, then a read. The best data, but it doubles the calls
  and adds a search purpose; left for later.
