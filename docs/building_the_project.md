# Building the project

Read this when setting up the environment, running or testing anything, adding a dependency,
committing, or deploying.

**Status:** the Python project is scaffolded (task 1.1), the model client exists (task 1.2) and the domain models exist (task 1.3):
`uv sync`, the tests, lint, format and model-check commands work today. The terminal app runs
end to end since task 1.5.2: it asks the questions and prints the report, on stub agents until
the real ones exist (`docs/terminal_app.md`). The API runs since task 2.5.3, and the frontend
in `web/` since task 3.1.1. When a command here is wrong or
missing, fix this file in the same commit: it must always describe what works today.

- [Machine](#machine)
- [Environment variables](#environment-variables)
- [Commands](#commands)
- [Verifying a task](#verifying-a-task)
- [Tests: offline and live](#tests-offline-and-live)
- [Dependencies](#dependencies)
- [Git](#git)
- [Deployment](#deployment)
- [Keeping the docs true](#keeping-the-docs-true)

## Machine

- Development is on **Windows**. Commands must work in PowerShell; do not add bash-only scripts.
  Put repeatable tasks in `pyproject.toml` scripts or `package.json` scripts instead.
- `uv` keeps the project's virtual environment in `.venv/` (git-ignored) and creates it on the
  first `uv sync` or `uv run`. Do not install packages into the global Python.
- The repo's parent folder holds private planning notes. Never move or copy them into the repo.

| Tool | Needed from | For |
|---|---|---|
| Python 3.12 or newer, and `uv` | Task 1.1 | Backend, agents, tests |
| `gh` (GitHub CLI) | Task 1.1 | Push, pull requests, checks |
| Node.js LTS and npm | Task 3.1.1 | Next.js frontend |
| WSL (Ubuntu) with the `nebius` CLI | Task 3.5 | The endpoint ("Deployment") |

## Environment variables

Real values live in `.env` (git-ignored). `.env.example` lists the same names with empty values
and must be updated whenever a name is added. Read them only through `src/shopper/config.py`.

| Name | Service | Needed from |
|---|---|---|
| `NEBIUS_TOKEN_FACTORY` | Nebius Token Factory | Task 1.2 |
| `NEBIUS_MODEL_SMALL`, `NEBIUS_MODEL_MEDIUM`, `NEBIUS_MODEL_LARGE` | A tier's model, overriding the default in `config.py`; optional (`architecture/models.md`, "Tiers") | Task 3.10 |
| `TAVILY_API_KEY` | Tavily | Task 1.6: the terminal app needs it with live sources |
| `FIRECRAWL_API_KEY` | Firecrawl | Task 1.6: the terminal app needs it with live sources |
| `EBAY_CLIENT_ID`, `EBAY_CLIENT_SECRET` | eBay Browse API | Task 2.2 |
| `SHOPPER_SOURCES` | `live` (the default) or `fixtures`: real services or the recorded responses in `tests/fixtures/` | Task 1.6 |
| `SHOPPER_AGENTS` | `real` (the default) or `stubs`: the API on the stub agents (`agents/stubs.py`), so a run spends one supervisor model call and no search or page credits. A pasted link is still read: with live sources a readable page costs a page credit and a model call, so pair it with `SHOPPER_SOURCES=fixtures` | Task 3.1.1 |
| `TAVILY_DAILY_CREDIT_LIMIT` | The daily ceiling on Tavily credits; 100 when not set | Task 1.6 |
| `LANGSMITH_TRACING` | `true` traces a terminal-app run, or each run of the API, in LangSmith; off when not set or `false` | Task 1.9.9 |
| `LANGSMITH_API_KEY` | LangSmith, an org on the EU region (`eu.smith.langchain.com`); needed only with tracing on | Task 1.9.9 |
| `LANGSMITH_PROJECT` | The LangSmith project the traces go to; `true-cost-copilot` when not set | Task 1.9.9 |
| `DATABASE_URL` | A Postgres database the API saves its sessions in (`AsyncPostgresSaver`); the SQLite file `.cache/sessions.sqlite` when not set, which the deployment uses (task 3.5) | Task 2.5.2 |
| `SESSIONS_PER_IP_PER_HOUR` | The sessions one client IP may start in an hour; 30 when not set | Task 2.5.2 |
| `SESSIONS_PER_DAY` | The sessions all clients together may start in 24 hours; 100 when not set | Task 3.5 |
| `TRUSTED_PROXY_HOPS` | The proxies in front of the API that each append to `X-Forwarded-For`, so the limit per IP reads the client's address; 0 (the connection's own address) when not set | Task 2.5.2 |
| `FRONTEND_ORIGINS` | The origins whose pages may call the API (CORS), comma-separated; `http://localhost:3000`, the Next.js dev server, when not set | Task 2.5.4 |

Never print, log or commit a value. If a key is missing, fail with a message that names the
variable, not its value.

The frontend reads one setting of its own, from `web/.env.local` (git-ignored) or the
environment at build time: `NEXT_PUBLIC_API_URL`, the API's address, `http://localhost:8000`
when not set (`web/lib/api/client.ts`). It holds no secret: the browser sees it.

LangSmith gets its settings from `config.py` through `tracing.py`, which sets them on every
run, tracing off included: it never reads `LANGSMITH_*` from the environment on its own, and
no test is traced (`tests/conftest.py`). The EU endpoint is fixed in `config.py`.

## Commands

| To | Run |
|---|---|
| Install or update Python deps | `uv sync` |
| Run the tests | `uv run pytest` |
| Lint | `uv run ruff check` |
| Format | `uv run ruff format` |
| Check the model tiers live (spends credits) | `uv run python -m shopper.checks.check_models`, add `--compare` for the small-tier comparison |
| Run the supervisor evaluation live (spends credits) | `uv run pytest -m live tests/eval`, add `--supervisor-tier medium` to run it on the medium tier |
| Check the web search and the page fetch live (3 credits) | `uv run python -m shopper.checks.check_sources "<product page URL>"` |
| Run the terminal app | `uv run python -m shopper.terminal.cli "I need a new frying pan, budget 50 euro"`; add `--skip-all` before the text to answer no questions |
| Read the newest traced runs (the LangSmith CLI, installed separately; no credits) | `langsmith trace list --project true-cost-copilot --limit 5 --show-hierarchy`; one trace with `langsmith trace get <trace-id> --project true-cost-copilot --full`; the model calls with their time, tokens and cost with `langsmith run list --project true-cost-copilot --run-type llm --include-metadata`. Add `--api-url https://eu.api.smith.langchain.com` unless `langsmith auth login` was given the EU endpoint |
| Run the API locally | `uv run uvicorn shopper.api.main:app_from_env --factory --workers 1 --no-access-log`; one worker, since the sessions, the cache and the running list are per process, and no access log, which would hold every request's path and client address. `SHOPPER_SOURCES=fixtures` runs it on the recorded searches and pages |
| Run the API on the stub agents and the recorded sources (one supervisor model call per start) | In PowerShell, `$env:SHOPPER_AGENTS = "stubs"; $env:SHOPPER_SOURCES = "fixtures"`, then the command above. The recorded blocked page, `https://example.org/shop/blocked`, gives an unreadable link |
| Write the API's OpenAPI schema to a file (no server, no keys) | `uv run python -m shopper.api.schema web/lib/api/openapi.json` |
| Install the frontend's deps (from `web/`) | `npm install` (`npm ci` in CI) |
| Run the frontend (from `web/`) | `npm run dev`, on `http://localhost:3000`, which the API lets call it by default |
| Lint and check the formatting of the frontend (from `web/`) | `npm run lint` (ESLint, then `prettier --check`); `npm run format` formats |
| Typecheck the frontend (from `web/`) | `npm run typecheck` (`next typegen`, then `tsc --noEmit`) |
| Test the frontend's helpers (from `web/`) | `npm test` (Vitest, offline) |
| Build the frontend (from `web/`) | `npm run build` |
| Write the schema and the frontend's types again after an API change (from `web/`) | `npm run generate`; commit both files in `web/lib/api/` |

## Verifying a task

A task is done when all of these hold:

1. Its "Done when" line in `docs/ROADMAP.md` is true, shown by a command and its output, not by
   reading the code.
2. `uv run pytest` and `uv run ruff check` pass.
3. New behaviour has a test.
4. Any doc the change made untrue is corrected.
5. The checkbox is ticked and the task moved to `docs/ROADMAP_DONE.md` on the task's branch, so
   both reach `main` with the pull request.
6. The pull request's checks pass.
7. A task that changed `web/` passes the visual check: the pages it touched, open on the dev
   server in the browser at 390 px and 1280 px wide, have no layout fault, no console error and
   no failed request, and `impeccable detect` on each page's URL at both widths
   (`--viewport 390x844` and `--viewport 1280x800`) reports no finding; advisories do not
   count. No screenshot script and no Playwright. `/task` runs this check.

If the "Done when" line cannot be met, stop and say why. Do not tick the box and do not weaken
the line.

## Tests: offline and live

- The default run (`uv run pytest`) is fully offline: fake tools, recorded fixtures in
  `tests/fixtures/`, no API keys needed, no credits spent.
- Tests that call a real service are marked `live` and run only on request:
  `uv run pytest -m live`. Keep them few; each one spends credits.
- When a live response is useful as a fixture, record it once and strip anything personal or
  secret before committing.
- End-to-end transcripts for the tone pass go in `tests/transcripts/`.

## Dependencies

- Add with `uv add <package>` (or `uv add --dev` for tooling) so `pyproject.toml` and the lock
  file stay in step. For the frontend, `npm install <package>` inside `web/`.
- Prefer the standard library and what is already installed. Ask before adding a framework or
  anything with a large footprint.
- `langsmith` comes with `langgraph` and is not declared on its own; `tracing.py` and `llm.py`
  import it (task 1.9.9).

## Git

One branch and one pull request per roadmap task. `main` only changes through a merged pull
request, with the one exception below.

**Per task**

1. Start from a clean, current `main`: `git switch main`, `git pull`. If the working tree has
   uncommitted changes, or an earlier task's pull request is still open, stop and say so.
2. Create the branch: `task/<number>-<short-name>`, e.g. `task/1.4-horizon-math`.
3. Commit on the branch as often as is useful. Messages start with the task number, e.g.
   `1.4: cost-per-year and horizon math`.
4. Tick the task's roadmap box and move the task to `docs/ROADMAP_DONE.md` on the branch, so
   both arrive on `main` with the merge.
5. Push the branch and open the pull request with `gh pr create`. Title: the task number and
   title. Body: the "Done when" line, the command output that proves it, the verifier's verdict,
   and anything left open.
6. Wait for the checks: `gh pr checks --watch`. If one fails, fix it on the branch and push.
7. **Do not merge.** Report the pull request link and stop. The developer merges, or says to.
8. When told to merge: `gh pr merge --squash --delete-branch`, then `git switch main` and
   `git pull`. Squash, so each task is one commit on `main`.

**Exception: planning edits.** Changes only to `CLAUDE.md`, `GLOSSARY.md`, `docs/` or `.claude/` that are made
outside a task (planning, decisions, roadmap updates) may be committed straight to `main` with a
message starting `docs:`. Code never takes this route.

**Checks on every pull request.** GitHub Actions runs `uv run ruff check` and `uv run pytest`
(the offline run; no secrets are available to it, and none are needed); for `web/`, `npm ci`,
lint, typecheck, test and build; and a check that `npm run generate` leaves the committed schema
and types unchanged. A pull request with a failing check is not ready, whatever the local run
said.

**Always**

- Before each commit, check that `.env` and any cache or database file are not staged.
- `.gitignore` must cover `.env`, virtual environments, caches, the page cache, SQLite files,
  `node_modules` and build output.
- Line endings are normalised to LF by `.gitattributes`. A file that shows as changed with no
  visible difference is a line-ending problem; fix the setting, do not commit the churn.
- Never force-push `main`, and never rewrite its history.

## Deployment

| What | Where | Address |
|---|---|---|
| FastAPI backend | Nebius Serverless Endpoint `truecost-unboxed-api`, project region `eu-west2`, `cpu-d3` `2vcpu-8gb`, 20 GiB disk | `https://port8080-cq1kfp68n2g43g0.tunnel.applications.eu-west2.nebius.cloud` |
| Next.js frontend | Vercel Hobby project `truecost-unboxed`, deployed with its CLI (no Git connection) | `https://truecost-unboxed.vercel.app` |
| Image | Private GHCR, built by `.github/workflows/deploy.yml` | `ghcr.io/nd-code-ai/hackathon-app-sustainable-shopper:latest` |

Secrets live in SecretStash (`nebius mysterybox`), never in an image or a commit. The endpoint
holds no volume: a stop or restart loses its disk, so the sessions, the cache and the credit
ledger, and the counts of the limits, which are in memory. The deployed app traces in LangSmith,
with the notice `eu_market.md` ("Personal data") asks for.

**When it runs.** Up on 2026-10-30 until 21:00 CET, then stopped. Started on 2026-11-30, because
the rules give the judging as 9 to 23 December and the organiser on Discord as 1 to 15 December,
and stopped on 2026-12-23 at 12:00 PT (21:00 CET), which also ends the tracing. The README states
this window, and so must the Devpost testing instructions. Nothing starts or stops it on its own.
The registry token must outlive 23 December.

**The CLI** runs in WSL (documented for Ubuntu and macOS only), installed with the script from
`docs.nebius.com/cli/install`. From PowerShell, use `--exec`: `wsl --` runs the command through a
shell first, which strips the quotes from JSON. `bash -ic` is what puts `nebius` on the path.

**Stop, and start again** (the start takes about 4 minutes; the URL stays the same, measured in
task 3.5):

```powershell
wsl -d Ubuntu --exec bash -ic "nebius ai endpoint stop --id aiendpoint-e04dhqmp5f014nmf91"
wsl -d Ubuntu --exec bash -ic "nebius ai endpoint start --id aiendpoint-e04dhqmp5f014nmf91"
```

After a start the cache is empty, so run the three examples on the page once (about $0.25 and up
to about 50 Tavily credits), one of them from a phone.

**A redeploy of the backend** keeps the URL: run the workflow (`gh workflow run deploy.yml`), wait
for it, then the same command as above with `restart`, which pulls the tag again and empties the
disk. **A redeploy of the frontend**, from `web/`: `npx vercel --prod --yes`. `vercel link` also
adds lines to `web/.gitignore` and writes a `web/.env.local` holding only a token; neither is
needed.

**A changed setting** means a new endpoint, since settings cannot change after creation, and so a
new URL: delete it, create it again as below, then in `web/` run `npx vercel env add
NEXT_PUBLIC_API_URL production --value <url> --yes --force` and deploy. `FRONTEND_ORIGINS` allows the
production domain only, so a preview deployment cannot call the API. Inside WSL (`wsl -d Ubuntu`):

```bash
nebius ai endpoint create --name truecost-unboxed-api --parent-id <project id> \
  --image ghcr.io/nd-code-ai/hackathon-app-sustainable-shopper:latest \
  --registry-secret true-cost-registry \
  --platform cpu-d3 --preset 2vcpu-8gb --disk-size 20Gi --container-port 8080 \
  --env LANGSMITH_TRACING=true --env TAVILY_DAILY_CREDIT_LIMIT=283 \
  --env SESSIONS_PER_IP_PER_HOUR=10 --env SESSIONS_PER_DAY=46 --env TRUSTED_PROXY_HOPS=1 \
  --env FRONTEND_ORIGINS=https://truecost-unboxed.vercel.app \
  --env-secret NEBIUS_TOKEN_FACTORY=true-cost-keys --env-secret TAVILY_API_KEY=true-cost-keys \
  --env-secret FIRECRAWL_API_KEY=true-cost-keys --env-secret LANGSMITH_API_KEY=true-cost-keys \
  --env-secret EBAY_CLIENT_ID=true-cost-keys --env-secret EBAY_CLIENT_SECRET=true-cost-keys
```

**The models' swap, by 9 November 2026** (`architecture/models.md`, "Tiers"). The endpoint receives
only the variables and secret keys named when it was created, and settings cannot change after that,
so `NEBIUS_MODEL_SMALL` and `NEBIUS_MODEL_MEDIUM` cannot reach it: adding them to the secret would
change nothing, and passing them would mean a new endpoint and a new URL. They are for a local run or
a new endpoint. On this endpoint the swap is a two-line change to `DEFAULT_MODEL_IDS` in `config.py`
and a redeploy of the backend, as above. Then re-warm the cache, as after any start.

**The secrets** are made once, in a terminal, with `scripts/nebius_secrets.py`, which reads the keys
from `.env` and asks for a classic GitHub token with only `read:packages`, checking it with GitHub
first. `--replace-registry <secret id>` stores a new token and leaves the keys alone.

**The numbers.** Worked for the 24 days of the window, with an 80% margin:
`SESSIONS_PER_DAY` = $114.60 of Token Factory credit × 0.8 ÷ (24 × $0.083 a session) = 46, and
`TAVILY_DAILY_CREDIT_LIMIT` = 8,504 credits × 0.8 ÷ 24 = 283. The endpoint itself, about $1.60 a
day, comes out of the separate Nebius AI cloud credit ($120.98). `TRUSTED_PROXY_HOPS` is 1 as
measured (`docs/findings/task_3.5.md`). No code ceiling for Firecrawl: its plan stops when its
credits run out, a known risk.

## Keeping the docs true

The docs are small on purpose and are read by task, not all at once. When code and a doc
disagree, the code is the fact: correct the doc in the same commit. When adding a new doc, add
its row to the table in `CLAUDE.md`, with a clear "when to read" trigger.
