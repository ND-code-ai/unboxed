# Findings from task 1.9.7: the LCA tier 3 call on the large model

Run with `scripts/lca_probe.py` (its docstring gives the command). The reply of the full
reasoning call is recorded in `tests/fixtures/nebius/lca-kettles.json`, which the agent tests
use. Model: `nvidia/Nemotron-3-Ultra-550b-a55b` (the large tier).

## The probe

One call to the large tier with `ESTIMATE_PROMPT` (`agents/lca/prompt.py`), the strict JSON
schema of `EstimateReply`, `max_tokens` 16,000 and three kettles: the Russell Hobbs Structure
28081-70 as a linked product whose page states "plastic" and "stainless steel" and 1.1 kg, the
Fellow Corvo EKG and the Bosch TWK3A011. The same call was then sent once more with the
`low_effort` request body (`LOW_EFFORT_REQUEST` in `config.py`).

The probe ran twice, because the first run's timings were cut off the terminal; the recorded
reply and the figures below are from the second run. The first run's reply was valid too, with
five factor rows instead of three (it added a printed circuit board and silicone rubber).

| Call | Time | Prompt tokens | Completion tokens | Reasoning text | Finish | Valid |
|---|---|---|---|---|---|---|
| Reasoning in full | 12.5 s | 836 | 4,506 | 15,592 characters | stop | yes |
| `low_effort` | 11.1 s | 836 | 4,475 | 12,217 characters | stop | yes |

## What was set

- **`low_effort` is not honoured on the large model.** The completion tokens and the time are the
  same as with full reasoning, unlike on the medium tier (`task_1.7.2.md`). The call reasons in
  full, as the roadmap asked.
- **`LCA_MAX_TOKENS` = 16,000**, about 3.5 times the 4,506 used for three options, which leaves
  room for a fourth option and a retry's longer answer.
- **`LCA_TIMEOUT_SECONDS` = 60**, about five times the 12.5 s measured; at the measured rate of
  about 360 tokens a second, 16,000 tokens take about 45 s.
- **`LCA_TIME_CAP_SECONDS` = 150** on the whole estimate: room for the call and its one retry
  after invalid output (two calls of up to 60 s each), and no more.

## What the reply showed

- Every option was estimated; none was declined. Each echoed its name exactly and in order.
- The linked product's page materials were marked as fixed inputs 1 and 2, and its masses add
  up to the page's 1.1 kg, so the weight scale is exactly 1.
- One factor table served all three options: polypropylene 1.5 to 3.5, stainless steel 2 to 6,
  nichrome 8 to 25 kg CO2e per kg, all primary.
- The heating element came back as a separate component (nichrome, 0.05 kg) in each option.
  The Fellow Corvo EKG has a temperature control and a display, but no electronics input came
  back for it in this run (the first run's reply had a printed circuit board for each kettle).
  The live run of task 1.9.8 judges this, with the `lca-reviewer`.
- Manufacturing and assembly came back as 0.15 to 0.4 kg CO2e for two kettles and 0.2 to 0.5 for
  the third, small beside the materials (2 to 6.6 kg CO2e).
- The summed ranges, worked out by hand and asserted in `tests/agents/lca/test_lca.py`: Russell
  Hobbs 2.35 to 6.45, Fellow 2.175 to 5.975, Bosch 2.575 to 7.025 kg CO2e, each already wider
  than 2x, so none was widened.
