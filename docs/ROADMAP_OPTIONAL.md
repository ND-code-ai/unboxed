# Roadmap: optional layers

Only after the submission, and merged or deployed only after the judging period ends (Wed 23 Dec
2026, 12:00 PT; the top of `ROADMAP.md` says why). Each is what the deadline cut from a task in
`ROADMAP.md`, or a layer that was never in the plan. The rules at the top of `ROADMAP.md` apply here too: one
session per task, its own branch and pull request, and a finished task moves to
`ROADMAP_DONE.md`.

- [ ] **2.2 eBay Browse API, with the marketplace interface.** Includes task 2.1: a common search
  interface and a fixture implementation with cached sample listings. OAuth client-credentials
  token from the app keyset in `.env` (cached until expiry); item search on `EBAY_NL`, widening
  to other EU marketplaces, filtered to used and refurbished conditions and a maximum price.
  Start in the sandbox, then switch to production keys. No scraping.
  Moved to the optional layers on 30 October 2026 (submission day), with task 2.3. From the 2.3
  panel, for the client: on a failure, a live run returns the typed failure (`rate_limited`,
  `unavailable`, `timed_out`, `limit_reached`) and never falls back to fixtures, which serve the
  tests and `SHOPPER_SOURCES=fixtures` only; a fixture's match includes the marketplace; results
  are not cached beyond the run (the licence allows listing details at most 6 hours older than
  eBay's site); each listing carries the time it was retrieved and the seller type when eBay
  sends it (`seller_type`: `business`, `private` or none; not sent on `EBAY_NL`). First allow
  developer.ebay.com in the environment's network settings, or check the API facts from the
  developer's machine: a research pass could read only search summaries, so the filter syntax,
  `buyingOptions`, `conditionIds`, `convertedFromCurrency` and `X-EBAY-C-ENDUSERCTX` are
  unconfirmed.
  Prep: no grill; built to the spec above.
  Read: `architecture/data_sources.md` (eBay, Cache and fixtures), `eu_market.md`.
  Done when: a live search returns title, price, condition, link and location, and an API error
  or rate limit returns its typed failure, never fixtures.

- [ ] **2.3 Second-hand agent.** Grilled and panelled on 30 October 2026 (submission day) and
  moved here with task 2.2, which it needs: the panel found that the simple version would show
  nothing or the wrong thing. Settled; raise one only if the code contradicts it:
  - **When.** Only when the request has a budget and a priced option is over it, by the rule of
    `calc/budget.py` (with its stated shipping); otherwise no listings and a `decided` trail
    entry. It searches for used copies of one option: the last over-budget option in report
    order (the durable pick when it is over budget, else the linked product or the cheapest).
  - **Safety-critical products** get no search: a whole-word match of the English category
    against a list in `config.py` (car seat, helmet, climbing harness), a `decided` entry, and
    one calm fixed line in `wording.py` saying a listing cannot show whether one has been in a
    crash or a fall.
  - **The query** is built in code, with no model: `search_name(name, brand)` from
    `agents/tco/checks.py` plus the name's model-number words, so it reads the same on every
    marketplace (task 1.13 measured that a page's whole name finds little, and eBay requires every
    word). `EBAY_NL`, then `EBAY_DE`, then `EBAY_BE`, while fewer than three listings are kept.
  - **The filters**: fixed-price listings only (an auction's bid is no price), used and
    refurbished condition ids and never "for parts or not working", the budget as maximum price
    in EUR, delivery to NL, a fixed page size in `config.py` in eBay's default order, and the NL
    location header with a fixed postcode from `config.py` so eBay states shipping. Code then
    drops: a listing eBay converted from another currency (ADR 0001: the warning and an
    `excluded` entry the doc already requires), one that does not ship to NL, one whose price
    plus stated shipping is over the budget (the rule options follow), and duplicates by item id.
  - **The model filter.** One small-model call per marketplace reads each listing's title and
    condition and drops it only on positive evidence in the title (another product, a part or
    accessory, a named defect, spam); other sizes of the model are kept with their own title.
    Code checks every id it returns. Widening counts the listings kept. Listings are not judged
    against the answers: a used copy is the option's product. Code keeps the three cheapest by
    price plus stated shipping; unknown shipping ranks on price alone and says so.
  - **Failures.** An eBay failure or a filter call that fails twice gives no listings (never
    unfiltered ones) and a trail entry; no new warning code.
  - **What shows.** A listing: its title, price, shipping (missing stays unknown), condition as a
    fixed English label per condition id in `wording.py`, country, link, private or business when
    eBay sends it, and when it was seen. No cost per year, lifespan, CO2e or "less than new"
    figure: the open questions on used items in `calculations.md` stay open. A search that ran
    and kept nothing shows "No used listings found within €X", one that failed "Used listings
    could not be looked up" (words in `wording.py`).
  - **Where.** `ReportLines` gains a `listings` section (each with its `option_id`); the CLI
    prints it under its option; the results page shows it as one block below the rows and the
    deck, headed with its option's name, and the "Hide options over my budget" switch does not
    hide it. A `Recalculation`'s lines carry the listings unchanged.
  - **Wiring** (the agent cannot reach eBay today): task 2.2's search view becomes an argument of
    `SecondHandAgent`, with the marketplace service in `Sources`; `_second_hand` meters it
    (`SECOND_HAND_SEARCH_LIMIT = 3` in `config.py`) and logs it with a new `Service.EBAY`; the
    stub and `agents/default.py` follow. `Listing` gains `seller_type` and its retrieval time.
    The schema in `web/lib/api/` is regenerated and the web samples gain listings.
  - **Fixtures.** This task records its own, trimmed to the fields `Listing` needs: one per tuned
    category for its searched option at a stated test budget, and one widening case. The licence
    reading for committing them is noted beside Tavily's in `data_sources.md`.
  - **Docs.** `eu_market.md` ("eBay marketplaces": the search language, the widening count, its
    open decision) and the progress lines in `wording.py` ("Checking for used listings...",
    "Finished checking for used listings.") change in the same commit.
  Prep: grilled and panelled (30 October 2026); built to the spec above. Needs task 2.2.
  Read: `architecture/agents.md` (The graph, Data model, Agent contract), `architecture/data_sources.md` (eBay, Cache and fixtures), `eu_market.md`, `architecture/models.md` (Which component uses which tier, Rules), `DESIGN.md`.
  Done when: the CLI report and the results page show listings for a product option that is over
  budget new, on a named demo query checked live to trigger the search (recorded in
  `docs/findings/`); a listing over the budget with its shipping is dropped; and a
  safety-critical category searches nothing and says why.

- [ ] **2.7 Conversation: refine and negotiate.** Moved here on submission day (30 October 2026),
  with tasks 2.8 and 3.4: the chat only shows in the browser once all three are done. Shortened
  for the deadline; task 2.6 (explain and what-if) follows it. The conversation agent's
  classification, for `refine` and `negotiate` only; every other message gets one fixed reply
  saying what the chat can do (its words in `wording.py`, written by the rules of `wording.md`).
  The turn model in `state.py`. `refine` and `negotiate` dispatched to reruns of the specialists
  that own the change, reusing the cache; report versions with a "what changed" summary computed
  in code; earlier versions kept; the rerun limit. In the CLI, a chat prompt opens after the
  report.
  Prep: grill, no panel; the classification and the fixed reply.
  Read: `architecture/conversation.md` (Kinds of message, What a rerun runs, Report versions, Limits), `architecture/agents.md` (The graph), `architecture/interview.md` (How answers are used), `architecture/calculations.md`, `architecture/models.md` (Rules).
  Done when: "I don't want to season a pan" produces version 2 without the carbon steel option and
  an `excluded` trail entry; "find something under €40" produces a version with the new budget
  (and refreshed listings once task 2.3 is built); the change summary lists what changed; "why is this pan better?"
  gets the fixed reply; and a sixth rerun is refused with a message offering a new session.

- [ ] **2.8 Conversation endpoint.** `POST /sessions/{id}/messages` only, streaming progress for
  any rerun and then the answer, returning the new report version when there is one. Reading an
  earlier version (`GET /sessions/{id}/versions/{n}`) is a later layer below.
  Prep: no grill; follows the API of tasks 2.5.3 and 2.5.4 (its events, error body and lock per
  session).
  Read: `service_architecture.md` (API surface), `architecture/conversation.md` (Report versions).
  Done when: an API test runs a session to its report, sends a refine and a negotiate message,
  and gets the same results as the CLI, including version 2 after the first.

- [ ] **3.4 Chat panel.** Shortened for the deadline. Beside the results: a chat that streams
  answers, and two starter messages the chat can act on, built by code from the report with no
  model call: a lower budget ("Find something under €40") and leaving out one option. When a
  message produces a new report version, the results page re-renders with a "what changed" note.
  Cited sources, explain starter questions and opening earlier versions are later layers below.
  The panel extends the world of `DESIGN.md` (no new look) and continues the thread of task
  3.1.2 rather than starting an empty one: the composer, hidden after the report until now,
  returns as the chat's, and "Start again" stays. As the last frontend step, run `/impeccable critique`
  on both pages, then `/impeccable polish` on what it finds.
  Prep: no grill; built to the spec above.
  Read: `DESIGN.md`, `architecture/conversation.md`, `service_architecture.md` (API surface), `product.md` (Tone, Demo moments), `code_conventions.md` (Next.js).
  Done when: in the browser, after the frying-pan report, clicking the lower-budget starter
  updates the results page to version 2 with its "what changed" note, on desktop and on a phone.

- [ ] **2.6 Conversation: explain and what-if.** `explain` answers built from the report, its
  trail and its sources; `what_if` dispatched to the recalculation in `calc/`; `new_topic` and
  `off_topic` replies; the number check on every answer. Replaces the fixed reply of task 2.7.
  Then in the chat panel: the sources an answer cites (linked to the trail panel) and one or
  two explain starter questions beside the starters of task 3.4.
  An AI synthetic estimate (LCA tier 3) is explainable in words: asked why a CO2e figure is what
  it is, the answer says what the estimate was built from (each material, its form and mass and
  where each came from, as the result's inputs and its trail hold them) and that the model made
  it; the number check applies, so it adds no figure the report does not hold. Its line on the
  report names no source beyond its label (task 3.1.4 panel, 29 October 2026).
  Read: `architecture/conversation.md`, `architecture/agents.md` (The graph, Agent contract), `architecture/calculations.md` (Changing the assumptions), `product.md` (Tone), `eu_market.md` (Environmental claims), `architecture/models.md` (Which component uses which tier, Rules).
  Done when: after the frying-pan report, five explain questions are answered with cited sources
  from the report; "what if I only cook twice a week?" returns the cost per use recalculated by
  `calc/`; a question the report cannot answer gets a plain "not in this report"; "I need a
  kettle" offers a new session; and a test shows an answer containing a figure not in the
  report is rejected and replaced.

- [ ] **Earlier report versions.** `GET /sessions/{id}/versions/{n}` (from task 2.8), and opening
  an earlier version in the chat panel (from task 3.4).
  Read: `service_architecture.md` (API surface), `architecture/conversation.md` (Report versions).
  Done when: after a rerun, version 1 can be fetched from the API and opened in the browser.

- [ ] **The rest of 1.10.** The other five queries (one more in each tuned category, one
  energy-heavy, one clothing). Check the model tiers: latency per agent, how often the large tier
  ran, and whether any medium-tier component works as well on the small tier. Check the typical
  yearly cost line (task 1.8.1): how often a recurring-cost factor gets an amount (a low rate
  argues for a follow-up search aimed at the amount; task 1.8.1 found one in four categories,
  `docs/findings/task_1.8.1.md`), and whether the line beside each option's own recurring-cost
  line reads as clutter.
  Read: `product.md`, `building_the_project.md` (Tests), `architecture/models.md`.
  Done when: the transcripts are saved and the tier findings are recorded in `docs/findings/`.

- [ ] **The rest of 3.6.** Task 3.6 was cut on submission day (30 October 2026): its four demo
  cases became the check that opens task 3.10. Left: a model timeout caused on purpose and shown
  on the page, no durable alternative, a category where the brief finds no sourced factors, a
  session abandoned at the questions, and the items under "For optional task 3.6" in
  `left_over_tasks.md`.
  Read: `service_architecture.md` (Architecture rules), `architecture/data_sources.md`.
  Done when: each case shows a friendly message and none crashes.

- [ ] **3.6.1 Leftovers: the unreadable-link notice.** Found while checking 1.7.4; the web page
  part moved to task 3.1.2. A link that could not be read, in a request that names a product, gets
  the full interview and the `link_unreadable` warning, but the warning does not say why more
  questions are asked than for a pasted link. Decide whether the message should say so; if yes,
  write the words into this task first, then into `wording.py`. Extend the pasted-link interview test in
  `tests/test_cli.py` so the unreadable case also asserts the warning comes before the first
  question.
  Read: `wording.md`, `architecture/interview.md`, `terminal_app.md`.
  Done when: with an unreadable link and a named product, the warning shows before the first
  question in the terminal, and a test checks it.

- [ ] **Rent or borrow.** Not built, and not in the schemas: until this task is done no agent
  looks for a rental price and no model holds one, and no other task adds either. Today the app
  shows cost per use for every option and leaves the conclusion to the user. The intent: when
  usage is low, owning may not be the best value, so the app suggests renting or borrowing, but
  only when it has a sourced rental price to compare against; it never invents one. First settle the open question in
  `architecture/calculations.md` (whether to show a note when no rental price was found, and
  below how many uses a year). Then: an optional rental price with its source in the schemas, a
  search for one when uses per year is low, and a comparison of rental cost against cost per use
  computed in `calc/`. Finding rental prices must use the existing search tool; a new service
  needs asking first.
  Read: `architecture/interview.md` (How answers are used), `architecture/calculations.md`, `architecture/agents.md` (Data model), `product.md`.
  Done when: a low-usage query (a tile cutter used twice) shows a sourced rental price beside the
  cost per use, and the same query with no rental price found shows cost per use only, with no
  invented figure.

- [ ] **LCA tier 2: benchmark.** Moved out of week 2 (it was task 2.4) for the deadline. Three
  tasks, one session each, in this order:
  - **1.9.3 Emission-factor table.** Data only: the starter materials in `lca.md` copied from the
    published DESNZ file (ADEME for gaps), one row per material and form with factor per kg,
    scope, dataset, year, region, licence and link; a lookup behind the tier 2 interface.
    Done when: the lookup returns a cited factor for each starter material and nothing for a
    material not in the table.
  - **1.9.5 Materials and weight for every option.** Only a linked product has them today. The
    evidence read of task 1.8.3 also extracts materials and weight with their sources, as task
    1.8.6 did for factor values; no new search. Done when: a live run reports how often each is
    found per tuned category.
  - **1.9.4 Tier 2 in the cascade.** Match each material to a table row (decide whether code or
    the small model does it, and update `models.md`); `calc/` multiplies; the source names
    dataset, year and row; the mixed-dataset warning. Tier 2 fills the same `LcaInput` as tier
    3, with the table's factor; its manufacturing line comes from an open dataset or its
    boundary is materials only (ADR 0006). Done when: an option with known materials
    shows a "Benchmark estimate" range, and one with a material missing from the table drops to
    tier 3 with a warning.

  Read: `architecture/lca.md`, `architecture/agents.md` (Data model, Warning codes), `architecture/option_research.md` (for 1.9.5), `architecture/models.md` (Which component uses which tier).

- [ ] **LCA tier 1: published figure.** Two tasks:
  - **1.9 Search experiment.** A script run by hand (a few credits), like task 1.8: how often a
    search finds an Environmental Product Declaration or maker's sustainability report about the
    selected options' product or product line; whether a snippet holds the figure and its
    boundary, or full page text is needed; which language, country and excluded domains work.
    Saves fixtures, writes `docs/findings/task_1.9.md`, fills the last row of "Search purposes"
    in `data_sources.md`. If tier 1 almost never matches, drop 1.9.2.
  - **1.9.2 Tier 1 in the cascade.** One search per option with that purpose; a read that keeps
    only a figure about this product or product line and extracts range, boundary and URL;
    otherwise the next tier. Adds the warning for mixed boundaries. Done when: from the
    fixtures, an option with a published figure shows "Published figure" and its URL.

  Read: `architecture/lca.md`, `architecture/data_sources.md` (Research rules, Search purposes, Tavily, Cache and fixtures), `architecture/agents.md` (Warning codes).

- [ ] **3.3 10-year visualisation with editable assumptions.** Moved here on submission day
  (30 October 2026): a chart and sliders take the most build and demo time of what was left and
  add little over the results page's horizon comparison as text, which the grilling of task
  3.2.1 chose. It takes in that grill's "A 10-year chart on the results page". One durable item
  versus N replacements: cumulative cost and CO2e over the horizon. The user can change lifespan, horizon
  and uses per year; the chart and numbers update through the recalculate endpoint, and a
  changed value is marked and can be reset. A `calc/` function gives the cumulative cost and
  CO2e year by year over the horizon; it is on the report and in task 2.5.2's `Recalculation`,
  so the first render and the sliders show the same figures and the page computes none (2.5
  panel). The sliders use the bounds of task 2.5.2. The chart formats only its axis tick
  labels: CO2e is drawn as a band from low to high, never as a midpoint, and the series names
  with their confidence label, and any value the chart shows, arrive as Lines (ADR 0008). They are a
  `chart` section of `ReportLines` and of the `Recalculation`'s lines, built by a section
  function in `report_lines.py`; the CO2e series' name carries its confidence part (task 3.1.4).
  Prep: no grill; built to the spec above.
  Read: `product.md`, `architecture/calculations.md`, `DESIGN.md`, `adr/0008-api-sends-finished-lines.md`.
  Done when: the chart is readable in a screenshot without explanation, in both views of the
  results page, on desktop and on a phone, and changing a lifespan updates every dependent figure.

- [ ] **The rest of 2.3.** Left out of task 2.3's design: searching when the request asks for
  used items (a field from the supervisor, whose prompt task 1.10 evaluated); used copies of every
  over-budget option, not only one; search terms in each marketplace's language; judging
  listings against the answers; hiding listings older than 6 hours on a session read again; and
  a caveat for safety-critical products from the supervisor's classification instead of the
  keyword list.

- [ ] **One kind of product per category.** Cut from task 3.10 on submission day. A category
  name can cover kinds of product that are bought and used differently: kettle (electric or
  stovetop), iron (for clothes, or a cast-iron pan), scale (kitchen or bathroom), pan (frying pan
  or saucepan). Nothing makes every stage hold the same kind, so each can drift to another. Seen
  in "A kettle, €60" (LangSmith trace `01a18c78-43fd-7260-8e41-994246ed696b`, and
  `docs/findings/task_1.10.md`): the local category term came back "waterketel", the stovetop
  kind, where an electric kettle is a "waterkoker"; the brief took induction-hob compatibility, a
  whistle and copper polishing from kitchenaid.com's page on tea-kettle types; the induction-hob
  question, a compatibility factor, can remove every electric kettle; and the report brought in
  an unrelated product. The fix is one kind, settled once and checked at each stage after:
  - **Supervisor.** The category names one kind. When the name covers several, it takes the kind
    shops in the market list under that name ("electric kettle" in the Netherlands), says so in
    its trail entry ("Understood as: electric kettle"), and the user corrects it as any other
    reading (`supervisor.md`, corrections); no extra question.
  - **Local category term.** Found for that kind, not for the bare name, and accepted only if it
    names the kind (a "waterketel" for an electric kettle is refused and searched again).
  - **Brief.** A source page about another kind gives no factor; above all no compatibility
    factor, the only kind that removes options.
  - **Options.** A candidate whose name or listing category is another kind, or another product,
    is dropped by the term check (`option_research.md`), and `category_cut` (`config.py`) does not
    widen a beslist.nl list past the kind (`left_over_tasks.md`).
  - **Phrasing.** A care question asks about a burden, never a benefit ("a wide lid opening for
    easy cleaning. Is that fine with you?").

  Read: `architecture/supervisor.md`, `architecture/category_brief.md`, `architecture/option_research.md`, `docs/findings/task_1.10.md`.
  Done when: live, "A kettle, €60", "An iron, €40" and "A scale, €30" each ask about one kind
  and report only that kind, and the frying pan, drill and kettle reports of task 1.10's queries
  are no worse than before.

- [ ] **3.5.1 Persistent storage on Nebius.** Cut in its grilling on submission day (30 October
  2026): task 3.5 runs the endpoint for one window with no deploy and no restart, so only a restart
  by the platform would lose the sessions, the cache and the credit ledger, and a store first tried
  that day could not be fixed after the deadline. For when the app is deployed again after the
  judging period.
  Settled: no Postgres fallback. Nebius Managed PostgreSQL costs about $100 a month before disk
  (2 vCPU, 8 GB), against about $0.80 for a 10 GiB filesystem; without a working volume the
  deployment avoids restarts instead. Task 2.5.2's Postgres checkpointer stays in the code, unused.
  Proposed in the grill, not yet confirmed:
  - mount a Nebius shared filesystem at the image's working directory plus `.cache` (for example
    `--volume <filesystem>:/app/.cache:rw`), holding the whole folder: the SQLite file, the cache
    and the ledger; no new setting, and the working directory and the mount path are recorded
    together in `building_the_project.md` (Deployment);
  - the per-IP and per-day session counts stay in memory (`eu_market.md`: an IP is never saved);
  - the cache is warmed again on every start anyway, since listing pages and product pages expire
    after a day (`SEARCH_CACHE_MAX_AGE`, `PAGE_CACHE_MAX_AGE`);
  - the sweep runs only while the endpoint is up, so the filesystem is made just before the
    endpoint starts and deleted with it when it stops for good (no `--forbid-deletion`).

  Attaching a volume is a setting, so the endpoint is recreated: a new URL, a new
  `NEXT_PUBLIC_API_URL` and a Vercel deploy. Known only from search extracts of docs.nebius.com,
  so confirm with `nebius ai endpoint create --help` and `nebius compute filesystem create --help`
  first: `--volume SOURCE:CONTAINER_PATH[:rw|ro]` takes a filesystem or a bucket (a bucket mount
  has no random writes or locks, so not for SQLite); the filesystem is network SSD behind
  virtiofs, made with `--size-gibibytes 10 --type network_ssd`, $0.08 per GiB a month and billed
  while the endpoint is stopped; whether it must share the endpoint's project and region is not
  documented.
  Checks, in order: `PRAGMA journal_mode;` returns `wal` and the `-wal` and `-shm` files appear on
  the mount (langgraph's `AsyncSqliteSaver.setup()` reportedly sets WAL, and sqlite.org warns
  about WAL on network filesystems, though one process on one host may be fine); two analyses at
  once both reach a report, with no `database is locked`; if either fails, set
  `PRAGMA journal_mode=DELETE` after `setup()` in `api/checkpointer.py` and repeat. Watch for
  `sweep_failed` (`left_over_tasks.md`).
  Read: `building_the_project.md` (Deployment), `architecture/data_sources.md` (Cache and fixtures), `eu_market.md` (Personal data).
  Done when: a session started on the public URL, paused at the questions, survives `nebius ai
  endpoint restart` and is answered to a report; and the cost per month is recorded in
  `building_the_project.md` (Deployment).

- [ ] **A screenshot of the shop page as evidence.** Firecrawl returns a `screenshot` in the same
  call that reads a product page (1.13), at no extra credit according to its docs; its link
  expires after 24 hours, so it would be stored with the cached page. The results page of task
  3.2.1 could show a small "as seen on <shop> on <date>" image beside the price. Evidence only,
  never a source of the price (ADR 0004). Moved here from task 3.2's left-over items when the
  task was split (29 October 2026).
  Read: `architecture/data_sources.md` (Firecrawl, Cache and fixtures), `adr/0004-firecrawl-confirms-shop-prices.md`, `DESIGN.md`.

- [ ] GitHub Issues with three milestones generated from this file (`gh issue create`).
- [ ] GitHub Project board on top (`gh auth refresh -s project` first).
