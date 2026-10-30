# External data sources

Read this when working in `src/shopper/tools/`, on a research loop (category research, option
research; its steps are in `option_research.md`), on the eBay integration, or on anything that
calls a service outside this repo.

Each kind of data has one source. Do not add scrapers or other providers without asking.

| Need | Source | Key in `.env` |
|---|---|---|
| Category research and option research: decision factors, product options, prices of new options, durability evidence, recurring costs, EPDs | Tavily search | `TAVILY_API_KEY` |
| Listings, used and refurbished; from the eBay task on, also the first choice for the price of a new option | eBay Buy API (Browse API), marketplace `EBAY_NL` first, then other EU marketplaces | `EBAY_CLIENT_ID`, `EBAY_CLIENT_SECRET` |
| A product link the user pasted, and the comparison sites' listing pages and product pages | Firecrawl, one page per request | `FIRECRAWL_API_KEY` |

Dutch marketplaces (Marktplaats, Vinted) are out of scope: no usable API, scraping blocked.

## Rules for every source

- **Behind an interface.** Each source implements a small `Protocol` and has a fixture-backed
  twin that reads recorded responses from `tests/fixtures/`. The default test run uses the twin.
- **Live or fixtures is an explicit choice.** `SHOPPER_SOURCES` is `live` (the default) or
  `fixtures`. There is no silent fallback: in live mode a missing or rejected key is a
  configuration error that raises, because nothing can run. Running the demo from fixtures is a
  deliberate switch, so a report never mixes real and recorded research unnoticed.
- **Cache on disk.** See "Cache and fixtures".
- **Typed failure.** A tool returns a result that says what went wrong. It does not raise
  through the agent. See "Failure kinds".
- **Count usage.** Each result carries the credits the service reported. Code writes one log
  line per agent per analysis: each graph node meters the tool view it hands its agent
  (`tools/usage.py`) and logs what it used to the logger `shopper.usage`, for example "tavily
  credits used by brief: 2". The terminal app shows these lines on the error stream. Credits are
  not put on the trail, which is shown to the user.

## Research rules

These hold for every loop that reads search results: category research (brief agent), option
research (TCO analyzer) and the tier 1 LCA search. Why code drives the loop is in
`docs/adr/0003-code-driven-research-loop.md`.

- **Code runs the loop.** Code builds the search query, searches, and gives the results to the
  model, which returns structured output. The model does not call tools.
- **Search queries come from code templates**, filled only with the category, a product option's
  name, or the text of a choice the brief agent wrote. The user's input never reaches a search
  query. A stated answer enters a search query only when code has mapped it onto a choice;
  otherwise it is applied when the model reads the results.
- **The model may propose one follow-up.** A read also returns `gaps` (what the model expected
  to find and the results did not cover, each with a reason) and an optional `follow_up_query`.
  Code runs the follow-up when there are gaps, or too few sourced values survive (for the brief:
  fewer than three factors), and a call remains. The follow-up must contain the category or the
  option's name and be at most 120 characters, and it is checked like every string a model
  writes (no currency marker or generic environmental term), or it is discarded; unlike other
  model-written strings it may hold plain digits, since a size or a model number narrows a
  search ("frying pan 28 cm", "Russell Hobbs 28081-70"), and a currency marker keeps a price out
  of it (task 1.11; in task 1.10, 3 of 4 follow-ups lost to a digit). It gets
  a `decided` trail entry. The model that writes it sees only the category and the search
  results. The agent passes it to the web search marked as a follow-up (`follow_up`, the mark
  for any search query a model wrote); the fixture twins answer such a query only when it was
  recorded, so a follow-up comes back as `not_recorded` with them and is skipped with an
  `excluded` trail entry.
- **The second read replaces the first, unless it kept fewer.** It covers all search results so
  far, de-duplicated by URL before they are numbered. It stands when it kept at least as many
  cited items as the first (factors for the brief; a tie goes to
  the second); otherwise the first stands, with a `decided` trail entry that gives both counts
  (task 1.11: in task 1.10 the drill's second read kept no factor and replaced a first of 8). A
  gap that survives the read that stands is written to the trail. A gap never becomes a factor
  or a value.
- **Cite by number, with a quote.** The model cites a search result by its number and returns a
  short supporting quote. Code keeps the value only if the quote is found in that result's
  text, after the same normalisation on both sides (case, whitespace, non-breaking spaces,
  curly quotes, and every kind of hyphen or dash as a plain hyphen); punctuation at the two ends
  of the quote does not count, so a quote that ends with a full stop where the text goes on
  after a comma is found. Otherwise the value is dropped with an `excluded` trail entry. The
  live runs of task 1.7 showed both: the model writes a non-breaking hyphen for a plain one, and
  ends a quote with a full stop. The check is `is_quoted` in `agents/shared/research.py`; the
  normalisation is `find_phrase` in `agents/shared/phrases.py`, which the budget phrase and a
  stated requirement's phrase use too.
- **A number must be in the quote.** Any amount, count of years or other number must appear in
  its quote. If transcripts show the model paraphrasing too often, the check for text values
  may be relaxed to "the cited result exists"; it is never relaxed for a number.
- **The model does no arithmetic.** For a recurring cost it returns the amount, the interval and
  any pack count, each quoted, and code reads them and computes the yearly figure. With no
  interval in the source, the cost stays missing (`option_evidence.md`, "Evidence").
- **An ellipsis in a quote** joins parts that are each found in order, for a text value only. A
  quote that code reads a number from holds the number and its unit in one part, so two true
  parts cannot make a claim no source states.
- **Who is speaking.** Each citation carries `stated_by`: `tester`, `owner`, `manufacturer` or
  `seller`, judged by the model and recorded on the trail entry. For a finding, code sets the
  kind from it (`tester` a test, `owner` an owner report), and a statement by a manufacturer or a
  seller is not a finding (`option_evidence.md`, "Findings"). A manufacturer's claim is worded as
  "the manufacturer states" (`docs/eu_market.md`).
- **Which results to use** is the model's judgement in the read prompt: independent testers,
  consumer organisations and manufacturer manuals before shop pages; off-topic results are
  ignored. The trail records how many results were shown and how many were cited. Tavily's
  `score` is not used as a threshold; it is not comparable between search queries.
- **The quote is not shown.** It exists for the check and for debugging. The user sees the
  summarised value and the link (`docs/product.md`: summarise and link, never copy). A finding's
  quote is not on the trail either: after its checks it goes to a debug log line and is dropped
  (`docs/adr/0005-findings-summarised-quote-logged.md`).
- **Money from search.** An option's price is accepted in euro only. A recurring cost in USD or
  GBP is converted at a fixed rate and labelled; any other currency is dropped with an
  `excluded` trail entry (`docs/adr/0002-fixed-rate-conversion-recurring-costs.md`). One amount
  parser in `calc/` reads every amount: a budget, a JSON-LD price, a price or a cost in a
  search result.
- **Each search gets a trail entry** of kind `found`: the search query, the number of results,
  and whether it came from the cache.

## Search purposes

Every search has one purpose. The purpose sets the template, the language, the country boost
and the excluded domains, which all live in `config.py`. A template is written in its purpose's
language and only the category, an option's name or a choice's text is filled in
(`SEARCH_TEMPLATES`; the brief agent's two so far).

| Purpose | Used by | Language and country | Excluded domains |
|---|---|---|---|
| Category, what to look for: "{category} buying guide what to look for" | Brief agent | English, no country | Social, video, Pinterest, forums, marketplaces and shops |
| Category, consumables and care: "{category} care maintenance and replacement parts" | Brief agent | English, Netherlands boost | The same |
| Listing pages: "{term} kopen", the local category term, or the English category when the term stands in too few listed names (task 1.13) | TCO analyzer | Dutch, Netherlands boost | Restricted to the comparison sites instead (`COMPARISON_SITE_DOMAINS`: beslist.nl, kieskeurig.nl; `docs/findings/task_1.12.md`, "Decided", item 2) |
| Evidence: durability and recurring costs: "{product} durability lifespan warranty" (task 1.8.3) | TCO analyzer | English, Netherlands boost, full page text | Social, video, Pinterest, marketplaces and every eBay domain (task 1.8 found ebay.co.uk and a Facebook post) |
| Findings: what testers and owners report: "{product} long term review durability", snippets only (task 1.8.4) | TCO analyzer | English, no country | Video, Pinterest, marketplaces and shops (`SHOP_DOMAINS`: retailer review pages are not fetched, `docs/product.md`; the read also judges a shop's page no list names, `option_evidence.md`, "Findings"). Reddit, forums and comparison sites are allowed, because owner reports are found there |
| Published footprint (EPD) | LCA agent, tier 1 | Decided in task 1.9 | Decided in task 1.9 |

Code also drops a purpose's excluded domains from every search's results (task 1.8.5), so
a recorded search made before a domain was excluded answers as a live one does.

No search passes a preferred list of independent testers. The live check in task 1.6 sent the
list (Consumentenbond, Test-Aankoop, Stiftung Warentest, Which?, RTINGS, iFixit and a few English
test sites) with `include_domains_mode="prefer"`: it was accepted, but no listed site came back
with or without it, so the preference stays in the findings read's prompt only (task 1.8.4). The
list stays in `config.py` (`PREFERRED_TESTER_DOMAINS`) for that prompt. The discovery and price
searches of tasks 1.8 to 1.12 are gone since task 1.13
(`docs/adr/0007-options-from-comparison-site-product-pages.md`).

## Option research

The steps of option research (listing pages, judgement by name, product pages, judgement by
page, select, evidence, findings), which offer stands on a product page, how product options are
selected and what a lifespan needs are in `option_research.md`.

## Calls per analysis

Each agent may call a source at most this many times in one analysis. Code enforces the limit,
not the prompt: the graph hands each agent a freshly limited view of the tool every time its
node runs, so the count is per invocation and is not kept in the graph state. Once the limit is
used, the tool returns `limit_reached`, and the agent continues with what it has and records
the gap in the trail. Cache hits do not count.

| Agent | Source | Most calls per analysis |
|---|---|---|
| Brief agent | Tavily search | 3: two templates and one follow-up |
| TCO analyzer | Tavily search | 14: 2 listing searches (the second with the English category), 3 evidence, 3 findings, and 6 for slots refilled after an answer |
| LCA agent, tier 1 (an optional layer; tier 3 searches nothing) | Tavily search | 1 per option, so 3, once tier 1 is built |
| Second-hand agent | eBay Browse | 1 per marketplace searched, so 3 |
| TCO analyzer, for listing and product pages | Firecrawl | 12 (`TCO_FETCH_LIMIT`); the reads also stop at 12 pages counted with cache hits, at most 3 at once (`option_research.md`, "Product pages") |
| Supervisor, for a pasted link | Firecrawl | 1 |
| Conversation agent, per message | Tavily search | only through the agents it reruns; their limits apply again, and their cache is reused |

An uncached analysis therefore uses at most 17 Tavily credits, 20 once LCA tier 1 is built, and
at most 13 Firecrawl credits. The plan has 1,000 Tavily credits a month and a one-off 8,000 from
the hackathon, about 500 such analyses; a normal run uses fewer,
because the category searches are cached and a follow-up runs only when there are gaps. The
limits live in `config.py`.

**Daily ceiling.** A small ledger file in the cache folder (`.cache/live/tavily_credits.json`,
today's total only) adds up the credits Tavily reports per day. Past `TAVILY_DAILY_CREDIT_LIMIT` the tool returns `daily_limit_reached` without
calling Tavily. It applies everywhere, with the value read from the environment: 100 by default
for development, set explicitly for task 1.10 and for the deployment. Pay-as-you-go stays off
on the Tavily account, so running out returns `credits_exhausted` and never a bill.

## Cache and fixtures

- **One stored format.** A cached response and a fixture are the same file: the request as
  readable fields (search query or URL, the parameters, the purpose), `retrieved_at`, and the
  response. A live response becomes a fixture by copying and trimming the file.
- **Cache key.** The normalised search query (trimmed, lower-cased, whitespace collapsed) plus
  every parameter that changes the results; for a page, the URL. The cache is in `.cache/`,
  which is git-ignored, with files named by a hash of the key. Each mode has its own folder,
  `.cache/live/` and `.cache/fixtures/`, so recorded research never answers a live run. An
  entry's `retrieved_at` is the time it was stored, so a fixture's recorded date does not age it.
  After editing a fixture, delete `.cache/fixtures/`, or the cached copy keeps answering.
- **How long an entry lasts** depends on the search purpose: a listing pages search and a
  fetched page last one day, since they show prices; every other search does not expire. Clearing the cache is deleting
  the folder.
- **What is cached.** Successes, including a search with zero results. Failures are not.
- **Fixtures** in `tests/fixtures/` have readable names and are matched on the search query and
  purpose, not on a hash, so changing a parameter in `config.py` does not orphan them. A miss
  in the fixture twin is a programmer error and raises with the search query in the message; it
  is never returned as `not_found`. The one exception is the app run on the fixtures
  (`SHOPPER_SOURCES=fixtures`, `sources_from_env`), with the real agents or the stubs: a page no
  fixture holds is `not_recorded` there and the run goes on, since the live model can pick a
  candidate no recording read and a user can paste any link; the tests' twin still raises (task
  3.2.1).
- **Failure paths** (rate limit, credits, timeout, a broken body) are tested at the HTTP layer
  with an injected transport, not through the twin.
- **What is committed.** Only a few fixtures: the three tuned categories and what the tests
  quote. Each keeps real URLs and titles, with the content cut to the sentences the tests use.
  The cache is never committed. Tavily's terms forbid redistributing the service and say
  nothing about stored output; this is the cautious reading. The six category fixtures
  (frying pan, kettle and drill, each with both brief templates) are trimmed copies of the live
  responses of task 1.7, with at least three quotable factors per category. The typical yearly
  cost has the three brief searches of the electric toothbrush recorded in task 1.8.1 (both
  templates and the read's follow-up, `tests/fixtures/tavily/electric-toothbrush-*`), the one
  live category whose results stated a consumable's price with an interval; each result keeps
  its first sentence, and the one the test quotes keeps that sentence
  (`docs/findings/task_1.8.1.md`). The Firecrawl fixtures for a pasted link are still
  hand-written with example.org URLs (`left_over_tasks.md`, task 1.10); the price pages of task
  1.8.5 that the page fetch's tests read are real, trimmed to the JSON-LD product data and the
  page text's first heading and lines about stock. No copy was hand-edited; the one case no live
  page showed, an `AggregateOffer` with only a `lowPrice`, is built in its test.

  Option research runs on what task 1.12 recorded for the three tuned categories: the listing
  pages search and its open control search (`tests/fixtures/tavily/{category}-listing-pages.json`,
  `-control.json`, each result cut to its first sentence), and 33 pages of beslist.nl and
  kieskeurig.nl (35 since task 1.10 recorded two more drills, read once the bare Makitas no
  longer count as buyable)
  (`tests/fixtures/firecrawl/{category}-{read number}-{site}-…-page.json`), trimmed
  to the JSON-LD product data, shoppers' reviews and pictures left out, and the page text's first
  heading and stock lines (`docs/findings/task_1.12.md`). Task 1.13 added the drill's listing
  search with the English category (`drill-listing-pages-category.json`, every snippet kept; it
  finds no listing page) and the evidence and findings searches of the nine options the three
  tuned categories show offline (`tests/fixtures/tavily/{category}-evidence-…`, `-findings-…`,
  every snippet kept and full page text cut to `RAW_CONTENT_MAX_CHARACTERS`), recorded with
  `scripts/record_fixtures.py` (`docs/findings/task_1.13.md`). Task 1.15 recorded the evidence
  searches again for the search names (`search_name`), the searches of the options that changed
  (the WMF, whose sale now stands, and the drill's three), beslist.nl's drill category with three
  of its product pages (`drill-15` to `drill-18`, written from the day's live cache with
  `--cached`), and the braadpan, hapjespan and wok pages again with their text as far as the
  page read sees it (`--with-text`), so a test can replay that read (`docs/findings/task_1.15.md`).
  Task 1.14 recorded the WMF (beslist.nl) and GreenChef pages again the same way, from the live
  cache, and the real model's page read of those five pages, each with its prompt and input
  (`tests/fixtures/nebius/page-read-frying-pan-*.json`, `scripts/temperature_check.py record`),
  which a test replays (`docs/findings/task_1.14.md`).
  The evidence queries are the options' search names and the findings queries their names, so
  when the options change (other judgements, a re-recorded page) they are recorded again; an
  offline test fails when a tuned category's option gets `not_recorded` for either.
  No model reply is recorded for the searches: the offline runs answer the reads by hand. The discovery,
  price and findings searches of tasks 1.8 to 1.11, their price pages and the model replies over
  them went with the steps they served in task 1.13.
- **The brief store** keeps what category research produced, so a category is researched once:
  one file per category in `.cache/<mode>/brief/` (`tools/brief_store.py`), holding the
  researched factors, a phrased question per factor that can be asked about, the picked usage
  frequencies, the local category term and the trail entries of the research. A brief is stored
  only when both template searches, every read, the phrasing call and the call for the local term
  succeeded. With three or more factors it
  does not expire; with fewer, none included, it lasts one day. Its key is the normalised
  category plus a hash of the prompts, the search templates, the fixed words a stored question
  holds, the fixed rates a stored typical yearly cost was converted at, the two model IDs and the
  quote-check rule, so changing any of those researches every category again. On a hit the
  trail replays the stored entries after one that says they come from the cache and when they
  were researched. Which questions are asked is decided after reading, not stored.

## Failure kinds

| Kind | Tavily | Firecrawl |
|---|---|---|
| `not_found` | The search returned no results | The page answered 404, also when Firecrawl itself returned 200 with that status inside |
| `blocked` | Not used | The site is not supported (403), or the page answered 403 inside a 200 response |
| `unavailable`, for a page | Not used | The page answered another status of 400 or more inside a 200 response |
| `rate_limited` | 429, after one retry when `Retry-After` is 5 seconds or less | 429, after one retry after `Retry-After` (up to 60 seconds) or a 20 second pause |
| `timed_out` | No answer within 20 seconds; no retry | 408, or no answer within the timeout |
| `credits_exhausted` | 432 or 433 | 402 |
| `daily_limit_reached` | The local daily ceiling | Not used |
| `limit_reached` | The agent used its calls for this analysis | The same |
| `not_recorded` | A search query a model wrote (a follow-up, a listing search filled with the local term or the category, or an evidence or findings search filled with an option's name) that the fixture twin has no recording for; one it has is answered | A page no fixture holds, when the app runs on the fixtures; the tests' twin raises |
| `unavailable` | A 5xx, a connection error, or a body that cannot be read | The same |

A 400 or 422, or any other 4xx the table does not name, means the request itself is wrong;
that is a programmer error and raises. So does a missing or rejected key (401).

## Tavily

- **Plain HTTP.** One POST to `/search` with `httpx`; no SDK. The SDK does not expose
  `Retry-After`, returns untyped dicts and installs a tokenizer the app does not use.
- **Fixed parameters**, in `config.py`: `search_depth="basic"` (1 credit), `auto_parameters`
  off (it can switch to advanced, 2 credits), `max_results=8` set explicitly,
  `chunks_per_source=3`, `topic="general"`, `include_usage=true`. Never `advanced` without
  changing this doc, because it doubles the credits.
- **The generated answer is always off** (`include_answer`). It has no URL, so it cannot be a
  source.
- **Snippets only.** The model reads each result's `content`, at most about 1,500 characters
  (136 to 1,489 in the live check of task 1.6). Full page
  text (`include_raw_content`, no extra credits) is the first thing to try if transcripts show
  snippets are too thin; task 1.9 decides it for the tier 1 LCA search. The
  extract endpoint is not used.
- **Full page text for the evidence search** is on, for that purpose only
  (`include_raw_content="text"`, no extra credits): in the live check of task 1.8.3 snippets
  gave no option a recurring cost in the kettle or the drill, the rule fixed before that check
  (`docs/findings/task_1.8.3.md`). It arrives in a `raw_content` field of the search result,
  cut to `RAW_CONTENT_MAX_CHARACTERS` in `config.py`, and the evidence read sees the cut text in
  place of the snippet, so the quote check runs on the same text the model saw. Many results
  come back with no full text; they keep their snippet. The read's token limit and timeout are
  their own settings (`EVIDENCE_MAX_TOKENS`, `EVIDENCE_TIMEOUT_SECONDS`). Fixtures of that purpose
  keep the field.
- **From the API reference** (checked in task 1.6): the key goes in an `Authorization: Bearer`
  header; `include_domains_mode` exists, with `restrict` (the default) and `prefer`, and acts
  only when `include_domains` is set; `country` takes a full country name, and a wrong one is a
  400; at most 150 `exclude_domains` and 300 `include_domains`; a 429 carries `Retry-After` in
  seconds; the error body is `{"detail": {"error": ...}}`.
- **The live check of task 1.6** is in `docs/findings/task_1.6.md`.

## eBay Browse API

- OAuth client-credentials token, cached until it expires.
- Item search on the marketplaces listed in `config.py` (`EBAY_NL` first; order, widening and
  search language are in `docs/eu_market.md`), filtered by condition and maximum price. Used conditions for the
  second-hand agent; new condition for current prices of new options.
- Start against the sandbox, then switch to production keys through `config.py`.
- Returned per listing: title, price and currency, shipping cost when the API gives it,
  condition, link, country, whether it ships to the Netherlands, and the marketplace it came
  from.
- A listing priced in a currency other than EUR is dropped, with a warning and an `excluded`
  trail entry that links to it; nothing is converted (`docs/adr/0001-euro-only.md`).
- The second-hand agent (optional task 2.3, which holds the details) searches with a query built
  in code from the option's name, fixed-price listings only and never "for parts or not
  working"; code drops a converted price, a listing that does not ship to NL and one over the
  budget with its stated shipping, the small model drops other products and spam on the title,
  and code keeps the 3 cheapest.
- Results are not cached beyond the run: the licence allows listing details at most 6 hours
  older than eBay's site. Fixtures serve the offline tests.
- The seller's account type (business or private) comes with a search result only on some
  marketplaces, not `EBAY_NL`; it is shown when present.
- Follow the API's terms on how listings are displayed and linked.

## Firecrawl

- **One page at a time, never a crawl.** Called for a URL the user pasted, and for the
  comparison sites' listing pages and the candidates' product pages: at most 12 per analysis, at
  most 3 at once, stopping at 5 buyable candidates
  (`docs/adr/0007-options-from-comparison-site-product-pages.md`; `option_research.md`, "Product
  pages"). No crawling, no bulk or background fetching of retail sites.
- **A rate limit** is retried once, after its `Retry-After` up to 60 seconds or after a 20
  second pause when it states none (`FIRECRAWL_RETRY_PAUSE_SECONDS`,
  `FIRECRAWL_MAX_RETRY_AFTER_SECONDS`): Firecrawl answered 429 after nine reads within about a
  minute in task 1.12. After the second 429 the page is skipped.
- **Shops it cannot read** (live check before task 1.8.5, `docs/findings/task_1.8.5.md`): bol.com
  refuses Firecrawl and Amazon pages hold no JSON-LD. Neither is read: their offers reach option
  research through the comparison sites' product pages, which name bol. and Amazon as sellers.
- **Markdown and raw HTML, not built-in extraction.** Request the `markdown` and `rawHtml`
  formats. Do not use Firecrawl's JSON extraction (4 extra credits per page). The live check in
  task 1.6 confirmed that the two formats together cost 1 credit (`creditsUsed` was reported)
  and that `rawHtml` keeps the `application/ld+json` script blocks.
- **Embedded product data first.** Code reads the `application/ld+json` blocks from the raw
  HTML with the standard library and takes the name, the brand (a `Brand`'s name, or the text) and the offer from the first `Product` node,
  also inside a `@graph` or with a list of types. `offers` may be one object, a list or an
  `AggregateOffer`, read as below; a price may be a number or a string with a decimal comma,
  read by the amount parser in `calc/amounts.py`; a block that is not valid JSON is skipped. One offer reader (`tools/json_ld.py`) serves the
  pasted link, the listing pages and the product pages: a `ProductGroup` counts as a `Product`, and one with no offer
  of its own offers its variants' (`hasVariant`); the products in an `ItemList` are never the
  page's product, so a listing page has no product, but they are read as its listed products
  (`listed`: each one's name, its link made whole, the brand it names, and its
  `AggregateOffer`'s lowest price in euro, which is no offer; task 1.12); every offer of the
  product is read too (`offers`: price and shipping rate in euro, availability, condition and
  seller, the used ones included), and option research chooses among them (`option_research.md`,
  "The offer on a product page"); the offer the page is read at is the first that is new (`itemCondition` new
  or absent) and has a price; in an `AggregateOffer` with nested `offers`, the cheapest such
  offer that is in stock, else the cheapest one, which then says it is not; an `AggregateOffer`
  with only a `lowPrice` gives no price, because a "lowest price" is no offer. An offer's price
  is its `price`, else that of a `priceSpecification` with no `priceType` (a typed one, such as
  a strikethrough price, is not what it costs now). Its `availability` and its `seller` are read
  too. A price with no
  `priceCurrency` stays unknown. The
  small model reads the markdown only for what JSON-LD lacks: the materials and the weight, with
  its unit, which code turns into kilograms (`agents/linked_product/prompt.py`). It reads at most
  the first `PAGE_TEXT_MAX_CHARACTERS` of it (`config.py`), and no call is made for an empty
  page text. A failed call leaves the materials and weight unknown, with an `excluded` trail
  entry. The product name and brand come from JSON-LD only; the brand is what the evidence step checks a result against (`option_evidence.md`, "Evidence"). If no price is found, it stays unknown; the
  model never supplies one. A price in a currency other than EUR is also unknown, with the
  warning `link_price_other_currency`; it is never read as euros (`docs/adr/0001-euro-only.md`).
- **Firecrawl's own cache does not save credits** (a hit still costs one), so the app's cache
  is what makes a second run free.
- **The v2 API** (checked in task 1.6): `POST /v2/scrape` with `formats` `markdown` and
  `rawHtml`; the page's own status is in `data.metadata.statusCode`. `metadata.creditsUsed` is
  not always present; when it is missing the fetch is counted as 1 credit.
- **An unreadable link** is one where no product name could be taken from the page: a typed
  failure, a 403 or 404 inside a 200 response, an empty page, or a page with no product on it.
  What happens next depends on whether the category is known. The `read_link` node in
  `graph.py` does this, with `agents/linked_product/agent.py` (`agents.md`, "The graph"):

  | Category known | Product name read | What happens |
  |---|---|---|
  | Yes | Yes | The pasted-link path: the product becomes the linked product, the first option |
  | No | Yes | The model names the category and scope from the product name, and the request is replaced with a copy that has them (`supervisor.md`, "Category"); then as the row above, unless the new scope does not run |
  | Yes | No | The session continues as a typed need, with the warning `link_unreadable`, which says the linked product could not be read and is not among the options |
  | No | No | The request becomes `unclear` and the session ends with fixed words asking for the product name (`wording.request_not_run`); the page offers the input pre-filled |

  The trail says what was read and whether it came from the cache.

## Adding a source

Ask first. If agreed: add the interface and fixture twin, the key to `.env.example` and to the
table in `docs/building_the_project.md`, and a row to the table above.
