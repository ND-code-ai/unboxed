# Findings from task 1.2: the models

Measured 2026-10-04. Re-run them with
`uv run python -m shopper.check_models` (one completion and one structured result per tier) and
`uv run python -m shopper.check_models --compare` (small-tier comparison). Both spend credits.

- **IDs confirmed.** All three tier IDs in `models.md`, and `nvidia/Nemotron-3_5-Lightning`, are listed by the
  `/models` endpoint and answer a chat completion.
- **Structured output works on every model.** All four accept
  `response_format: {"type": "json_schema", ...}` with a pydantic-generated schema and returned
  JSON that validated on the first try in every call made (three tiers: 1 of 1 each; Nano and
  Lightning: 16 of 16 each). That is a small sample, so the retry in `llm.py` stays. Without
  `response_format`, Nano wrapped its JSON in a Markdown code fence; `llm.py` strips one if
  present.
- **All four models reason before answering.** The reasoning arrives in a separate field
  (`reasoning` or `reasoning_content`), not in `content`, but it is billed as output tokens: a
  one-line JSON answer cost 90 to 540 completion tokens. `MODEL_MAX_TOKENS` in `config.py` leaves
  room for it; a low limit would cut the answer off.
- **Small tier: Nano.** Compared with Lightning on a request-parsing prompt (eight requests,
  English and Dutch, one URL, every scope; two rounds; budget and scope checked against expected
  values). Both were schema-valid and correct 16 of 16. Nano was about four times faster: median
  3.7 s against 15.9 s, slowest 5.3 s against 22.4 s, with the 16 calls sent at once. Lightning
  also spent more reasoning tokens at the same price. Latency decides it, because the questions
  must reach the user within a few seconds. Lightning's ID is kept in `config.py` as
  `SMALL_TIER_ALTERNATIVE` for re-running the comparison only.
- **Latency of one call**, same short prompt, one sample each: Nano 2 to 4 s, Super 1 s,
  Ultra 0.5 s. The larger tiers were not slower; the tier rules in `models.md` are about cost.
