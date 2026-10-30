# Roadmap: finished tasks

Tasks moved here from `ROADMAP.md` when they were completed, in the order they were done and with
their text unchanged. Nothing needs to read this file to start a task; open it to see what a
finished task promised, or to check a task again.

## Week 1 — the brains (core multi-agent logic)

- [x] **1.1 Project scaffold.** `pyproject.toml` (uv), package `src/shopper`, pytest, ruff,
  `.env.example`, minimal README, first commit pushed to `origin/main`.
  Read: `building_the_project.md`.
  Done when: `uv run pytest` passes on a placeholder test and the repo is on GitHub.
- [x] **1.2 Nebius client.** `config.py` and `llm.py` using the OpenAI-compatible endpoint, with
  the three tiers mapped to the documented model IDs. Confirm each ID responds, test whether each
  returns output that validates against a schema, and compare Nano with Lightning for the small
  tier. Before its pull request: bring the branch up to date with `main`, and update the comment
  in `src/shopper/config.py` that points to the old location of the model findings; they are now
  in `architecture/models.md`.
  Read: `architecture/models.md`, `building_the_project.md`.
  Done when: a script prints a completion and a schema-valid structured result from each tier,
  and the findings (IDs confirmed, structured output per model, small-tier choice) are recorded
  in `architecture/models.md`.
- [x] **1.2.1 Continuous integration and line endings.** Add `.gitattributes` normalising text
  files to LF and renormalise the repo, so files stop showing as changed for line endings alone.
  Add a GitHub Actions workflow that runs `uv run ruff check` and `uv run pytest` on every pull
  request and on pushes to `main`, with no secrets. Use current versions of the actions (check
  with the `docs-researcher` subagent). Pushing a workflow file may need the `workflow`
  permission on the GitHub login: `gh auth refresh -s workflow`.
  Read: `building_the_project.md` (Git, Tests: offline and live).
  Done when: this task's own pull request shows the checks running and passing, and
  `git status` is clean on a fresh checkout.
- [x] **1.3 Schemas.** `state.py`: every model in the data model table: source, request (with
  scope and category), decision factor, question, answer, product option (with factor values, materials,
  durability evidence and recurring cost), LCA result, listing, assumptions, trail entry,
  comparison, caveat, warning (with its closed set of codes), check item, evidence summary,
  report. Domain models only: no
  LangGraph state type (task 1.5.1) and no agent extraction schemas (each agent's own task).
  Read: `architecture/agents.md` (Data model), `architecture/supervisor.md` (Scope, Category), `architecture/interview.md` (Decision factors, Questions, How answers are used), `architecture/lca.md` (What every result carries, Rules), `architecture/calculations.md` (Inputs, Definitions, Changing the assumptions, Evidence summary), `adr/0001-euro-only.md`, and `GLOSSARY.md` at the repo root for names.
  Done when: schemas validate sample data in tests, including a report where every question was
  skipped, a declined report, an unclear report and a report with no options; and tests show
  the rules under the data model table are enforced (a lifespan without a source, CO2e low above
  high, a sixth question, a non-EUR currency, a budget of zero, a category on an unclear request
  and an unknown warning code are each rejected).
- [x] **1.4 Deterministic math.** `calc/`: cost per year including recurring costs, cost per use,
  purchases over a horizon, horizon cost and CO2e, comparison against a baseline, whether each
  option is within budget, the nothing-within-budget warning, recalculation from changed
  assumptions, and the evidence summary counts.
  Read: `architecture/calculations.md`, `architecture/agents.md` (Warning codes).
  Done when: unit tests cover both worked examples in the doc (frying pan and vacuum cleaner),
  the edge cases (zero or unknown lifespan, no uses per year, no recurring cost found), an
  option over, at and under the budget and one with no budget given, a budget below every
  option with and without a listing (warning, then no warning), a recalculation with a
  user-set lifespan, and an evidence summary where nothing is sourced.
- [x] **1.4.1 Schema hardening.** Fix the gaps found after 1.3 and 1.4: a negative price,
  a zero or negative lifespan and a negative CO2e value are accepted; a decision factor accepts
  a source that is not a URL; and an unknown baseline id passed to the comparison is echoed back
  silently, so every saving comes out missing. An unknown baseline id is a programming error
  and is rejected. The dictionaries on frozen models
  (`Assumptions.lifespan_overrides`, `ComparisonRow.missing_reasons`) can still be changed in
  place; that is left to the convention, not enforced.
  Read: `architecture/agents.md` (Data model), `architecture/calculations.md` (Definitions, Rules).
  Done when: tests show that each of the non-positive values is rejected, that a decision factor
  with a non-URL source is rejected, and that an unknown baseline id raises an error; and the
  existing tests still pass.

- [x] **1.5 Supervisor parsing.** `agents/supervisor.py`: turn the input into a request. Adds the
  scope `several_products` to `state.py`; like `unclear`, it carries no category. Code refuses
  over-long input, rejects empty input and finds the product URL; the small model, at
  temperature 0, names the category, classifies the scope and returns the budget phrase
  verbatim; code finds that phrase in the input, widens it to whole tokens and reads the amount
  and currency from it with a pure `read_budget` in `calc/budget.py`, so a mistyped budget ("5o
  euro") becomes a warning and is never read as 50. Scope and category are the model's
  judgement; there is no lookup table (see `supervisor.md`, "No lookup table"), and
  `src/shopper/data/scope_table.csv`, left from an earlier design, is deleted. The supervisor's
  prompt is a named constant beside the function: the job and the language rule, the category
  rule, the seven scopes with their precedence, the when-unsure rules and at most three worked
  examples each with its reason, the one-product rule with its examples, and the budget-phrase
  rule. It has no tone instructions, because the supervisor writes nothing the user reads.
  Every fixed message is a template in one module, `src/shopper/wording.py`, which imports
  nothing from the rest of the package; `calc/budget.py` takes its message from there too.
  Parsing is one function that takes the input, the model client and a tier, and returns the
  request, its warnings and its trail entries, or raises a typed error when the input is
  over-long or the model call fails; it knows nothing of LangGraph, so task 1.5.1 can wrap it
  as a node unchanged. `ChatRequest` in `llm.py` gains an optional temperature, which
  the Nebius API and the Nemotron models accept (`models.md`, "The client"). A first `cli.py` prints what was understood (category,
  budget, any warning), or the message for a request that does not run, and stops there. No
  graph, no questions, no report.
  Read: `architecture/supervisor.md`, `architecture/agents.md` (Data model, Warning codes, Agent contract, Adding an agent), `product.md` (Tone, Scope), `wording.md`, `eu_market.md` (Market), `adr/0001-euro-only.md`, `architecture/models.md` (Which component uses which tier, Rules, The client).
  Done when, offline (fake model replies, which prove what code does and nothing about how the
  model classifies): tests cover every row of both budget tables in `supervisor.md` and every
  entry of the other-currency list; the four phrase steps, including "40" out of "40 pounds",
  "50" out of "€150", a re-spaced phrase, a phrase that is not in the input, and an amount the
  model and code read differently; each repair; each input the model never sees, including the
  same URL twice; a category on a `several_products` request is rejected; the trail entries;
  each template in `wording.py` equals its row in `wording.md`, read from the doc by the test;
  no held-out evaluation product appears in the prompt; and a failed model call and over-long
  input each end with their own line and a non-zero exit.
  Done when, live: `cli.py "I need a new frying pan, budget 50 euro"` prints category "frying
  pan", scope `tuned` and a budget of €50; "budget 5o euro", "budget 0" and "budget £40" each
  print no budget and the matching warning; and the evaluation in `supervisor.md`
  ("Evaluation", about 24 cases) passes in two runs in a row. The evaluation is what shows
  that a food request and a car are declined, a Dutch request gets an English category, a
  fridge and a portable heater get `energy_heavy`, nonsense is asked to rephrase and two
  products are asked to name one.

- [x] **1.5.1 Graph skeleton.** Adds the LangGraph dependency (`uv add "langgraph>=1.2.13"`; no
  saved-checkpointer package yet). `graph.py`: the state type, the
  `parse_request` node wrapping the parsing function from task 1.5, stub agents in `agents/`
  (brief, TCO, LCA, second-hand) that say in the trail that they are stubs, the `interview` node
  that pauses after the brief and resumes with the answers, and the `assemble_report` node,
  which every outcome passes through: it runs `calc/` for real on the stub data and adds the
  caveat for the scope, the check-before-you-buy list, the evidence summary and the
  nothing-within-budget warning. The check list and the caveats are built by pure functions
  that `assemble_report` calls. The graph is built once (`build_graph`, with the model client,
  a checkpointer from `memory_checkpointer` and the bundle of four agent functions, the stubs
  by default) and then driven through two async functions: `start_session`, which returns what
  was understood with the questions, or the report for a request that does not run, and
  `resume_session`,
  which takes the answers and returns the report; the CLI in task 1.5.2 calls these four names
  and nothing else. `cli.py` is not changed in this task.
  Start with a spike: add the dependency and prove that the checkpoint serializer, with the
  allow-list collected from `state.py`, returns an equal value for one sample of every state
  type, including a `Report` with Decimals and `missing_reasons`. If it does not, stop and
  update `agents.md` ("The state") before building the graph.
  The stubs ignore the category and the answers. Each writes one `decided` trail entry whose
  summary starts with "Stub:", with no tier and no model, and every source a stub gives has the
  label "Stub value". Brief: two factors with `https://stub.invalid/...` sources and two
  questions, usage frequency (every day 365, a few times a week 150, about once a week 50, a
  few times a year 10) and hob compatibility (gas, electric, induction); no stated answers.
  TCO: the two options of the frying-pan worked example, lifespans sourced as `model_estimate`
  with reference "stub", and on each a hob-compatibility factor value with fit `unverified`.
  LCA: no result for either option and no warning; a made-up CO2e figure is never returned.
  Second-hand: no listings, and the entry "Stub: used listings are not searched yet".
  Read: `architecture/agents.md`, `architecture/interview.md` (Flow, Questions, How answers are used), `architecture/calculations.md` (the frying pan worked example, Evidence summary), `architecture/supervisor.md` (What code does and what the model does, Trail), `wording.md`, `building_the_project.md` (Dependencies), `code_conventions.md` (Python, Tests), and `GLOSSARY.md` at the repo root for names.
  Done when: offline tests, with a fake model client, start a session for "I need a new frying
  pan, budget 50 euro" and get the request and the stub questions, then resume it once with
  both questions answered (usage "about once a week", hob "induction"), once with usage chosen
  and hob "not sure", and once with every answer skipped, and each time get a
  report whose figures match the worked example and whose trail shows the supervisor and every
  stub; the fully answered report has the worked example's cost per use and two `unverified`
  items on the check-before-you-buy list (hob compatibility, one per option), the not-sure one
  has a single `unanswered` item, and the skipped one has no cost per use and the same single
  item, usage frequency never being on the list; direct tests of the pure functions cover a
  stated answer (no check item), each scope's caveat, and a stated usage answer whose uses per
  year reach the assumptions;
  the evidence summary shows two lifespans estimated and two footprints missing; a declined
  request, an unclear request and one naming several products each leave the graph as a report
  holding only the request, its trail and its warnings, with no pause; a fridge request's
  report carries the energy caveat; a budget warning is in the state at the pause and on the
  report; a budget below every stub option adds the nothing-within-budget warning, and a budget
  of €30 marks the €40 option as over budget without it; with a
  brief, passed in through the agent bundle, that returns no questions the graph still pauses,
  and resuming with no answers returns the report with the worked example's figures; the state
  reloaded after a pause holds model instances, and the report saved at the end equals the one
  returned; resuming an unknown session and resuming a finished one each raise their own typed
  error; resuming a session whose parsing call failed raises the not-paused error and makes no
  model call; answers naming a factor with no question or a choice that is not on its
  question, two answers for one factor, an answer with a status other than chosen or not sure,
  and an answer that carries its own uses per year each raise, and the session can still be
  resumed; no test asserts the order of the LCA and second-hand trail entries; a failed
  supervisor call raises the typed error and no report exists; and the tests from task 1.5
  pass unchanged.

- [x] **1.5.2 Terminal interview and report.** **Read `terminal_app.md` first, and keep it
  simple:** the terminal app is a tool for testing and small prototyping, not the product, so
  build only what that doc and this entry list, with plain `print` and `input`.
  `cli.py` now runs the graph through the four names from task 1.5.1: it shows what was
  understood (category, budget, any warning), asks each question with its reason and numbered
  choices, and prints the report as plain sections ending with the trail. The report's lines
  come from a new module, `report_text.py`. The keys at a prompt, the order of the sections,
  where the code goes and the words of every new label are settled in `terminal_app.md`; the
  new labels get their rows in `wording.md` and their templates in `wording.py` in this task.
  Every number printed is one `calc/` produced; the CLI only formats.
  Read: `terminal_app.md`, `wording.md`, `architecture/interview.md` (Flow, Questions, Check before you buy), `product.md`, `architecture/calculations.md` (Definitions, Rules, Evidence summary), `architecture/agents.md` (The graph, Data model), `eu_market.md` (Market).
  Done when: `cli.py "I need a new frying pan, budget 50 euro"` runs end to end on stubs, once
  with typed answers and once with `--skip-all`, and prints the evidence summary line, the
  comparison with the worked example's figures, the check-before-you-buy list and the trail;
  typing "skip all" at the second question skips the rest; an answer that is not a listed
  number is asked again; a food request, nonsense input and a failed supervisor call print the
  same lines as in task 1.5; a fridge request prints the energy caveat; "budget 5o euro" shows
  its warning before the questions and again on the report; `tests/test_graph.py` and the
  tests in `tests/test_cli.py` for a request that does not run, a failed model call and
  over-long input pass unchanged; and the three `test_cli.py` tests of what was understood are
  rewritten to check the opening lines.

- [x] **1.5.3 Budget currency judged by the model.** A supervisor change only; `cli.py` and
  `report_text.py` are not touched. Today `read_budget` in `calc/budget.py` ignores a word on
  no currency list, so "budget 10 dolla" and "10 pesos" become a €10 budget with no warning.
  The lists stay as a floor and the model judges the rest. `Extraction` in
  `agents/supervisor.py` gains `budget_currency` (`eur`, `other`, `none_stated`), required and
  nullable like its other four fields, with its enum beside it and not in `state.py`; the prompt
  names five fields and gains a line for it. `read_budget` takes the judgement as an optional
  second argument and applies the order in `supervisor.md` ("Words on no list"): a listed other
  currency first, then a euro marker, then the model. The trail reason for a budget dropped on
  the model's judgement reads `budget_other_currency (judged by the model)`; the warning the
  user reads is the same either way. `extraction` in `tests/fakes.py` always writes the field
  and takes it as a fifth optional argument, so no test call changes. In `tests/eval/`, `Case`
  gains an optional expected budget outcome (the warning code, or a euro amount), judged by its
  own function from the parsed request and its warnings; the `(scope, category)` answer and
  the tests that build it stay as they are. Check with `check_models` or the live run that the
  small tier fills the field under the strict schema.
  Read: `architecture/supervisor.md` (What code does and what the model does, Budget, Trail, the evaluation), `architecture/agents.md` (Warning codes), `wording.md` (Warnings).
  Done when: unit tests cover the three steps of the order with the judgement given, including
  "€50 (about $55)" giving the warning and "50 max" with `none_stated` giving €50; the four
  "Budget currency" cases are in `tests/eval/` with an offline test of their judging; every
  earlier test passes unchanged; and one live evaluation run, approved by the user when the
  task starts because it spends credits, passes twice in a row.

- [x] **1.5.4 A dropped category gets a second try.** Today a category that fails the form
  check is dropped, and with no link the request becomes `unclear`, although the product was
  understood ("frying pan 28 cm"). The parsing function asks the model once more, naming the
  category it gave and the rule it broke; a second failure is dropped as today. Nothing new is
  shown to the user: they confirm the result the usual way, from what is shown back above the
  questions, and no new state, wording or API step is added. Suggesting a category to the user
  was considered and rejected (a new pause, wording and page step for little gain). "Repairs" in
  `supervisor.md` changes, which now says repaired, not retried.
  Read: `architecture/supervisor.md` (Category, Corrections), `architecture/models.md` (Rules).
  Done when: a fake reply of "frying pan 28 cm" followed by "frying pan" gives the category
  "frying pan" with a trail entry for the second try, two failing replies leave the request
  `unclear`, and a category that passes makes one model call.

- [x] **1.6 Web search and product-page tools.** The tools only; nothing in the graph uses them
  yet. Tavily search over plain `httpx` (declare it with `uv add`), with the search purposes,
  fixed parameters and per-purpose domain lists in `config.py`; Firecrawl page fetch (markdown
  and raw HTML) with JSON-LD parsing for name and euro price; one amount parser in `calc/`
  shared with the budget; the on-disk cache and the fixture twin in one stored format; typed
  failures; the per-agent call limit and the daily ceiling; `SHOPPER_SOURCES` and
  `TAVILY_DAILY_CREDIT_LIMIT` in `config.py`, `.env.example` and the table in
  `building_the_project.md`. The agent types in `agents/bundle.py` and `build_graph` take the
  tools; the stubs ignore them and the graph tests from task 1.5.1 keep passing. One live run,
  at most three calls, confirms the three points `data_sources.md` lists as "to confirm"; its
  findings are written there.
  Read: `architecture/data_sources.md`, `adr/0003-code-driven-research-loop.md`, `architecture/agents.md` (The graph, Agent contract).
  Done when: against fixtures, a repeated search query makes no network call, the call after an
  agent's limit returns `limit_reached`, a fetched product page gives its name and euro price,
  a second fetch of the same link makes no network call, a blocked page gives a typed failure,
  and each HTTP failure kind is covered by a test with an injected transport.
- [x] **1.6.1 Pasted link in the graph.** The node that fetches the pasted link after the
  supervisor; where the fetched product lives in the state; the model's read of the markdown
  for what JSON-LD lacks (decide the tier here); the category taken from the product name when
  the supervisor had none; the four outcomes of the table in `data_sources.md` ("An unreadable
  link"). Adds the warning code `link_unreadable` and the fixed words for the session that
  ends, to the enum, the table in `agents.md`, `wording.md` and `wording.py`. Proposed words,
  to be approved: "We couldn't read the product at your link, so it is not among the options
  below. These are options for {category}." and "We couldn't read the product at your link.
  Name the product to start, for example 'a frying pan, budget €50'."
  Read: `architecture/data_sources.md` (Firecrawl), `architecture/supervisor.md` (Category), `architecture/agents.md` (The graph, Warning codes), `wording.md`.
  Done when: in the CLI, a pasted product link yields a populated product option, a second run
  of the same link makes no network call, an unreadable link with a known category continues
  with the warning, and an unreadable link with no category asks for the product name.
- [x] **1.7 Category research and questions.** Research the category's decision factors with
  sources (including consumables and care) and turn them into three to five questions with
  reasons and choices; usage frequency is always one of them and is asked last; "not sure" and
  skipped answers go to the check list. Stated answers and the pasted link are task 1.7.1, so
  until then a request that says "for induction" is still asked the hob question. Everything
  below was decided before the task. Bring `interview.md`, `agents.md`, `data_sources.md`,
  `terminal_app.md`, `wording.md` with `wording.py`, and `models.md` in line with it here.

  Factors. A researched factor's source is a web URL; the factor of kind `usage` has none.
  Eight caps the researched factors only, inside the brief agent; the report's bound rises to
  nine. Factor ids carry a prefix per origin (researched, usage, user), so a cached id never
  collides with another. Each researched factor keeps its citation's `stated_by` on its trail
  entry and in the cache. Code rejects a digit, a currency marker or a generic environmental
  term (`eu_market.md`) in every string the model writes: a factor whose name or `why` fails is
  dropped with an `excluded` trail entry, and a question or reason that fails counts as not
  phrased. A recurring-cost factor carries no amount yet (task 1.8.1).

  The usage question. The usage ladder (`GLOSSARY.md`) is a code constant of seven rungs:
  several times a day 1,000; every day 365; a few times a week 150; about once a week 50; about
  once a month 12; a few times a year 4; about once a year 1. In the phrasing call the small
  model picks four rungs by id for the category. A valid pick is four distinct known ids, which
  may skip rungs, and is shown in ladder order. Otherwise, and when there are no researched
  factors, code offers 365, 150, 50 and 12. The model never writes uses per year. The stub's
  usage question is built from the ladder, and the graph tests from task 1.5.1 keep passing the
  stub bundle.

  The other questions. One question per factor, in research order, at most four; a factor that
  could not be phrased is skipped. For a `compatibility` or `requirement` factor the small model
  writes two to four choices: every number in a choice must be found in the cited result's
  text, and a choice has a maximum length in `config.py`, because it fills search queries in
  task 1.8. For a `care` factor the model writes one statement that opens "Some {category}s
  ..."; code adds the closing question "Is that fine with you?" and the pair "That's fine" and
  "I'd rather avoid it", which have constant choice ids. A `recurring_cost` factor gets no
  question until task 1.8.1 and so appears on the check-before-you-buy list. "It doesn't matter
  to me" is not an answer: record it in `interview.md` as an open question.

  Research follows `data_sources.md` ("Research rules"): two template searches run together,
  one read, and one follow-up search when the read reports gaps or fewer than three factors
  survive. The follow-up has the purpose `category`; in fixtures mode it is skipped with a
  trail entry, because the fixture twin raises on a search query it has no fixture for. A
  request with no category (a pasted link whose page named none) gets no research and no cache
  read or write: the usage question only, one `decided` trail entry and no warning.

  Cache. A typed brief store in `tools/` (a `Protocol`, built from the sources' cache folder and
  clock) is passed to the brief agent, so `BriefAgent`, the stub and the `brief` node change
  here. It keeps one file per category in `.cache/<mode>/brief/`: the factors, a phrased
  question per eligible factor and the ladder pick. A brief is stored only when both template
  searches, the read and the phrasing succeeded. With three or more factors it does not expire;
  with fewer, zero included, it lasts one day. The key is the normalised category plus a hash of
  the prompts, the search templates, the two model IDs and the quote-check rule. On a hit the
  trail replays the stored research entries after one entry that says they come from the cache
  and when they were researched.

  Warnings (enum, table in `agents.md`, `wording.md`, `wording.py`); the words are approved.
  `research_unavailable`, whenever the brief ends with no researched factor: "We couldn't
  research {category}, so the questions and the check list are shorter than usual."
  `questions_unavailable`, when there are factors but the phrasing call failed twice: "We
  couldn't prepare the questions for {category}. What they would have asked about is on the
  check-before-you-buy list." Either way the session continues with the usage question. One or
  two factors is not a warning; the trail records the gaps.

  Terminal app and wiring. `SessionStart` gains the factors. Under each researched question the
  CLI prints "Source: {site}", and for a factor a manufacturer or a seller stated, "Source:
  {site} (the manufacturer states)" or "(the seller states)"; the site name comes from a pure
  helper. The usage question has no source line. While research runs the CLI prints
  "Researching {category}...". `STUB_AGENTS` stays whole; a default bundle holds the real brief
  and `cli.run()` takes the bundle, so the CLI tests choose theirs.

  Verification. Run it live for frying pan, kettle and drill (at most nine Tavily credits).
  Replace the hand-written example.org fixtures with trimmed real ones, keyed to the categories
  the supervisor returns ("drill", not "cordless drill"), add the consumables-and-care ones, and
  keep at least three quotable factors in each. Then run the read three times per category on
  the cached searches, which spends no Tavily credits, and record the range of surviving
  factors in `data_sources.md`. A category falls short when two of the three reads give fewer
  than three factors. If a tuned category falls short, relax the quote check for text values
  only: the model also returns a key term, and code keeps the factor only when that term is
  found in the cited result's text; a number always stays in its quote. Full page text is not
  tried here; if the relaxed check still falls short, add a roadmap task for it. The target is
  questions within 10 seconds for a cached category and 30 seconds for an uncached one, from
  pressing Enter: measure with `Measure-Command` around a `--skip-all` run, record it in
  `models.md`, and replace the "within a few seconds" rule there. A miss is recorded and becomes
  a roadmap task.
  Read: `architecture/interview.md`, `architecture/data_sources.md` (Research rules, Search purposes, Calls per analysis, Cache and fixtures), `architecture/agents.md` (The graph, Data model, Agent contract, Warning codes), `product.md`, `wording.md`, `terminal_app.md`, `eu_market.md` (Environmental claims), `architecture/models.md` (Which component uses which tier, Rules), and `GLOSSARY.md` at the repo root for names.
  Done when: for three different categories the CLI shows sourced questions with their source
  lines and no researched factor lacks a source; a second run of the same category is answered
  from the brief cache and its trail says so; with the search tool failing the CLI shows the
  usage question and `research_unavailable`; with the phrasing call failing it shows the usage
  question and `questions_unavailable`; a test shows a figure in a model-written question is
  rejected; and the measured times and survival rates are recorded.
- [x] **1.7.0 One folder per agent.** Move the agents into one package each, with `git mv` so
  history follows, and change nothing else. `agents/<agent>/` holds `agent.py` (the agent
  function), `prompt.py` and, where the agent has them, `models.py` and `checks.py`: so
  `brief.py`, `brief_prompt.py`, `brief_models.py` and `brief_checks.py` become
  `agents/brief/agent.py`, `prompt.py`, `models.py` and `checks.py`; the same for `supervisor`
  and `linked_product`. The helpers every research loop shares, `research.py` and
  `model_text.py`, move to `agents/shared/`. `bundle.py`, `stubs.py` and `default.py` stay in
  `agents/`. Tests mirror the layout (`tests/agents/brief/`, ...) and keep file names that are
  unique across folders, because of pytest's default import mode. Update every path in the
  docs: `code_conventions.md` ("Prompts are data", "One concern per module"),
  `service_architecture.md` (Repo layout) and the `agents/...` paths named in
  `docs/architecture/`. Before starting, merge or close the open branches that touch `agents/`,
  or they will conflict.
  Read: `code_conventions.md`, `service_architecture.md` (Repo layout, Architecture rules), `architecture/agents.md`.
  Done when: each agent is in its own folder and the shared helpers in `agents/shared/`; no
  import or doc names an old path; git shows the moves as renames; and `uv run pytest` passes
  with the same number of tests as before the move.

- [x] **1.7.1 Stated answers.** One small-model call per request, after the factors are known,
  reads what the request already states. It sees the request text, the factors and their
  choices, and is told the category and the budget are already known. Per requirement it returns
  the factor (or "new"), the choice when one fits, and the exact phrase. Code keeps a
  requirement only when its phrase is found in the request, after the same normalising the
  budget phrase and the quote check use (one shared helper); one that is not found goes to the
  trail only. A requirement that fits a factor but none of its choices is a `stated` answer with
  a free-text value, and that factor gets no question. A requirement that fits no factor goes to
  the trail only until task 1.7.3. A stated usage is mapped onto any of the seven usage
  frequencies, not only the four offered: the model returns the phrase and the frequency id, and
  code copies the uses per year from it. With no clear frequency the usage question is asked.
  Stated answers are shown above the questions (`wording.md`): "From your request: {factor}:
  {value} ("{phrase}")", and for usage "From your request: {frequency}, {n} uses a year
  ("{phrase}")". When the call fails twice, every question is asked and the new warning
  `stated_answers_unavailable` is raised (enum, table in `agents.md`, `wording.md`,
  `wording.py`); approved words: "We couldn't pick out the requirements in your request, so only
  your answers to the questions are applied." Measure the time until the questions appear,
  because this adds a call to the cached path.
  Read: `architecture/interview.md`, `architecture/agents.md` (The graph, Data model, Agent contract, Warning codes), `architecture/supervisor.md` (Category), `architecture/data_sources.md` (Research rules), `wording.md`, `terminal_app.md`, `architecture/models.md` (Which component uses which tier, Rules).
  Done when: "a frying pan for induction, I cook every day" asks neither the hob nor the usage
  question, shows both lines above the questions and both as stated on the report; and with the
  call failing the CLI asks every question and shows the warning.

- [x] **1.7.3 Requirements the user states.** A requirement from the call of task 1.7.1 that
  fits no factor becomes a factor of kind `requirement` with a source of kind `user` and an id
  prefixed `user-`: its name is the user's phrase and its `why` is the fixed text "You asked for
  this." At most three, not counted toward the eight (the report's bound rises to twelve); one
  past the cap goes to the trail only. Code refuses a new requirement whose phrase is a generic
  environmental term (`eu_market.md`), the budget phrase or the URL; a refused one goes to the
  trail only.
  Read: `architecture/interview.md`, `architecture/agents.md` (Data model), `eu_market.md` (Environmental claims), `wording.md`, `terminal_app.md`.
  Done when: a drill "with a spare battery" shows the user's factor; "an eco-friendly pan"
  creates no factor; and a request with four extra requirements keeps three and puts the fourth
  in the trail.
- [x] **1.7.4 The pasted-link interview.** With a linked product the brief asks at most two
  researched questions and the usage question; the two are the first two `compatibility` or
  `requirement` factors in research order, phrased about the user's situation and never as a
  claim about the product. The brief agent's signature gains the linked product. A link that
  could not be read gets the full interview. Rewrite the pasted-link section of `interview.md`
  to match; the mismatch between the linked product and an answer is found in task 1.8.
  Read: `architecture/interview.md`, `architecture/agents.md` (The graph, Agent contract), `architecture/data_sources.md` (Research rules), `terminal_app.md`.
  Done when: a pasted link asks at most three questions, none of them a claim about the
  product; and a link that could not be read gets the full interview.

- [x] **1.7.2 Time to the questions.** Task 1.7 measured 41.8 to 59.3 s from pressing Enter to
  the questions for an uncached category and 7.4 to 19.6 s for a cached one, against targets of
  30 s and 10 s (`docs/findings/task_1.7.md`). Uncached, most of the time is the read
  on the medium tier (16 to 37 s, up to 7,485 tokens with its reasoning) and, when a follow-up
  runs, a second read; cached, it is starting the app (2.8 s) and the supervisor's parsing call
  (3.5 to 11.6 s). Find what shortens them without losing factors or questions, measuring each
  change on the cached searches of the three tuned categories: for example a shorter text per
  search result in the read, phrasing that starts per factor while the read is still running,
  or a lower reasoning effort where the model supports one. Record what was tried in
  `docs/findings/task_1.7.2.md`.
  Read: `architecture/models.md`, `architecture/interview.md` (How the brief is researched), `architecture/data_sources.md` (Research rules, Calls per analysis), `terminal_app.md`.
  Done when: the measured times of frying pan, kettle and drill are within the targets, with the
  surviving factors and phrased questions no fewer than in task 1.7; or the developer agrees to
  other targets, which `models.md` then states.

- [x] **1.8 Option research experiment.** A script run by hand (about 24 credits), before any
  option research is built: three discovery query shapes (general, with the chosen answers, with
  the budget phrase), each with and without the preferred testers named and with and without the
  Netherlands boost, on the three tuned categories; the price search for two known products; and
  a recurring-cost search aimed at euro amounts. The measure: of six candidates, how many get an
  accepted euro price, is one of them cheap, how many have at least one quoted durability hint in
  a discovery result that names them, and how many recurring costs survive. Save the responses in
  the cache format, keep the useful ones as fixtures, and write the findings into
  `docs/findings/task_1.8.md`, with the discovery query shape and country the results support.
  Read: `architecture/data_sources.md` (Research rules, Search purposes, Option research, Cache and fixtures), `eu_market.md`, `adr/0002-fixed-rate-conversion-recurring-costs.md`.
  Done when: the findings file answers each measure for each category, names the discovery
  query shape and country chosen with the reason, and the fixtures the next tasks use are saved.

- [x] **1.8.2 Candidates, prices and selection.** Steps 1 to 4 of option research
  (`option_research.md`): discover, shortlist, price, select, as that doc describes them.
  - Shortlist: up to six candidates with brand, marked hints (`years` and `lifetime` read by
    code) and, for a set request, a quoted piece count; the linked product and any candidate
    with a quoted `fails` are dropped.
  - Price: one read per candidate with the page kind, stock, variant and the open flag list;
    the name check needs the brand plus one other word of the name; `calc/amounts.py` reads
    "86 euro en 98 cent"; several prices are narrowed as the doc says; a fixture miss for a
    model-written name is `not_recorded`.
  - Select: slots filled in order with exclusion and deterministic ties; an empty slot gets a
    `decided` trail entry.
  - Schema: `ProductOption` gains `price_source`, `price_seen_on` (a date; all three or none
    with `price`), `price_variant` and `piece_count`; `CheckReason` gains `price`, the only
    reason with no factor. `SearchOutcome` and `ProductPage` carry `retrieved_at`, also on a
    cache hit. `read_link` sets the linked product's price source and date. `TcoAgent` takes
    the request, the linked product, the factors, the questions and the answers, and returns
    the linked product among its options, so `_tco` in `graph.py` no longer adds it.
  - Warnings: `one_option_only` and `no_options_found` (three wordings, chosen in the doc's
    order) in the enum, `wording.py` and their tests; the rows are in `wording.md`.
  - Change the comment on `MAX_CHOICE_CHARACTERS` in `config.py`: the limit is now for the
    question's layout.
  - Required tests: the Fellow Corvo EKG and Hario Buono price fixtures with the expected price;
    "Russell Hobbs 28081-70 Structuur" accepted and another model of the brand rejected;
    "Niet op voorraad" read as not in stock; outliers on [30, 35, 100]; the cheapest candidate
    that is also the most durable.
  - Write `docs/findings/task_1.8.2.md`: per tuned category, how many candidates got an accepted
    price (7 of 18 by hand in task 1.8), whether a cheap one did, how many price searches came
    back empty, and, checked by hand, how many hints were about another product.
  Read: `architecture/option_research.md`, `docs/findings/task_1.8.md`, `architecture/data_sources.md` (Research rules, Search purposes, Calls per analysis, Cache and fixtures), `architecture/agents.md` (The graph, Data model, Agent contract, Warning codes), `eu_market.md`, `wording.md`, `architecture/models.md` (Which component uses which tier, Rules).
  Done when: the CLI prints up to three priced options, each with "price seen at <site>" and its
  link, for the three tuned categories; every candidate left out and every empty slot has its
  reason in the trail; and both warnings, each `no_options_found` wording included, show on a
  fixture that causes them.

- [x] **1.8.5 Confirm prices on the shop page.** Step 5 of option research, as
  `architecture/option_research.md` ("Confirm") and `adr/0004-firecrawl-confirms-shop-prices.md`
  describe; the design was settled and the live check made before the task
  (`findings/task_1.8.5.md`). bol.com joins the price purpose's excluded domains, and code drops
  excluded domains from every search's results, so the recorded price searches behave like
  live ones. A shop on the config list of shops that publish no offer data (`amazon.*`) is not
  read: its search price stays unconfirmed. Every other selected option's price page is read
  once, in parallel; one offer reader serves these pages and the pasted link. Selecting again
  reruns the pure `select()` of task 1.8.2 on the pool with the confirmed prices until every
  selected option is confirmed, kept unconfirmed or dropped. "Confirm the current price" stays
  on the check-before-you-buy list only for an unconfirmed option. Add the fourth wording of
  `no_options_found` (none in stock where it was priced) to `wording.md` and `wording.py`, words
  to be approved. Record real pages for the three tuned categories, at most 15 reads, trimmed to
  the JSON-LD and the stock lines; hand-edit a copy only where no live page shows the case.
  Note in `left_over_tasks.md`: trying a dropped candidate's next shop, and the linked
  product's stock. The section "Firecrawl, for a pasted product link" in `data_sources.md` is
  now "Firecrawl"; update the docstrings that name it.
  Read: `architecture/option_research.md`, `adr/0004-firecrawl-confirms-shop-prices.md`, `findings/task_1.8.5.md`, `architecture/data_sources.md` (Rules for every source, Search purposes, Calls per analysis, Cache and fixtures, Failure kinds, Firecrawl), `wording.md`, `eu_market.md`.
  Done when: on recorded pages, an out-of-stock option is replaced by the next selected
  candidate, a changed price is taken from the page, a page with no offer drops its option, a
  bol.com result is never a price, and the Fellow Corvo EKG is not priced at bol.com's €86,98.

- [x] **1.8.3 Option evidence.** Step 6 of option research: one search per product option,
  the linked product included, for durability evidence and recurring costs, and one read of its
  results. A sourced lifespan needs a quoted number of years; otherwise it is a model estimate
  built from the durability evidence. Add the fixed-rate conversion of
  `adr/0002-fixed-rate-conversion-recurring-costs.md` for recurring costs. The terminal prints
  what each lifespan rests on. The design is settled in `option_research.md` ("Evidence"),
  including the live check that picks the template; the shortlist moves to full reasoning.
  Answers are task 1.8.6, which extends this read.
  Read: `architecture/option_research.md`, `architecture/data_sources.md` (Research rules, Search purposes), `architecture/agents.md` (Data model, Agent contract), `product.md` (Durability evidence), `eu_market.md` (Guarantees and lifespan), `architecture/calculations.md`, `adr/0002-fixed-rate-conversion-recurring-costs.md`, `wording.md`, `terminal_app.md`.
  Done when: the CLI prints cost per year and cost per use for three categories, each lifespan
  shows its evidence or is marked as a rough estimate, a recurring cost in USD shows converted
  and labelled (a test with a recorded model reply over a real result counts, when no live run
  finds one), and `docs/findings/task_1.8.3.md` records the live check.

- [x] **1.8.7 Fewer lost options.** The live runs of task 1.8.3 selected 2, 2 and 1 options for
  the three tuned categories. Priced candidates were lost two ways: selection left a slot empty
  while one was left over (the Demeyere Atlantis at €189,90, with a quoted `limits_life` hint), and
  "Confirm" rightly dropped three listing or search pages (beslist.nl, supersales.nl,
  grizzlytools.shop, whose €18,69 was a drill chuck) with no second shop tried
  (`left_over_tasks.md`, 1.10). As `option_research.md` now describes ("The shortlist",
  "When a price is accepted", "Selection", "Confirm") and ADR 0004's amendment for this task:
  - The shortlist returns each candidate's `durability_judgement`, `long`, `medium`, `short` or
    `unknown`, against most products of its kind, with a one-line reason naming the make; the
    schema and the prompt describe each value. A missing judgement or a reason that fails the
    text check counts as `unknown`.
  - A slot whose own rule finds no candidate is filled from the priced candidates left: within
    the budget first, then judgement (`long`, `medium`, `unknown`, `short`), then price, then
    shortlist order; a candidate with a quoted `limits_life` hint only when none without one is
    left. The durable pick stays on quoted hints alone. The `decided` entry says the slot's rule
    found nothing and, when the judgement decided, "judged by the model" with value and reason.
    The judgement is never on the report.
  - A candidate dropped at "Confirm" tries its next accepted price once, from another site in the
    same price read, within the 5 reads.
  - An Amazon price is accepted only from a product page (`/dp/`, `/gp/product/`).
  Read: `architecture/option_research.md` (The shortlist, Price, Selection, Confirm), `adr/0004-firecrawl-confirms-shop-prices.md`, `docs/findings/task_1.8.3.md`, `architecture/models.md` (Rules).
  Done when: offline tests on pools rebuilt from the three trails of task 1.8.3
  (`.cache/live/check_1_8_3/`) show an empty slot filled with its `decided` entry, a candidate
  with a quoted `supports_long_life` hint outranking one judged `long`, a `limits_life` candidate
  filling a slot only when nothing else is left, grizzlytools.shop's drop followed by one try of
  the next price, and an amazon.de `/s?` price refused; and one live `--skip-all` run of the
  three categories (about 20 Tavily credits) gives three options wherever three priced
  candidates survive "Confirm", recorded in `docs/findings/task_1.8.7.md`.
- [x] **1.8.6 Option answers.** The evidence read of task 1.8.3 also writes the factor values,
  as settled in `option_research.md` ("Evidence", "Answers"): it also sees the confirmed price
  page and the linked product's page (cached, no credit), judges each answered factor, and a
  `meets` or `fails` stands only on a quote code finds in a passage that names the product;
  anything else is `unverified` and goes on the check-before-you-buy list. A `fails` removes the
  option with no refill and the warnings are worked out after this step; a `fails` on a
  `care-avoid` factor marks the option; the linked product gets the mismatch line instead. The
  shortlist's fits stay a pre-filter only. `FactorValue.value` becomes optional (empty only when
  `unverified`; the stub changes with it). Add the four rows of `terminal_app.md` ("Factor
  values") to `wording.md` and `wording.py` together. Re-record the evidence fixtures the prompt
  change makes stale. Write `docs/findings/task_1.8.6.md` with the counts of `meets`, `fails` and
  `unverified` per option from the live runs.
  Read: `architecture/option_research.md` (Evidence, Confirm), `architecture/data_sources.md` (Research rules), `architecture/agents.md` (Data model, Warning codes), `architecture/interview.md` (How answers are used, Check before you buy, Pasted product link), `wording.md`, `terminal_app.md`.
  Done when: in live CLI runs, an answer visibly excludes an option (its `excluded` trail line),
  a `care-avoid` answer marks an option without excluding it, and a pasted link whose product
  does not meet an answer shows the mismatch line. Suggested cases: an induction answer for a
  frying pan, `care-avoid` on hand washing, a link to a pan whose page says it is not for
  induction with "for induction" in the request. A scenario the real pages do not produce is
  proven by an offline test instead, and named as unproven live in the findings and in
  `left_over_tasks.md`.

- [x] **1.8.4 Owner and tester findings.** Step 7 of option research, as settled in
  `option_research.md` ("Findings") and `docs/adr/0005-findings-summarised-quote-logged.md`: one
  search and one read per product option, at the same time as "Evidence" and merged after it;
  up to three durability findings, each a checked summary with its kind set from `stated_by`,
  its source and link, and an overall rating only from its own checked rating quote; the quote
  logged at debug level, never on the trail. `Finding` gains `summary`, `source` and
  `published_date` in place of `text` and `url`; durability evidence gains the findings state.
  First the live check, with its rule fixed before credits are spent: two templates, full page
  text or not, little or full reasoning (about 18 Tavily credits); results in
  `docs/findings/task_1.8.4.md`, and the same run records the fixtures. Add `SHOP_DOMAINS` to the
  findings purpose's excluded domains. Add the findings words to `wording.md` and `wording.py`
  together, and show "No durability evidence found" only when there are no findings either.
  Read: `product.md` (Durability evidence), `architecture/option_research.md` (Findings, Evidence), `adr/0005-findings-summarised-quote-logged.md`, `architecture/data_sources.md` (Research rules, Search purposes, Cache and fixtures), `architecture/agents.md` (Data model), `terminal_app.md` (What a lifespan rests on), `wording.md`.
  Done when: for the three tuned categories, findings appear in the CLI with their site and
  link, or as "No owner or tester reports found"; a failed search shows "Owner and tester
  reports not looked up"; tests show a summary sharing 6 words with its source, a generalised
  owner report and an owner rating with no review count are each dropped; an offline test fails
  when a tuned category's findings search is `not_recorded`; and no quote reaches the trail.

- [x] **1.8.1 Typical yearly cost of a consumable.** Settled in a design interview, then
  revised during the task at the developer's request: the recurring-cost question with "I'd
  rather avoid it" became an information line, because every option of such a category has the
  cost and declining it changed nothing on the report (`docs/findings/task_1.8.1.md`,
  "Revision").
  - **The read.** Only the first `recurring_cost` factor the brief read gives gets an amount:
    an amount quote, an interval quote and an optional pack-count quote, all from the result
    that factor cites. The typical yearly cost is computed in code by the helper the option's
    recurring cost uses, moved out of `agents/tco/recurring_cost.py` so the brief and the
    options share it (amount, pack count, interval parser in `calc/recurring.py`, and the
    fixed-rate conversion for USD and GBP). `DecisionFactor` gets
    `typical_yearly_cost_converted_from`. An amount that fails a check (quote not in the
    result, no interval in time, a pack with no count, an unsupported currency) leaves the
    factor with no amount, with an `excluded` trail entry giving the reason. No follow-up
    search is added for a missing amount. The prompt change changes the brief cache's hash, so
    stored briefs are researched again.
  - **The line.** Code writes it from fixed words in `wording.md` (factor, amount, site, and
    "converted from {currency} at a fixed rate" when converted), shown after the "From your
    request" lines above the questions and on the report, also for a pasted link. A
    recurring-cost factor gets no question and takes no place among the four; the phrasing
    call never sees it. It has no answer, so it stays on the check-before-you-buy list, with or
    without an amount. Nothing in the options changes: their figures use their own recurring
    cost.
  - **Docs.** "Recurring costs are factors" and "Questions" in `interview.md`; the "Which
    factors" note in `option_research.md` ("Answers"); the line in `wording.md`; the report
    layout in `terminal_app.md`; a row "Typical yearly cost on a recurring-cost factor" in the
    table of ADR 0002.
  - **Live run.** Re-record the consumables-and-care fixtures and run the vacuum cleaner live;
    record the credits used in `docs/findings/task_1.8.1.md`. The USD case may come from a
    recorded fixture when no live source states dollars.
  Read: `architecture/interview.md`, `architecture/option_research.md` (Recurring cost, Answers), `architecture/data_sources.md` (Research rules, Cache and fixtures), `architecture/calculations.md`, `adr/0002-fixed-rate-conversion-recurring-costs.md`, `wording.md`.
  Done when: for a category with a consumable (a vacuum cleaner's filters) the CLI shows the
  typical yearly cost with its source, computed in `calc/`, above the questions and on the
  report, and asks no question about it; a cost stated in USD is shown converted and labelled;
  and a source with no interval gives the factor with no amount and no line.
- [x] **1.9.1 Tier 3 data model and arithmetic.** No model call yet. A new domain model
  `LcaInput` (name, form, the source of the name and form, mass and its source, factor low
  and high in kg CO2e per kg and its source) replaces `Material` in `LcaResult.inputs`;
  `LcaResult` gains a manufacturing and assembly range with its source. A pure function in
  `calc/` sums mass times factor plus manufacturing, at each end, then widens the total to
  high at least twice low around the geometric midpoint (the ratio in `config.py`; the reason
  for 2x in `lca.md`). Weight scaling: when the linked product's page states a weight, scale
  only the assumed masses of bulk materials, never a sourced mass nor a separate component
  (electronics, motor, battery), so the total matches, and only when the scale lies between
  0.5 and 2; otherwise keep the masses and say so in a trail entry. Scaled masses keep the
  `model_estimate` source. Mass and factor must be above 0. Adds the warning code
  `co2e_unavailable` to the enum and the table in `agents.md`: one per option the model
  declined or whose inputs failed a check, or one for the report when the call failed; "not
  found" in the evidence summary covers both. The stub raises none. The boundary of a tier 3
  result is fixed by code: "cradle to gate: materials and manufacturing". Update the existing
  tests that build `LcaResult`, add `LcaInput` to the checkpointer round trip, and update the
  tier 3, `inputs` and rules rows of `lca.md` and the LCA result row of `agents.md`; in
  `lca.md` also note that tier 2's manufacturing line must come from an open dataset, or tier
  2's boundary is materials only (ADR 0006).
  Prep: no grill; grilled and panelled.
  Read: `docs/adr/0006-tier-3-returns-factors-code-multiplies.md`, `architecture/lca.md`, `architecture/agents.md` (Data model, Warning codes), `architecture/calculations.md`.
  Done when: unit tests on hand-built inputs give the right range, including the spread at,
  below and above 2x, a total under 2x built from inputs each over 2x, scaling inside and
  outside the 0.5 to 2 window, and a sourced mass left untouched.
- [x] **1.9.6 CO2e avoided as an interval.** `calc/comparison.py` subtracts the ends
  separately, which gives an inverted or falsely narrow range once ranges are wide (baseline
  10 to 20 against 1 to 15 gives 9 to 5). Subtract intervals: low is baseline low minus
  option high, high is baseline high minus option low. The figure exists only when its low
  end is above 0; otherwise it is missing with the reason that the ranges overlap. It carries
  the weaker of the two confidence labels ("AI synthetic estimate" is weaker than "Benchmark
  estimate", which is weaker than "Published figure"). Update `calculations.md`, and rewrite
  its open question on used items to name the cut-off approach as the candidate (no added
  manufacturing, shipping not estimated, never a "saves" claim), to be checked against the
  standards by `docs-researcher` and reviewed by `lca-reviewer` before it is built.
  Prep: no grill; settled in the 1.9.1 grill.
  Read: `architecture/calculations.md`, `eu_market.md` (environmental claims).
  Done when: offline tests show a figure for separated ranges, none with the overlap reason
  for overlapping ones, and the weaker label on mixed tiers.
- [x] **1.9.7 LCA agent on the large model.** Replaces the stub. One call to the large tier
  for all options, reasoning in full. The model returns one factor table per report (material
  and form, factor low and high) and per option, in input order with its name echoed, the
  inputs (name, form, mass, pointing at the table), a manufacturing and assembly range, or a
  decline with a reason. Code matches entries by position; a missing or duplicate entry is a
  decline. The linked product's page materials and weight go in as numbered fixed inputs that
  keep their URL source. The prompt: a material's form is primary unless the page states
  recycled content; a component whose emissions per kg are far above its bulk material's
  (electronics, motors, batteries and similar) is its own input; decline only when the
  product cannot be identified or its materials have no basis; the piece count of a set is
  given and the figure covers the whole item as sold. Code copies each factor into the inputs,
  checks them and calls the 1.9.1 function. One trail entry per option names the tier and
  model and says what was estimated or declined. Sets `LCA_MAX_TOKENS` and
  `LCA_TIMEOUT_SECONDS` from one timed probe, and a time cap on the whole LCA node; tries
  `low_effort` once on the large model and records whether it is honoured. Note in
  `conversation.md` that a rerun should not re-estimate an unchanged option (for the
  conversation tasks). Update `models.md` (LCA tier 3 row).
  Prep: no grill; grilled and panelled.
  Read: `docs/adr/0006-tier-3-returns-factors-code-multiplies.md`, `architecture/lca.md`, `architecture/agents.md` (Agent contract), `architecture/models.md` (Which component uses which tier, Rules), `product.md` (tone).
  Done when: agent tests with a recorded response cover a full estimate, one option declined,
  a timeout, invalid output twice and a linked product with page materials and weight, and
  each gives the right results, warnings and trail entries.
- [x] **1.9.8 CO2e on the report, and the live run.** The CLI shows the confidence label, not
  the tier number, derived from the tier when shown: "{low} to {high} kg CO2e to make, over
  {horizon} years ({label})", with "for the set of {n}" for a set and the range per unit when
  the option has no lifespan. A "Built from:" line lists names, forms and masses, marking an
  estimated material, form or mass "(estimated)"; factors are never shown. The avoided line
  follows 1.9.6: "About {low} to {high} kg CO2e less to make over {horizon} years ({label})".
  Fixed wording, including both `co2e_unavailable` messages, goes in `wording.md`;
  `terminal_app.md` loses its "not settled yet" note. Then one live run by hand on the three
  tuned categories and a cordless tool, recorded as a fixture, with one result compared
  against a published figure for a similar product (a maker's declaration or an ADEME product
  factor) and the `lca-reviewer` verdict, in `docs/findings/task_1.9.8.md` with latency and
  tokens.
  Prep: no grill; grilled and panelled.
  Read: `terminal_app.md`, `wording.md`, `product.md`, `eu_market.md` (environmental claims), `architecture/lca.md`.
  Done when: offline, the CLI shows a CO2e range with the "AI synthetic estimate" label for
  each option, and an option the model cannot estimate shows no result and the new warning;
  the findings file exists with the reviewer's verdict.

- [x] **1.9.9 LangSmith tracing.** Before 1.10, so its runs can be judged as traces rather
  than terminal output. The `langsmith` package is already installed with LangGraph; no new
  dependency. Tracing is off by default and on only when `.env` sets it, with the key, the
  project and the EU endpoint read through `config.py` and passed to LangSmith, never read by it
  from the environment on its own. The graph's nodes are traced as runs, and every model call
  as a child run with its tier, model ID, request (messages, `max_tokens`, timeout, the
  reasoning and temperature arguments `_effort` and `_temperature` build), reply and tokens:
  `nebius_chat` calls the `openai` client directly, so wrap it, since tracing the graph alone
  does not reach it. Tests and `-m live` runs never trace unless the setting is on, and the
  deployed app (3.5) does not trace without asking. A trace holds what the user typed, so
  `eu_market.md` ("Personal data") gets the rule: tracing is a developer tool for test runs,
  its project is private, and the request text of real users is not traced. Then one live
  terminal-app run of the frying pan with tracing on, recorded in `docs/findings/task_1.9.9.md`:
  whether the reasoning settings arrive as `_effort` builds them (the left-over item on
  `nebius_chat`), and the latency tracing adds.
  Prep: no grill. Ask the `docs-researcher` how LangSmith takes its settings in code (client,
  `tracing_context`, `wrap_openai` or `@traceable`) and the EU endpoint for the installed
  version.
  Read: `building_the_project.md` (Environment variables, Dependencies), `eu_market.md` (Personal data), `architecture/models.md`, `architecture/data_sources.md` (Rules for every source).
  Done when: with tracing off, `uv run pytest` passes and a test shows no trace is sent; with
  it on, one live frying pan run appears in the LangSmith project as one trace with a run per
  graph node and a child run per model call showing its tier, model, request arguments and
  tokens; the findings file says whether the reasoning settings arrived as built.
- [x] **1.11 Option research batch.** From the 1.10 grill (`docs/findings/task_1.10.md`,
  "Decided", items 9 and 12). The price read classifies what each amount's page sells (the item
  itself, a set or bundle, a part or accessory, another kind of product, unclear), with a quote
  code finds; code keeps only the item itself, or a set when one is asked for; the linked
  product is exempt. Both follow-up reads (brief and shortlist) keep the read with more cited
  items, a tie going to the second, which fixes the drill brief losing its factors. A model call
  that times out is retried once (matrix row 10; `_ask` in `llm.py` already retries invalid
  output). A follow-up search query may hold a digit (a size, a model number) and still refuses
  prices and currencies (row 2; `follow_up_fault`, and the rule in `data_sources.md`).
  Changed during the task (`docs/findings/task_1.11.md`): the outlier rule (row 6, a price under
  a third of the other candidates' median) was dropped by the developer, as it removes real
  cheap candidates on the recorded prices; the timeout retry was found already in place in the
  `openai` client and is pinned by a test; the low temperature (row 11) moved to task 1.14.
  Prep: no grill; decided in the 1.10 grill.
  Read: `architecture/option_research.md` (Price, Selection), `architecture/data_sources.md` (Research rules), `architecture/models.md`, `docs/findings/task_1.10.md` (Decided).
  Done when: a replay of the recorded 1.10 price searches, offline from fixtures (a price search
  lasts one day in the cache), rejects the Oxo €183.72, GreenPan €799 and Brother XM2701 €21.39
  prices (or the findings say which a snippet could not show), and tests cover a follow-up read
  with fewer factors than the first, a model call that times out once and then answers, and a
  follow-up query with a model number kept and one with a price discarded.
- [x] **1.12 Measure option research from what is sold here.** The prototype of a new first step:
  for the three tuned categories, a listing search on comparison sites with a hand-written
  Dutch term, product-page reads with the page classification of 1.11, an open control search
  judged from its URLs, and the roundup match. The pass rule, the ceiling and what is recorded
  are fixed in `docs/findings/task_1.10.md` ("Decided", items 1 to 3) and are not changed
  during the task. Needs 1.11 merged.
  Prep: no grill; decided in the 1.10 grill.
  Read: `docs/findings/task_1.10.md` (Decided), `architecture/data_sources.md` (Firecrawl, Cache and fixtures, Calls per analysis), `eu_market.md`.
  Done when: `docs/findings/task_1.12.md` holds the counts by hand against the pass rule and the
  verdict, within 15 Tavily and 35 Firecrawl credits, with fixtures recorded for every search
  and page the prototype used.
- [x] **1.13 Option research from comparison sites, on fixtures.** Option research starts from
  the listing pages of beslist.nl and kieskeurig.nl and prices every candidate from its own
  product page, as decided in `docs/findings/task_1.12.md` ("Decided", items 1 to 14): the local
  category term from category research, the durability judgement deciding the slots, shipping,
  `incomplete` and out of stock marked, and the old discovery, shortlist, price and Confirm steps
  removed. Records the evidence and findings searches for the new product names (about 6 to 10
  Tavily credits). ADR 0007 supersedes the step order of ADR 0004; `option_research.md` and
  `data_sources.md` are rewritten for what landed. One session; merged only when green, else
  task 1.15 takes the fallback (item 15).
  Prep: done (grill and panel, 23 October 2026).
  Read: `docs/findings/task_1.12.md` ("Decided: the rework of task 1.13"), `architecture/option_research.md`, `architecture/data_sources.md`, `eu_market.md`, `docs/adr/0004-firecrawl-confirms-shop-prices.md`, `architecture/calculations.md` (Definitions, Rules), `architecture/interview.md` (How the brief is researched), `architecture/models.md` (Which component uses which tier), `architecture/agents.md` (Data model).
  Done when: offline, with the fixture twin, each of the three tuned categories gives at least two
  product options in the terminal app, every price from a product page's offer, and the checks
  on the pull request pass.

- [x] **1.15 Price wording and the live run, or the fallback.** After a merged 1.13: the words in
  `wording.md` and on the report for the price source and date, shipping, `incomplete`, out of
  stock and the durability judgement's trail line (`docs/findings/task_1.12.md`, "Decided",
  items 4, 8, 10, 11 and 14); the live run of the three tuned categories; the fixtures recorded
  again, the braadpan, hapjespan and wok pages with their text (item 9). If 1.13 was not merged:
  matrix rows 3, 4, 5, 7 and 16 of `docs/findings/task_1.10.md`, from `main`.
  Prep: no grill; decided in the 1.13 grill.
  Read: `docs/findings/task_1.12.md` ("Decided: the rework of task 1.13"), `architecture/option_research.md`, `eu_market.md`, `wording.md`.
  Done when: the three tuned categories give at least two product options each in the terminal
  app, live, every price from a product page's offer or (on the fallback) an accepted search
  price.

- [x] **1.14 Temperature of the extracting reads, measured.** Split off from task 1.11 (matrix row
  11 of `docs/findings/task_1.10.md`). The Nemotron 3 model cards recommend temperature 1.0 for
  reasoning, so a low temperature for the reads that extract (brief, the product-page read,
  evidence; the shortlist and the price search's read go in task 1.13) goes against them (`docs/findings/task_1.11.md`). Measure before setting one: the
  same recorded searches read several times at the default and at a low temperature, counting
  how often the kept factors, candidates and accepted prices change, and watching for
  repetition or answers cut off at `max_tokens`. Set one value in `config.py` only if it wins.
  Prep: no grill; decide the temperatures and the number of reads before spending credits.
  Read: `architecture/models.md`, `docs/findings/task_1.11.md`, `architecture/data_sources.md` (Cache and fixtures).
  Done when: `docs/findings/task_1.14.md` holds the counts at both temperatures and the choice,
  and either the extracting reads pass the chosen setting from `config.py` (a test shows it on
  each read's request) or the findings say why they keep the default.
- [x] **1.10 End-to-end test and tone pass.** Shortened for the deadline. Run five queries: one
  in each tuned category (cookware, small appliances, tools) and two outside them (one unusual
  durable product, one that is not a product). Fix wrong extractions; remove any preachy wording
  or generic environmental claim from prompts, questions and output. The model-tier study and
  the check of the typical yearly cost line are optional layers.
  Prep: no grill; a test run, not a design.
  Read: `product.md`, `building_the_project.md` (Tests), `eu_market.md`.
  Done when: five saved transcripts in `tests/transcripts/` look correct and neutral in tone, the
  two outside queries show the right caveat or decline, and no transcript holds a trail entry
  starting "Stub:" or a source on `stub.invalid`, except the second-hand agent's "Stub: used
  listings are not searched yet", which stays until task 2.3 replaces the stub.

## Week 2 — the hands (tools and infrastructure)

- [x] **2.5.1 Saved sessions and progress.** The part of task 2.5 below HTTP, split from it in its
  grilling and panel (24 October 2026): the API over it is task 2.5.3, recalculate and the
  deployment guards are task 2.5.2. In `graph.py` and the CLI; no FastAPI yet. `graph.py` gains
  what the API needs beyond the four names from task 1.5.1, each named in its docstring: the
  session id passed in by the caller of `start_session`, a progress callback for start and
  resume, the check of a resume split from the run so a caller can refuse before it starts,
  reading a saved session, and the checkpointer's serde as a public function. `terminal_app.md`
  gains the progress lines.
  Settled (Cowork review, the grilling and its panel, 24 October 2026); raise one only if the
  code contradicts it:
  - Checkpointer: `AsyncSqliteSaver` (`langgraph-checkpoint-sqlite`, `aiosqlite`) on a file whose
    path is in `config.py`, with the allow-list of `memory_checkpointer` through the public serde
    function; `memory_checkpointer` stays for the CLI and the tests. A thread that no longer
    loads, because a model in `state.py` changed after it was saved, reads as not found; task
    2.5.2's sweep removes it.
  - Progress: the callback gets the agent (the `Agent` enum: `parse_request`, `read_link` and
    `assemble_report` are the supervisor; `interview` is not reported) and a status: `started`
    the first time one of the agent's nodes starts, `finished` after its last (the LCA and
    second-hand agents run at once). The words for `started` are in `wording.py`; the CLI prints
    them, one line per agent.
  - Reading a saved session gives one of: `paused`, with what `SessionStart` holds; `finished`,
    with the report; `interrupted`, with the code `run_stopped`, when it neither waits at
    `interview` nor holds a report (a restart mid-run or an unexpected exception); or not found.
    Whether a run is going on now only the API knows (task 2.5.3).
  Prep: grilled and panelled (24 October 2026); built to the spec above.
  Read: `architecture/agents.md` (The pause), `terminal_app.md`, `wording.md`.
  Done when: the CLI prints a line as each agent starts; a session saved in a SQLite file on
  `tmp_path` reads back as paused and then as finished; a run stopped partway reads back as
  interrupted; and the CLI tests still pass on the memory checkpointer.
- [x] **2.5.3 Session runs and streams.** The rest of task 2.5's session work, split in its panel
  (24 October 2026), then split again by size (24 October 2026): the contract and the hardening
  are task 2.5.4. The FastAPI app in `src/shopper/api/` over task 2.5.1. `POST /sessions`
  (streams the request as understood, warnings so far and the questions),
  `POST /sessions/{id}/answers` (resumes, streams progress per agent, then the report),
  `GET /sessions/{id}` and `GET /health`. `service_architecture.md` (API surface) gains
  `GET /sessions/{id}`. Adds `fastapi` and `uvicorn`.
  Settled (Cowork review, the grilling and its panel, 24 October 2026); raise one only if the
  code contradicts it:
  - App: `create_app(chat, sources, checkpointer)` builds it, and its `lifespan` calls
    `build_graph` once; every route reuses the graph. Async throughout. Tests pass the fake model,
    the fixture sources and a saver on `tmp_path`, and run the lifespan themselves, because
    `httpx.ASGITransport` does not.
  - Runs: every run, the start's and the answers', is an `asyncio` task kept in a list of running
    sessions in the process, never the response's own generator, so it finishes when its client
    disconnects; the stream reads the task's events from a queue. The list is the lock per
    session. An answers request checks it first (409 `session_running`), takes the slot, then
    runs task 2.5.1's check of the saved state and the answers, then starts the task, which frees
    the slot in `finally`.
  - `GET /sessions/{id}` returns one named `SessionView`: `running` when the session is in the
    running list, otherwise what task 2.5.1 reads from the saved session. An `interrupted`
    session is final: the frontend offers to start again with the text kept, as "Edit" does.
  - Streams: Server-Sent Events, written by hand (a `StreamingResponse` that waits on the queue
    for 15 s and sends a keep-alive comment when nothing came; no `sse-starlette`). The route
    makes the session id, a random UUID used as the LangGraph thread id (a client never chooses
    it), and sends it first. `POST /sessions` sends `session_started`, then `understood` with the
    request once it is known to run, `progress` for the supervisor and the brief, then `session`
    with the `SessionStart` (holding the report for a request that does not run). The answers
    stream sends `progress`, then `report`. The events are one `StreamEvent` union of named
    pydantic models and carry only their listed fields; task 2.5.4 declares it in the OpenAPI
    schema. Check first whether `httpx.ASGITransport` buffers a whole response (the
    `docs-researcher` agent); if it does, a test cannot disconnect mid-stream through it, and
    the keep-alive interval must be one a test can shorten.
  - A progress event is task 2.5.1's callback as `agent` and `status`, plus `message`, its words
    from `wording.py`, so the terminal app and the web app say the same.
  - Errors: every response that is not a success has the body `{code, message}`. Before a stream
    starts: 404 `session_not_found` (expired included), 409 `session_running`, 409
    `session_not_paused`, 422 `invalid_answers` and 422 `input_too_long` (the supervisor's
    `MAX_INPUT_CHARACTERS`). Once it has started, an `error` event: `model_call_failed`, or
    `run_stopped` for anything unexpected. Each of these codes' message is a `wording.md` row and
    a `wording.py` template, added in this task.
  - One worker process (`uvicorn --workers 1`): the SQLite file, the cache, the credit ledger and
    the running list are per process. Two runs at once can take a few credits past the daily
    ceiling, because the ledger is checked before a search and added to after; accepted.
  Prep: grilled and panelled (24 October 2026); split by size (24 October 2026); built to the
  spec above.
  Read: `service_architecture.md` (API surface), `architecture/agents.md` (The pause), `wording.md`.
  Done when: an API test runs a session end to end with answers and with skip all, and the
  result matches the CLI; a client that disconnects during the start or the run finds the
  session through `GET /sessions/{id}`; two answers requests sent at once give one run and one
  409 `session_running`; and the keep-alive is sent.
- [x] **2.5.4 Session API contract and hardening.** Split from task 2.5.3 by size (24 October
  2026). Over task 2.5.3's app: what the frontend's generated types and its messages need, and
  what keeps personal data out of the logs. Before 3.1, which builds on both.
  Settled (Cowork review, the grilling and its panel of task 2.5, 24 October 2026); raise one
  only if the code contradicts it:
  - Errors: FastAPI's own validation answers with the body `{code, message}` too
    (`invalid_request`), and each route declares its error models for the OpenAPI schema. Every
    code's message is a `wording.md` row and a `wording.py` template, also for the codes task
    2.5.2 brings (`too_many_sessions`, saying when to try again, `no_report_yet`, `no_options`,
    `unknown_option`, `invalid_assumptions`), so task 3.1 shows the final text.
  - The `StreamEvent` union of task 2.5.3 is declared once as the stream routes' documented
    response, so the OpenAPI schema holds it.
  - The OpenAPI schema is the frontend's contract: named pydantic models, so task 3.1 can
    generate TypeScript types from it (`openapi-typescript`).
  - Logs hold no personal data: uvicorn runs with `--no-access-log`, and an error is logged as
    its class, code, session id and agent, never its message or traceback, which can carry the
    input.
  - CORS allows only the frontend's origins, from `config.py`.
  Prep: settled with task 2.5.3 (grilled and panelled, 24 October 2026); built to the spec above.
  Read: `service_architecture.md` (API surface), `wording.md`.
  Done when: a marker string in the input appears in no log record; a request FastAPI rejects
  gets `invalid_request` in the `{code, message}` body; the OpenAPI schema names the
  `StreamEvent` union, `SessionView` and each route's error models; and every error code,
  task 2.5.2's included, has its `wording.md` row.
- [x] **2.5.5 Reading the interview reply.** Added 26 October 2026, so the questions can be
  answered in the user's own words in the page's chat thread (task 3.1.2); split by size after
  its panel, the API being task 2.5.6. One round: the questions are asked once and a reply is
  read once; follow-up questions stay with the conversation tasks. This task is everything below
  the API. Settled in the grilling and its panel (26 October 2026); raise one only if the code
  contradicts it:
  - **Where it is read.** Before `Command(resume=…)`, never as a graph node: a node that raised
    would save the answers as its resume value. The reader is an agent of `AgentBundle`, stubbed
    with the other stubs so `STUB_AGENTS` spends no call on it, reached through one entry point in
    `graph.py` that loads the saved factors, questions and stated answers and resumes with what
    was read. A paused session with no questions still has its reply read, for factors of the
    user's own. A blank reply is none. The terminal app is unchanged.
  - **The reader.** `read_stated`'s machinery with a prompt of its own for a reply. The text it
    reads and its name (request or reply) become parameters of `_kept`, `_located`,
    `own_phrase_fault` and the trail texts; for a reply the link check runs only when the link
    stands in the reply, and a phrase not found gets a fixed trail summary that does not repeat
    it. It is shown every factor, each marked, and a phrase about one never goes to "new":
    asked, a `stated` answer in its question's place; settled by the request, the trail ("the
    request already answers it"); phrased but not asked, a `stated` answer as from the request;
    not phrased, a `stated` free value; a recurring cost, the trail. A question can be answered
    "not sure" (uncertainty or indifference is never a value). A care factor takes only one of its
    two choices; a free value goes to the trail, for the request reader too. A phrase about a
    person, not the product or its use, is never a requirement.
  - **The request does not change.** The reading may mark a phrase `changes: budget | category`;
    it goes to the trail, and the result says the reply asked to change the request (task 2.5.6
    shows the line). For a reply, code also refuses a factor of the user's own whose phrase holds
    a URL, is only a number or an amount, or holds the category or the local category term.
    Otherwise a reply adds factors of the user's own under the request's rules: `user-N`
    continues the request's numbering, the cap of 3 is shared, and one past it goes to the trail
    only (`interview.md` says so).
  - **Which answer counts**, strongest first: the request's `stated`, a `chosen` chip, the reply
    (`stated` or `not_sure`), a `not_sure` chip, `skipped`; the others go to the trail. An answer
    from the reply has `stated_in: reply` (`request` by default); a validator allows it only on
    `stated` and on a reply's `not_sure`, which keeps its phrase, and `_check` refuses it from a
    caller. The resume value is a model in `state.py`, placed by `complete_answers(…,
    from_reply=())`: answers request-stated, the reply's own-factor answers, the reply's answers to
    factors not asked, then one per question; factors researched, request's own, reply's own,
    usage, written in full by the interview node. The combined set is checked before resuming.
    The full reply is not saved; kept phrases are, as from the request.
  - **When it does not go on.** A reading that fails twice raises `ReplyUnreadError`, and no chip
    with nothing kept (everything lost to the request included) is a result of its own; either
    way the graph does not resume, the session stays paused and nothing more is spent. The trail
    entry for a reply that changed no answer is split: nothing placed, or placed but lost to a
    chip or the request.
  Prep: grilled and panelled (26 October 2026); built to the spec above.
  Read: `architecture/interview.md` (Stated answers, How answers are used), `architecture/agents.md` (Agent contract, Adding an agent).
  Done when: through the entry point in `graph.py`, with a recorded reading that maps onto choice
  ids, a frying-pan session answered only by a reply has the same options, figures, factor and
  choice ids and check-before-you-buy list as one answered with those chips; a reply that names
  nothing leaves the session paused without chips and runs to a report with its unplaced phrase
  in the trail with one; a failed reading leaves it paused and a second resume works; tests cover
  the order of which answer counts, the shared cap and numbering, a factor not asked, "no idea
  which hob", "I meant a wok", "make it €40", a care reply as a free value and a save and reload
  of a paused session; and `interview.md` says what was built.
- [x] **2.5.6 The interview reply in the API.** The rest of task 2.5.5, split by size: what the
  page sees of a reply, so task 3.1.1 builds on the final contract. Settled in 2.5.5's grilling
  and panel; raise one only if the code contradicts it:
  - **Request.** `POST /sessions/{id}/answers` takes, beside the chips, an optional `reply`. Over
    the supervisor's `MAX_INPUT_CHARACTERS` it is refused in `runs.answer` before the slot is
    taken (not a pydantic `max_length`, which would answer `invalid_request`) with a new 422
    `reply_too_long`. The answers run reads the reply through task 2.5.5's entry point before it
    resumes; `Sessions` gains the chat client and the bundle. Every new code goes into
    `RefusalCode` or `RunErrorCode`, `_STATUS`, the route's `_errors(...)` and `wording.ERRORS`.
  - **When it does not go on.** `ReplyUnreadError` is sent as the `error` code `reply_unread`
    and logged as agent `brief`; no chip with nothing kept as `reply_unanswered`. Both leave the
    session paused: `service_architecture.md` ("Errors") gains this group beside the codes that
    leave it `interrupted`.
  - **Stream.** `ProgressEvent` gains `step` (`research` or `reply`): the reading's lines are the
    brief's "Reading your reply..." and "Finished reading your reply.", only with a reply. Then
    `reply_read`, before `tco`: the reply's kept `stated_answers`, the `factors` it added, and
    `asks_to_change_request`, as data (task 3.1.2 settles finished lines).
  - **Lines** (`wording.md`): "From your reply: {factor}: {value} ("{phrase}")", the usage
    and own-factor forms as for the request, and "From your reply: {factor}: not sure
    ("{phrase}")"; on the report request lines, then reply lines, then the typical yearly cost
    line. In the thread only: "Nothing in your reply answered a question, so it changed no
    answer." or "Your reply changed no answer: your choices or your request already answer it.";
    "A reply can't change what you're looking for or the budget, so the results are still for
    {category}, budget {budget}. To change either, press Edit."; `reply_too_long` "That is more
    text than the app can read, so nothing was sent. Answer in a sentence or two.";
    `reply_unread` "The app couldn't read your reply just now, so nothing was run. Send it again,
    or answer with the choices."; `reply_unanswered` "Nothing in your reply answered the open
    questions, so nothing was run. Answer in your own words or with the choices, or press Skip
    all."
  - **Personal data.** The marker test puts a marker in the reply, in a kept and in a refused
    phrase, and finds it in no log record.
  Prep: grilled and panelled with task 2.5.5; built to the spec above.
  Read: `service_architecture.md` (API surface), `wording.md`.
  Done when: an API test answered only by a reply streams the reading's progress and
  `reply_read` before the report; `reply_unread` and `reply_unanswered` leave the session paused,
  free the slot, show as `paused` in `GET /sessions/{id}`, and a second send works;
  `reply_too_long` is refused before the slot; each new code and line has its `wording.md` row;
  and `service_architecture.md` and `wording.md` say what was built.
- [x] **2.5.2 Recalculate and deployment guards.** The rest of task 2.5, split in its grilling
  (24 October 2026). Before 3.5 because the deployment needs the guards; task 3.3 uses the
  recalculate endpoint. The messages for its codes are written in task 2.5.4. Settled in the
  grilling and its panel; raise one only if the code contradicts it:
  - `POST /sessions/{id}/recalculate` takes the complete assumptions (horizon, uses per year,
    lifespan overrides), not a change to them, in a request model of its own with bounds whose
    values are in `config.py`: horizon 1 to 30 years, uses per year 1 to 3,650, a lifespan
    override 0.1 to 100 years; outside them 422 `invalid_assumptions`. The shared `Assumptions`
    does not change. It reads the saved report (404 `session_not_found`) and saves nothing: the
    saved report keeps its own assumptions, and the frontend holds the current values. It
    returns a named `Recalculation`: the assumptions used, and the comparison and evidence
    summary from `calc/recalculation.py`, with the request's budget and the default baseline,
    and beside them the lines of what it recomputes, in task 3.1.4's `ReportLines` shape and
    built by the same functions as the report's (ADR 0008).
    Refused: an override for an option id the report does not have (422 `unknown_option`), a
    session with no report yet (409 `no_report_yet`, from a new `SessionHasNoReportError` in
    `graph/sessions.py`) and a report with no options (409 `no_options`). `conversation.md` gains
    a note that a what-if lives only in the browser until the chat tasks decide otherwise.
  - Checkpointer: one setting, chosen in `make_checkpointer(settings)`. `DATABASE_URL` set gives
    `AsyncPostgresSaver` (`langgraph-checkpoint-postgres`); unset keeps task 2.5.1's
    `AsyncSqliteSaver`. Both with the public serde of task 2.5.1. A unit test checks which class
    is chosen without connecting; offline tests never use Postgres, which cannot run on Windows'
    default event loop anyway. Which one the deployment uses is task 3.5.1.
  - Threads are kept 7 days after their latest checkpoint, then deleted; that includes a thread
    whose parsing call failed, which holds only the input. A sweep runs at startup and then
    hourly from the `lifespan`, through the saver's own `alist` and `adelete_thread` (check both
    exist in the pinned versions), so both savers share it. It takes each thread's newest
    checkpoint, skips a session in the running list, and catches and logs (its code only) an
    error in one pass so the next pass still runs. `SESSION_RETENTION_DAYS` is in `config.py`;
    `eu_market.md` (Personal data) says how long sessions are kept.
  - The deployment runs without endpoint auth (a browser cannot hold a token), so `POST
    /sessions` gets a limit per client IP, beside the daily credit limit:
    `SESSIONS_PER_IP_PER_HOUR` in `config.py`, 30 by default. A session counts once it is
    created, after the length check; a declined request counts, since it spends a model call.
    Counted in memory only, expired entries cleared on each check, the IP never saved, logged or
    put in a thread; above it 429 `too_many_sessions`. `TRUSTED_PROXY_HOPS` in `config.py`: 0,
    the default, uses the connection's own address; N uses the Nth `X-Forwarded-For` entry from
    the right, never the leftmost, which the client writes. Startup logs whether a proxy is
    trusted, with no IP. `eu_market.md` (Personal data) says an IP is held in memory for an hour
    for this limit and nothing else, and that the platform's own proxy logs are outside the app.
  Prep: grilled and panelled with tasks 2.5.1 and 2.5.3; built to the spec above.
  Read: `service_architecture.md` (API surface), `architecture/calculations.md` (Changing the assumptions), `architecture/conversation.md` (Report versions), `eu_market.md` (Personal data).
  Done when: recalculate returns new numbers without calling any agent, and a value out of
  bounds gets 422; the sweep deletes a thread older than 7 days, keeps a newer one and skips a
  running one; the 31st session in an hour from one IP gets 429, and a forged leftmost
  `X-Forwarded-For` entry does not avoid it; and the checkpointer class follows `DATABASE_URL`.

## Week 3 — the face (UI, deployment, pitch)

- [x] **3.1.1 Frontend skeleton and the API client.** Split from task 3.1 by size (26 October
  2026). The Next.js app in `web/` (App Router, TypeScript strict, ESLint and Prettier) and what
  the page needs from the backend, under a bare page: an input box that starts a session, its live
  agent progress, and what the stream ends with (the questions, or the report of a request that
  does not run) shown as plain data, with a button that answers with none ("skip all").
  - Backend: a setting in `config.py` that runs the API on the stub agents (`STUB_AGENTS`), so a
    run from the browser spends one supervisor model call and no search or page credits; with
    `SHOPPER_SOURCES=fixtures` the recorded blocked page (`https://example.org/shop/blocked`) gives
    an unreadable link. And a command that writes the OpenAPI schema to a file, with no server and
    no keys.
  - The types are generated from that file with `openapi-typescript` and committed; CI checks
    that they are current.
  - Every call goes through `web/lib/api`: the start and the answers are streams over `POST`
    (`EventSource` only does `GET`, so the stream is read with `fetch` and parsed by a helper in
    `web/lib`), and `GET /sessions/{id}`. A stream that drops is picked up from `GET
    /sessions/{id}` with the id from `session_started`; `session_running` shows as still working,
    not as an error; an `interrupted` session offers to start again with the text kept; an error
    body shows its `message`. An `error` event whose code leaves the session paused
    (`reply_unread`, `reply_unanswered`, task 2.5.6), or a `paused` view after an answers request,
    means the answers were not applied: the page keeps the questions and what the user gave and
    shows the message, never the offer to start again.
  - Vitest for the helpers in `web/lib` (`code_conventions.md`, "Tests"), and a CI job for `web/`:
    install, lint, typecheck, test, build. `building_the_project.md` gains the commands and the
    stub setting.
  - The visual check for every frontend task from here on, documented in
    `building_the_project.md` ("Verifying a task") and run by `/task`: open the pages the task
    touched on the dev server in the browser at 390 px and 1280 px, check the console for errors
    and failed requests, and run `impeccable detect` on each page's URL at both widths
    (`--viewport 390x844` and `--viewport 1280x800`). No screenshot script and no Playwright.
  Prep: no grill; built to the spec above.
  Read: `service_architecture.md` (API surface), `code_conventions.md` (Next.js), `building_the_project.md`.
  Done when: with the stub agents and the fixture sources, a query typed in the browser streams
  its progress and shows its questions as data, "skip all" shows the report as data, and a
  declined request shows its report as data; a stream cut mid-run is picked up from `GET
  /sessions/{id}`; the `web/` CI job and the check on the generated types pass; and the bare
  page passes the visual check at both widths, with no console errors and no failing
  `impeccable detect` finding.
- [x] **3.1.5 Interview lines in the API.** Split from task 3.1.2 by size after its grilling and
  panel (26 October 2026): what the API sends so the page's thread shows finished lines
  (`docs/adr/0008-api-sends-finished-lines.md`), before task 3.1.2 builds the page on it. New
  words go into `wording.md` with their templates, never ahead of them: the tests require every
  row to have one. Settled in the grilling and its panel; raise one only if the code contradicts
  it:
  - **Rounding first**, as the first commit, before any API test records today's output. Every
    single value shown rounds half up, then drops ".00" or ".0" (€0.125 is "€0.13", €12.995 is
    "€13", 2.96 years is "3"); a positive amount under €0.005 shows "under €0.01", a new
    `wording.md` row. Every range shown rounds outward: CO2e as today, and now the typical
    lifespan. Masses stay half up. The trail's weight scale (`_shown` in `agents/lca/trail.py`)
    follows the same rule and never prints as the bound of its window. `_years` becomes a public
    formatter beside `euros()` in `calc/`. Tests: 0.004, 0.005, 0.125, 2.675, 9.996 and 12.995;
    years 0.04, 0.96, 2.25 and 2.96. `architecture/calculations.md` gains the rule.
  - **`Line`** is `{parts}`, each part tagged `kind`: `text {text}`, `link {text, url}` and
    `control {key}`; the `confidence` part comes with task 3.1.4. Pydantic models in `wording.py`,
    which still imports nothing from the package; no markup in any text. Control keys are a
    closed list, today `edit`. The "Edit" row moves from "Labels" to "On the page", with `EDIT`
    in `web/lib/wording.ts` and its Vitest row, and `wording.EDIT` goes.
  - **`wording.py`'s line functions return Lines.** A template fills into a Line, each
    placeholder's value a string or a part, so the choice of template stays in one place; the
    templates and their row tests do not change, and their function tests compare Lines. The
    functions that build warnings and error messages keep returning strings. The terminal prints
    a Line by joining its parts' text and dropping control parts, so a control part only ends a
    line; a sentence that names a control keeps its name as words.
  - **`src/shopper/lines.py`** reads a session, a reply or a report and calls `wording.py`:
    `stated_answer_lines` and `typical_cost_lines_of` move in from `report_text.py`, with the
    understood line (ending in the `edit` control), the decline and rephrase messages, each
    question's source line and the reply's lines. The site in a source line and in a typical
    yearly cost line is a link to its source. The CLI and `api/` both use it, and the CLI's
    words do not change.
  - **On the API**, lines travel beside the data, built when the API answers and never saved:
    `understood.line`; `session.lines`, a `SessionLines` with `understood`, `declined`,
    `stated`, `typical_costs` and `sources` by question id; `reply_read.lines`; `report.lines`,
    the decline for now (task 3.1.4 adds the rest); and the paused and finished views of `GET
    /sessions/{id}`, which carry the same lines as their events. `resume_with_reply` passes the
    paused session's request and factors to `replied`, so the reply's lines see the saved
    factors and those the reply adds.
  - **The reply's lines:** the "From your reply" lines, then the thread lines of `wording.md`
    ("The reply, in the thread"); the "From your reply" rows say "in the thread and on the
    report". A reply that ends unanswered gets no thread line, except, when it asked to change
    the request, a new row: "A reply can't change what you're looking for or the budget. To
    change either, press Edit." `reply_unanswered` gains a second wording, which the API chooses
    when the paused session has no questions: "Nothing in your reply added a requirement, so
    nothing was run. Add one in your own words, or press Show me options."
  - **The input cap:** `MAX_INPUT_CHARACTERS` is published as the `maxLength` of
    `StartRequest.input` and `AnswersRequest.reply` in the OpenAPI schema, documented and not
    enforced, so `input_too_long` and `reply_too_long` keep their codes.
  - **Stubs:** `stub_reply` answers a question whose choice's text stands in the reply, and
    nothing else, so the existing unanswered tests hold; `stub_brief` gains a recurring-cost
    factor with a typical yearly cost and a source URL. Task 3.1.2 checks the page on them.
  - **Tests**, at the test points of `code_conventions.md`: each line function by direct call;
    each event's and view's lines as plain text against expected strings written in the test,
    for the understood line with and without a budget, a decline after a link in the `session`
    event and in `GET` finished, a source line with "(the manufacturer states)", a reply that
    adds a factor of the user's own, a reply that asks to change the request, and
    `reply_unanswered` with and without questions; and the formatters' edge cases.
  Prep: grilled and panelled with task 3.1.2 (26 October 2026); built to the spec above.
  Read: `adr/0008-api-sends-finished-lines.md`, `wording.md`, `service_architecture.md` (API surface), `architecture/calculations.md`, `terminal_app.md`.
  Done when: the lines test passes for every case above; the CLI prints the same words as before
  but for the new rounding; the stubs answer a reply that names a choice; the regenerated types
  carry `Line`, `SessionLines` and the cap; and `service_architecture.md`, `wording.md` and
  `calculations.md` say what was built.
- [x] **3.1.2 Interview as a chat thread.** The page part of task 3.1, on task 3.1.1's app and
  client and the lines of task 3.1.5: one chat thread in one section of the page, whose composer
  is the input box and whose turns are what the user and the app say (`GLOSSARY.md`, "Thread").
  Every line it shows comes from the API (ADR 0008); only the words of its own controls are in
  `web/lib/wording.ts`. One round: the chat about the report is task 3.4. Settled in the
  grilling and its panel (26 October 2026); raise one only if the code contradicts it:
  - **One thread per session.** "Edit", the `edit` control that ends the Looking-for line,
    always works, also while a stream is open: each run has a token and the page drops events
    from a run that is not current; Edit empties the thread and puts the input back in the
    composer, and the old run finishes on the server. A Vitest case: Edit during a run, then the
    old session's event.
  - **Before the first send**, after a `not_a_product` decline and after "Start again": an empty
    composer and three example buttons, "A frying pan, budget €50", "A kettle, budget €60" and "A
    cordless drill, budget €120" (the recorded queries). A tap fills and focuses the composer and
    does not send. After an `unclear` or `several_products` decline, or a code that offers to
    start again, the composer opens with the input in it. Sending starts a new session, so an
    empty thread.
  - **The app's turns**, in the terminal app's order (`cli.py`): the Looking-for line, then
    `SessionStart.warnings`, the "From your request" lines and the typical yearly cost lines,
    before the first question; the decline and rephrase messages; and the questions, each with
    its reason, its source line, its choices as chips and "Not sure".
  - **Answering.** Tap chips, type a reply in the composer (capped at the schema's `maxLength`),
    or both, and send once. Send is disabled until a chip is tapped or something is typed. "Skip
    all" is always there: it clears the marks and the composer, then sends nothing. With no
    questions, "Show me options" takes its place. After sending, the questions turn stays with
    its chips frozen and the picked ones marked; the user's turn is the reply as typed, "Skip
    all" or "Show me options", and chips alone add no user turn. The next turn shows
    `reply_read.lines` and the progress to the report, shown as plain data.
  - **When the answers were not applied** (`reply_unread`, `reply_unanswered`,
    `invalid_answers`, `internal_error`, `reply_too_long`, or a lost stream read back as
    paused): the user's turn stays, the message follows as the app's turn, the reply goes back
    into the composer, the chips unfreeze with their marks kept, and sending again works.
  - **Progress:** one line per agent step, the started line while the step runs, replaced by its
    finished line when it ends, announced through `aria-live`. The supervisor's "Reading your
    request..." goes once the Looking-for line or a decline arrives, and its closing "Finished."
    gets no line. A line still running when its stream ends keeps its started words, without the
    working mark.
  - **After the report** the composer is hidden and a "Start again" button empties the thread
    and opens an empty composer; "Edit" still works.
  - **The page's own words**, rows under `wording.md` "On the page", in `web/lib/wording.ts`,
    compared by the Vitest test: the composer's label "What do you need?", and at the questions
    "Your answer to the questions"; its placeholder "Paste a product link, or say what you need
    and your budget", at the questions "Answer in your own words, or tap the choices", and with
    no questions "Add anything else that matters, or show me options"; "Send", "Not sure", "Skip
    all", "Show me options" and "Start again"; the three examples; and, under the composer only
    while the deployed app traces, "What you type here is logged to improve the app." (how the
    page knows is task 3.5). A Vitest case checks that the `wording.md` rows saying "press Edit",
    "press Skip all" and "press Show me options" name the labels of `wording.ts`.
  - `architecture/interview.md` gains the case with no questions.
  Prep: grilled and panelled (26 October 2026); built to the spec above.
  Read: `GLOSSARY.md` (Thread), `adr/0008-api-sends-finished-lines.md`, `architecture/interview.md` (Questions, The reply), `code_conventions.md` (Next.js), `product.md`, `wording.md`.
  Done when: with the stub agents and the fixture sources, a query typed in the thread goes
  through the questions to the report as plain data, once answered with chips and once with a
  typed reply that names a choice; a reply that answers nothing keeps the questions and the reply
  and can be sent again; skip all works; "Edit" returns to the composer with the text kept, also
  while the first stream runs; an unreadable link shows its warning above the first question;
  and the page passes the visual check of task 3.1.1 at both widths.
- [x] **3.1.3 The visual world (Impeccable).** Gives the chat thread of task 3.1.2 its look,
  with the Impeccable skill, run in a local session (its scripts serve a decision page on
  localhost; a cloud session cannot use it). Its own branch and pull request like any task.
  - `PRODUCT.md` already exists at the repo root (26 October 2026): it summarises the product
    for design work and defers to `docs/product.md`, `wording.md` and `eu_market.md`, so the two
    cannot drift. `/impeccable init` keeps it rather than writing a new one. Then
    `/impeccable hooks on`.
  - A new world for the chat page, as Impeccable's new-work flow runs it, from
    `docs/design/chat_page_brief.md`: the job, success, the two modes (the first viewport is an
    Experience surface, the questions and progress below are Operate), the memorable moment (the
    box: labelled, sealed and scanned, opened), the anti-references and the references. Write
    that into Impeccable's surface brief before the roll, and run the direction round with
    `concept-seed --scope direction --mode experience`. A first attempt in Operate mode (27
    October 2026) gave form-like pages and was abandoned; `.impeccable/` was cleared, so start
    fresh. Code-led unless image generation is available (`impeccable context` says). Choose
    the direction yourself on its decision page; the category-standard door is there if every
    dealt direction misses.
  - The box is built in code as the brief says (three layers, hinged flaps, no WebGL, no SVG
    filters, `aria-hidden` drawing with the text in the thread, reduced motion respected), in
    `web/components/`, from the geometry reference `docs/design/references/box-open.png`.
  - Adds Tailwind CSS and shadcn/ui to `web/`, which task 3.1.1 built with plain CSS, and names
    Tailwind in `PRODUCT.md`'s "Stack". The world's tokens go in Tailwind's theme; shadcn/ui
    components, when used, are restyled in the world's vocabulary through those tokens, not left
    at their default look.
  - It ends with its documenter: `DESIGN.md` and `.impeccable/design.json`. Add a row for
    `DESIGN.md` to the "Where to find things" table in `CLAUDE.md` ("Any change under `web/`").
  Prep: no grill; Impeccable asks its own questions.
  Read: `design/chat_page_brief.md`, `product.md`, `code_conventions.md` (Next.js), `eu_market.md` (Environmental claims), `wording.md` (Progress).
  Done when: the chat page of task 3.1.2 is built in the chosen world and passes the visual check
  of task 3.1.1 at both widths (`building_the_project.md`, "Verifying a task"), with no console
  errors and no failing `impeccable detect` finding, Impeccable's finish review is recorded in
  the pull request, and `DESIGN.md` exists with its tokens.

- [x] **3.1.4 Report lines in the API.** Added in the panel of task 3.1.2 (26 October 2026), so
  the contract that the results dashboard (3.2), task 2.5.2's `Recalculation` and the chart of
  3.3 inherit is decided in a task with room to decide it, and 3.2 is layout only (ADR 0008).
  The report's lines in the API, built from what `report_text.py`'s sections show, every figure a
  label and a value. Settled in the grilling and its panel (29 October 2026); raise one only if
  the code contradicts it:
  - **`ReportLines`** (`src/shopper/report_lines.py`): `declined`; `evidence_summary` (none for
    a declined report); `caveats` (Lines); `warnings`, each a `WarningLine {code, option_id,
    line}`; `stated` ("From your request", then "From your reply"); `typical_costs`; `options`,
    one `OptionLines` each in report order; `check`; `trail`. A declined report has `declined`
    only, every other field empty; a report with no options has every section but the options,
    the savings and the price line of the check list. A caveat or warning is one text part.
  - **`FigureLine {label: Line, value: Line, missing: bool}`.** Every "Label: value" line of an
    option block is one, its template split at ": " with its words unchanged; the terminal
    prints `label: value`. `missing` is true for "not available ({reason})" (a missing lifespan
    and what it blocks keep `LIFESPAN_NOT_READ`), "could not be confirmed" and "recurring costs
    not found"; false for the CO2e of making one item, shown when there is no horizon figure.
  - **`OptionLines`**, in the terminal's order: `option_id`; `name` (a link part to the
    option's link when it has one); `price` (value "€30 (28 cm)"), then `shipping` and
    `price_seen` (Lines, only for a price from a web page), which the terminal joins to the
    price with ", "; `link` (the URL as a link part's text, so the terminal keeps "Link: <url>");
    `factor_values`, each a `FactorFigure {factor_id, figure}`; `lifespan`; `rests_on` (Warranty,
    Wears, Repairs, Care, "Typical for ...", Test, Owner report) and `rests_on_state` (the lines
    for no evidence or no findings); `recurring_cost`; `cost_per_year`, `cost_per_use`,
    `purchases`, `horizon_cost`, `co2e`; `built_from`; `co2e_less` (label "Against
    {baseline}"); `marks` (out of stock, sold incomplete); `over_budget`; `savings`, which the
    terminal prints after every block, in option order. A lifespan the user set reads "N years
    (set by you)", a text part.
  - **`check`** is `CheckLines {groups, confirm_price}`: each `CheckGroup {label, items}` ("Not
    yet known", "Could not be confirmed"; an empty one left out), each item one Line ("Name: why
    (Option A, Option B)"); `confirm_price` none when no price is to be confirmed. The list is
    report-wide: lines go on naming an option the page's budget switch hides.
  - **`trail`** is `TrailLine {agent, by, line}`: `by` is "agent [tier, model]", `line` the
    rest; the terminal prints `by line`. A trail source is a link part only for a URL source,
    its text the full reference.
  - **Confidence part** `confidence {text, basis}` (`published`, `benchmark`, `estimate`), only
    where the words exist: the CO2e labels in `co2e` and in "Against", "rough estimate" on a
    lifespan, and every "estimated" in `built_from`, in its label or its value. Its text has no
    brackets; they stay text parts, so the terminal's words hold (`ESTIMATED` becomes
    "estimated"). `CO2E_LABELS` becomes one map from tier to text and basis, so the two cannot
    drift; `co2e` takes `horizon_co2e_tier` (or the result's tier for one item) and "Against"
    takes `co2e_avoided_tier`. Tests cover mixed tiers. The comment above it stops saying the
    page may show a badge. A CO2e value of tier 1 or 2 carries its result's source (a link for
    a URL, the dataset as text); tier 3 none, its label names the model. Not in the evidence
    summary, on a sourced lifespan or on the savings line.
  - **Links:** one helper, `source_site(source)`, gives a link part only for a URL source with
    an http(s) scheme, else the site as text; every "(site)" in an option block uses it (price
    seen, factor values, a sourced lifespan, the evidence items, the typical lifespan, the
    recurring cost, findings). Who is speaking ("(the manufacturer states)") is text after the
    link, not inside it: `factor_value`'s bracket trick goes. The finding templates lose
    `{url}`: the only change to the CLI's words; each finding's URL stays in its trail line.
  - **Words:** the row labels ("Price", "Cost per year", "Warranty", "Built from", "Against
    {baseline}", ...) and the two headings move into `wording.py`. The headings are not sent:
    the page names its own sections in `wording.ts`, as `wording.md` says of page headings and
    tooltips. `filled()` takes a confidence part too.
  - **Code:** `report_lines.py` imports only `wording`, `calc/` and `state`; one public
    `..._lines_of` function per section and `report_lines_of`. `declined_line`,
    `stated_answer_lines` and `typical_cost_lines_of` move into it from `lines.py`, which
    imports them back, so no report code imports the graph. `_kg` becomes `kilograms()` in
    `calc/display.py`. `report_text.py` keeps every public section name and signature, each the
    plain text of its section, with "  " before `rests_on`, `rests_on_state` and `built_from`
    and "- " before a check item; its `report_lines()` is renamed `printed_report()`. Task
    2.5.2 builds its lines with the same section functions on a copy of the report with its
    recomputed values.
  - **API and page:** `report.lines` and the finished view carry `ReportLines`; regenerate
    `openapi.json` and the types, exporting `FigureLine`, `OptionLines`, `FactorFigure`,
    `CheckLines`, `CheckGroup`, `TrailLine`, `WarningLine` and `ConfidencePart` from
    `web/lib/api/types.ts`. `LineView` gains a `confidence` case (its text in a plain span: no
    colour, seal or icon), tested with `renderToStaticMarkup`. The thread still shows the report
    as data until task 3.2.
  - **Tests and docs:** each section function by direct call (a new row in `code_conventions.md`);
    the `report` event and finished view as plain text against strings in the test, on the
    frying-pan report; `report_text.py`'s tests unchanged but for the finding URL and the
    rename. `terminal_app.md`, `service_architecture.md` (Lines), `calculations.md`
    (`kilograms()`) and `code_conventions.md` follow.
  - **Order of commits**, each green: the line functions of `wording.py` return Lines; the
    section functions, with `report_text.py` printing them; the API and the types; `LineView`
    and the docs. The `LineView` step may move to task 3.2 if the session runs out.
  Prep: grilled and panelled (29 October 2026); `/task` builds it to the spec above.
  Read: `adr/0008-api-sends-finished-lines.md`, `wording.md`, `terminal_app.md`, `service_architecture.md` (API surface), `architecture/calculations.md`.
  Done when: the frying-pan report's lines reach the API grouped by section and by option, every
  figure a label and a value; the CLI's printed report keeps its words, but for a finding's URL;
  and showing a figure needs no numeric field of `Report`.
- [x] **3.2.1 Results page.** Split from task 3.2 by size (29 October 2026); the evidence trail,
  the route line and the opened box are task 3.2.2. The evidence summary line and any caveat and
  warning at the top. Up to three options: price, cost per year, cost per use, lifespan with its
  durability evidence including what owners and testers report, CO2e range with its confidence
  label (styled neutrally, never a badge), the factors the user answered, and the
  check-before-you-buy list. The recurring cost line sits beside the cost figures. Used
  alternatives come with task 2.3. Options over the budget are marked "Over your budget", and a
  "Hide options over my budget" switch filters them out using the within-budget value from the
  API; the page does not compare prices itself. Report-wide lines (the check list, the evidence
  summary, a savings or "Against" line) go on naming an option the switch hides, the baseline
  included: it is the cheapest by sticker price, and within budget counts shipping. Beside a
  price's shipping, a tooltip says that shipping, when stated, may be uncertain (1.10 grill).
  The page's section headings are its own, in `web/lib/wording.ts`: `ReportLines` sends none.
  Settled in the grilling (29 October 2026, no panel); raise one only if the code contradicts it:
  - The results page (`GLOSSARY.md`) is a view of the same page, not a route: it replaces the
    field and the box when the report lands, and a session read back as finished opens it too
    (task 3.2.2 puts the opened box in front of it). The report turn keeps its `lines`; the raw
    JSON goes. On a wide screen the options take columns 1 to 8 and the thread's rounds stay,
    read-only, in columns 9 to 12, where task 3.4's chat grows, "Start again" at their foot; on
    a phone the rounds fold under the options. An empty band above the options holds the place
    of 3.2.2's route line, so nothing shifts when it arrives.
  - Two views. Rows, the wide screen's default: the options side by side, each figure lined up
    across them (subgrid). The deck, always on a phone: one option card at a time, swiped or
    stepped with previous and next buttons, under a pinned strip of each option's name and cost
    per year (its `OptionLines`, so the page still formats nothing); the baseline first, then the
    API's order; no sideways page scroll; with reduced motion the cards swap without a flip.
    Optional, the first cut if time runs short: on a wide screen a "Rows" / "Cards" control
    switches to the deck. It starts on Rows and is not remembered.
  - Every field of `ReportLines` but `trail` shows, as text, the fields not named above included
    (`price_seen`, `link`, `purchases`, `horizon_cost`, `savings`, `co2e_less`, `marks`,
    `built_from`, `rests_on_state`). `stated` and `typical_costs` show once, report-wide, by the
    check list; `factor_values` stay with their option. No chart (`ROADMAP_OPTIONAL.md`).
  - The budget switch shows only when at least one option is over the budget and at least one is
    within it; it starts off, is not remembered and works in both views. An option whose
    within-budget value is unknown is never hidden.
  - The shipping tooltip sits beside every shipping line, worded to hold for a stated amount,
    "free shipping" and "shipping not stated", so the API needs no flag; its words follow
    `docs/wording.md` and live in `wording.ts`. It opens on a tap and from the keyboard.
  - Every control's words (the switch, the view control, previous and next, the tooltip, the
    headings) are in `wording.ts`. Written in the build (29 October 2026): the headings "Your
    options", "Durability evidence" (under the lifespan, so it names the lines without saying the
    figure rests on them), "Your answers", "Check before you buy"; "Rows" and "Cards" (group
    "View"); "Previous option", "Next option"; the strip "Options"; the tooltip's button "About
    shipping", shown as "?", and its words "Shipping comes from the shop's page on the day the
    price was seen, when the page stated it. What you pay at checkout can differ, for example with
    your address."
  Built in the world of task 3.1.3: read `DESIGN.md` first, and run Impeccable for a whole
  surface inside an established world (the look is fixed; it deals three layouts of the views
  above and you pick one). The strip and the deck get their names in `DESIGN.md` (Components).
  Layout only: every line and figure comes from task 3.1.4's `ReportLines` (ADR 0008), and the
  page shows no numeric field of `Report`; a `confidence` part keeps its neutral look.
  Prep: grilled (29 October 2026), no panel; built to the spec above.
  Read: `DESIGN.md`, `adr/0008-api-sends-finished-lines.md`, `product.md`, `architecture/lca.md` (labels), `architecture/interview.md`, `eu_market.md`.
  Done when: the frying-pan query renders completely, on desktop and on a phone, shown once on
  the dev server with the real agents on the recorded sources (model calls only) and by Vitest
  component tests on a sample with three options and every field filled; an option over the
  budget shows its mark and disappears when the switch is on (a stub run with a €30 budget); and
  with no budget there is no mark and no switch.
- [x] **3.2.2 Evidence trail and the opened box.** Split from task 3.2 by size (29 October
  2026), on the results page of task 3.2.1. The evidence trail in a panel, one line per
  `TrailLine` of `ReportLines.trail`, each naming its agent. The route line of task 3.1.3
  (`design/chat_page_brief.md`, "The route line") sits above the options with every station
  ticked; each station opens that agent's part of the trail, so the panel needs no index of its
  own. The opened box: when the report lands the lid opens with nothing rising out of it, and
  "See the comparison" opens the results page. Every figure lives on the results page, not in
  the box (decided 29 October 2026; `chat_page_brief.md`, "Opened").
  Built in the world of task 3.1.3: read `DESIGN.md` first. Layout only, as task 3.2.1: the
  trail's words come from `ReportLines` (ADR 0008), the button's from `web/lib/wording.ts`.
  Prep: no grill; built to the spec above.
  Read: `DESIGN.md`, `design/chat_page_brief.md` (The memorable moment: the box, The route line), `adr/0008-api-sends-finished-lines.md`, `product.md`.
  Done when: on the frying-pan report, each station of the route line opens its agent's trail
  lines and the panel shows every trail line; the opened box shows "See the comparison", which
  opens the results page; on desktop and on a phone, and with reduced motion.
- [x] **3.5 Deploy backend and frontend.** Moved up so deployment problems show early. Backend on
  a Nebius Serverless Endpoint; frontend on Vercel. Grilled on 2026-10-30.
  Known from the Nebius docs (`docs.nebius.com/serverless`): an endpoint runs any container image
  on a CPU platform and preset behind a managed HTTPS URL, billed per second while it runs and not
  at all while stopped, with no scale-to-zero; `--env` and `--env-secret` (from SecretStash, still
  `nebius mysterybox` in the CLI) pass settings and keys; auth is off unless `--auth token`;
  `--volume` mounts a filesystem or a bucket; settings cannot change after creation, so a new
  image is pushed under the same tag and the endpoint restarted, which keeps its URL, and a
  changed setting means delete and recreate, which gives a new URL. A restart or a stop loses the
  container's disk. Not documented, so measured here: the request timeout, SSE buffering, and
  whether the client's IP reaches the container.

  **Image.** The `uv` base image, `uv sync --frozen --no-dev`, `uvicorn
  shopper.api.main:app_from_env --factory --host 0.0.0.0 --port 8080 --workers 1
  --no-access-log`. Docker is not installed here: a GitHub Actions workflow (`deploy.yml`, started
  by hand) builds it for linux/amd64 and pushes it to private GHCR under a fixed tag with the
  built-in `GITHUB_TOKEN`. The endpoint pulls with `--registry-secret`, a classic GitHub token with
  only `read:packages`, kept in SecretStash. No Nebius credential goes in GitHub.

  **Endpoint.** `cpu-d3`, `2vcpu-8gb` (`4vcpu-16gb` if serverless does not offer it),
  `--disk-size 20Gi`, `eu-north1`, container port 8080. The `nebius` CLI is documented for Ubuntu
  and macOS only, so it runs in WSL, called from PowerShell as `wsl -d Ubuntu -- nebius ...`. A
  redeploy: run the workflow, then `nebius ai endpoint restart`. Settings: `LANGSMITH_TRACING=true`,
  `TAVILY_DAILY_CREDIT_LIMIT=300`, `SESSIONS_PER_IP_PER_HOUR=10`, `SESSIONS_PER_DAY=100`,
  `TRUSTED_PROXY_HOPS` as measured, `FRONTEND_ORIGINS` the production Vercel origin only (preview
  deploys cannot call the API). Sessions use the SQLite checkpointer (no `DATABASE_URL` yet); where
  sessions, the cache and the daily credit ledger are kept for good is task 3.5.1.

  **Who can call it.** Endpoint auth stays off: the page calls the API from the browser, so a token
  would be in the public bundle, and a judge needs the URL with no login. Anyone with the URL can
  therefore spend, so add a site-wide ceiling of `SESSIONS_PER_DAY` started sessions (`config.py`,
  100 by default) beside the per-IP limit in `api/limits.py`, counted in memory, because model
  calls have no other cap. `too_many_sessions`'s words are about one connection and the last hour,
  so the ceiling's refusal has its own fixed words (`wording.md`). No code ceiling for Firecrawl:
  the plan stops when its credits run out, recorded as a known risk.

  **Frontend.** Vercel Hobby cannot Git-deploy a private repository owned by a GitHub organization,
  so `npx vercel --prod` from `web/`, with no Git connection. `NEXT_PUBLIC_API_URL` is a Vercel
  Production environment variable; a new endpoint URL means changing it and deploying again.

  **The tracing notice.** `GET /health` gains `tracing: bool`, from `LANGSMITH_TRACING` through
  `config.py`; the page fetches it on load and shows task 3.1.2's notice under the composer when it
  is true (`eu_market.md`, "Personal data"), nothing while loading or when the call fails. This
  replaces the fixed `tracing={false}` in `web/app/page.tsx`. Write the schema and the types again.

  **Checks, in order.** First a throwaway endpoint on `SHOPPER_AGENTS=stubs`,
  `SHOPPER_SOURCES=fixtures` and `SESSIONS_PER_IP_PER_HOUR=2`, which rehearses the create, env and
  secret steps. Its image carries a temporary log line with the number of `X-Forwarded-For` entries
  and the names of any forwarding headers, never their values; that commit is dropped before the
  pull request. From it set `TRUSTED_PROXY_HOPS`, then check that a laptop on wifi and a phone on
  mobile data are counted apart. Delete it. If no client IP reaches the container, the per-IP limit
  is a site-wide cap: set it to about 30 an hour, say so in `service_architecture.md`, and check
  instead that the limit reads the address the platform gives. Then, on the real endpoint, one real
  analysis with its answers stream of about two minutes (findings 1.10), and `curl -N` on a long
  stream. If the platform cuts a stream, the page must still reach the report through
  `GET /sessions/{id}`; if it does not, fix that here. Warm the cache by running the three examples
  once, one of them from the phone.

  **When it runs.** On while building up to the submission (2026-10-30), then stopped. Started again
  before the judging period opens (Wed 9 Dec 2026, 09:00 PT), the cache warmed again unless task
  3.5.1 has landed, and stopped after it closes (Wed 23 Dec 2026, 12:00 PT), which also ends the
  tracing. About $1.60 a day. Record the exact steps and these dates in `building_the_project.md`
  (Deployment).
  Prep: grilled, no panel; start with `/task`.
  Read: `building_the_project.md` (Deployment), `architecture/data_sources.md` (Calls per analysis, Cache and fixtures), `service_architecture.md` (the limit per client IP), `eu_market.md` (Personal data), `wording.md`.
  Done when: the public URL completes a query from a phone.
  Changed by the developer on the day, over the text above: no volume (grilled for task 3.5.1);
  the project's region is `eu-west2`; `SESSIONS_PER_DAY=46`, `TAVILY_DAILY_CREDIT_LIMIT=283` and
  `TRUSTED_PROXY_HOPS=1`; up on 2026-10-30 until 21:00 CET, then from 2026-11-30 to 2026-12-23
  12:00 PT; the URL is `truecost-unboxed.vercel.app`. `wsl --exec` in place of `wsl --`. The
  ceiling's words: "Many sessions were started on this app in the last day, so no new one was
  started. Try again tomorrow." (`docs/building_the_project.md`, "Deployment").
- [x] **3.10 Front-end fine-tuning.** The last build task, added on submission day: small fixes
  to the page that the developer lists at the start of the session, one at a time, in the order
  given. Fixes only, no new feature, and nothing that changes the API or its schema. Time-boxed so
  it merges and is deployed before the video is recorded and before the deadline (Fri 30 Oct
  2026, 10:00 PT, which is 18:00 in the Netherlands); a fix not done by then is left out.
  It opens with what was task 3.6, edge-case hardening, cut to a check because the backend already
  handles each case (`link_unreadable`, the supervisor's declined and unclear outcomes, a missing
  budget, per-agent timeouts): on the deployed page, type a
  dead shop link, nonsense ("asdf qwerty"), a need with no budget ("I need a kettle") and an
  out-of-scope request ("a used car under €5000"). Any that freezes, crashes or reads badly goes
  first on the list of fixes.
  Fixed whatever the list: a reload, or a product link followed in the same tab and then Back,
  returns to the opening and loses the results, because the page keeps the session id in memory
  only (`web/lib/thread.ts`; found in task 3.2.1's browser run). Keep the id in `sessionStorage`
  and, on load, read the session back through `GET /sessions/{id}`, a paused session at its
  questions and a finished one at its results; an unknown or expired id clears it and shows the
  opening. Not in the URL: `GET /sessions/{id}` has no auth, so a shared link would show the
  session's input to anyone.
  Also fixed: the example "A kettle, €60" (`EXAMPLES`, `web/lib/wording.ts`) researches a stovetop
  kettle. A run on submission day (LangSmith trace `01a18c78-43fd-7260-8e41-994246ed696b`) read
  the local term as "waterketel", the stovetop kind (an electric kettle is a "waterkoker"), and
  took induction-hob compatibility, a whistle and copper polishing from kitchenaid.com's page on
  tea-kettle types, as task 1.10 had found; the compatibility question can remove every electric
  kettle. Not fixed in the brief on the last day, since its prompt and sources shape every
  category. Try "An electric kettle, €60" once live in its place; if its report is wrong too, put
  a category in that the developer has seen give a good report, or keep two examples. The
  README's limitations say which categories were checked and that others are less reliable.
  Last on the list, taken from task 3.4 when it moved to the optional layers: run
  `/impeccable critique` on both pages, then `/impeccable polish` on what it finds, before the
  video is recorded.
  Prep: no grill; the list of fixes is given at the start.
  Read: `DESIGN.md`, `design/chat_page_brief.md`.
  Done when: the four inputs each end in a fixed message or a report, none freezing or crashing;
  a reload of a finished report and of a session at its questions shows it again; every example
  shown on the page gives a sound report live; each listed fix is visible on the public URL; the
  critique and polish have run on both pages; and the pages touched pass the visual check in
  `building_the_project.md` at 390 px and 1280 px.
  Changed by the developer on the day, over the text above. The fixes, in order: the title
  "unboxed." with the tagline "The price tag is only the start"; a budget note, once, when a request
  has no number and no link ("Have a budget in mind? Add it here, for example €50. Or press Next to
  go on without one."), and Enter sends; the ticks and the second-hand station gone; a wider pulse
  (a box shake was tried and reverted); the stations' notes in plain words, from the first send to
  the results page, with a cross and a hint ("Press a station to see what that step does. Once your
  options are ready, each one shows what it found."), and no live trace, which needs a new stream
  event and a backend redeploy; a reload during a run says "Still working on your request..."; no
  agent, tier or model in the trail, and "LCA tier 3" reads as CO2e; "See the comparison →" in paper
  with a hard shadow, in the opening, and "Your comparison is ready." in the status line. The critique
  (26 of 40) and the polish were done for the wide screen only, on the developer's call: the results
  lead with the savings, naming the options Option A, B, C, then the larger cost per year straight
  after the price, in one sheet per option with thin rules; unconfirmed answers fold into one line
  ("Interior material, temperature control: not confirmed on the pages read"), the model's reading of
  the product stands under "Durability evidence" under its label, and links show their site alone. A
  skipped answer reads "usage frequency?" in the panel as on the box. The reply's and the request's
  readers take a frequency only for the product's use overall, in the code but live only with a
  backend redeploy. `NEBIUS_MODEL_SMALL`, `NEBIUS_MODEL_MEDIUM` and `NEBIUS_MODEL_LARGE` override the
  tiers' models, for Nebius retiring Nano and Super on 9 November (`building_the_project.md`,
  "Deployment"). The phone's half is in `design/phone_fixes_after_hackathon.md`, and the 390 px check holds
  for what was left as it was. All three examples stay, on the developer's call after their live runs
  on 30 October: the frying pan compares three, with the durable ones cheaper over 10 years; "An
  electric kettle, €60" compares three electric kettles and the cheapest comes out best, on rough
  lifespans; the cordless drill found one option, sold without its battery, with nothing to compare
  it against. So "every example gives a sound report" is the developer's judgement here. The README's
  limitations line goes to task 3.7. A dead link gets its decline, not the questions.
- [x] **3.11 CO2e for scale: car kilometres.** Added on submission day, kept small. The option
  sheet's "less to make" line (`co2e_less`) gains a comparison anyone can picture: "About 10 to 30
  kg CO2e less to make over 10 years (label); for scale, about 100 to 310 km in an average new EU
  car (EEA, 2025, test figure)". Researched on submission day:
  - **The factor.** 96.7 g CO2 per km, the average new car registered in the EU in 2025 (European
    Environment Agency, June 2026,
    `https://www.eea.europa.eu/en/newsroom/news/average-co2-emissions-from-new-cars-and-vans-significantly-decreased-in-2025`).
    In `config.py` with its source, its year and that it is a test (WLTP) value, as the model
    prices are. It counts the tailpipe only and averages in electric cars, so it gives more
    kilometres per kilogram than a real drive would: the cautious way round.
  - **Code only** (CLAUDE.md rule 1): a `calc/` function turns the line's low and high kilograms
    into kilometres, the low end rounded down and the high end up to tens of km; under 10 km at
    the high end the comparison is left out. No model writes it.
  - **Words and source.** One fixed text in `wording.py` (and `docs/wording.md`), appended to the
    same Line, so the schema, the page and the terminal app need no change; the source is a link
    part to the EEA page. It says "for scale" and names the car and the year, because the car
    chosen changes the answer up to 2.5 times (the US EPA's average petrol car is about 244 g/km).
  - **Only beside the difference**, never beside an option's own total: the difference is what a
    shopper acts on. It keeps the line's confidence label. Only tier 3 estimates exist so far
    (tiers 1 and 2 are optional), so it shows with them; showing it only for a published or
    benchmark figure would show it nowhere today.
  - **Not used:** trees (estimates from 10 to 40 kg a tree a year, and they read as offsetting,
    which the EU rules on green claims from 27 September 2026 forbid as a product claim) and phone
    charges (grid-dependent, and the counts run to hundreds).

  `lca-reviewer` reviews the change (CLAUDE.md). Deployed with 3.10, before the deadline; if it is
  not done in time it waits for after judging.
  Prep: no grill; built to the spec above.
  Read: `architecture/calculations.md`, `docs/wording.md`, `eu_market.md` (wording of environmental claims), `adr/0008-api-sends-finished-lines.md`.
  Done when: the frying-pan report's option sheet shows the kilometres beside its "less to make"
  line with the EEA link, a test covers the rounding and the cut under 10 km, and `lca-reviewer`
  finds nothing to change.
  Changed on the day, over the text above, after `lca-reviewer`. The words: "; for scale, about 100
  to 320 km in an average new car in Europe, electric cars included (car figure: EEA, 2025, tailpipe
  test; real drives emit more)": a comparison states its basis, and the source is the car figure's
  alone. The example's 310 km is 320 by the task's own rule (310.2, rounded up to tens). "The cautious
  way round" above is wrong: a low g/km gives more kilometres, which makes the difference look
  larger, so the line says so and `calculations.md` lists it under "Known simplifications". The figure
  covers the EU, Norway and Iceland and is provisional. From 1,000 km the ends round to two significant
  figures. The words are in `wording.py` only, as `docs/wording.md` asks.
- [x] **3.7 README, licence and architecture diagram.** Problem, how it works, setup steps a
  stranger can follow, limitations, a section on how the Nemotron models and Nebius services
  are used and where Token Factory helped, and a short "where this is heading" note on EU
  Digital Product Passports. Add the open-source licence file; which licence is an
  open decision, so ask first.
  Prep: no grill; the licence question is asked during the task.
  Read: `product.md`, `service_architecture.md`, `building_the_project.md`, `eu_market.md`.
  Done when: a stranger can run it locally from the README, and the licence shows at the top of
  the repository page.
