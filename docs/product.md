# Product and tone

Read this when writing an agent prompt, UI copy, the report layout, the README pitch, or the demo
script. The exact words of fixed messages (caveats, warnings, declines, labels) are in
`src/shopper/wording.py`; how they are written is in `wording.md`.

## The experience

1. The user pastes a product link or types a need, optionally with a budget.
2. **Interview first.** The app shows up to five questions about what matters for this kind
   of product, including what buyers usually find out too late, each with a one-line reason.
   Every question can be skipped ("Not sure", or "skip the rest" for all that are left) or
   answered in the user's own words ("Something else"), and one optional step after them asks
   "Anything else we should know?". Details:
   `architecture/interview.md`.
   Above the questions the app shows what it understood, for example "Looking for: frying pan ·
   Budget: €50 · Edit", with any warning about the budget. "Edit" starts again with the user's
   text pre-filled, so a mistake is caught before any product search runs. This step is shown
   even when there are no questions to ask.
3. Progress is visible while the agents work, and stays available afterwards as an evidence
   trail: which agent found what, from which source.
4. The report shows, side by side for up to three options: price, cost per year, cost per use,
   expected lifespan with the evidence behind it, CO2e range with its confidence label, the
   factors the user answered, and the 10-year comparison.
5. **The user can change the assumptions**: lifespan per option, the horizon, and uses per year.
   The numbers update. An estimate the user can correct is more honest than one they must trust.
6. A "check before you buy" list names what is still unknown.
7. If the durable option is over budget new, used listings that fit the budget are shown.
8. **The user can talk to it.** Beside the report, a chat answers questions about it ("why does
   this one last longer?"), tries what-ifs ("twice a week?"), and takes pushback ("find one under
   €40", "I don't want to season a pan"). When the agents rework the options, a new version of
   the report appears with what changed. Details: `architecture/conversation.md`.

The 10-year comparison is the centrepiece: one durable item against the cheap replacements it
avoids, in money and in CO2e. It must be understandable from a screenshot with no explanation.

## Durability evidence

A lifespan is the number every headline figure depends on, so it is never shown bare. Next to
each lifespan, show what it rests on, each item with its source:

- warranty length offered by the maker;
- whether spare parts and repairs are available;
- the material or construction that determines wear (a coating that degrades, a solid metal that
  does not);
- any care the lifespan depends on.

If none of these can be found, say the lifespan is a rough estimate and show it as such. Never
turn this evidence into a score or rating out of ten.

**What owners and testers report.** Part of the same evidence: two or three short findings per
option about what fails and how long the product lasts in practice, from independent tests,
expert reviews and owner discussions found through search.

- Summarise and link; never copy review text.
- Label each finding as an independent test or an owner report.
- Show a rating only when a source gives one, as that source's overall rating, never as a
  durability score: with the source name, and with the number of reviews when owners gave it (a
  tester's score has none). Never blend ratings or compute one.
- "No owner or tester reports found" is a valid result and is shown. When the reports could
  not be looked up, the report says that instead.
- Retailer review pages are not fetched; there is no scraping.

## Principles

1. **Wallet first.** The budget is a hard constraint, not a suggestion. Never recommend something
   the user said they cannot afford; find the best option inside the budget, new or used.
   An option that costs more than the budget is still shown, because it is what the used
   listings are measured against, but it is always marked "Over your budget" and is never
   presented as the pick. The results page has a "Hide options over my budget" switch. Whether
   an option is over budget is computed in `calc/`; the page only filters on that value. The
   budget is never asked about in the interview. With no budget given, nothing is marked and
   the switch is not shown.
2. **Never preachy.** Sustainability is the bonus of the better-value choice. No guilt, no
   lectures, no judgement of the cheap option or of the user.
3. **Honest about uncertainty.** Every environmental figure shows its label ("Published figure",
   "Benchmark estimate", "AI synthetic estimate") and its source. Unknown is shown as unknown.
4. **Practical.** End with something the user can act on: a product, a listing, or a next
   question to ask.
5. **Buy the right thing once.** Help the user learn what matters before they search, so the
   purchase fits and is not replaced early.
6. **Show the work.** Every figure can be traced to an agent, a source and an assumption the
   user can change.

## Tone

Plain, specific, calm. Lead with money, follow with impact.

| Do | Don't |
|---|---|
| "The €20 pan lasts about 2 years, so it costs €10 a year." | "Cheap pans are terrible for the planet." |
| "A €40 carbon steel pan fits your budget and lasts 30+ years: about €1.33 a year." | "You should invest in quality instead of buying junk." |
| "Over 10 years that is one pan instead of five." | "Think of the landfill you are filling." |
| "Estimated 4 to 9 kg CO2e (benchmark estimate)." | "Saves 6.47 kg of CO2!" |
| "About 5 to 12 kg CO2e less to manufacture over 10 years (benchmark estimate)." | "The eco-friendly choice." |
| "We could not find a lifespan for this product." | A guessed number with no label |

How this applies when something does not go to plan (a declined request, an unusable budget,
nothing within budget) is in `wording.md`, with a "do" and a "don't" for each case.

Avoid: should, must, guilt, shame, "the planet needs you", exclamation marks, and claims of
precision the data does not support. Never use generic environmental claims such as
"eco-friendly", "green" or "sustainable" about a product; give the specific figure instead.

## Scope

Broad door, deep core.

- **Accepted: any physical, durable product, except motor vehicles.** The full flow runs for all
  of them; the brief agent researches each category fresh.
- **Tuned and tested: cookware, small household appliances, and tools.** These are the categories
  the test queries, fixtures and example buttons cover. The frying pan is the reference example.
- **Declined: things that are not durable physical products**, such as food and drink,
  consumables used up in use (shampoo, batteries, printer ink), services, subscriptions, digital
  goods, living things and property. **Motor vehicles are declined too** (cars, motorcycles,
  mopeds): fuel, tax and insurance are most of what they cost, and none of that is in the
  figures. Decline with a friendly message that says what the app covers.
- **Asked to rephrase: input the app could not understand.** Nothing runs; the user is asked to
  try again with one product.
- **Asked to name one: input that names more than one product.** Nothing runs; the user is told
  that is what was seen and asked to name one.
- **Never refuse any other durable product for being outside the tuned categories.** Run it, and let the
  evidence summary and caveats show how solid the result is.

The words of every caveat, decline, rephrase message and budget warning are in `wording.py`.

Market: Netherlands first, European Union overall; EUR; English interface. Market details and the
EU rules on environmental claims are in `docs/eu_market.md`.

## Evidence summary

One factual line at the top of every report saying how much of it rests on sources (on a wide
screen under the savings, in the same block), for example:
"Lifespan sourced for 3 of 3 options. CO2e to make: published for 1, benchmark estimate for 2."

- Counts only. Never a score, grade, percentage of confidence or colour rating.
- Computed in code from the report, not written by a model.
- Thin evidence is shown, not hidden: "Lifespan sourced for 0 of 3 options" is a valid line.

## Demo moments

Five moments the product should make easy to show in under three minutes. When a design choice
is open, prefer the one that makes these clearer.

1. The interview raises something the viewer had not thought of.
2. The user changes a lifespan and the 10-year chart redraws.
3. The evidence trail shows what each step found, decided and left out. The page names no model;
   the three model tiers doing different jobs show in the terminal app's trail and in LangSmith.
4. A real used listing appears within the budget. Not in the hackathon version: the page shows
   nothing of the second-hand agent, whose stub still runs (task 3.10).
5. The user pushes back in the chat ("find one under €40"), and the agents rework the options in
   front of them, with a new report version showing what changed.

## Future sources

Not built, and not to be built without asking. Mention them in the README and the pitch as where
the app is heading.

- **EU Digital Product Passports.** Products will carry a QR code linking to the maker's
  passport, with materials, durability and footprint data. The registry opened in 2026 for
  businesses and authorities, has no public API, and no household goods carry passports yet
  (batteries come first, from 2027). When passports exist for a product, a passport link pasted
  by the user would be handled like a product link, and its figures would count as published
  figures (LCA tier 1) and as the strongest durability evidence. The report's structure is
  already close to a passport's, so the accurate claim is "ready for Digital Product Passports",
  never "uses" them.
