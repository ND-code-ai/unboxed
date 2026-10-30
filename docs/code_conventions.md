# Code conventions

Read this before writing or reviewing code. Formatting, import order and lint rules are not
covered here: ruff (Python) and ESLint/Prettier (Next.js) own those, so run them instead of
reasoning about style.

Two principles apply to both languages: code is **functional** and **modular**.

If you are writing only Python or only Next.js, read the shared principles and that one section.

- [Shared principles](#shared-principles)
- [Python](#python)
- [Next.js](#nextjs)
- [Tests](#tests)

## Shared principles

**Functional**

- Prefer pure functions: output depends only on arguments, no hidden reads or writes.
- Keep side effects (network, disk, clock, environment, randomness) at the edges and pass their
  results inward as plain data.
- Treat data as immutable. Return new values instead of mutating arguments.
- No module-level mutable state and no singletons. Pass dependencies in as parameters.
- Make failure explicit in the return type at boundaries, rather than raising through layers.

**Modular**

- One responsibility per module, and a name that says what it is.
- Small functions that do one thing; if a function needs a comment to explain its sections,
  split it.
- Depend on interfaces, not implementations, wherever something is swappable (marketplace,
  search, page fetch, model client).
- Import direction follows `docs/service_architecture.md` ("Dependencies point inward").
- No duplication across packages: `api/` and `cli.py` reuse `src/shopper`, they do not copy it.
- Do not add a dependency for something a few lines of code can do.

## Python

- **Types everywhere.** Full type hints on every function. Data crossing a boundary (agent
  output, API request and response, tool result) is a pydantic model, not a dict.
- **Immutable models.** Pydantic models are frozen; derive a changed copy with `model_copy`.
- **Classes are for data and interfaces only.** Use pydantic models for data and `Protocol` for
  swappable interfaces. Behaviour lives in functions, not in methods on stateful objects.
- **Agents are functions.** A LangGraph node is `(state) -> partial state update`. It does not
  mutate the state it receives.
- **Pure core.** Everything in `calc/` is pure and deterministic: no I/O, no model calls, no
  current time. Pass dates and horizons in as arguments.
- **Effects in `tools/` and `api/`.** Network and disk access live there. An agent receives its
  tools as parameters, so tests can pass fakes.
- **Configuration through `config.py` only.** No `os.environ` reads elsewhere, no model IDs or
  URLs hard-coded in agents.
- **Prompts are data.** Each agent is a package, `agents/<agent>/`, with the agent function in
  `agent.py`. Keep its prompt as a named constant or template in `agents/<agent>/prompt.py`,
  separate from control flow; `agent.py` imports it.
- **One concern per module.** An agent that outgrows `agent.py` splits by concern into modules
  of its package: `models.py` for the schemas of its model calls and the tuples its steps pass
  on, `checks.py` for the pure checks on what its model wrote. Helpers every research loop
  shares live in `agents/shared/`.
- **Async for I/O.** Network calls are `async`; pure functions stay synchronous.
- **Errors.** Tools return a typed result that can represent failure (not found, blocked, rate
  limited). Raise only for programmer errors. The one exception is the supervisor's parsing
  function, which raises a typed error for over-long input and for a failed model call, because
  no request and no report can exist then (`architecture/supervisor.md`); its reading of the
  product name at a pasted link (`read_product_name`, called by `read_link` in
  `agents/linked_product/agent.py`) raises the same error for the same reason; the entry point
  catches it and shows the fixed line from `wording.py`. `resume_session` and `check_resume` in
  `graph/sessions.py` likewise raise a typed error for a session that is unknown or not waiting
  for answers (`architecture/sessions.md`, "The pause"), `read_report` there one for a session
  that is unknown or holds no report, and the reply's reader (`read_reply` in
  `agents/brief/reply.py`) raises `ReplyUnreadError` when its call fails twice, which
  `resume_with_reply` raises unchanged, because nothing may resume then.

## Next.js

- **TypeScript, strict mode.** No `any`; type API data from the backend's OpenAPI schema instead
  of hand-writing duplicate types.
- **App Router, server components by default.** Mark a component `"use client"` only when it
  needs state, effects or browser APIs, and keep that boundary as low in the tree as possible.
- **Function components only**, kept small and presentational: props in, markup out.
- **No business logic in the frontend.** All cost and impact numbers come from the API. The
  frontend formats and displays them; it never recomputes them.
- **One API module.** All calls to the backend go through `web/lib/api`. Components do not call
  `fetch` directly.
- **State stays local.** Prefer props and URL state; lift state only as far as needed. No global
  store unless a task calls for one.
- **Charts are pure components** that take prepared data as props; data shaping happens in a
  separate function that can be tested.
- **Pure helpers in `web/lib`**, UI in `web/components`, routes in `web/app`.
- **Copy follows the product tone:** plain, practical, no moralising. Label estimates as
  estimates and show the confidence tier wherever a CO2e figure appears.

## Tests

How to write a good test is the `tdd` skill's job; use it for any task that writes code. This
section holds only what is specific to this project.

**Agreed test points.** These are the public interfaces tests are written against. They are
confirmed, so do not stop to ask before testing at one of them. Ask only when a task needs a
test point that is not on this list, and add it here once agreed.

| Test point | Tested through |
|---|---|
| Each domain model in `state.py` | Construction with sample data, for the rules under the data model table in `docs/architecture/agents.md` and the report shapes only; no test that a field holds the value it was given, or of what pydantic already guarantees |
| Each public function in `calc/` | Direct call with plain values; expected results from the worked examples in `docs/architecture/calculations.md`, never recomputed in the test |
| Each tool interface in `tools/` (search, page fetch, marketplace, brief store) | The interface, against recorded responses in `tests/fixtures/`; the brief store against a folder on disk and a clock the test sets |
| `nebius_chat` in `llm.py`, with LangSmith tracing | The `ChatModel` with an injected `httpx` transport, run inside `traced` (`tracing.py`) with a fake LangSmith client: the request body sent and the runs posted; the CLI's `run` the same way for the trace of a session |
| The HTTP client of each service in `tools/` | Its service function with an injected `httpx` transport; one test per failure kind (`docs/architecture/data_sources.md`, "Failure kinds") |
| Each agent node in `agents/` | The node function `(state) -> update`, with fake tools and a recorded model response |
| The supervisor's parsing function in `agents/supervisor/agent.py` | Direct call with the input and a fake `ChatModel` whose reply is written by hand. This proves what code does with a reply, not how the model classifies |
| `read_budget` in `calc/budget.py` | Direct call with a phrase; expected results from the budget tables in `docs/architecture/supervisor.md` |
| The checks on a finding in `agents/tco/` (copied words, the summary's numbers and generalising words, the rating) | Direct call with plain text; cases from `docs/architecture/option_evidence.md`, "Findings" |
| The line functions of `wording.py` and `lines.py` (task 3.1.5) | Direct call with plain values, or with a session or report that `assemble` built; a Line compared as its parts or as plain text |
| The lines of each API event and view (task 3.1.5) | As for each API endpoint: each event's and view's lines as plain text, against expected strings written in the test, never against the CLI's output |
| The display formatters in `calc/` (`euros()`, the years formatter, `kilograms()`, `whole_minutes()`; tasks 3.1.5, 3.1.4 and 2.5.2) | Direct call with the edge cases of the rounding rule in `docs/architecture/calculations.md`, the expected strings written in the test |
| The supervisor evaluation in `tests/eval/` | Live only (`-m live`), through the parsing function and the real model; plus offline tests that no held-out product is in the prompt, and of the functions that judge a case, with answers written by hand |
| The assembled graph | `cli.py` or the graph entry point, end to end on fakes, including the pause and resume and the skip-all path. An agent is replaced only through the bundle passed to `build_graph`, and the reply's reader through the one passed to `resume_with_reply` |
| The pure functions `assemble_report` and `interview` call (check list, caveats, completing the answers) | Direct call with plain values |
| Each section function in `report_text.py`, and `printed_report` | Direct call with a report that `assemble` built; each section on its own lines (`docs/terminal_app.md`, "Where the code goes") |
| Each section function in `report_lines.py`, and `report_lines_of` (task 3.1.4) | Direct call with a report that `assemble` built; a Line compared as its parts or as plain text, a figure as its label, its value and whether it is missing |
| The terminal prompts in `cli.py` | `ask`, with the typed lines passed in as a function in place of `input`; `parse_arguments` by direct call |
| Each API endpoint | HTTP request against the app built by `create_app` with the fake model, the fixture sources, the stub agents and a SQLite file on `tmp_path`, through `httpx.ASGITransport`, with the lifespan run by the test (the transport does not run it). The transport reads a whole response before returning it, so a client that disconnects mid-stream is a request sent straight to the ASGI app |
| What the settings reach in `app_from_env` (`api/main.py`, task 3.5) | HTTP request against the app it builds, on settings the test sets and no `.env`, for what stops short of a model call: `GET /health`, and a start refused by a ceiling of 0 |
| The conversation agent | Each kind of message with a fake model and the fake specialists; the number check with an answer that contains a figure not in the report |
| Frontend data-shaping helpers in `web/lib` | Direct call |
| How `LineView` lays out each kind of part (task 3.1.4) | `renderToStaticMarkup` of the component with a Line written in the test, compared with the markup expected |
| The results page's components, `ResultsView` and `OptionSheets` (task 3.2.1, its "Done when" line) | `renderToStaticMarkup` of the component with a `ReportLines` sample written in the test (`web/tests/lib/report_samples.ts`): the words shown compared with the sample's lines, the controls by their attributes; their state (the switch on, a card stepped to) is checked on the dev server, and what it filters on is the helpers' direct call |
| The route line before the results page, `RunRoute` (task 3.10) | `renderToStaticMarkup` of the component with stations from `lib/thread.ts`: each station's control and its closed note, and the hint; opening one is checked on the dev server |
| The page's own lines in `web/lib/wording.ts` | The functions that fill them, by direct call; a line that repeats an API code's words compared with that code's message in `wording.py` by pytest, which reads the file |
| `make_checkpointer` in `api/checkpointer.py` (task 2.5.2) | Direct call inside a running event loop, with and without a database URL; the class of what it makes, which connects to nothing |
| The session sweep in `api/sweep.py` (task 2.5.2) | `sweep` and `swept` by direct call, on a SQLite saver on `tmp_path` whose checkpoints the test writes with `aput` at times it sets, and a time passed in; what is left read back through the saver's `alist` |
| The schema command, `write_schema` in `api/schema.py` | Written to a file on `tmp_path`, compared with `/openapi.json` as the app built by `create_app` serves it |

**Project rules.**

- Fakes are passed in as parameters. The only things faked are the edges: external services, the
  model and the clock. Never fake code in this repo.
- The default run never touches a live service (see `docs/building_the_project.md`).
- Mirror the source layout under `tests/`.
