# Findings from task 1.9.9: LangSmith tracing of a frying pan run

Run on 2026-10-21 with the terminal app,
`uv run python -m shopper.cli --skip-all "I need a new frying pan, budget 50 euro"`, live
sources, timed with `Measure-Command`. Tracing went to the project `true-cost-copilot` on the EU
region (`eu.api.smith.langchain.com`). The traces were read back with the LangSmith client.

## The EU endpoint and the key

The first traced run used a key from an org on the US region. The EU endpoint refused every
upload with `403 Forbidden`, logged on the error stream. The run itself finished and printed
its report, so a failed upload does not break the app. With a key from an org created on
`eu.smith.langchain.com` the uploads went through. A key works on its own region only: the EU
key gets 403 from the US endpoint.

## What a trace holds

Two traced runs, each with the brief already cached. Each run is one trace, rooted at the
`session` run that `tracing.py` opens:

- Under `session` are two `LangGraph` runs: the start up to the pause, and the resume.
- Each of the seven graph nodes that ran (`parse_request`, `brief`, `interview`, `tco`, `lca`,
  `second_hand`, `assemble_report`) is a run under its `LangGraph` run.
- `interview` appears twice. The first run is marked as an error, `GraphInterrupt`: that is
  LangGraph's pause, not a failure. The second, at the resume, is clean.
- Every model call is an `llm` run named `nebius_chat`, a child of its node.
- Each `nebius_chat` run has the tier (metadata `tier`), the model ID (`ls_model_name`), the
  messages, `max_tokens`, `timeout`, `response_format`, `temperature` when one is set,
  `extra_body` when one is built, the reply and the prompt, completion and total tokens. The
  reply includes the model's reasoning (`reasoning_content`, 8,271 characters on one call),
  which shows why a call decided what it did.

After these two runs, three things were added so a trace reads without opening each run: a
model call's run is named after the schema it asks for (`nebius_chat · Shortlist`, `nebius_chat ·
PriceReading`), it is tagged with its tier and `full-reasoning` or `little-reasoning`, and the
`session` run's output is the printed report.

| Trace | Runs | Model calls | Session run |
|---|---|---|---|
| First | 22 | 10 | 178.6 s |
| Second | 29 | 17 | 191.2 s |

The second trace has more calls because its option research ran more price and findings reads.

## The reasoning settings arrive as built

Every model call in the two traces, by node and tier:

| Node | Tier | `extra_body` | `temperature` | Expected (`models.md`) |
|---|---|---|---|---|
| `parse_request` | small | none | 0 | full reasoning, temperature 0 |
| `brief` (stated answers; the rest was cached) | medium | `chat_template_kwargs: {enable_thinking: true, low_effort: true}` | none | little reasoning |
| `tco`, shortlist and evidence reads | medium | none | none | full reasoning |
| `tco`, price and findings reads | medium | `chat_template_kwargs: {enable_thinking: true, low_effort: true}` | none | little reasoning |
| `lca` | large | none | none | full reasoning |

The `low_effort` request body is `LOW_EFFORT_REQUEST` from `config.py`, unchanged, on exactly
the calls that ask for it. No call that reasons in full carries it. The offline test
`test_a_low_effort_call_sends_and_traces_the_reasoning_settings` (`tests/test_tracing.py`)
checks the same body through an injected `httpx` transport, so the left-over item from task
1.7.2 is closed.

## The latency tracing adds

| Run | Tracing | Time |
|---|---|---|
| 1 | on | 183.1 s |
| 2 | off | 246.2 s |
| 3 | on | 195.3 s |

All three runs came after the same uncached run, so the brief came from the cache in each. The
untraced run was the slowest. The time the model calls take varies by more than a minute from
run to run, so these wall times cannot show what tracing costs during the run, where the
uploads go out on a background thread.

What can be measured is the end of a run. The process ran 4.1 to 4.5 s longer than its
`session` run. Starting the app takes 2.0 s (`import shopper.cli`, three runs). So the upload
of the last runs at exit, `client.flush()` in `tracing.py`, costs at most about 2 to 2.5 s; that
figure includes shutting the interpreter down.
