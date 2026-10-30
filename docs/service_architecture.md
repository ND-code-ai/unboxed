# Service architecture

The map of the system. Read this when you need to know how the parts fit together, where a file
belongs, or what the API looks like. Detail on each part lives in `docs/architecture/`; open only
the file for the part you are changing.

| Part | File |
|---|---|
| Agents, graph, shared state, warning codes | `architecture/agents.md` |
| The pause, session functions, progress, saved sessions, session errors | `architecture/sessions.md` |
| Parsing the request: scope, category, budget, corrections | `architecture/supervisor.md` |
| Model tiers, the model client | `architecture/models.md` |
| Category brief: decision factors, research, the local term | `architecture/category_brief.md` |
| Interview questions, the usage question, how answers are used | `architecture/interview.md` |
| Answers in words: the request's stated answers, the reply | `architecture/reading_answers.md` |
| Option research: candidates, prices, selection | `architecture/option_research.md` |
| What is read for each chosen option: evidence, findings | `architecture/option_evidence.md` |
| Cost and impact formulas | `architecture/calculations.md` |
| Life-cycle estimates and their tiers | `architecture/lca.md` |
| Tavily, eBay, Firecrawl, caching, fixtures | `architecture/data_sources.md` |
| Conversation after the report: kinds of message, reruns, report versions | `architecture/conversation.md` |
| What a live run measured, one file per task | `findings/task_<number>.md` |

Market-specific rules (EUR, eBay marketplaces, EU claims and data rules) are in `eu_market.md`.

## Overview

```
Next.js (web/)  --HTTP-->  FastAPI (src/shopper/api)  -->  LangGraph graph
                                                            |- Supervisor
                                                            |- Brief agent    -> Tavily
                                                            |    (pause: user answers)
                                                            |- TCO analyzer   -> Tavily, eBay
                                                            |- LCA agent      -> Tavily, LCA data
                                                            |- Second-hand    -> eBay
                                                            |- calc/ (deterministic math)
                                                            `- Conversation agent
                                                                 (after the report: explain,
                                                                  what-if, or rerun specialists)
```

One session has two steps. First the supervisor parses the input and the brief agent returns
questions. After the user answers or skips, the other agents gather inputs (options, prices,
lifespans, materials, listings), `calc/` computes the numbers, and the supervisor assembles one
report object. The API returns it and the frontend renders it. After that, the session stays
open for a conversation: each message is answered from the report, recalculated, or turned into
a rerun that produces a new report version (`architecture/conversation.md`). `cli.py` runs the same graph from
the terminal, so the terminal app and the web app can never disagree.

## API surface

| Endpoint | Purpose |
|---|---|
| `POST /sessions` | Start: the input, one text that may hold a need, a product URL and a budget; there is no separate budget field. Runs the brief agent and streams the session id, the request as understood, progress per agent, then the session: any warnings so far and the questions, or the report for a request that does not run. A correction is a new session |
| `POST /sessions/{id}/answers` | The choices picked (`GivenAnswer`s), the user's reply in their own words, both or neither for "skip all". Reads the reply first, then resumes the graph; streams the reading's progress and what the reply gave, progress events per agent, then the report |
| `GET /sessions/{id}` | The session as it is now (`SessionView`): `running`, or as it is saved: `paused` with the questions, `finished` with the report, each with the lines of its event, or `interrupted` (final: the page offers to start again with the text kept, as "Edit" does). A client that lost its stream finds the session here |
| `POST /sessions/{id}/recalculate` | The complete assumptions (`RecalculateRequest`: horizon, uses per year, lifespan overrides), not a change to them. Returns a `Recalculation`: the assumptions used, the new comparison and evidence summary from `calc/`, and the lines of what they change (the evidence summary and the options). Runs no agent and saves nothing: the saved report keeps its own assumptions, and the page holds the current values |
| `POST /sessions/{id}/messages` | A chat message about the current report. Streams progress events for any rerun, then the answer; returns the new report version when there is one |
| `GET /sessions/{id}/versions/{n}` | A previous report version |
| `GET /health` | Liveness check for deployment, and `tracing`: whether the runs are traced, so the page shows its notice under the composer (nothing while it loads or when the call fails) |

The report schema is defined once in `src/shopper/state.py`. FastAPI publishes it as OpenAPI and
the frontend generates its types from that (`openapi-typescript`); do not hand-write a second copy.
`api/schema.py` writes the schema to `web/lib/api/openapi.json` with no server and no keys, and
`npm run generate` (in `web/`) writes it and the types; both files are committed, and CI checks
that writing them again changes neither.

**The contract.** `/openapi.json` names every model the frontend reads: `SessionView`, the
`StreamEvent` union, documented as each stream route's success under `text/event-stream`, and
`ApiError`, declared on each route for every status it can answer with, its description naming
the codes. Both unions are discriminated, by `status` and by `event`, and a model's schema as the
API sends it marks every field required, defaults included (`DomainModel` in `state.py`), so the
generated types narrow and need no check for a missing field. No model is sent both ways: the
answers route takes `AnswersRequest`, its choices picked as `GivenAnswer`s (`chosen` with a
choice or `not_sure` with none) and an optional `reply`, and the API sends `Answer`, which holds
what only code writes, such as `stated_in`. `StartRequest.input` and `AnswersRequest.reply`
publish the supervisor's `MAX_INPUT_CHARACTERS` as their `maxLength`, and in their description,
which the generated types carry as a comment (openapi-typescript writes no `maxLength` into a
type; the number itself is in `openapi.json`). It is documented and not enforced: a
longer text is refused with `input_too_long` or `reply_too_long`, not `invalid_request`.

**The app.** `create_app(chat, sources, checkpointer)` in `api/app.py` builds it. Its lifespan
opens the checkpointer, an async context manager such as `saved_sessions(path, database_url)`
(`api/checkpointer.py`), because a saver is made inside the running event loop; it then calls
`build_graph` once, and every route reuses the graph. `make_checkpointer` chooses the saver:
`AsyncPostgresSaver` when `DATABASE_URL` is set, otherwise `AsyncSqliteSaver` on the file, both
with the state's serde; the deployment uses the file (task 3.5; a volume for it is optional task
3.5.1). The lifespan then sweeps the
sessions (`api/sweep.py`): at startup and then hourly, a session is deleted 7 days
(`SESSION_RETENTION_DAYS`) after its newest checkpoint, through the saver's own `alist` and
`adelete_thread`, unless it is in the running list; a pass that fails is logged by its class and
`sweep_failed` only, and the next pass runs. `api/main.py` builds the app on the real model, the agents
`SHOPPER_AGENTS` chooses (the stubs call no model and no tool; the supervisor and a pasted link's
reading still run, so with live sources a readable link costs a page credit and a model call),
the sources
`SHOPPER_SOURCES` chooses, `SESSIONS_DATABASE`, the origins of `FRONTEND_ORIGINS` and the tracing
`LANGSMITH_TRACING` sets. CORS lets only pages on those origins call the API from a browser
(`GET` and `POST`, with a `content-type` header).

**The limit per client IP.** The deployment runs without endpoint auth, which a browser could not
hold a token for, so `POST /sessions` takes at most `SESSIONS_PER_IP_PER_HOUR` (30 by default)
sessions an hour from one client IP, beside the daily credit limit (`api/limits.py`). A session
counts once it is started, after the length check; a declined request counts, since it spends a
model call. The counts are kept in memory only, each start older than the hour cleared on every
check, and the IP is never saved, logged or put in a thread. `TRUSTED_PROXY_HOPS` (0 by default)
says how the IP is read: 0 uses the connection's own address; N uses the Nth `X-Forwarded-For`
entry from the right, which the nearest trusted proxy wrote, never an entry left of it, which the
client writes; with fewer entries than N, the connection's own address. Startup logs whether a
proxy is trusted, with no IP. On the Nebius endpoint the value is 1: its proxy replaces the header
with one entry, the client's address, and the connection's own address is private, so uvicorn
rewrites nothing (`docs/findings/task_3.5.md`).

**The ceiling per day.** Anyone with the URL can spend and model calls have no other cap, so
`POST /sessions` also takes at most `SESSIONS_PER_DAY` (100 by default) sessions from all clients
together in the last 24 hours, in memory too, so a restart clears it. A start refused by either
limit counts towards neither. Past it, 429 `too_many_sessions_today`.

**Runs.** Every run, a start's and an answers', is an `asyncio` task kept in the process's list of
running sessions (`api/runs.py`), never the response's own generator, so it finishes when its
client disconnects. The list is the lock per session: an answers request takes the session's slot
before it checks the saved state and the answers, and the run frees it when it ends. An answers
run calls `resume_with_reply` (`architecture/sessions.md`, "The pause") with the graph's model
client and agent bundle, which `Sessions` holds, so the reply is read inside the run, before the
graph resumes. The route
makes the session id, a random UUID used as the LangGraph thread id; a client never chooses it.
Each run sets its own LangSmith tracing context inside its task (`tracer` in `tracing.py`): with
tracing on, a start and its answers are a trace each, under the input and the answers as JSON;
off, nothing is traced even when the process environment asks LangSmith to.

**Streams.** Server-Sent Events, written by hand: the stream reads the run's events from a queue
and sends a `: keep-alive` comment when nothing came for 15 s (`KEEP_ALIVE_SECONDS`). Each event's
name is on its `event:` line and, as `event`, in its data, which is one model of the `StreamEvent`
union (`api/models.py`), with only its listed fields. A start sends `session_started` (the session id)
first, then `progress` (agent, status, step, `message` from `wording.py`) for the supervisor,
`understood` (the request, once it is known to run, and its line), `progress` for the brief agent,
and `session` (the `SessionStart` and its lines). An answers stream with a reply sends `progress` for the brief agent reading
it (step `reply`; every other progress event's step is `research`), then `reply_read`: what the
reply gave as data (its answers that count as `stated_answers`, the factors of the user's own it
adds, `asks_to_change_request`, and `answered_already` for a reply that changed no answer because
a choice or the request already answers all it answers), and its lines. Every answers stream
then sends `progress` per agent and `report` (the report and its lines).

**Lines.** Every line the page shows arrives with the data, built by `lines.py` and
`report_lines.py` from the line functions of `wording.py` as the API answers and never saved
(`docs/adr/0008-api-sends-finished-lines.md`). A `Line` is `{parts}`, each part tagged `kind`:
`text {text}`, `link {text, url}`, `confidence {text, basis}` (a figure's confidence label,
`basis` `published`, `benchmark` or `estimate`) or `control {key}`; the keys are a closed list,
today `edit`, whose words are the page's (`web/lib/wording.ts`). `understood.line` is the "Looking for"
line, ended by the `edit` control. `session.lines` is a `SessionLines`: `understood`; `declined`,
the decline or rephrase message of a request that does not run, which then has no `understood`;
`stated`, the "From your request" lines; `typical_costs`; and `sources`, the source line under each
researched question, by the question's id. The site in a source line and in a typical yearly cost
line is a link to its source. `reply_read.lines` are the "From your reply" lines, then at most one
line on what the reply changed (`wording.reply_in_thread`). `report.lines` is a
`ReportLines`: `declined`, which a declined report has alone; `evidence_summary`; `caveats`;
`warnings`, each a `WarningLine {code, option_id, line}`; `stated`; `typical_costs`; `options`, one
`OptionLines` per option in report order, whose every figure is a `FigureLine {label, value,
missing}` (`missing` when the value says why the figure is not there) and whose factor values are
`FactorFigure {factor_id, figure}`s; `check`, a `CheckLines {groups, confirm_price}` of
`CheckGroup {label, items}`s; and `trail`, each a `TrailLine {agent, by, line}`. A site in an
option block is a link to its source when that is a web address, and a CO2e label, a rough
estimate and an "estimated" are `confidence` parts. The page needs no numeric field of `Report`
to show a figure. The paused and finished views
of `GET /sessions/{id}` (`PausedSessionView`, `FinishedSessionView`) carry the lines of the
`session` and `report` events. The terminal app prints the same lines' text and leaves out the
controls.

**Errors.** A response that is not a success has the body `{code, message}`, the message from
`wording.py` (`ERRORS`). Before a stream starts: 404
`session_not_found` (an expired session too), 409 `session_running`, 409 `session_not_paused`, 422
`invalid_answers`, 422 `input_too_long` (over the supervisor's `MAX_INPUT_CHARACTERS`), 422
`reply_too_long` (a reply over the same limit, refused before the session's slot is taken), 429
`too_many_sessions` (a start over the limit per client IP; its message says in how many whole
minutes, rounded up, the oldest start counted leaves the hour), 429 `too_many_sessions_today` (a
start over the ceiling per day), 422 `invalid_request` for a body
FastAPI's own validation rejects (its `detail`, which quotes the input, is never sent), and 500
`internal_error` for anything unexpected, such as a database
error, answered by a guard around the app so nothing reaches the server's own error log. A
recalculation is refused with 422 `invalid_assumptions` for a value outside its bounds (horizon 1
to 30 years, uses per year 1 to 3,650, a lifespan 0.1 to 100 years, in `config.py`; published as
each field's `minimum` and `maximum` and not enforced by validation, so they are not
`invalid_request`), 404 `session_not_found`, 409 `no_report_yet` for a session that is paused or
interrupted (`SessionHasNoReportError`), 409 `no_options` for a report with none, a declined one
included, and 422 `unknown_option` for a lifespan set for an option the report does not have.
Once a stream has started, an `error` event. Two codes leave the session `interrupted`: `model_call_failed`
when the supervisor's model call fails, and `run_stopped` for anything unexpected. Two leave it
`paused`, nothing resumed, so it can be answered again: `reply_unread` when the reply's reading
fails (`ReplyUnreadError`, logged as agent `brief`), and `reply_unanswered` when no choice was
picked and the reply kept nothing, sent after `reply_read` and not logged; its second wording is
for a session that paused with no questions (`wording.reply_unanswered`).

**Logs.** No personal data: uvicorn runs with `--no-access-log`, and an error is logged as its
class, code, session id and agent (the last one that started and had not finished), never its
message or traceback, which can carry the input (`api/error_log.py`). aiosqlite logs each
statement with its parameters at debug level, the saved input among them, so its logger is kept
at info. A test runs a session to its report, a run that stops, a failed model call and refused
bodies with a marker in the input, and a reply to its report and one not read with the marker in
a kept and in a refused phrase, and finds it in no record at any level; another finds no client
IP in any record. Whether psycopg logs a statement's parameters, as aiosqlite does, is checked
before any deployment uses Postgres.

**One worker process** (`uvicorn --workers 1`): the SQLite file, the cache, the credit ledger, the
running list and the counts per client IP are each per process. Two runs at once can take a few credits past the daily
ceiling, because the ledger is checked before a search and added to after; accepted.

## Repo layout

```
README.md               pitch, setup, architecture (judges read this)
LICENSE                 MIT, chosen in task 3.7
CLAUDE.md               onboarding and pointers
pyproject.toml          Python deps (uv)
.env.example            key names without values
docs/                   see the table in CLAUDE.md
src/shopper/
  config.py             settings and model IDs per agent
  llm.py                OpenAI-compatible client for Nebius
  tracing.py            LangSmith tracing of a terminal-app session, off unless .env turns it on
  wording.py            every fixed message as a template, and Line, the
                        parts a finished line is made of
  lines.py              the lines of a session or a reply, which the API sends and the
                        terminal app prints (ADR 0008)
  report_lines.py       the lines of a report, by section and by option, every figure a label
                        and a value
  state.py              domain models (pydantic)
  graph/                the graph and the pure functions its nodes call
    graph.py            LangGraph wiring, the graph state built from the domain models, and a
                        run of the graph with its progress events
    sessions.py         the sessions it runs, each under its id: starting one, reading it or its
                        report back, checking a resume and resuming it with the answers or a reply
    interview.py        completing the answers (the reply's placed among them), uses per year
    report.py           assembling a report: caveats, check-before-you-buy list
  terminal/             the terminal app (docs/terminal_app.md)
    cli.py              terminal entry point
    report_text.py      the report as plain lines
  checks/               live checks, run by hand: check_models.py (the model tiers) and
                        check_sources.py (the web search and the page fetch)
  agents/               one package per agent: agent.py (the agent function), prompt.py and,
                        where it has them, models.py (its model schemas) and checks.py (its checks
                        on what the model wrote)
    supervisor/         parsing the input into a request
    linked_product/     the pasted link
    brief/              category research and the questions; usage_frequency.py holds the
                        usage frequencies and the question about how often the product is used,
                        stated.py what the request states, reply.py the reply's reader
    shared/             research.py, model_text.py and phrases.py (the research rules, the check
                        on what a model writes, and finding a phrase a model copied from a text)
    bundle.py           the four agent functions the graph runs and the reply's reader
    stubs.py            a stub of each; the API runs them all with SHOPPER_AGENTS=stubs
    default.py          the bundle the entry points run otherwise
                        (tco, lca and secondhand follow as packages of their own)
  tools/                Tavily search, Firecrawl page fetch, their fixture twins, the cache, the
                        brief store and the call limits and credit meter; marketplaces/ from the
                        eBay task
  calc/                 cost-per-year and 10-year impact math; display.py, how an amount and years
                        are rounded and written where they are shown
  data/                 lifespan and emission-factor reference tables
  api/                  FastAPI app: app.py (the app and its routes), runs.py (the runs and their
                        streams), models.py (bodies, stream events, the error body),
                        recalculation.py (a report recalculated), checkpointer.py (the saver
                        chosen and opened), sweep.py (deleting old sessions), limits.py (sessions
                        per client IP), main.py (what uvicorn runs), schema.py (writes the OpenAPI
                        schema to a file)
web/                    Next.js frontend (App Router, TypeScript strict)
  app/                  routes: page.tsx, the page; globals.css, the world's tokens in Tailwind's
                        theme (DESIGN.md)
  components/           UI: Thread.tsx (the chat thread's state and its calls, beside the box) and
                        presentational parts: the box (ProductBox), its labels, its turns, the
                        questions asked one at a time, a line's parts, the composer; ui/, the
                        shadcn/ui components, restyled through the tokens
  lib/                  helpers: thread.ts (the thread, its composer, the open question, the
                        labels and the box's state, a pure reducer),
                        follow.ts (what the API answered, as the reducer's results), lines.ts (how
                        a line's parts are laid out), sse.ts (reading a stream), wording.ts (the
                        page's own lines)
    api/                every call to the API: client.ts; openapi.json and schema.d.ts, generated
                        and committed; types.ts, names for the generated schemas; limits.ts, the
                        schema's caps on the input and the reply
  tests/                Vitest, mirrors lib/
scripts/                hand-run live checks and runs, not shipped; record_fixtures.py, which
                        records a search or a page as a fixture (task 1.13); nebius_secrets.py,
                        which puts the deployment's keys in SecretStash (task 3.5)
Dockerfile              the API's image, built by .github/workflows/deploy.yml (task 3.5); web/
                        vercel.json names the frontend's framework for its deploys
tests/                  mirrors src/; fixtures/ and transcripts/ inside
```

## Architecture rules

1. **Math is code, not prompts.** Agents extract inputs; `calc/` computes every number the user
   sees.
2. **Dependencies point inward.** `calc/` and `state.py` import nothing from `agents/`, `tools/`
   or `api/`. `wording.py` imports nothing from the package, so `calc/`, the agents and the entry
   points can all use it. Agents use tools; tools never call agents. `api/` and `cli.py` are thin entry points
   over the same graph and tools.
3. **Swappable edges.** Every external service sits behind an interface with a fixture-backed
   implementation, so the app and the tests run offline.
4. **Fail soft.** Unreadable link, eBay error or rate limit, model timeout: return a clear partial
   report that says what is missing, never a crash.
5. **The frontend holds no business logic** and does no cost or impact math.

## Open decisions

Ask before deciding any of these.

- The open questions listed at the end of `architecture/conversation.md`.
- Whether to use the EU energy label database for durability and energy-use evidence; access and
  coverage are unverified.
- The market questions listed at the end of `eu_market.md`.
- The open questions listed at the end of `architecture/calculations.md`.
