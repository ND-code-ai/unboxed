# Findings from task 1.8.6: option answers

The live check of task 1.8.6: `uv run python -m shopper.cli "<request>"` with the answers piped
in, run on 18 October 2026 on the final code. Outputs are in `.cache/live/run_1_8_6/` (not in
the repo). The cached briefs of task 1.7 were used, so the brief spent no credit.

## The runs

| Run | Request | Answers | Options |
|---|---|---|---|
| 1 | "a frying pan for induction, budget 60 euro" | none (input ends at the first question) | 1 |
| 2 | "I need a new kettle" | quickly, not sure, induction, rather avoid descaling, not sure | 1 |
| 3 | a mediamarkt.nl link to a Tefal Simple Cook pan, "for induction" | not sure on all | 1 |
| 4 | a coolblue.nl link to the Tefal Supreme Gusto 28 cm, "for induction" | not sure on all | 2 |
| 5 | "a dishwasher safe frying pan, budget 100 euro" | none | 0 |

The frying pan asks no care question: its brief's first four researched questions are about
size, material, coating and oven use, and only those four are asked. The kettle's fourth is
descaling, so run 2 is the only one with a `care-avoid` answer. Run 3's page has no JSON-LD
`Product`, so the link was unreadable (`link_unreadable`) and the run went on as a category
request. Run 5 priced no candidate (`no_options_found`, nothing with a price in euro).

## Fits per option

| Run | Option | Meets | Fails | Unverified |
|---|---|---|---|---|
| 1 | Oxo Ceramic Professional Non-Stick | 1 (induction, homesandgardens.com) | 0 | 0 |
| 2 | Cuisinart CPK-17P1 PerfecTemp | 1 (power, nytimes.com) | 0 | 2 (induction, descaling) |
| 3 | The 10-inch Tramontina Professional Nonstick Fry | 0 | 0 | 1 (stove compatibility) |
| 4 | Tefal Supreme Gusto Koekenpan 28 cm (linked) | 0 | 1 (induction, coolblue.nl) | 0 |
| 4 | Tramontina Professional Fusion 10-Inch | 0 | 0 | 1 (induction) |
| | **Total, 5 options** | **2** | **1** | **4** |

Each of the four `unverified` came from the read itself. The checks turned no value
`unverified`: every quote of a `meets` or a `fails` was found in its result, in a passage that
named the product.

## Against "Done when"

- **The mismatch line: shown live.** Run 4 printed "Does not match your answer for for
  induction: niet geschikt voor inductie (coolblue.nl) (the seller states)" beside the linked
  Tefal, which stayed first. The quote came from the linked product's own page, given to the read
  as one more result. Its fetch was a cache hit (0 Firecrawl credits for the TCO analyzer).
- **An answer excluding an option: not shown live.** No run produced a `fails` on an option
  that was not the linked product: runs 1 to 4 had one priced candidate besides the linked
  product, or none, and none of their pages said it fails an answer. Shown offline by
  `test_an_option_that_fails_an_answer_is_removed_with_the_quote_and_its_site` and
  `test_when_every_option_fails_an_answer_none_met_the_answers`
  (`tests/agents/tco/test_tco_answers.py`).
- **A `care-avoid` answer marking an option: not shown live.** Run 2's descaling answer came
  back `unverified`. Shown offline by
  `test_a_care_factor_declined_and_needed_marks_the_option_and_removes_nothing` and, for the
  report line, `test_the_factor_values_follow_the_link_in_the_order_of_the_factors`
  (`tests/test_report_text.py`).

## Observations

- **A factor of the user's own is named by its phrase,** so its lines read "for induction:
  could not be confirmed" and "Does not match your answer for for induction". When the phrase
  holds the product ("a frying pan for induction", run 1), the value line starts with it. This is
  for the tone pass.
- **"Power: boils a full kettle in about seven minutes" was judged `meets`** for "Yes, quickly".
  The quote stands; whether seven minutes is quick is the model's judgement, and nothing checks
  it.
- **The page text is cut at 6,000 characters,** like a search result's full text. The Tefal's
  "niet geschikt voor inductie" was within it. A shop page's spec table further down would not
  be.

## Credits

Tavily: 20 for the five runs (3, 3, 7, 3, 4). Firecrawl: 3 (two pasted links, one price page).
One medium-tier call re-recorded `tests/fixtures/nebius/evidence-levoit-core-300.json`, whose
input changed with the prompt. The new reply also names other consumables, so its test now
expects "other consumables not counted".
