# Category brief

Read this when working on the brief agent's research: the decision factors of a category, the
local category term, and the two warnings of a short brief. The questions asked from the factors
are in `interview.md`.

## Decision factors

Each factor found by the brief agent has:

| Field | Meaning |
|---|---|
| `id` | Assigned by code, with a prefix per origin so a cached id never collides with another: `researched-1` for a factor found in a web source, `usage-1` for how often the product is used, and `user-1` for one the user stated in the request that fits no other factor. Questions, answers and options refer to the factor by it |
| `name` | Short label, e.g. "Hob compatibility" |
| `kind` | `compatibility`, `requirement`, `recurring_cost`, `care`, or `usage` |
| `why` | One plain sentence on why it matters |
| `source` | URL it came from, with who is speaking there (`stated_by`: `tester`, `owner`, `manufacturer` or `seller`). A factor of the user's own has a source of kind `user` whose reference is the user's phrase; the factor of kind `usage` has none |
| Typical yearly cost | Optional, with its own source and, when converted, the currency it was converted from (`typical_yearly_cost_converted_from`, USD or GBP); for the first `recurring_cost` factor only (see "Recurring costs are factors") |

Rules:

- **Sourced, not recalled.** Every researched factor comes from a search result and carries its
  URL; its quote must stand in that result (`data_sources.md`, "Research rules"), or it is
  dropped. The model does not list specs from memory.
- **What a model writes is checked.** Code rejects a digit, a currency marker or a generic
  environmental term (`docs/eu_market.md`) in every string a model writes; a follow-up search
  query alone may hold digits (`data_sources.md`, "Research rules"). The check is
  `agents/shared/model_text.py`. A factor's name and `why`, a question, its reason and a care
  statement may not hold "should" or "must" either (`product.md`, "Tone"; task 1.10), a check
  of `agents/brief/checks.py` alone, since the user's own phrases may hold them. A factor whose
  name or `why` fails is dropped with an `excluded` trail entry that does not repeat its words;
  a question whose words fail counts as not phrased (`interview.md`, "Questions").
- **At most eight researched factors** per category, ordered by how often they cause a wrong
  purchase. With the usage factor and at most three of the user's own (`reading_answers.md`, "Stated answers"),
  a report holds at most twelve.
- **Recurring costs are factors.** Consumables such as filters, bags or cartridges are captured
  as factors of kind `recurring_cost`. Only the first one the read gives gets a typical yearly
  cost: the read quotes an amount, an interval and, when the price is for a pack, a pack count,
  all from the result that factor cites, and code computes the yearly figure with the reading
  an option's recurring cost uses (`agents/shared/yearly_cost.py`: the amount parser, the pack
  count and interval parser in `calc/recurring.py`, and the fixed-rate conversion for USD and
  GBP, `docs/adr/0002-fixed-rate-conversion-recurring-costs.md`). Its source is the factor's.
  An amount that fails a check (a quote not in the result, no interval in time, a pack with no
  count, a currency that is not converted, or no amount quoted at all) leaves the factor with no
  amount; an `excluded` trail entry gives the reason. No search is added to find a missing
  amount. A recurring cost is information, not a question: the figure is shown as one line
  above the questions and on the report (`wording.typical_cost`), labelled when it was
  converted, and is never asked about, since every option of a category with a consumable has
  that cost and declining it could change nothing. The factor has no answer, so it is on the
  check-before-you-buy list, with or without an amount: what the product bought costs is still
  to check. The math uses the cost found for each product option, never the category-typical
  one (see `calculations.md`).
- **Care is a factor.** If reaching the stated lifespan needs maintenance (seasoning a carbon
  steel pan, descaling a kettle), say so here, because it affects whether the lifespan holds.

## How the brief is researched

Category research follows `data_sources.md` ("Research rules"): two template searches run
together (the purposes `category` and `category_care`, templates in `config.py`), one read by the
medium model with little reasoning (`models.md`), and one follow-up search with a second read
when the read reports gaps or fewer than three factors survive. One phrasing call, also on the
medium tier but reasoning in full (`models.md`), then phrases a question per factor that can be
asked about and picks the usage frequencies to offer. The brief is kept in the brief store, so a
category is researched once (`data_sources.md`, "Cache and fixtures").

**The local category term.** Beside the two searches, one medium-tier call that reasons in full
(`models.md`) gives the word shops in the Netherlands use for the category, such as
"koekenpan" for a frying pan: one to three Dutch words, in lower case, with no brand, budget or
size (task 1.13). A reply whose term holds no letter (the model wrote "..." now and then in
task 1.15) is invalid output, asked for again once like any other. Code lowers and trims the
term and checks it is at most three words and holds
nothing a model may not write; a term that fails is left out with an `excluded` trail entry,
and option research then searches with the category's own words. The term is stored with the
brief and goes to the TCO analyzer, which searches the comparison sites' listing pages with it
(`option_research.md`, "Listing pages"). A failed call leaves the brief unstored, as a failed
read does, so the next request of the category tries again.

A request with no category (a pasted link whose page named none) is not researched and not
cached: it gets the usage question only, one `decided` trail entry and no warning. The
stated-answers call still runs, with the usage factor alone, so a stated usage is not asked.

Two warnings say when the brief is short (`agents.md`, "Warning codes"). `research_unavailable`:
the brief ends with no researched factor. `questions_unavailable`: there are factors, but the
phrasing call failed; what the questions would have asked about is then on the
check-before-you-buy list. Either way the session continues with the usage question. One or two
factors is not a warning; the trail records the gaps.
