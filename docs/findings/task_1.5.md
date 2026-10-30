# Findings from task 1.5: the supervisor on the models

Measured 2026-10-11 with the supervisor's prompt and the evaluation in `tests/eval/`
(25 cases; `supervisor.md`, "Evaluation").

- **Temperature 0 does not give the same answer every time.** The same input, sent six times at
  temperature 0, came back with two or three different categories ("bicycle", "electric
  bicycle", "electric bike"). A `seed` made no difference. The Nemotron models reason before
  answering, and the reasoning differs from call to call.
- **Scopes hold; categories wobble.** With the final prompt, both runs of the evaluation
  returned the expected scope for all 25 cases, on the small tier and on the medium tier. What
  fails is the rule that both runs return the same category: two or three cases differ per pair
  of runs, and not the same cases each time ("clothes dryer" and "laundry dryer"; "knife set"
  and "kitchen knife"; "electric bicycle" and "electric bike"). Over four runs per case, 22 of
  25 cases were stable on each tier.
- **The medium tier is not more stable.** Same prompt, same day: 22 of 25 stable over four
  runs, against 22 of 25 for the small tier. The supervisor therefore stays on the small tier;
  moving it up would not make the categories repeat.
- **The evaluation's rule follows from this.** It requires the same category in both runs only
  where a case states the expected one (`supervisor.md`, "Evaluation"). A category that differs
  between near-synonyms costs a miss in the brief cache.
- **Switching the reasoning off is worse.** With `enable_thinking` off (tried in a scratch
  script, not in `llm.py`) the small tier answered in about 40 tokens and its categories were
  stable, but 6 of 25 scopes were wrong, among them a caveat scope returned as `tuned`.
- **`check_models --compare` now uses the supervisor's prompt.** With that longer prompt the
  alternative small model (Lightning) put its reasoning in the answer in 3 of 16 calls and took
  a median 46 s, which confirms the choice of Nano.
