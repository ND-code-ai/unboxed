# Market and EU rules

Read this when working on anything market-specific: currency and prices, eBay marketplaces,
search language, wording of environmental claims, guarantees, or personal data.

The rules sections are design guardrails for this project, not legal advice. If a task depends on
the exact legal position, say so and ask.

## Market

- **Netherlands first, European Union overall.** Currency is EUR. Metric units.
- **Prices are consumer prices including VAT.** Show shipping separately when the source gives
  it, and say when it is unknown; a cheap listing with high cross-border shipping is not cheap.
- **Interface language is English.** Listings and product pages are shown in their original
  language. A Dutch interface is an open decision.
- **Input in any language, output in English.** The user may write in any language. Everything
  the app writes is in English, also when the user wrote in another language: categories,
  questions, the report and chat replies. The app quotes the user as written: the budget phrase
  in a warning, the phrase a stated answer was taken from, and the request's original text.

## eBay marketplaces

- Default marketplace is `EBAY_NL`. The list of marketplaces to search lives in
  `src/shopper/config.py`, in priority order; the initial list is `EBAY_NL`, `EBAY_DE`,
  `EBAY_BE`.
- Search the first marketplace; widen to the next ones only when it returns too few usable
  listings within budget. Always show the listing's country and whether it ships to the
  Netherlands.
- Build search terms in the marketplace's language (Dutch for NL and BE, German for DE) and add
  the English or brand term where products are commonly listed under it.
- **Euro only, one exception.** Prices are never converted (`docs/adr/0001-euro-only.md`); only a
  recurring cost in USD or GBP is, at a fixed rate and labelled
  (`docs/adr/0002-fixed-rate-conversion-recurring-costs.md`). A listing
  priced in another currency is dropped, with a warning on the report and an `excluded` trail
  entry that links to it. A budget or a pasted-link price in another currency is left missing,
  with a warning. A budget with a recognised other-currency marker is never read as euros; the
  list of markers, and its limit, are in `architecture/supervisor.md` ("Reading the phrase").

## Environmental claims

EU rules against greenwashing (Directive (EU) 2024/825, applied from 27 September 2026) prohibit
generic environmental claims that are not substantiated. This matches the product principles, so
treat it as a hard rule for every prompt, report and piece of UI copy:

- **No generic claims.** Never call a product "eco-friendly", "green", "sustainable",
  "climate-friendly", "better for the planet" or similar. State the specific, measured thing:
  "estimated 4 to 9 kg CO2e to manufacture (benchmark estimate)".
- **Every figure is specific, sourced and labelled** with its confidence tier and scope, as
  `docs/architecture/lca.md` requires.
- **A claim about one aspect is not a claim about the whole product.** Lower manufacturing CO2e
  does not make a product "low impact" overall.
- **Comparisons state their basis:** same scope, same horizon, same assumptions for both options.
- **No invented labels, scores or badges** that look like a certification. Report real third-party
  labels only when the source shows them, and name the scheme.
- **No carbon-neutral or offset-based claims**, even when a manufacturer makes them. Report them
  as "the manufacturer states", never as fact.

## Guarantees and lifespan

- New goods bought from a business in the EU come with a legal guarantee of at least two years.
  Goods bought from a private seller do not. eBay listings can be either; show which when the
  listing says.
- The legal guarantee is a consumer right, not a lifespan estimate. Never use it as the lifespan
  input, and never present a lifespan estimate as a guarantee.

## Personal data

The app collects no personal data: no accounts, no email addresses, nothing about the user
beyond the request and the session's conversation. Keep it that way; collecting any personal
data would bring data-protection rules (GDPR) into scope, so ask first.

- Never put personal data a user types into the chat in a search query, a log line or a fixture.
- A session, with what was typed in it, is kept for 7 days after its latest change
  (`SESSION_RETENTION_DAYS`) and then deleted; that includes a session whose request could not be
  read, which holds only the input.
- A client's IP address is held in memory for an hour to limit the sessions it starts, and for
  nothing else: it is never saved, logged or put in a session. The hosting platform's own proxy
  logs are outside the app.
- No analytics or tracking of individuals.
- LangSmith tracing is a developer tool. A trace holds what was typed, so its project is
  private and on the EU region. The deployed app traces only when the developer chooses to, and
  never silently: while it traces, a notice by the input box says that requests are logged to
  improve the app. It traces whenever the deployment runs, the hackathon judging included, and
  stopping the endpoint after the judging ends it (`building_the_project.md`, "Deployment").

## Open decisions

- Which marketplaces beyond `EBAY_NL` to search by default, and how many listings count as "too
  few".
- Whether to offer a Dutch interface.
