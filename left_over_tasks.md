# Left-over tasks

Items a task left open or noticed for another task. `/task` shows the items under a task's
heading when that task starts, and asks whether to include, defer or drop each one. It adds new
items here in the commit that completes a task. Delete an item once it is resolved.

Each item ends with the task it came from.

## For task 1.9 (optional layer: LCA tier 1)

- **The footprint search has no purpose yet.** `SearchPurpose` in `config.py` has no member for
  the tier 1 published-footprint (EPD) search, whose country and domains `data_sources.md` leaves
  to this task. Add it with its row in `SEARCH_PURPOSE_PARAMETERS`. (from 1.6)

- **The known simplification assumes cradle to gate.** "Known simplifications" in
  `calculations.md` says CO2e covers the item from cradle to gate; a published figure may have
  another boundary (cradle to grave). Make the line, and the evidence summary's "CO2e to make"
  (task 1.10, `EVIDENCE_FOOTPRINTS` in `wording.py`), defer to the result's `boundary` then.
  (from 1.9.1, LCA review; widened by 1.10)

- **CO2e avoided across different boundaries.** `_against_baseline` in `calc/comparison.py`
  subtracts two results without comparing their `boundary`; with only tier 3 that is one fixed
  boundary. Once a published figure can be cradle to grave or a benchmark materials only,
  withhold the figure with its own missing reason when the boundaries differ, as
  `calculations.md` ("CO2e avoided") says; tier 2 needs the same. (from 1.9.6, LCA review)

- **The words of a sourced CO2e line.** A tier 1 or 2 figure names its result's source after its
  label, "(benchmark estimate, pans-dataset, row 12)" (`CO2E_SOURCED` in `wording.py`), a link to
  the site for a page; the "Against" line names none. With real references (the dataset, its year
  and row, or an EPD's page) check that the line still reads well and that the reference is the
  one `lca.md` names. (from 3.1.4)

## For task 2.3

- **Categories vary between runs.** The supervisor can name one product two ways from one run
  to the next ("electric bicycle", "electric bike"; `docs/architecture/models.md`, "Findings
  from task 1.5"). Search terms built from the category should not depend on its exact words.
  (from 1.5)

## For task 2.2

- **The eBay search URL, if logging is set to info.** httpx logs "HTTP Request: GET <url>" at
  info level, and the eBay Browse API's search is a GET with the search terms, built from the
  request, in `q=`. Under uvicorn's default logging that record is dropped (the `httpx` logger
  inherits the root's warning level), so it is written only if logging is configured at info,
  such as by `logging.basicConfig` or a platform's logging agent. A small guard: keep the `httpx`
  logger at warning in the API, as `saved_sessions` (`api/app.py`) does for aiosqlite. (from
  2.5.4)

## For task 2.6

- **Which factor row a page material used.** A fixed input keeps the page's name ("plastic")
  while its factor is the model's row ("polypropylene"); `LcaInput` keeps no trace of the row.
  When the user asks why a CO2e figure is what it is, the answer could name the row; that needs
  the row's material on `LcaInput` (`state.py`). (from 1.9.7, LCA review, deferred by 1.9.8)

- **Questions about a question: a nice-to-have, assess before building.** It is an open
  question in `docs/architecture/conversation.md`. A chat during the interview has unknowns: a
  `Turn` refers to a report version and none exists yet, the conversation agent answers from a
  report, and a message could arrive while the graph is paused in `interview`. First check
  whether showing each factor's `why` and source beside its question, with no model call,
  already covers it; build the chat only if it does not. (from 1.5.1)

## For optional task 3.5.1

- **A deploy loses the runs in progress.** A run whose client has gone is still going at shutdown
  fails its next write once the lifespan closes the SQLite file, and reads back as `interrupted`.
  Until storage outlives a restart the whole session goes anyway. (from 2.5.3, widened by 2.5.4,
  deferred by 3.5)

- **The Postgres saver's logs.** `make_checkpointer` (`api/checkpointer.py`) keeps aiosqlite's
  logger at info, because at debug it logs each statement's parameters, the saved input among
  them; check whether psycopg does the same before `DATABASE_URL` is set, and run the marker test
  (`test_the_input_appears_in_no_log_record`) against the checkpointer the deployment uses. (from
  2.5.4, deferred by 2.5.2)

- **One checkpoint that will not load stops the whole sweep.** `sweep` (`api/sweep.py`) reads
  every checkpoint through the saver's `alist`; an error there ends the pass, logged as
  `sweep_failed`, and if it recurs each hour nothing is deleted, against the 7 days of
  `eu_market.md`. Watch for `sweep_failed` in the store chosen. (from 2.5.2, review)

## For optional task 3.3

- **The workflow's first run from `main`.** `deploy.yml` can be started by hand only once it is on
  `main`, so task 3.5 built its images from temporary branches with a push trigger, and
  `gh workflow run deploy.yml` has not run yet. The first task that redeploys the backend checks it.
  (from 3.5)

- **What the page does with a refused recalculation.** `OUTCOMES` in `web/lib/thread.ts` places
  `no_report_yet`, `no_options`, `unknown_option` and `invalid_assumptions` as `unchanged` only so
  the page typechecks; the sliders decide how each is shown. `RecalculateRequest` takes the
  complete assumptions, `uses_per_year` included (null when not known). (from 2.5.2)

## For task 3.4

- **The thread's module holds several things.** `web/lib/thread.ts` holds the reducer, the
  error-code outcomes, the back-off for reading a session again, the composer's view and the
  chips. When the chat adds its own turns and messages, move the composer's view and the chips
  into modules of their own. (from 3.1.2, review)

## For optional task 3.6 ("The rest of 3.6")

- **An empty search is cached.** A search with zero results counts as a success, so it is cached
  (`data_sources.md`, "What is cached"), for a day on a listing search and for good otherwise. In
  task 3.5 the first frying pan on the endpoint found no listing pages where the same request found
  6 minutes later, so every frying pan had no options until a restart cleared the disk
  (`docs/findings/task_3.5.md`). Decide whether an empty result is cached at all. (from 3.5)

- **An unknown path or method gets FastAPI's `detail`.** A 404 for a path no route has, or a 405,
  is Starlette's `{"detail": ...}`, not `{code, message}` (`api/app.py`); the page never sends one,
  but a stale client could. (from 2.5.4)

- **A rejected key raises mid-analysis.** `RejectedKeyError` (`tools/http.py`) is raised at the
  first call with a key the service refuses, inside the graph. `cli.py` catches it around the
  whole run; the API ends the run with a `run_stopped` event (`api/runs.py`), which says only to
  start again. A code of its own could say what happened. (from 1.6, narrowed by 2.5.3)

- **An agent that raises after the interview strands the session.** If the TCO, LCA or
  second-hand node raises, the session is neither paused nor finished: `read_session` in
  `sessions.py` reads it as `interrupted`, `resume_session` raises `SessionNotPausedError`, and
  nothing can continue it. Agents are meant to return a warning instead of raising, but nothing
  enforces that. (from 1.5.1, narrowed by 2.5.1)

- **A beslist.nl filtered list cut to a broad category.** `category_cut` (`config.py`) cuts a
  `/r/` or `/c/…merk~` list to the path before it, which can be a parent wider than the product
  ("drill kopen" gives `…/klussen_486172_488680`, DIY accessories), while a `/c/` facet without a
  brand is read with its filters; only the term check guards the category. (from 1.15, review)

- **Pasted links on real pages.** Task 1.6.1 was shown only on fixtures. Run the four outcomes of
  `data_sources.md` ("An unreadable link") on real bol.com and coolblue.nl links; judge how often a
  page has no JSON-LD `Product` name, whether `PAGE_DETAILS_PROMPT`'s materials and weight are
  right, whether the two questions `MAX_LINKED_QUESTIONS` asks (`agents/brief/agent.py`) are the
  ones that decide a fit, and whether the linked product's own offer counts as a confirmed price
  and states its shipping (`_price_seen`, `agents/linked_product/agent.py`). (from 1.6.1, 1.7.4,
  1.8.5 and 1.15, deferred by 1.10)

- **A scope changed to itself.** `_unreadable` in `agents/linked_product/agent.py` writes "Changed
  the scope from unclear to unclear" when the supervisor already scoped a bare link `unclear`, as
  the live supervisor did for the blocked fixture page in task 3.1.1's browser run. (from 3.1.1)

- **The LCA with a pasted link.** No live run has had page materials, a page form or a page weight
  as fixed inputs since the prompt changed; check that "70% recycled" passes, that a weight among
  the numbered inputs declines nothing (`_fixed_inputs`, `agents/lca/agent.py`), and that "Built
  from" marks the page's parts unestimated. Run with the links above. (from 1.9.7, 1.9.8,
  deferred by 1.10)

- **Conditional questions: decide, do not assume.** A question shown only for a given answer to
  another would need a condition on `Question` and keep the single pause in `graph.py`. With
  "cordless" now in the category (task 1.10), add it only if a transcript shows a first answer
  splitting a category so far that the first report is wrong. (from 1.5.1, deferred by 1.7 and
  1.10)

## For task 3.8

- **The sealed box needs the real agents.** With `SHOPPER_AGENTS=stubs` the answers' run ends in
  under a second, so the box seals and opens in a blink and the scan window is never read; the
  20 to 30 s of a real run is what shows it. Record the demo's sealed state on the real agents.
  (from 3.1.3)

- **The recorded sources give the live model's picks fewer options.** On `SHOPPER_SOURCES=fixtures`
  the real agents picked the Demeyere Proline 7, whose product page no fixture holds; since task
  3.2.1 that page is `not_recorded` and the frying pan showed two options, not three. Record the
  demo on the live sources, or record the pages its run reads. (from 3.2.1)

- **Demo moment 3 is three stations open at once.** On the results page, open "your request",
  "questions" and "CO2e" on the route line: their parts of the trail stand one under another with
  the small, medium and large tiers named on their lines (`components/TrailPanel.tsx`). The
  questions part scrolls inside its sheet, so CO2e sits below it. (from 3.2.2)

## Unassigned

- **A budget is lost when a pasted link makes an unclear request run.** `_to_request` in
  `agents/supervisor/agent.py` reads the budget only for scopes that run, so a request the model
  calls `unclear` gets none; when `read_link` then names the product and the request runs, it runs
  with no budget and no warning, though the user wrote one. Read the budget for `unclear` too, or
  read it again after `read_link`. Not checked live. (from 3.7, found while drawing the supervisor)

- **The recorded sources run only the frying-pan example.** The brief's searches were recorded for
  the categories "kettle" and "drill" (task 1.15), but the supervisor reads "A cordless drill" as
  "cordless drill" (`tests/terminal/test_cli.py`), and likely the kettle example as "electric
  kettle", so on `SHOPPER_SOURCES=fixtures` their template searches raise `FixtureMissingError`
  (`tools/fixtures.py`), uncaught. Record those searches
  (`scripts/record_fixtures.py`), or turn a missing template fixture into a failed search; then the
  README's "Run it locally" can name all three examples. (from 3.7, found by `task-verifier`)

- **The README promises self-improvement loops.** Its limitations say, at the developer's request,
  that future work aims to close the gap between the checked categories and the rest with
  self-improvement loops (traced runs and the trail's turned-away candidates fed back into the
  prompts, search terms and checks). No task in `docs/ROADMAP_OPTIONAL.md` describes one yet; add
  it there, or reword the README's line. (from 3.7)

- **Most factor values come back "could not be confirmed".** The one evidence search per option
  (`"{product} durability lifespan warranty"`, `data_sources.md`) is aimed at lifespans and rarely
  returns a page stating a kettle's interior material or a pan's hob compatibility, so the read has
  no quote and every value is `unverified` (nine of nine on a live kettle run, 30 October 2026;
  2 meets, 1 fails, 4 unverified in `docs/findings/task_1.8.6.md`). Two fixes, in order of effort:
  give the factor read the product page already fetched for the price (`option_research.md`,
  "Product pages"), as the linked product's own page is given today, with `stated_by: seller`; or
  one spec search per option ("{product} specificaties", one Tavily credit each). Until then the
  page folds the unconfirmed values into one line per option and keeps the list on the
  check-before-you-buy card. (from the Cowork review of the live page, 30 October 2026)
  The first fix looks done already: `agents/tco/agent.py` passes each candidate's own product
  page to the read (`own_page`), so check a live run before building it; the README names only
  the spec search as missing. (from 3.7)

- **The rehearsal's image tag is still in GHCR.** `ghcr.io/nd-code-ai/hackathon-app-sustainable-shopper:rehearsal`
  holds the temporary proxy log of task 3.5, which logs counts and header names and no address. No
  endpoint uses it; delete the tag in the package's settings on GitHub. (from 3.5)

- **The app's new name.** The developer named the app Unboxed in task 3.5 and task 3.10 put it on
  the page; the README, the docs, `GLOSSARY.md`, `FastAPI(title=...)` and the LangSmith project still
  say True Cost Copilot; the README keeps the title and says the page is called unboxed. (from 3.5,
  narrowed by 3.10 and 3.7)

- **The phone's half of the critique.** `docs/design/phone_fixes_after_hackathon.md` lists what the
  wide screen got and the phone did not, at the developer's call, with the other phone findings.
  (from 3.10)

- **The trail's plain words belong in Python.** `TRAIL_PLAIN_WORDS` and `TRAIL_KIND` swap the API's
  terms on the page, because changing them there needed a backend redeploy on submission day (ADR
  0008). Word them in `agents/lca/trail.py`, the supervisor's trail and `wording.py`, and drop the
  swap. Until then no test catches a backend rewording: the old term just shows again. The rest of
  the trail's jargon waits with them: `Factor "Size" (requirement)`, 25 "Judged …" lines, "price seen
  at bol. via" and "stated by a seller" for a magazine. (from 3.10)

- **The critique's other findings, wide screen too** (30 October, 26 of 40). Focus falls to the page's body after Next and "Show my options"; Next option is disabled while it
  has the focus (`aria-disabled`); "Edit" stays live during the sealed run and on the opened box and
  discards the run or the report unasked, though `product.md` means it for before the search; a slow
  answers request shows an empty scan window and status line until its first event (`STILL_WORKING`
  would fit); the panel is empty for most of the results' scroll (sticky rounds need the panel's
  `overflow-hidden` changed to clip). (from 3.10)

- **What a reload cannot give back.** Tapped chips at the questions, and on a finished report the
  "Looking for" and "From your reply" lines, since they are not in a report's lines. A reload during
  a run shows every station ahead, with "Still working…", since the view says only that it runs.
  (from 3.10)

- **The notes keep the words of the wait.** The stations' notes open at the questions and on the
  opened box too, in the present tense of the wait ("We're working out what you typed"), at the
  developer's call; the same goes for the current station's wider ring, on every station, where the
  ask named the questions station. (from 3.10)

- **A usage read from the reply shows only in its small line.** When the reader takes a frequency
  from the reply, the usage label on the box and in the panel does not show it, though it sets the
  cost per use of the whole report; only "From your reply" says so. (from 3.10)

- **The CO2e estimate can still fail for a whole report.** All of a report's options come from one
  reply, so one check failing the same way for each, or one timeout, leaves no CO2e. On the live pass
  of 30 October a drill's call timed out with three runs at once. The stray pointer that failed two
  other runs is fixed (`checks.py`); a retry with the check's words in the prompt, as invalid JSON
  gets, and one for a timeout would save the rest. (from 3.11's live pass)

- **A fixed input can label the wrong row as from the page.** Nothing compares a row's material with
  the page material it points at, so "stainless steel" pointing at the page's plastic shows as plastic
  from the page, summed with steel's factor. A strict name match would break the allowed plastic to
  polypropylene, so it needs a compatibility rule of its own. A dropped pointer also leaves no trail
  entry, so how often that slip happens cannot be seen. (from the review of the fixed-input fix)

- **The car's decline reads awkwardly.** "It can't help with "car"." (`wording.py`), after a
  supervisor call of about 30 s. (from 3.10)

- **The eBay promise in the docs.** `CLAUDE.md` and the README still promise used alternatives from
  eBay, while the page shows nothing of the second-hand agent, whose stub still runs. (from 3.10)

- **A test point added unasked.** `code_conventions.md` gained the `RunRoute` row in task 3.10 without
  the agreement its table asks for. Confirm or change it. (from 3.10)

- **Smaller code notes from the 3.10 review.** `enterSends` sits in `AskBudget.tsx` though two composers
  use it; `readBack` in `thread.ts` is about 40 lines and the module is about 1,190; `SHEET_TOP` and
  `SHEET_COST` repeat entries of `TOP` and `COST`; the Title's three classes are written in three
  places; `.impeccable/design.json` still describes the twelve ticks and is older than `DESIGN.md`
  (`/impeccable document` refreshes it). (from 3.10)

- **"Built from" repeats a material.** The drill's line listed carbon steel five times and
  copper twice (`_built_from` in `report_lines.py`); merging rows of one material and form belongs
  in Python, since the page formats nothing, or the model could name the part. Components show no
  form since task 1.9.8. (from 1.9.8, LCA review, deferred by 3.2.1)

- **One rule for a rough estimate, in two places.** `_is_rough` in `report_lines.py` marks a
  lifespan as a rough estimate by the same rule `_lifespan_field` in `calc/evidence.py` counts
  it as estimated; expose one function from `calc/` for both. The page shows the mark through the
  lifespan line, so it uses neither. (from 1.5.2, deferred by 3.2.1)

- **Recurring-cost wording.** The typical cost line can read "Brush head replacement cost:
  typically €31.99 a year" while the same factor sits under "Not yet known" on the check list
  (`report_lines.py`, `check_lines_of`), and the phrasing call once asked about the user's own
  toothbrush (`agents/brief/prompt.py`). No toothbrush ran in task 1.10. The stub brief's
  "Seasoning oil" shows both on every stub run since task 3.1.5 (`agents/stubs.py`), and since
  task 3.2.1 the results page sets them in one block. (from 1.8.1, widened by 3.1.5, deferred by
  3.2.1)

- **Whether an option has a figure is written twice.** `rowsOf` in `web/lib/results.ts` decides
  which rows exist from its groups' checks (`option.savings !== null`), and `fieldOf` in
  `web/components/OptionCell.tsx` checks the same fields again to draw them; a new figure means
  editing `Field`, a group and the switch. (from 3.2.1, review)

- **The trail names agents by their code names.** Each trail line starts with `tco`, `lca`,
  `second_hand` or `brief` (`wording.trail_by` in `wording.py`, from `Agent`'s values), as the
  terminal prints it; on the results page those lines sit under stations named "options", "CO2e"
  and "second-hand". Names from the glossary, in `wording.py`, would read better on both. (from
  3.2.2)

- **A larger button from 1024 px, written twice.** `lg:min-h-11 lg:px-6 lg:py-2
  lg:text-base` turns a small button into a default one on a wide screen in
  `components/FaceComposer.tsx` (twice); a size in `components/ui/button.tsx` would hold it once.
  (from 3.2.2, review)

- **Templates edited by string replacement.** `wording.spoken` puts who is speaking after the
  `({site})` of a template, and `wording.co2e` puts a set's pieces and a source into ` ({label})`,
  both with `str.replace`; a template whose brackets change would quietly lose them. Tests would
  catch the words, but a template per case, or a check that the replacement matched, would say
  why. (from 3.1.4 review)

- **A count on a `progress` event.** The box's scan (`docs/design/chat_page_brief.md`) would
  show what each agent found as it finds it ("6 candidates", "3 priced", "2 used listings").
  The trail has the numbers; the event does not carry them. An optional `count` or `detail`
  field on the finished event, from the trail, with its wording in `wording.py`. Optional for
  the submission; deferred in the 3.1.4 panel. (from the 3.1.3 brief)

- **The chat page's ceiling, from Impeccable's finish review.** Three things the review named
  that the build does not yet use: the panel's content does not visibly snap to the twelve
  columns of the grid; the count on the box ("1 of 2 labelled") is set small where the
  Total Design habit is a large numeral; and the opening composer's Send shows as a dashed,
  disabled box until something is typed, so the panel's first viewport reads quieter than the
  decision sketch the world was chosen from (a 72 px question, a 24 px Send). A later `polish`
  pass. (from 3.1.3)

- **Agreeing to a care factor reads as nothing.** Live, "I don't mind seasoning it now and then"
  and "seasoning is fine with me" gave no requirement for a care factor not asked, five runs of
  five (`docs/findings/task_2.5.6.md`); rule 3 of `REPLY_PROMPT` (`agents/brief/prompt.py`), "not
  minding is never a value", likely beats the care question's "That's fine" choice. With no
  choice picked such a reply gets `reply_unanswered`. (from 2.5.6, deferred by 3.1.2)

- **Tier 3 masses and run-to-run spread.** In task 1.10 the Bosch GSR 120-LI's range moved from
  about 25 to 55 kg per unit to 47 to 100 kg on cached inputs, and the model's masses were about
  twice the maker's (1.95 kg against 0.97 kg with battery). Revisit `LCA_MIN_SPREAD` (ADR 0006)
  and pass a maker's stated weight in when the page lacks one. In two drill reruns the check
  turned down two drills' inputs ("lithium-ion battery pack points at fixed input 1" with no
  fixed input given; `agents/lca/agent.py`). (from 1.10, LCA review)

- **Kettle materials copied between options.** The Russell Hobbs 24992-70 (a stainless body) got
  the plastic Seeger's materials in task 1.10 (`ESTIMATE_PROMPT`, `agents/lca/prompt.py`).
  (from 1.10, LCA review)

- **The CO2e over 10 years has no rough mark.** It is purchases times a rough lifespan, like the
  savings line that now says so (`report_lines.py`, `_co2e`). (from 1.10, LCA review)

- **Use phase for products that use energy.** About 80% of a kettle's impact is in use; "CO2e to
  make" discloses the scope, but a fixed caveat for energy-using products could say so
  (`wording.py`, rules in `docs/wording.md`). (from 1.10, LCA review)

- **A high-factor input escapes the component flag.** In the live run of task 1.9.8 a neodymium
  magnet (30 to 50 kg CO2e per kg) came back with `component` false, so a page weight would
  scale it. The prompt now names magnets; a guard in `scaled_to_weight` (`calc/co2e.py`) that
  never scales an input whose factor is far above the option's bulk materials would not rely on
  the model. Changes `calculations.md` ("Weight scaling"). (from 1.9.8, LCA review)

- **The same material gets other factors in each call.** Stainless steel and printed circuit
  boards came back with different ranges for the pans and the kettles, so a rerun can move a
  figure with no change in input. Pinning common materials in a table is the LCA tier 2 layer's
  work (`docs/ROADMAP_OPTIONAL.md`); the model would fill only the gaps. (from 1.9.8, LCA review)

- **The three quotes of a recurring cost travel together.** `amount_quote`, `interval_quote`
  and `pack_count_quote` are on both `ReadFactor` (`agents/brief/models.py`) and
  `ReadConsumable` (`agents/tco/models.py`) and go together into `yearly_cost` in
  `agents/shared/yearly_cost.py`; one small model for them would change both read schemas.
  (from 1.8.1, review)

- **A URL's host is read in three places.** `on_domain` in `tools/search.py`,
  `wording.site_name` and the domain count in `check_sources.py` each parse a URL's host their own
  way; one helper in `tools/` could serve all three. (from 1.8.5, widened by 1.8.7, narrowed by
  1.13)

- **"A factor of the user's own" is not in the glossary.** `GLOSSARY.md` ("Decision factor") says
  a factor can be stated by the user, but the term used in `interview.md`, the code and the trail
  for a `user-` factor has no entry; add one if the page or the API names it. (from 1.7.3)

- **The supervisor still builds its trail entries on its own.** Task 1.8.2 moved the shared
  entries to `agents/shared/trail.py`, which the brief and TCO agents bind to their name
  (`agents/brief/trail.py`, `agents/tco/trail.py`); `_entry` in `agents/supervisor/agent.py` and
  in `agents/linked_product/agent.py` could do the same. (from 1.7.1, narrowed by 1.8.2)

- **The test point for `calc/` names only `calculations.md`.** `docs/code_conventions.md`
  ("Tests") takes the expected results of a `calc/` function from the worked examples in
  `docs/architecture/calculations.md`, but `chosen_offer` (`calc/offers.py`, task 1.13) follows
  rules in `docs/architecture/option_research.md`, which has no worked example; its tests use
  values written from those rules. Task 1.8.3 added four more of the kind: `quoted_lifespan`,
  `replacements_per_year`, `quoted_money` and `to_euros` (`calc/lifespans.py`,
  `calc/recurring.py`, `calc/money.py`, `calc/conversion.py`), tested from the tables in
  `option_evidence.md` ("Evidence") and the ADR 0002. Agree whether the test point should name
  the doc that owns the rule. (from 1.8.2, widened by 1.8.3 and 1.13)

- **The state key `answers` holds two things.** The brief node writes the stated answers under
  `answers` (`graph.py`), and the `interview` node replaces them with the complete set;
  `SessionStart.stated_answers` reads the key before the pause, and `read_session` (task 2.5.1)
  reads it only there, the finished session through its report. Say so in `GLOSSARY.md` or
  rename the key if a later reader takes it at both points. (from 1.7.1, narrowed by 2.5.1)

- **The reading machinery lives under the request's name.** `stated.py` (`agents/brief/`) now
  exports the checks both readers use (`numbered_factor`, `own_factor`, `stated_answer`,
  `located_phrase`, the trail texts), and `read_stated` and `read_reply` (`reply.py`) each hold the
  same try-again-once block and a near-copy of the `_kept` loop. If either grows, move the shared
  part into a module of its own. (from 2.5.5, review)

- **ISO 4217 codes were typed by hand.** `OTHER_CURRENCY_CODES` in `calc/budget.py` was written
  from memory, not copied from the published list; compare it with the list once. (from 1.5)

- **A stated answer's choice is not checked against its question.** `Answer` in `state.py` now
  lets a `stated` answer carry a `choice_id` (the choice code mapped it onto). `complete_answers`
  in `graph/interview.py` checks the reply's against every phrased question since task 2.5.5, but
  not the request's; `stated.py` only ever sets one from that question. Decide whether to check
  the request's too. (from 1.7.1, deferred by 1.7.3, 1.7.4 and 1.8.6, narrowed by 2.5.5)

- **The Firecrawl fixtures are hand-written.** `tests/fixtures/firecrawl/` holds example.org
  pages for the page fetch's tests; replace them with trimmed copies of real shop pages.
  (from 1.6, deferred by 1.7 and 1.10)

- **A search purpose for consumable prices.** The template searches rarely state a consumable's
  price (`docs/findings/task_1.8.1.md`); whether one more call per brief is worth it is a
  question for `SEARCH_TEMPLATES` in `config.py`. (from 1.8.1, deferred by 1.10)

- **Say when the model estimated a typical product, and what it left out.** A field on
  `OptionEstimate` (`agents/lca/models.py`) for "estimated as a typical {kind}" and for what the
  item includes as sold, shown on "Built from" and in the trail. (from 1.9.8, deferred by 1.10)

- **Warranties from US pages for an EU purchase.** Terms differ by region; judge whether the trail
  names the region or the evidence read prefers EU pages. Task 1.10 showed a "lifetime" warranty
  from interfixpro.com for a Makita. (from 1.8.3, deferred by 1.10)

- **Trace the searches and page fetches.** A trace shows the model calls only; trace each call of
  `tools/sources.py` as a `tool` run with its query or URL, cache hit, credits and failure kind.
  (from 1.9.9, deferred by 1.10)

- **The evidence search name for a name with no dash.** `search_name` (`agents/tco/checks.py`)
  keeps such a name whole, and a Dutch category word beside the English template words found
  nothing for several products. (from 1.15, deferred by 1.10)

- **A local term with no synonym.** `names_kind` (`agents/tco/checks.py`) reads compounds, but a
  drill named only "Schroefmachine" (the Makita DF001DW) still does not name an
  "accuboormachine", nor does the Bosch Advanced Drill 18V-80 "Schroefboormachine", a cordless
  drill with no "accu" in its name (task 1.10); that needs other terms from the local-term call.
  (from 1.15, narrowed by 1.10)

- **A page title quoted as the evidence of a fit.** In task 1.10 the Tefal So Expert was left
  out on the quote "# Tefal - So Expert - …", the page text's first heading with its markdown
  sign (`agents/tco/answers.py`); the trail could cut the sign, or the read be asked for the
  words that state the coating. (from 1.10, review)

- **The offline drill case keeps the category "drill".** The live supervisor says "cordless
  drill" since task 1.10, but `OPTIONS["drill"]` in `tests/test_cli.py` writes "drill", because
  the brief searches were recorded for it; record the "cordless drill" brief searches and switch
  the case. (from 1.10, review)

- **Size choices in inches.** The frying pan's size question offered "8 inches", "10 inches",
  "12 inches", copied from a US source as rule 1 of `PHRASING_PROMPT` requires
  (`agents/brief/prompt.py`), though the market is metric (`eu_market.md`). (from 1.10)

- **A factor named for one thing, asked about another.** The drill brief's factor "Voltage and
  amp hours" carries the question "What kind of tasks do you plan to use the drill for?", so a
  stated answer reads "Voltage and amp hours: Light household tasks" (task 1.10). The read's
  name and the phrasing call's question come from separate calls (`agents/brief/prompt.py`).
  (from 1.10, review)

- **The rough lifespan ignores the durability judgement.** In task 1.10's drill transcript the
  Bosch GSR 120-LI, chosen as the durable pick and judged long, got a rough estimate of 3 years
  against 4 for the EasyDrill judged short, so the durable pick costs €250.43 more over 10 years
  (`agents/tco/durability.py`, the evidence read's `estimated_years`). A lifespan decision.
  (from 1.10, verifier)

- **A refilled slot that fails again leaves no entry.** In task 1.10's final frying pan run the
  Tefal Renew ON refilled the cheapest slot and failed the answer too; the slot ended empty with
  no `decided` entry saying so (`agents/tco/agent.py`, `selection.py`). (from 1.10)

- **The e-bike's scope wobbles.** One of three live supervisor evaluations of task 1.10 scoped
  "een elektrische fiets voor woon-werkverkeer" `tuned` once and `general` once
  (`tests/eval/supervisor_cases.py`); the other two passed. (from 1.10)

- **The supervisor's call is most of a cached run.** It took 11.0 s at the median and up to
  18.8 s in task 1.10, so a cached run cannot show its questions within 12 s. Decide the kettle's
  scope before trying the medium tier (`docs/findings/task_1.7.2.md`). (from 1.7.2, judged in
  1.10)

- **The care template finds off-topic pages.** The kettle brief of task 1.10 kept stovetop
  factors (induction hob, copper and olive-oil polishing) from kitchenaid.com's page on kettle
  types; judge whether `SEARCH_TEMPLATES` in `config.py` needs other words. (from 1.7, judged in
  1.10)

- **Doubtful sourced lifespans.** The SIHOO M59AS chair's "3 years (techbits.cc)" in task 1.10
  is an owner's time of use, not a lifespan. Judge whether an owner's or seller's lifespan should
  be sourced at all, and whether it should show that it is a low end or about the line
  (`agents/tco/durability.py`, `report_lines.py`). (from 1.8.3, judged in 1.10)

- **A durability reason with a material grade or model number counts as unknown.** The Demeyere
  Proline 7's page judgement was lost to "a digit" in one 1.10 run (`judgement_fault`,
  `agents/tco/checks.py`). (from 1.8.7, judged in 1.10)

- **Findings stay empty.** No option of task 1.10's four transcripts got a finding from an owner
  or a tester (`agents/tco/findings.py`); check full page text or another template before the
  demo (`docs/findings/task_1.8.4.md`). (from 1.8.4, judged in 1.10)

- **The model judges whether a value meets an answer.** In task 1.10 the Tefal So Expert, whose
  name says "Antiaanbaklaag", was `unverified` against "No coating" in one run and `fails` on its
  title in the next (`EVIDENCE_PROMPT`, `agents/tco/prompt.py`); a `care-avoid` mark has still
  not run live. (from 1.8.6, judged in 1.10)

- **A rough estimate with no evidence is capped at 50 years.** The savings line now says when a
  rough estimate is behind it (task 1.10); whether `LIFESPAN_ESTIMATE_YEARS` needs a tighter cap
  is a lifespan decision. (from 1.8.3, narrowed by 1.10)

- **Not exercised in task 1.10.** None of these came up in the five transcripts, so each still
  waits for a run that shows it: a follow-up query with a size or model number finding more
  factors (`follow_up_fault`, `agents/shared/research.py`); a model number one letter short
  losing a warranty (`names_product`); a `ProductGroup` variant with only a `lowPrice`
  (`tools/json_ld.py`); the "typical" material form against a market mix (`ESTIMATE_PROMPT`); a
  set's `piece_count` on the CO2e line; the type-level lifespan clamp on a different
  construction (`estimated_lifespan`); who speaks on an option's own page (`_value`,
  `agents/tco/answers.py`); a fit lost to the 6,000-character page cut (`with_page`); the
  smaller LCA review points (`_warranty` without "limited", a tier word as a name word); a
  findings summary stretching a short test; a currency word in its ordinary sense
  (`fault_in`); a currency on no list missing from the quoted phrase (`_widened`); the
  supervisor's second try for a category (`CATEGORY_CORRECTION`); "for induction" against the
  frying pan's brief. (from 1.7 to 1.9.8, judged in 1.10)
