# Models

Read this when choosing which model a component uses, changing the model client, or working on
cost or latency.

- [Tiers](#tiers)
- [Which component uses which tier](#which-component-uses-which-tier)
- [Rules](#rules)
- [The client](#the-client)

## Tiers

Nebius Token Factory, OpenAI-compatible API:
`https://api.tokenfactory.us-central1.nebius.com/v1/`. Key: `NEBIUS_TOKEN_FACTORY`.

Three tiers. IDs and prices are from Nebius's Nemotron page as read on 2026-10-04. For
LangSmith to show a traced call's cost, the same prices are entered for the three IDs under
Settings → Model pricing in LangSmith; change both together.

| Tier | Model | ID | Price per 1M tokens (in / out) |
|---|---|---|---|
| small | Nemotron 3 Nano | `nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B` | $0.06 / $0.24 |
| medium | Nemotron 3 Super | `nvidia/nemotron-3-super-120b-a12b` | $0.30 / $0.90 |
| large | Nemotron 3 Ultra | `nvidia/Nemotron-3-Ultra-550b-a55b` | $1.00 / $3.00 |

These are the defaults. `NEBIUS_MODEL_SMALL`, `NEBIUS_MODEL_MEDIUM` and `NEBIUS_MODEL_LARGE`
override them, read once when the settings load; empty means the default (`model_ids` in
`config.py`). The request, the trail's "which tier ran" entry and the traces all take the ID from
`MODEL_IDS`, and a stored brief's version holds it, so a swap does not reuse old briefs.

**From 9 November 2026 the demo runs on the replacements.** Nebius removes Nano and Super from
Token Factory Serverless that day, with no rerouting
([deprecations](https://docs.tokenfactory.nebius.com/model-deprecations-november-2026)); Ultra stays.
The recommended replacements are `nvidia/Nemotron-3_5-Lightning` for small and
`nvidia/Nemotron-3.5-Super-VL` for medium. LangSmith's model pricing needs the new IDs then. The
defaults stay on the current models, as the submission and its findings were made on them. How the
deployed endpoint swaps: `building_the_project.md`, "Deployment". Not yet tested: the supervisor
eval and a fixture frying-pan run on both, checking `max_completion_tokens` (Super VL counts
reasoning tokens inside it) and that `chat_template_kwargs` `low_effort` is honoured.

## Which component uses which tier

| Component | Job | Tier |
|---|---|---|
| Supervisor | Parse the request into fields and classify its scope; the same for the product name at a pasted link | small |
| Brief agent, research | Turn search results into sourced decision factors | medium, with little reasoning (task 1.7.2; `docs/findings/task_1.7.2.md`) |
| Brief agent, questions | Phrase a question per factor and pick the usage frequencies | medium (moved up in task 1.7; `docs/findings/task_1.7.md`) |
| Brief agent, stated answers | Pick out the requirements the request already states, once per request | medium, with little reasoning (moved up in task 1.7.2; `docs/findings/task_1.7.2.md`) |
| Brief agent, the reply | Read what the user's reply to the questions says, once per reply, before the graph resumes (task 2.5.5) | medium, with little reasoning: the stated-answers call on other words (not yet measured live) |
| Brief agent, local category term | Give the word shops in the Netherlands use for the category, which option research searches with, once per category and stored with the brief (task 1.13) | medium, reasoning in full (task 1.12: the small tier gave the hand-written term in none of six answers, `docs/findings/task_1.12.md`) |
| Product-page extraction | Pull materials and weight from page text | small |
| TCO analyzer | Judge the candidates' durability from their listed names, then from their product pages; read what each product page sells and the amounts it states (task 1.13); read durability evidence and recurring costs (task 1.8.3); read what testers and owners report (task 1.8.4) | medium; the two judgements and the evidence read reason in full (the judgements as decided in task 1.12, `docs/findings/task_1.12.md`; with little reasoning the shortlist they replace kept 5 hints on 15 candidates, `docs/findings/task_1.8.2.md`), the page reads and the findings read reason little (the page read is the price read of task 1.8.2 with more fields; the findings read's full reasoning added no correct finding, `docs/findings/task_1.8.4.md`) |
| LCA tier 1 | Decide whether a found report is about this product | medium |
| LCA tier 2 | Identify materials and weights; the multiplication is code | medium |
| LCA tier 3 | Estimate from materials when nothing else exists: one call for every option, returning factors and masses (ADR 0006) | large, reasoning in full; `low_effort` was not honoured on the large model, and the call has its own limits and a time cap on the whole estimate (task 1.9.7; `docs/findings/task_1.9.7.md`) |
| Second-hand agent | Filter spam, parts-only and other products (search terms are the option's name, from code) | small |
| Conversation agent, classify | Decide the kind of message and extract the change it asks for | small |
| Conversation agent, answer | Write the reply from the report and the results | medium |
| Report assembly and all math | Plain code | none |

## Rules

- **All model IDs live in `src/shopper/config.py`**, mapped to the three tiers, and nowhere else.
  Agents ask for a tier, not a model name.
- **The large tier runs only for LCA tier 3**, that is, only when tiers 1 and 2 both failed for an
  option. It is the most expensive call by far; never use it for parsing, filtering or phrasing.
- **Use the smallest tier that does the job.** Move a component up a tier only with evidence
  from the test transcripts that the smaller one fails, and note the reason here.
- **Structured output is required.** Each tier must return output that validates against a
  schema. Every model did in task 1.2 (`docs/findings/task_1.2.md`); use `complete_structured` rather than
  parsing free text.
- **Set a timeout on every call.** A timeout becomes a warning in the report, not an exception.
  The supervisor's parsing call is the exception: no report can exist without a request, so its
  failure is an error (see `supervisor.md`).
- **Record which tier ran** in the evidence trail entry, so the report shows what each model did.
- **The questions reach the user within 12 seconds for a cached category and 30 seconds for an
  uncached one**, from pressing Enter, measured with `Measure-Command` around a `--skip-all` run
  of the terminal app, with at least five researched factors and four phrased questions for each
  tuned category. The developer set these in task 1.7.2, where the cached runs took 5.8 to 10.7 s
  and the uncached ones 21.7 to 27.6 s (`docs/findings/task_1.7.2.md`). What is left of a cached
  run is starting the app and the supervisor's call, which reasons in full on the small tier.
  The supervisor evaluation failed once on the small tier in that task, on the category of "a 3d
  printer for a beginner"; the medium tier missed the same case and misread scopes as well.
- **Little reasoning where it holds up.** The brief agent's read and its stated-answers call ask
  for little reasoning (`low_effort`); the phrasing call and the supervisor reason in full,
  because with little reasoning the phrasing's choices failed the checks and the supervisor
  misread scopes (`docs/findings/task_1.7.2.md`). Run the supervisor evaluation before changing
  the supervisor's tier or reasoning.
- **Give a call room to reason.** The reasoning counts toward `max_tokens`. A call that reads
  many search results passes its own limit and timeout (`BRIEF_MAX_TOKENS`,
  `BRIEF_TIMEOUT_SECONDS` in `config.py`); the defaults cut its answer off. The LCA tier 3 call
  does the same (`LCA_MAX_TOKENS`, `LCA_TIMEOUT_SECONDS`, set from a timed probe), and
  `LCA_TIME_CAP_SECONDS` caps the whole estimate, its retry included.

## The client

`src/shopper/llm.py`. `complete(chat, tier, prompt)` returns text;
`complete_structured(chat, tier, prompt, schema)` returns an instance of the pydantic schema and
does the one retry with the validation error described in `agents.md` ("Agent contract"). Both return a
`Completion` (value, tier, model ID) or an `LlmFailure` (`timeout`, `error` or `invalid_output`);
they do not raise for a service failure. A request that times out is sent once more:
`nebius_chat` sets the `openai` client's `max_retries` to 1, which retries a timeout, a
connection error, a rate limit and a server error once, each try with the request's full timeout,
so a `timeout` failure has waited twice that long (checked with a fake transport in task 1.11;
`tests/test_llm.py`). A request may ask for little reasoning
(`low_effort`): `nebius_chat` then sends `LOW_EFFORT_REQUEST` from `config.py`, Nemotron 3 Super's
low-effort mode, which Nebius honours (`docs/findings/task_1.7.2.md`); the small tier's model has
no such mode. A request may carry a temperature; the supervisor uses 0
(`supervisor.md`, "What code does and what the model does"), and the others leave it unset, so
Nebius uses 1.0, as the model cards recommend. The extracting reads (the brief's read, the
product-page read and the evidence read) were measured at 0 against that default in task 1.14:
no read changed less often at 0, and the evidence read gave lifespan estimates of one year for
a steel pan and a drill (`docs/findings/task_1.14.md`). The Nebius API and the Nemotron models accept
a temperature (checked by hand on 2026-10-11). Temperature 0 does not give the same answer every
time (`docs/findings/task_1.5.md`). `chat` is the `ChatModel` callable: `nebius_chat(api_key)`
in production, a fake in tests. `nebius_chat` wraps the `openai` client for LangSmith, so with
tracing on each call is a child run of its graph node with its tier, model ID, request
arguments, reply (the reasoning included) and tokens. The run is named after the schema the call
asks for (`nebius_chat · NamesJudged`) and tagged with its tier and `full-reasoning` or
`little-reasoning` (`tracing.py`, task 1.9.9).
