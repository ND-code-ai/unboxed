# Findings from task 1.8.1: typical yearly cost of a consumable

The live check of task 1.8.1, run on 18 October 2026: the CLI for the vacuum cleaner and the
electric toothbrush, and the brief agent alone (a scratch script calling `research_brief` with
the live sources) for four categories with a consumable. Outputs are in `.cache/live/run_1_8_1/`
(not in the repo).

## The runs

| Run | What ran | Category | Prompt | Recurring-cost factors | Typical yearly cost |
|---|---|---|---|---|---|
| 1 | CLI, input ends at the first question | vacuum cleaner | first | bags, filters | none: "the read quoted no amount" |
| 2 | brief only | air purifier | first | filter cost, filter interval | none: "the read quoted no amount" |
| 3 | brief only | water filter jug | first | filter frequency, cartridge lifespan | none: "the read quoted no amount" |
| 4 | brief only | vacuum cleaner | final | none kept | none |
| 5 | brief only | air purifier | final | HEPA filter, carbon filter | none: "the read quoted no amount" |
| 6 | brief only | electric toothbrush | final | brush heads | €53.32 a year, converted from USD |
| 7 | CLI, answers piped | electric toothbrush | final | brush heads | €53.32 (the cached brief of run 6) |
| 8 | CLI, revised, answers piped | electric toothbrush | final | brush head interval | none: "the read quoted no amount" |
| 9 to 15 | brief only, revised | electric toothbrush | final | brush heads, or none | none in six; "annual" not read in two before the parser fix |
| 16 | CLI, revised, answers piped | electric toothbrush | final | brush heads | €31.99 a year, converted from USD (the brief of run 15) |

Runs 1 to 7 ran with the recurring-cost question; runs 8 to 16 with the information line that
replaced it (see "Revision"). Run 7's answers: "I'd rather avoid it" to the cost question, not
sure to the other three, and every day. Runs 8 and 16: not sure to every question (in run 16
the usage question too, since it had one question fewer than the answers piped).

## Revision

After run 7 the developer asked to turn the question into an information line. In run 7 the
user answered "I'd rather avoid it" and nothing changed on the report but two "could not be
confirmed" lines: every electric toothbrush needs brush heads, so the answer could neither
remove an option nor steer the choice, and the question read as a choice that was not one. The
typical yearly cost is now one line after the "From your request" lines, above the questions
and on the report; no question is asked about a recurring cost, and its factor stays on the
check-before-you-buy list. Removed with the question: the choices `cost-fine` and `cost-avoid`,
the factor values `cost-avoid` gave and their mark line (`interview.md`, "Recurring costs are
factors"; `wording.md`, "The interview").

## What the searches give

- **The vacuum cleaner's searches state no consumable price.** Neither template search had an
  amount next to a bag or a filter (the only amounts were the prices of whole vacuum cleaners);
  the follow-up of run 4, "vacuum cleaner bag filter belt replacement cost and frequency", found
  shop carts and wholesale listings, none with an interval. So no read could quote an amount, and
  the factor stayed without one, as designed. No search is added for a missing amount.
- **The read split one consumable into two factors** in runs 2 and 3 ("Filter replacement cost"
  and "Filter replacement interval"), and quoted no amount even for the factor named after the
  cost. The final prompt asks for one factor per thing bought again, covering both what it costs
  and how often, to cite the result that states both, and to report a missing price or interval
  as a gap, so the read's own follow-up can look for it. Runs 4 to 6 kept one factor per
  consumable, and each read's follow-up asked for the price and the interval. Run 4 kept no
  recurring-cost factor for the vacuum cleaner, where run 1 kept two from the same template
  searches; with one run per prompt, whether the final prompt or the read's variation dropped
  them is not known.
- **The electric toothbrush** is the one category whose results stated a price with an
  interval: usmile.us, "A $40 brush that requires a $15 replacement head every 3 months costs
  $100 in Year 1." The read quoted "requires a $15 replacement head" and "every 3 months"; code
  read $15, converted it at 1.1253 per euro (€13.33), four times a year: €53.32. The trail names
  the rate, its date and that a bare "$" was read as US dollars.
- **The reading of the interval missed "annual".** Runs 9 and 10 cited brusho.io, "A $70 brush
  with $36 annual replacement heads costs $250 over five years", and the interval "annual" was
  not read. The interval parser in `calc/recurring.py` now reads "annual", a bare "per year" or
  "each month" as once, and the Dutch adjective forms; and a money amount in the quote is
  taken out before the interval is read, so it is no longer read as a count ("€30 per year" was
  30 replacements a year; "$15.99 each month" would have been 99 a month). Run 15 read
  $36 a year: €31.99.
- **The read varies from run to run.** Of the nine toothbrush briefs researched (runs 6, 8 to
  15), two gave an amount (runs 6 and 15); two quoted "annual" before the fix; the others cited
  a care page, or kept no recurring-cost factor.
- **The care searches of the tuned categories** (frying pan, kettle, drill) were searched again
  live: no result states a consumable's price with an interval (one pan shop page shows cart
  prices). Their fixtures are kept as they were, since a new copy would give the tests nothing new.
  The new fixtures are the toothbrush's three searches, trimmed (`data_sources.md`, "Cache and
  fixtures").

## Against "Done when"

The line as revised: the CLI shows the typical yearly cost with its source, computed in
`calc/`, above the questions and on the report, and asks no question about it; a cost stated in
USD is shown converted and labelled; a source with no interval gives no amount and no line.

- **Shown above the questions and on the report, with no question: live,** for the electric
  toothbrush (run 16): "Brush head replacement cost: typically €31.99 a year (brusho.io),
  converted from USD at a fixed rate." before the first question and again after the warnings
  of the report; the questions that follow are about power, travel and a care routine, and the
  factor is under "Not yet known". Not shown live for the vacuum cleaner, the task's example,
  whose searches state no filter or bag price (above). Offline for a vacuum cleaner's bags:
  `test_the_first_recurring_cost_factor_gets_a_typical_yearly_cost_read_by_code` and
  `test_a_recurring_cost_factor_with_an_amount_gets_no_question_and_no_phrasing`
  (`tests/agents/brief/test_brief.py`), and for the CLI
  `test_a_typical_yearly_cost_is_shown_above_the_questions_and_on_the_report`.
- **A cost stated in USD shown converted and labelled: live** (runs 6, 15 and 16), and on the
  recorded searches by `test_a_dollar_cost_in_a_recorded_search_result_is_read_and_converted`.
- **A source with no interval gives no amount and no line:** offline,
  `test_an_amount_that_fails_a_check_leaves_the_factor_with_no_amount_and_says_why` and
  `test_a_recurring_cost_factor_with_no_amount_has_no_line_and_stays_on_the_list`
  (`tests/test_report_text.py`). Live, the closest cases are no amount quoted (runs 1 to 5, 8)
  and "annual" before the parser fix: no amount, no line, the factor on the list.

## Observations

- **The quoted cost is a seller's worked example,** not a measured typical cost: usmile.us sells
  brushes and states "$15 every 3 months" to make a point about budget brushes. The read
  labelled it `owner`. The line names the site, so the user can judge it; who is speaking is
  the model's judgement, and nothing checks it.
- **The factor name repeats "cost"** ("Brush head replacement cost: typically €31.99 a year"),
  because the read names the factor. For the tone pass.
- **The other toothbrush questions ask about the user's own toothbrush** ("Does your electric
  toothbrush have a pressure sensor?"), a phrasing slip of the phrasing call, not of this task.

## Credits

Tavily: 52 in all. Before the revision, 39: The vacuum cleaner CLI run used 12 (2 for the brief, 10 for options), the
five brief-only runs 11 (two template searches each for the three new categories, and five
follow-ups; the second vacuum cleaner and air purifier runs found their template searches in the
cache), the three
care searches of the tuned categories 3, and the toothbrush CLI run 13 (its brief from the
cache, 0). After it, 13: run 8 used 4 (1 for the brief's follow-up, 3 for options), runs 9 to
15 used 6 (their follow-ups; one was in the cache), run 16 used 3. Firecrawl: 11 (3 and 4 for
the first two CLI runs' price pages, then 1 and 3). No Nebius fixture was recorded.
