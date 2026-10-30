# Findings from task 2.5.6: the reply's reading, live

Live runs on 2026-10-26 of the reply's reader (`read_reply` in `agents/brief/reply.py`) on the
medium model (`nvidia/nemotron-3-super-120b-a12b`, low effort, `REPLY_PROMPT`) on Nebius Token
Factory. The reader was called directly, with no search and no graph: the request "I need a new
frying pan, budget 50 euro" (category "frying pan", budget €50), the stub brief's hob question
and usage question asked, and a care factor "Seasoning" phrased but not asked, with the care
question's two choices. Eleven calls, no Tavily credits. The replies are those of task 2.5.5's
tests, plus a factor of the user's own.

## What each reply gave

| Reply | Time | What code kept | Trail |
|---|---|---|---|
| "I cook on induction, about once a week" | 2.2 s | Hob: Induction (choice 3, phrase "I cook on induction"); usage: about once a week, 50 uses a year | Two "Stated in the reply" entries |
| "I don't mind seasoning it now and then" (factor not asked) | 0.9 s | Nothing | Nothing |
| "no idea which hob" | 1.0 s | Hob: not sure, with its phrase | "Read in the reply ... not sure" |
| "I meant a wok" | 1.5 s | Nothing; asks to change the request | Ignored, "it asks to change the category, which a reply cannot" |
| "make it €40" | 1.3 s | Nothing; asks to change the request | Ignored ("€40"), "it asks to change the budget, which a reply cannot" |
| "it's a present for my dad, he just moved into his first flat" | 0.7 s | Nothing | Nothing |
| "it should be oven safe" | 1.4 s | A factor of the user's own, "it should be oven safe" | "Stated in the reply ... as a requirement of its own" |

Every call answered in 0.5 to 2.2 s, and none needed a second try.

## What went right

- The asked question and the usage frequency were mapped onto their choices, with the reply's
  own words as the phrases.
- "No idea" became `not_sure` on the question asked, as the prompt's rule 3 says.
- Both requests to change the request were marked and left the request as it was; the budget
  phrase was cut to "€40", which stands in the reply.
- The phrase about a person gave nothing (rule 5). No personal detail reached the answers or the
  trail.
- The factor of the user's own kept the whole phrase as its name. That reads a little long on the
  report ("From your reply: "it should be oven safe""), but it is the user's words, as for the
  request.

## What went wrong

- **Agreeing to a care factor reads as nothing.** "I don't mind seasoning it now and then" and
  "seasoning is fine with me" gave no requirement in four further runs (two each), so the
  seasoning factor not asked kept no answer. The model returned an empty list: code dropped
  nothing, since a dropped phrase leaves a trail entry. The likely cause is rule 3 of
  `REPLY_PROMPT` ("Not knowing or not minding is never a value or a choice"), which reads "don't
  mind" as indifference, while the care question's first choice, "That's fine", is just that
  (`wording.md`, "The interview"). In the page, such a reply with no choice picked gets
  `reply_unanswered`; with choices, the trail says only that the reply changed no answer, as
  nothing in it answers a factor. Left for a later
  task (`left_over_tasks.md`).
