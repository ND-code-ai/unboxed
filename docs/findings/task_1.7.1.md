# Findings from task 1.7.1: stated answers

Live runs on 2026-10-14, with the real models on Nebius Token Factory and the recorded Tavily
responses (`SHOPPER_SOURCES=fixtures`, so no Tavily credits were spent). The input in every run
was "a frying pan for induction, I cook every day".

## Time to the questions

`Measure-Command` around a `--skip-all` run of the terminal app, as `models.md` ("Rules")
describes:

| Run | Seconds |
|---|---|
| Uncached: searches, read, phrasing and the stated-answers call | 35.9 |
| Cached, from the brief store | 16.9, 19.8 |

Task 1.7 measured 13.5 to 19.6 s for a cached frying pan run without this call
(`task_1.7.md`), so the cached target of 10 s stays missed. The stated-answers call alone, on
the small tier, timed with the cached frying pan brief: 5.7, 6.1 and 16.1 s; with a hand-made
brief of three factors: 4.8, 5.2 and 11.7 s. It runs after research and before the questions,
on the cached path too, so it adds that time to every run. Task 1.7.2 is about this time.

## What the small model picked out

- **With a hob factor in the brief** (a hand-made one: hob compatibility with the choices
  Induction, Gas, Electric or ceramic; pan size; usage), three of three runs mapped "for
  induction" onto the choice Induction and "I cook every day" onto `every_day` (365 uses a
  year). Once the phrase was "a frying pan for induction" rather than "for induction": the
  phrase check passes it, because it stands in the request, and the line then quotes the longer
  phrase.
- **On the recorded frying pan searches** the brief has no hob factor: the read found none and
  reported the gap ("Compatibility with cooking surfaces"), and its follow-up search is not
  recorded. "For induction" then went to the trail as fitting no decision factor, which is the
  case task 1.7.3 handles, and only the usage line was shown. In one run the usage phrase was
  "every day" rather than "I cook every day".
- The call failed in none of the runs; no reply was invalid.
