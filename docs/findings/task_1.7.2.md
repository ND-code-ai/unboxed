# Findings from task 1.7.2: time to the questions

Live runs on 2026-10-15 with the real models on Nebius Token Factory and the cached Tavily
searches of task 1.7 for "I need a new frying pan, budget 50 euro", "I need a new kettle" and "I
need a cordless drill". Uncached means the category's brief was deleted first, so the read and
the phrasing ran again on the cached searches; a follow-up search the read asked for ran live in
the final runs (6 Tavily credits allowed, 3 used). Each model call was timed with a scratch
wrapper around the chat model; the final numbers are `Measure-Command` around a `--skip-all` run,
as `models.md` ("Rules") describes.

## Where the time went before

Kettle, reasoning in full everywhere: uncached 45.9 s to the questions, of which the read 26.2 s
(5,772 completion tokens, about 22,000 characters of it reasoning), the phrasing 10.1 s, the
supervisor 5.2 s and the stated-answers call 3.6 s. The input is small: 15 or 16 search results
come to about 3,000 prompt tokens, so a shorter text per search result would save little. The
time is the reasoning. Cached runs on this day, reasoning in full: 10.8 to 28.4 s for the three
categories and "a frying pan for induction, I cook every day" (12 runs); the supervisor took
4.1 to 10.9 s and the stated-answers call 6.3 to 22.7 s of that.

## What the models offer

Nemotron 3 Super (medium) has a low-effort mode and both models can switch reasoning off, through
`chat_template_kwargs` in the request body (NVIDIA's model cards). Nebius honours both: with
`{"enable_thinking": true, "low_effort": true}` the read took 2.4 to 7.4 s and 539 to 1,632
completion tokens instead of 13 to 39 s and up to 8,083. Nano (small) has no low-effort mode. A
reasoning budget exists only as a client-side helper that needs two calls.

## What was tried

| Change | Time | What it cost |
|---|---|---|
| Supervisor and stated-answers call on the small tier, reasoning off | cached 2.8 to 6.3 s | the frying pan once scoped `general`; "for induction, I cook every day" once returned nothing stated (1 of 3) |
| Both on the medium tier, little reasoning | cached 2.0 to 3.5 s | stated answers right in 12 of 12 runs; but the supervisor evaluation failed on scope in 3 of 3 runs (a microwave and a Dutch vacuum cleaner as `general`, a fan heater as `tuned`) |
| Supervisor on the medium tier, reasoning in full | 2.2 to 3.9 s per call | the evaluation's scopes all held, but "I need a new kettle" was `energy_heavy` in 3 of 3 runs; the prompt names no kettle, and `supervisor.md` makes it `tuned` |
| Phrasing with little reasoning | 3.1 to 5.3 s instead of 4 to 13 s | choices with numbers not in the source and choices over 40 characters: kettle 5 and 6 phrased questions, drill 4 and 5 |
| Read with little reasoning, prompt as it was | 2.4 to 5.0 s | kettle 4 factors twice (only 3 of 15 results cited); frying pan 8, drill 8 |
| Read with little reasoning, prompt asking for every factor the results support | 3.1 to 7.4 s | kettle 8, 8, 8; frying pan 6, 6; drill 8, 8 factors, with no follow-up search allowed; the final runs below kept fewer |

The supervisor evaluation on the small tier with full reasoning also failed once in this task,
on the category of "a 3d printer for a beginner" ("three dimensional printer"); the medium tier
missed the same case.

## What was kept

- The read with little reasoning and rule 5 of `READ_PROMPT` asking for every factor the results
  support (`agents/brief/agent.py`, `agents/brief/prompt.py`).
- The stated-answers call on the medium tier with little reasoning (`agents/brief/stated.py`).
  This resolves the left-over item of task 1.7.1: the call now takes 0.5 to 1.8 s, so running
  it beside the phrasing call would save little.
- The phrasing call and the supervisor as they were: the phrasing on the medium tier and the
  supervisor on the small tier, both reasoning in full.

## Time to the questions, from pressing Enter

`Measure-Command` around a `--skip-all` run of the terminal app, with the changes kept:

| Category | Uncached | Cached |
|---|---|---|
| frying pan ("I need a new frying pan, budget 50 euro") | 24.0, 24.7 s | 8.9, 10.4, 7.6 s |
| kettle ("I need a new kettle"), one follow-up search in the first run | 25.4, 21.7 s | 6.5, 10.7, 5.8 s |
| drill ("I need a cordless drill"), a follow-up search in both | 27.6, 24.7 s | 6.7, 6.4, 6.9 s |

Task 1.7 measured 41.8 to 59.3 s uncached and 7.4 to 19.6 s cached. Every uncached run is now
within 30 s. Two cached runs are just over 10 s; what is left of a cached run is starting the
app and the supervisor's call on the small tier, which reasons in full and took 4.1 to 10.9 s.
The developer set the cached target to 12 s (`models.md`, "Rules").

## Factors and phrased questions

| Category | Factors kept | Questions phrased | Task 1.7 |
|---|---|---|---|
| frying pan | 8, 8 | 7, 8 | factors 7, 6, 5; its stored brief 7 questions |
| kettle | 6, 7 | 6, 4 | factors 8, 8, 8; no brief stored |
| drill | 8, 7 | 6, 4 | factors 7, 8, 6; its stored brief 5 questions |

A factor was lost to a quote not found in its search result (two in the first kettle run, one in
the second and in the second drill run), and in the first kettle run the second read kept one
factor fewer than the first. A question is missing mostly because a recurring-cost factor gets
none until task 1.8.1 (one in the drill runs, two in the second kettle run), and otherwise for a
number in a choice that is not in the source, or a choice over 40 characters. The developer
accepted these counts: at least five factors and four phrased questions per tuned category
(`models.md`, "Rules").
