# Findings from task 1.7.3: requirements the user states

Live runs on 2026-10-14 with `--skip-all`, on the real models on Nebius Token Factory and live
Tavily searches (the frying pan and drill briefs came from the brief store after their first run;
two runs spent one Tavily credit each).

## The first prompt missed requirements about no factor

With the stated-answers prompt of task 1.7.1, which only named "new" as a value of `factor`, the
small model left out most requirements that fit no factor:

| Input | What the call returned |
|---|---|
| "I need a cordless drill with a spare battery, budget 120 euro" | "cordless drill" onto the factor "Power source type"; nothing for "with a spare battery" |
| "an eco-friendly frying pan" | nothing |
| "a frying pan with a lid, dishwasher safe, with a long handle, made in Italy" | "dishwasher safe" onto the care factor "Dishwasher safe" (as the choice "That's fine"), "made in Italy" as new; nothing for the lid or the handle |

A rule now asks for them in `STATED_PROMPT` (`agents/brief/prompt.py`): every requirement about
none of the factors, such as a feature, an accessory, a material or where it is made, returned
separately with factor "new".

## With the new rule

| Input | Result |
|---|---|
| "I need a cordless drill with a spare battery, budget 120 euro" | "cordless" onto "Power source type"; `user-1` "with a spare battery" |
| "a cordless drill with a spare battery, a carrying case, a belt clip and a built-in LED light" | "cordless" onto "Power source type"; `user-1` to `user-3` "spare battery", "carrying case", "belt clip"; "built-in LED light" to the trail: at most 3 are kept |
| "an eco-friendly frying pan" | "eco-friendly" returned as new and refused by code: its phrase holds a generic environmental term |

One run each, so how often the small model returns them is not measured. The phrase may be
shorter than the request's words ("spare battery" without "with a"); both stand in the request,
so both pass. Run times were 29 to 82 s, in the range task 1.7.2 is about.
