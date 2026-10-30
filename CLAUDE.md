# True Cost Copilot

Sustainable shopping assistant. Hackathon project (Nebius x NVIDIA, "Best Apps and Agents"
track), solo developer, three-week build.

## Why

Cheap products often cost more over time, in money and in environmental impact, but shoppers only
see the sticker price. This app shows the real cost of a purchase and a better option that still
fits the user's budget. It is wallet first and never preachy: sustainability is the bonus of the
better-value choice, not a guilt trip.

## What

A user pastes a product link or types a need ("I need a new frying pan, budget €50"). The app
first asks a few questions about what matters for that product, then returns cost per year and
per use, a 10-year comparison against cheap replacements, and used alternatives from eBay within
budget. After the report the user can keep talking to it: ask why, try a what-if, or push back,
and the agents rework the result. Any durable product except a motor vehicle is accepted; cookware, small appliances and tools are the tuned
categories. Netherlands first, EU overall, EUR. Details: `docs/product.md`.

Stack: Python (LangGraph agents, FastAPI) in `src/shopper/` and a Next.js frontend in `web/`.
Models run on Nebius Token Factory.

## How

1. Open `docs/ROADMAP.md` and take the first task. One task per session unless told
   otherwise.
2. Read the docs named on that task's "Read" line, and nothing else up front.
3. Do the work, verify it as `docs/building_the_project.md` describes, tick the box, move the task to
   `docs/ROADMAP_DONE.md`, commit.

The `/task <number>` command runs this procedure for one task (`.claude/commands/task.md`).
Subagents in `.claude/agents/`: `task-verifier` (before ticking a task), `lca-reviewer` (any
CO2e or lifespan change), `docs-researcher` (unfamiliar library or API).
If a task is wrong or too large, update the roadmap instead of deviating.

## Commands and quirks

Full list, and which ones work today, in `docs/building_the_project.md`.

- Test: `uv run pytest` (offline, no keys, no credits). Live services: `uv run pytest -m live`,
  only when asked, because it spends free-tier credits.
- Lint and format: `uv run ruff check`, `uv run ruff format`.
- Run: `uv run python -m shopper.terminal.cli "<input>"`.
- **Windows machine.** Commands must work in PowerShell; no bash-only scripts.
- Environment variables are read only through `src/shopper/config.py`.
- One branch and one pull request per task; never commit task work straight to `main`. Flow and
  naming are in `docs/building_the_project.md` ("Git"). `/task` follows it.
- Model IDs and which component uses which tier are in `docs/architecture/models.md`.
  The large model runs only for LCA tier 3.
- The repo's parent folder holds private planning notes. Never copy them into the repo.

## Where to find things

Do not read these in advance. Open one when its trigger applies.

| Doc | Open it when |
|---|---|
| `docs/ROADMAP.md` | Starting a session; choosing what to do. Holds only the tasks still to do |
| `docs/ROADMAP_OPTIONAL.md` | The submission is done, or a task names an optional layer |
| `docs/ROADMAP_DONE.md` | You need what a finished task promised |
| `GLOSSARY.md` | Naming a model, field, function or UI label; a word seems to mean two things |
| `docs/adr/` | About to change something that looks odd on purpose (currently: euro only; fixed-rate conversion for recurring costs only; the research loop is driven by code, not by model tool calls; options come from comparison sites' listing pages, priced on their own product pages (superseding Firecrawl confirming shop prices); a finding shows a summary, never its quote; LCA tier 3 returns factors and code multiplies; the API sends the page finished lines, made of parts; fixed wording lives in code, not in the doc) |
| `docs/building_the_project.md` | Setting up, running, testing, adding a dependency, committing, deploying |
| `docs/code_conventions.md` | Writing or reviewing Python or Next.js code |
| `docs/product.md` | Writing a prompt, UI copy, the report layout, the README or the demo |
| `DESIGN.md` | Any change under `web/`: the visual world's tokens, type, components and motion |
| `docs/design/chat_page_brief.md` | Designing or styling the chat page (task 3.1.3 and later passes): the job, modes, the box, anti-references |
| `docs/wording.md` | Writing or changing a caveat, a warning, a decline or any other message whose words are fixed (the words themselves are in `wording.py` and `web/lib/wording.ts`) |
| `docs/terminal_app.md` | Working on `cli.py` or `report_text.py`: the terminal app is a test tool and stays simple |
| `docs/eu_market.md` | Anything market-specific: EUR and prices, eBay marketplaces, search language, wording of environmental claims, guarantees, personal data |
| `docs/service_architecture.md` | You need the system map, the API surface, the repo layout, or the open decisions |
| `docs/architecture/agents.md` | Changing an agent, the graph, the schemas or the warning codes |
| `docs/architecture/sessions.md` | Working on the pause, `graph/sessions.py`, progress events, reading a saved session or the session errors |
| `docs/architecture/supervisor.md` | Working on how input becomes a request: scope, category, budget, corrections |
| `docs/architecture/models.md` | Choosing a model tier, changing the model client, or working on cost or latency |
| `docs/architecture/category_brief.md` | Working on the brief agent's research: decision factors, the local category term, a short brief |
| `docs/architecture/interview.md` | Working on the questions, the usage question, a pasted link's interview, or how answers shape results |
| `docs/architecture/reading_answers.md` | Working on how the request's stated requirements or the user's reply are read into answers |
| `docs/architecture/option_research.md` | Working on the TCO analyzer: candidates, prices, selection |
| `docs/architecture/option_evidence.md` | Working on what is read for each chosen option: lifespan, durability evidence, recurring cost, factor values, findings |
| `docs/architecture/calculations.md` | Working in `calc/` or displaying any number |
| `docs/architecture/lca.md` | Working on CO2e estimates or their reference data |
| `docs/architecture/data_sources.md` | Calling Tavily, eBay or Firecrawl; caching; fixtures |
| `docs/architecture/conversation.md` | Working on the chat after the report: message kinds, reruns, report versions |
| `docs/architecture/agent_diagrams.md` | An agent's steps change: redraw its figure there (figures for people, linked from the README; no task needs to read it) |
| `docs/findings/` | You need what a live run measured: credits, latency, tokens, what a model got right. One file per task; a task that measures writes its own |

## Rules that always apply

1. Numbers shown to the user are computed in code (`src/shopper/calc/`), never by a model.
2. No scrapers and no new external services without asking.
3. Every environmental figure carries its source and confidence label; unknown stays unknown.
4. No moralising language and no generic environmental claims ("eco-friendly", "green",
   "sustainable") in prompts or UI copy; state the specific, sourced figure instead.
5. Secrets live in `.env`. Never print, log or commit them.
6. When code and a doc disagree, fix the doc in the same commit.
