# Findings before task 1.8.5: what a price page tells Firecrawl

A live check on 17 October 2026, made while settling the design of task 1.8.5, before any code.
The question from the roadmap: does bol.com's JSON-LD carry `availability` and the seller, and
does a comparison site's `AggregateOffer` confirm a price? The pages were the ones that priced
options in task 1.8.2, read with the app's own Firecrawl request (`markdown` and `rawHtml`)
from a throwaway script. **3 Firecrawl credits** in all; the failed reads cost nothing.

| Page | Read | JSON-LD | Stock and seller |
|---|---|---|---|
| bol.com, Fellow Corvo EKG | No: HTTP 500 `SCRAPE_ALL_ENGINES_FAILED`, also on the stealth engine | In a browser: one `ProductGroup`, its `AggregateOffer` with `lowPrice` €152.66, `offerCount` 1, no `availability`, no seller | The page says "Niet leverbaar" |
| bol.com, Russell Hobbs 28081-70 Structuur | No: the same failure | Not looked at | Not looked at |
| amazon.nl, Tramontina Professional | Yes, 1 credit, status 200 | None: no `ld+json` block in 1.5 MB of HTML | Text only: "In stock" per size in a variant list |
| amazon.com.be, OXO Brew kettle | Yes, 1 credit, status 200 | None | Text only: "Op voorraad", "Verzonden en verkocht door Amazon.com.be"; also "no more in stock" in a review and bundle totals ("Totaalprijs") |
| beslist.nl, Fellow Corvo EKG Pro | Yes, 1 credit, status 200 | A `Product` with an `AggregateOffer`: `lowPrice` 149, `highPrice` 200, `offerCount` 7, and a nested `offers` list | Per shop in the JSON-LD: `availability`, `price`, `seller` (Galaxus.nl €149, bol.com €167.99, Amazon Partners €172.82, all `InStock`), shipping and return policy |

What follows from it:

- **bol.com cannot be confirmed.** Firecrawl cannot read it, and its JSON-LD would not have
  helped: an aggregate price with no stock, on a page that is not deliverable. A failed read
  keeps the search price, so the Corvo would have stayed at €86,98. bol.com is excluded from
  the price search instead.
- **Amazon publishes no offer data.** Reading it costs a credit and gives nothing code can rely
  on; under the first rule ("no JSON-LD offer: drop as not a shop page") every Amazon price
  would have been dropped. Amazon pages are not read, and their search price stays unconfirmed.
- **A comparison site with nested offers confirms by itself**: the cheapest new offer in stock,
  with its seller. An aggregate with only a `lowPrice`, as on bol.com, confirms nothing.
- **A variant risk the name check does not catch.** beslist.nl's page for the Corvo is the
  Corvo EKG **Pro**. The candidate's name, "Fellow Corvo EKG", has no model number, so the name
  check passes the Pro.

The decisions are in `docs/adr/0004-firecrawl-confirms-shop-prices.md` (amendment) and
`docs/architecture/option_research.md` ("Confirm").


## The recorded price pages (during the task)

Read on 17 October 2026 with the app's own Firecrawl request, to record the fixtures: the price
pages the recorded price searches of task 1.8 lead to, after bol.com's results are dropped.
**13 Firecrawl credits**, one per page, all answered; 11 pages are committed, trimmed, in
`tests/fixtures/firecrawl/`, and the two no test quotes were deleted (beslist.nl's Corvo EKG
Pro, which shows again what the check before the task found, and a ubuy.co.nl page with no
product data).

| Page | What its JSON-LD gives | What "Confirm" does |
|---|---|---|
| beslist.nl, Tramontina Professional 20 cm | `AggregateOffer` with 4 nested offers, all `InStock`; cheapest €39.95, Kookexpert.nl | Confirmed, "sold by Kookexpert.nl via beslist.nl" |
| kieskeurig.nl, Tramontina Professional 24 cm | Nested offers at €32.07, sellers Amazon and Amazon Marketplace | Confirmed at €32.07 |
| kieskeurig.nl, Hario Buono 1 L | Nested offers; cheapest €44.26 from "bol.", with a `StrikethroughPrice` of €52 in its `priceSpecification` | €44.26: the strikethrough price is not read |
| fonq.nl, GreenPan Stanley Tucci set | One `Offer`, €158.95, `OutOfStock` | Dropped: not in stock |
| profilec.be, Demeyere Atlantis 7 28 cm | One `Offer`, €234.99, no `availability`; no stock words in the text | Confirmed at €234.99 (search: €237.95), stock not stated |
| vanpommeren.nl, Hario V60 Drip Kettle Buono | A `ProductGroup` whose offers are on its two variants, €55.00 and €65.00, `InStock` | Confirmed at €55.00 |
| coffeefriend.nl, Fellow Corvo EKG Pro | An `Offer` whose price is only in a `UnitPriceSpecification`, €200.00, `InStock` | Confirmed at €200.00 |
| knibble.nl, Hario Buono V60 | No product: organisation, breadcrumb and FAQ only; the text says "uitverkocht" | Dropped: not a shop page |
| beslist.nl, Russell Hobbs listing (`/c/`) | No product: organisation and breadcrumb | Dropped: not a shop page |
| beslist.nl, GreenPan listing (`/c/`) | An `ItemList` of products, none the page's own | Dropped: not a shop page |
| show63.ru, the Ryobi's page in task 1.8 | Firecrawl answered 200 with the page's 404 inside | Dropped: not found |

What follows from it:

- **Two forms of offer the first design did not name**: a `ProductGroup` that offers its
  variants, and a price only in a `priceSpecification`. Both are read now; a typed
  specification (a strikethrough price) is not.
- **No hand-edited page was needed.** fonq.nl showed out of stock, and profilec.be and
  kieskeurig.nl showed a changed price. Only an `AggregateOffer` with only a `lowPrice` (bol.com's
  form) is built in its test.
- **A 404 page drops its option**, decided during the task: it was read and holds no offer. The
  other failures keep the search price unconfirmed.
- **Listing pages are caught on beslist.nl**, the case of task 1.8.2's left-over item: neither
  beslist.nl listing has a product of its own. An Amazon search page is not caught, because no
  Amazon page is read (`left_over_tasks.md`).
- **A comparison site may confirm an offer from a shop that cannot be read**: kieskeurig.nl's
  cheapest Hario offer is bol.com's, and its Tramontina offers are Amazon's. The offer, its
  stock and its seller come from the comparison site's data, so they are confirmed there.
