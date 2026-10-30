# Agents, graph and state

Read this when adding or changing an agent, the graph wiring, or the shared state and schemas.
Models and the model client are in `models.md`.

## The graph

Six agents, each a LangGraph node: a function that reads the shared state and returns a partial
update. Nodes never mutate the state they receive.

| Agent | Reads | Produces | Model tier |
|---|---|---|---|
| Supervisor | Raw user input; the page at a pasted link | Parsed request with its scope and category (see `supervisor.md`); the linked product; at the end, the assembled report | small / fast |
| Brief agent | Request; the linked product, when a pasted link was read; its brief store; at the pause, the user's reply | Researched decision factors for the category with their sources, the answers the request already states, then up to four questions about the factors it does not settle (two with a linked product) and the usage question last (see `interview.md`); every question it phrased, asked or not; the local category term that option research searches with (`category_brief.md`, "How the brief is researched"); before the graph resumes, what the reply says (`reading_answers.md`, "The reply") | medium for the research, the questions, the stated answers, the reply and the local term (`models.md`) |
| TCO analyzer | Request, the linked product, the local category term, decision factors, every question phrased (asked or not) and the usage question, answers | Up to 3 product options, the linked product among them (see `option_research.md`), each priced from an offer on a comparison site's product page, with expected lifespan, durability evidence and recurring costs | medium |
| LCA agent | Options | A CO2e estimate per option (see `lca.md`): today tier 3 only, one large-tier call for every option (`agents/lca/`) | medium; large only for tier 3 |
| Second-hand agent | Request, answers, options | The 3 cheapest used copies within budget of the last option over budget in report order (marketplaces per `docs/eu_market.md`) | small / fast |
| Conversation agent | The current report version, the user's message | The kind of message and the change it asks for; then an answer built from the results (see `conversation.md`) | small to classify, medium to answer |

Flow: supervisor (parse, then read a pasted link) -> brief agent -> **pause for the user's answers** -> TCO analyzer ->
LCA agent and second-hand agent (independent of each other, run in parallel) -> supervisor
(assemble, which runs `calc/`).

A diagram of this flow, for people, is in `graph_diagram.md`; one diagram per agent that runs
today, linked from the README, is in `agent_diagrams.md`.

`calc/` is not a node. `assemble_report` calls it (through `assemble` in `report.py`, a pure
function from the parts of the state to a report) for the comparison, the evidence summary and
the nothing-within-budget warning, so those exist only on the report, never in the state. The
LCA and second-hand nodes join at `assemble_report`, which waits for both.

The supervisor is three nodes, `parse_request`, `read_link` and `assemble_report`.
`parse_request` and `read_link` write their trail entries as the supervisor; `assemble_report`
writes none, because it decides nothing (`supervisor.md`, "Trail"). The parsing step (scope,
category, budget, corrections) is in `supervisor.md`. A request whose scope is `not_a_product`
(which includes motor vehicles), `several_products` or `unclear` goes straight from
`parse_request` to `assemble_report`, so every outcome leaves the graph as a report through the
same node.

The one exception is a request with a product link. It goes from `parse_request` to `read_link`
unless it is `not_a_product` or `several_products`, so an `unclear` request with a link is read
too: the page can name the product the text did not. `read_link` (`agents/linked_product/agent.py`)
fetches the page and handles the four outcomes in `data_sources.md` ("An unreadable link"). It
may replace the request with a copy that has the category and scope read from the product name,
or with an `unclear` copy when the page gave no product and there is no category; after it, a
request that does not run goes to `assemble_report` as above. The product it read is the
**linked product**, a product option with the id `option-link`, held under its own state key.
The TCO node passes it to its agent, which selects at most two candidates beside it and returns it
first among the options (the node adds nothing), so the LCA and second-hand agents and `calc/`
treat it as any other option.

**The state.** A `TypedDict` in `graph.py` whose keys mirror the parts of a report: `input`,
`request`, `linked_product`, `local_term` (the brief's, for the TCO analyzer), `factors`, `questions`, `answers`, `options`, `lca_results`, `listings`,
`assumptions`, `trail`, `warnings`, `report`; and `phrased_questions`, every question category
research phrased, asked or not, which is never on a report (a session saved before it existed has
none). The values are the frozen models from `state.py`.
`trail` and `warnings` are appended to, because the LCA and second-hand nodes run in parallel and
both write to them. Every other key has one writer at a time: `answers` is written first by the
brief agent (the `stated` ones) and then replaced by the `interview` node with the complete set,
and `factors` likewise, the `interview` node adding the user's own factors from the reply; the
`interview` node also writes `assumptions`.

A collection in the state is typed as a `Sequence` of models, not a tuple: LangGraph hands a
tuple back as a list once the state has been saved and reloaded. Nodes return tuples, never
change what they read, and the reducer for `trail` and `warnings` joins both sides into a new
tuple. The report is built from the state and is fully frozen again.

A key is absent until its node has run, so the `TypedDict` is not total and every read gives a
default. On the short path from `parse_request` to `assemble_report` only `input`, `request`,
`trail` and `warnings` exist, and `linked_product` when a link was read.

**After the first report: the conversation.** The session stays open. Each user message goes to
the conversation agent, which classifies it; code then dispatches the work to the specialists
(an explanation, a recalculation, or a rerun of the agents that own the change), and a rerun
produces a new report version. The conversation agent never calls another agent itself. Details,
including the turn and report-version models, are in `conversation.md`.

**The pause and the sessions.** The graph stops after the brief agent and resumes with the
user's answers; the `interview` node, the functions the entry points call, progress, reading a
saved session and the session errors are in `sessions.md`.

`agents/bundle.py` holds the bundle (`AgentBundle`), the type of each agent function and what
each returns (`BriefOutput`, `TcoOutput`, `LcaOutput`, `SecondHandOutput`): its part of the
state plus its trail entries and warnings. The node in `graph.py` copies that into the state. The
bundle's fifth function is the reply's reader, which is no node: `resume_with_reply` calls it
before the graph resumes, and it returns a `ReplyOutput` or raises `ReplyUnreadError`.
`agents/stubs.py` holds a stub of every agent, with fixed data, and `STUB_AGENTS`, the bundle of
all five stubs, which the graph and CLI tests pass; the stub brief has the hob and usage
questions and a recurring-cost factor with a typical yearly cost, and the reader's stub answers
each question one of whose choices the reply names as whole words, as a stated answer, and reads
nothing else and calls no model (task 3.1.5); the API runs `STUB_AGENTS` too when
`SHOPPER_AGENTS` is `stubs` (task 3.1.1).
`agents/default.py` holds `DEFAULT_AGENTS`,
the bundle the entry points run otherwise: the real brief agent (`agents/brief/agent.py`), the real TCO
analyzer (`agents/tco/agent.py`, every step of option research), the real LCA agent, the real
reply reader (`agents/brief/reply.py`) and the second-hand stub. The TCO stub puts the linked
product before its two fixed pans, as the real agent does.

**Evidence trail.** Every agent appends entries to a `trail` list in the state: which agent, what
it found, decided or excluded, the source, for exclusions the reason, and the model tier and
model that produced it. The trail is part of the
report. It is how the user and the judges see what each agent and model tier did.

The second-hand agent is always a node in the graph. It searches when the request has a budget
and a priced option is over it new, for used copies of the last such option in report order, and never for a
safety-critical category (a keyword list in `config.py`); otherwise it returns no listings. Either way it
writes a `decided` trail entry saying which, so the report shows why no used items were looked
for.

## Data model

Defined once in `src/shopper/state.py` as frozen pydantic models. Terms are defined in
`GLOSSARY.md`.

| Model | Key fields |
|---|---|
| Source | kind (`url`, `dataset`, `model_estimate` or `user`), reference, optional label, and for a web source a model read, who stated it (`stated_by`: `tester`, `owner`, `manufacturer` or `seller`) |
| Request | original text, product URL (optional), category (optional), budget (optional), currency (always EUR), scope |
| Decision factor | id (with a prefix per origin: `researched-`, `usage-` and `user-`), name, kind, why, source (a URL; the user for a factor of the user's own; none for the factor of kind `usage`), optional typical yearly cost, its source and the currency it was converted from (see `category_brief.md`) |
| Question | id, the factor it belongs to, text, reason, two to four choices; a choice may carry uses per year |
| Answer | the factor it is about, status (`chosen`, `stated`, `not_sure` or `skipped`), the choice or the stated value with the phrase it came from (a stated answer also carries the choice when code mapped it onto one), optional uses per year, and where the phrase was said (`stated_in`: `request` by default, or `reply`; a `not_sure` read in the reply keeps its phrase) |
| Interview answers | what the `interview` node resumes with: the answers picked, the answers read in the reply, the user's own factors the reply adds, the reply's trail entries |
| Product option | id, name, brand (optional: from the product page or the listing, or the linked product's JSON-LD), price with its source and the date it was seen (all three or none), the size or variant it was quoted for (optional) (the source's label names the shop when an offer on a comparison site gave it), the shipping that offer states (optional; only with a price), the marks `out_of_stock` and `incomplete` (`option_research.md`, "Selection"), link, piece count for a set (optional), lifespan in years and its source (both or neither), durability evidence, recurring cost per year and its source (both or neither; the source's label names the consumable) with its state (`found`, `not_found` or `not_looked_for`), the currency it was converted from (optional, USD or GBP) and whether other consumables were left out, factor values, materials, weight and its source (both or neither; the linked product's page) |
| Factor value | per option and factor: fit (`meets`, `fails` or `unverified`), a short text value (given with `meets` and `fails`, none with `unverified`, from task 1.8.6), source (the quoted result, or the factor's own source when `unverified`) |
| Material | name, optional form (e.g. primary, recycled), optional mass in kg, source; what a product option is made of |
| LCA input | name and optional form with their source, whether it is a separate component (electronics, a motor, a battery), mass in kg and its source, emission factor low and high in kg CO2e per kg and its source (`lca.md`) |
| Durability evidence | warranty (years or a lifetime, and whether it is limited), spare parts or repair availability, wear-determining material, care needed, and a lifespan typical for the type (a range of years, with the kind of product its quote names), each optional and each with a source; findings, each labelled `test` or `owner_report` (set by code from `stated_by`) with a summary, a source, an optional overall rating exactly as the source states it, a review count (required with an owner report's rating) and an optional published date; and a findings state, `found`, `none_found` or `not_searched`, which is `found` exactly when there are findings (`option_evidence.md`, "Findings") |
| Assumptions | horizon, uses per year, and per-option lifespan overrides set by the user (see `calculations.md`) |
| Trail entry | agent, kind (`found`, `decided` or `excluded`), what was found or decided, source, reason, model tier and model |
| LCA result | the option it is for, CO2e low and high, tier, source, boundary, inputs (LCA inputs), a manufacturing and assembly range with its source (fields in `lca.md`). An option with no estimate has no LCA result |
| Listing | id, the option it is a used copy of (optional), title, price, shipping cost (optional; missing means unknown), currency (always EUR), condition, link, country, ships to NL, marketplace |
| Comparison | baseline option, and per option every figure in `calculations.md`, each optional, with a reason when missing, a flag when recurring costs were looked for and not found, the currency a recurring cost was converted from, and whether the option is within budget (missing when there is no budget or no price) |
| Caveat | a code (`not_tuned`, `energy_heavy`, `clothing`); the wording in `wording.py` is applied when it is shown |
| Warning | code (one of a closed set, see "Warning codes"), message, the option it concerns (optional) |
| Check item | factor, option (optional), reason (`unanswered`, `unverified`, or `price` for a price to confirm, the one reason with no factor) |
| Evidence summary | counts only: lifespans sourced, estimated, set by the user and missing; footprints published, benchmark, model estimate and missing |
| Report | request, decision factors, questions, answers, options, LCA results, listings, assumptions, comparison, evidence summary, caveats, check-before-you-buy list, trail, warnings |

Rules for these models:

- **Ids are assigned by code**, never by a model. Models refer to each other by id.
- **Money is a `Decimal` in EUR.** An amount in another currency is left missing with a warning
  (`docs/adr/0001-euro-only.md`); the one exception is a recurring cost in USD or GBP, converted
  at a fixed rate and labelled (`docs/adr/0002-fixed-rate-conversion-recurring-costs.md`).
- **A rough estimate is a source too.** A lifespan with no web or dataset source has a source of
  kind `model_estimate`; it never has no source.
- **Only what is always true is validated.** At most five questions and twelve factors on a
  report (eight researched, the one of kind `usage` and three of the user's own), two to four choices, CO2e low not above high (for a result, its manufacturing range and each input's factor), an LCA input's mass and factors above zero, a manufacturing range given with its source, a tier 3 result with inputs, a manufacturing range and the boundary "cradle to gate: materials and manufacturing", a budget above zero, no category on an
  `unclear` or `several_products` request, a value and its source given together (lifespan, recurring cost, typical
  yearly cost, weight; a price with its source and seen-on date), a factor value's text given exactly when its fit is not `unverified` (task 1.8.6), a findings state of `found` exactly when there are findings and an owner report's rating only with its review count (task 1.8.4), an answer whose content matches its status (only a `stated` or `not_sure` answer is from the reply), and a reason on every `excluded`
  trail entry, a lifespan above zero, no negative price, cost or CO2e, and a decision
  factor whose source is a web URL or, for a factor of kind `requirement`, the user, except the factor of kind `usage`, which has no source.
  Unknown fields are rejected. A frozen model blocks
  reassigning a field, not changing a dictionary inside it (`lifespan_overrides`,
  `missing_reasons`): those are never changed in place, by convention
  (`docs/code_conventions.md`), and nothing enforces it. Ids are not cross-checked between models. "At most four researched questions and the usage
  question" is a rule for the brief agent, because a pasted link or a category with no sourced
  factors can give fewer.
- **One report shape.** A declined request, an unclear request, a request naming several products, a report where every answer is
  skipped and a report with no options are all valid reports. A report with nothing to compare
  has no comparison (it is missing, not empty). The check-before-you-buy list and the evidence summary
  are filled by code when the report is assembled, by pure functions that `assemble_report`
  calls. A factor of kind `usage` is never on the list: how often the product is used is an
  assumption the user sets, not something to check. For every other factor the list holds one
  `unanswered` item when it has no `chosen` or `stated` answer, and otherwise one `unverified`
  item per option whose value for that factor has the fit `unverified`. It also holds one `price`
  item, with no factor, per option with a price, shown as one line for all of them, since prices
  change (task 1.15; `option_research.md`, "Warnings"). A request that does not
  run gives a report with the request, its trail and its warnings, and nothing else; with no
  options `compare` is not called.
- **Not here.** The LangGraph state type is in `graph.py` (it is built from these models).
  The schema an agent asks its model to fill is a separate, smaller model beside that agent.

### Warning codes

`warnings` is how partial results are reported: each entry says what could not be used, found or
verified, and why. An unknown value is represented as missing, never as zero or a guess.

The codes are a closed set, an enum in `state.py`, so a mistyped code is rejected. A task that
needs a new code adds it to the enum and to this table.

| Code | Raised when | Raised by |
|---|---|---|
| `budget_unreadable` | The request states a budget that cannot be read as an amount ("5o euro") | Supervisor |
| `budget_not_positive` | The stated budget is zero or negative | Supervisor |
| `budget_other_currency` | The stated budget is in a currency other than EUR | Supervisor |
| `nothing_within_budget` | There is a budget, but no option and no listing within it (see `calculations.md`) | `calc/` |
| `link_unreadable` | The pasted link gave no product name and the category is known; the session goes on without the linked product | Supervisor (`read_link`) |
| `link_price_other_currency` | The page at the link states its price in a currency other than EUR; the linked product's price is missing (`docs/adr/0001-euro-only.md`). Carries the linked product's option id | Supervisor (`read_link`) |
| `research_unavailable` | The request has a category and the brief ends with no researched factor: the searches failed or found nothing, the read failed, or no factor passed the checks. Only the usage question is asked | Brief agent |
| `questions_unavailable` | There are researched factors, but the phrasing call failed (`category_brief.md`). The factors stay, so they are on the check-before-you-buy list; only the usage question is asked | Brief agent |
| `stated_answers_unavailable` | The call that reads what the request states failed (`reading_answers.md`, "Stated answers"). Nothing is stated, so every question is asked | Brief agent |
| `one_option_only` | Exactly one product option is left after the evidence step, the linked product included, whatever the reason | TCO analyzer |
| `no_options_found` | No product option is left after the evidence step. The message says which: the searches did not work, none met the answers, or nothing with a euro price was found, in that order (`option_research.md`, "Warnings") | TCO analyzer |
| `co2e_unavailable` | An option has no CO2e estimate: the model declined it or its inputs failed a check. One per such option, carrying its option id; or one for the report, with no option, when the call failed or the whole estimate passed its time cap (`LCA_TIME_CAP_SECONDS`). The evidence summary counts both as "not found". The stub raises none | LCA agent |

The three `budget_` codes leave the budget missing (see `supervisor.md`); `nothing_within_budget`
keeps it.

## Agent contract

- **Structured output only.** An agent returns a pydantic-validated object. On a schema failure,
  retry once with the validation error in the prompt; if it fails again, add a warning and
  continue without that part. The one exception is the supervisor's parsing call: without a
  request nothing can continue, so its failure is an error and no report exists (see
  `supervisor.md`).
- **Extract, never compute.** An agent finds inputs such as price, lifespan and materials. It
  does not divide, multiply or total them; that is `calc/`.
- **Cite.** A lifespan or material claim carries the URL or dataset it came from.
- **Tools as parameters.** An agent receives its tools as arguments, so tests pass fakes.
- **Tone.** Prompts follow `docs/product.md`: practical, budget first, no moralising.

## Models

Agents ask for a tier (small, medium or large), never a model name. Model IDs, which component
uses which tier, the tier rules, and the client in `llm.py` are in
`models.md`; what was measured is in `docs/findings/`.

## Adding an agent

1. Add the domain model it produces to `state.py`, if it does not exist yet.
2. Write the node function in `agents/<agent>/agent.py`, with its prompt as a named constant in
   `agents/<agent>/prompt.py`, which `agent.py` imports. The schema the model fills is defined
   in the agent's package (`models.py` once it has one), holding only the fields the model
   extracts; code maps it into the domain model and adds ids, sources' kinds and anything computed.
3. Wire it in `graph.py`. For one of the five functions in the bundle, the function matches its
   type in `agents/bundle.py` and takes the place of its stub in `DEFAULT_AGENTS`
   (`agents/default.py`); `STUB_AGENTS` keeps every stub for the tests.
4. Test it with fake tools and a recorded model response.
5. Add a row to the table above.
