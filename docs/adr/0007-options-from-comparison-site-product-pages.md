---
status: accepted
---

# Options come from comparison sites' listing pages, priced on their own product pages

Option research no longer searches for candidates in roundups and then for their prices. It
reads the listing pages of two Dutch comparison sites, beslist.nl and kieskeurig.nl, whose
`ItemList` names the products sold here, and prices each candidate from the JSON-LD offer on its
own product page, read with Firecrawl before selection. Every price on the report is an offer a
shop makes now; none comes from a search snippet. This supersedes the step order of
`docs/adr/0004-firecrawl-confirms-shop-prices.md`, which read a page only to confirm a price
already selected.

Why: the live runs of task 1.10 gave 0 to 3 options per category, lost at four steps (US models
from English roundups, names the price check refused, listing pages at "Confirm", stock), and the
prototype of task 1.12 found at least five buyable candidates within the budget in each tuned
category on these two sites (`docs/findings/task_1.12.md`). The roundups named none of the 27
products read there.

Decided in the grill and panel of task 1.12 ("Decided", items 1 to 16) and built in task 1.13.
The steps are in `docs/architecture/option_research.md`.

## What it changes

- **Removed:** the two roundup searches, the shortlist, the `"{product} prijs"` price search and
  "Confirm", with the search purposes `discovery` and `price`. Durability hints went with the
  roundups; the durability judgement, by name and then by product page, now orders the slots.
- **Firecrawl reads more:** at most 12 pages per analysis, the listing pages included and cached
  pages counted, at most 3 at once, stopping at 5 buyable candidates. A 429 is retried once
  after its Retry-After or a pause. ADR 0004 capped Firecrawl at 5 reads of selected options.
- **The offer decides:** the price without shipping is the option's price; the shipping it states
  counts toward the budget; an option out of stock or sold without a part it needs is marked,
  last in its slot and never the baseline.
- **bol.com and Amazon** are reached through the comparison sites' offers, not read themselves;
  the amendment of ADR 0004 about them no longer applies to option research.

## Considered options

- **Keep the search prices and confirm more pages** (ADR 0004 widened). Rejected: the candidates
  were the problem, not only the prices; the roundups named products not sold here.
- **Fall back to search prices when too few candidates are buyable.** Rejected: the existing
  warnings say so, and a search price is the unchecked figure this replaces ("Decided", item 3).
- **tweakers.net and klarna.com as well.** Rejected for now: neither gave a listing page through
  the listing search in task 1.12.
- **The first result with an `ItemList` per site, whatever it is.** Rejected in task 1.13: on the
  recorded searches that was a page filtered on a brand or a search word; a listing page of the
  whole category is the first result that no URL rule of the site rules out
  (`COMPARISON_SITES` in `config.py`). Task 1.15 added that a beslist.nl list filtered that way
  stands for its category, cut before `/r/` or `/c/`: the live kettle search found nothing else.
