# Calculations

Read this when working in `src/shopper/calc/` or on anything that displays a number. These
definitions are the single source of truth for every figure shown to the user.

Everything here is pure and deterministic: no I/O, no model calls, no current time.

## Inputs

Per option: `price` (EUR), `lifespan_years`, optional `recurring_cost_per_year` (consumables such
as filters or bags, default 0), CO2e per unit as a range (`co2e_low`, `co2e_high`, in kg).

Shared: `horizon_years` (default 10), optional `uses_per_year` and optional `budget` (EUR).

All money is EUR (`docs/adr/0001-euro-only.md`). The one exception is a recurring cost found in
USD or GBP, converted at a fixed rate before it arrives here and flagged on the option's row
(`docs/adr/0002-fixed-rate-conversion-recurring-costs.md`); the figures below never convert.

A recurring cost has three states (`option_evidence.md`, "Evidence"). Found: the math uses it.
Not found, when it was looked for: the math uses 0 and the option's comparison row is flagged as
"recurring costs not found", so the figure can be shown as excluding consumables. Not looked
for, because the category has no consumables: the math uses 0 with no flag. A converted cost
carries its original currency to the row's flag. A category-typical cost from a decision factor
is never substituted.

## Definitions

| Figure | Definition |
|---|---|
| Cost per year | `price / lifespan_years + recurring_cost_per_year` |
| Cost per use | `cost per year / uses_per_year`; missing when `uses_per_year` is not given |
| Purchases over the horizon | `ceil(horizon_years / lifespan_years)`, at least 1 |
| Horizon cost | `purchases * price + recurring_cost_per_year * horizon_years` |
| Horizon CO2e | `purchases * co2e_low` to `purchases * co2e_high` |
| Savings against a baseline | Baseline horizon cost minus this option's horizon cost |
| CO2e avoided against a baseline | Baseline horizon CO2e minus this option's, as intervals: low is baseline low minus option high, high is baseline high minus option low. See "CO2e avoided" below |
| Within budget | `price + shipping <= budget`, with the shipping the option's offer states (none when it states none); missing when the request has no budget or the option has no price |

The baseline is the cheapest option by sticker price unless the caller names another. An option
marked `out_of_stock` or `incomplete` (`option_research.md`, "Selection") is never the cheapest:
it cannot be bought as it is. An option sold `incomplete` is not set against the baseline at all:
its savings and CO2e avoided are missing with the reason that it is sold without a part it needs
to work, because its price buys less than the item.

**Nothing within budget.** When the request has a budget, at least one option has a price, no
option is within budget (with its stated shipping) and no listing is priced within it either, the
comparison step adds the warning `nothing_within_budget`. A listing is judged on its price alone,
because its shipping cost may be unknown. Its message states the budget and the cheapest priced option, for
example "Nothing found within €5; the cheapest option is €15." There is no threshold for an
implausible budget: a mistyped one shows up here, as a fact.

Worked example, horizon 10 years. Cost per use is at 50 uses a year and is missing when uses
per year is not given:

| Option | Price | Lifespan | Cost per year | Cost per use | Purchases | Horizon cost |
|---|---|---|---|---|---|---|
| Non-stick pan | €20 | 2 years | €10 | €0.20 | 5 | €100 |
| Carbon steel pan | €40 | 30 years | €1.33 | €0.03 | 1 | €40 |

Savings against the baseline: €60. These two rows are required unit tests.

Second required example, a vacuum cleaner with consumables, horizon 10 years, 50 uses a year:

| Option | Price | Lifespan | Recurring | Cost per year | Cost per use | Purchases | Horizon cost |
|---|---|---|---|---|---|---|---|
| Bagged, cheap | €80 | 4 years | €25 a year | €45 | €0.90 | 3 | €490 |
| Bagless, durable | €200 | 10 years | €10 a year | €30 | €0.60 | 1 | €300 |

Savings against the baseline: €190.

## CO2e avoided

Two ranges are subtracted as intervals, so the result spans every pair of values the two ranges
allow: low is the baseline's low end minus the option's high end, high is the baseline's high
end minus the option's low end. Subtracting the ends separately would give an inverted or falsely
narrow range once the ranges are wide (10 to 20 against 1 to 15 would give 9 to 5).

The figure exists only when its low end is above 0, which is when the option's whole range lies
strictly below the baseline's. Otherwise it is missing with a reason: the ranges overlap, or the
option's range is not below the baseline's (it lies wholly at or above it). A difference is never claimed
where the ranges allow none, and CO2e avoided is never negative. The baseline's own row has no
CO2e avoided, with the reason that it is the baseline.

The figure carries the weaker of the two confidence labels: "AI synthetic estimate" (tier 3) is
weaker than "Benchmark estimate" (tier 2), which is weaker than "Published figure" (tier 1). In
code that is the higher tier number, `co2e_avoided_tier` on the comparison row (each row's own
tier is `horizon_co2e_tier`); turning the tier into its label is presentation.

When all options are model estimates, their errors are partly correlated: they are estimated
against one factor table (`docs/adr/0006-tier-3-returns-factors-code-multiplies.md`), so for a
material two options share, a factor that is too high is too high for both. Materials they do not
share and each option's manufacturing range carry no shared error. Interval subtraction ignores
this correlation, which is conservative: within the ranges as given, it can hide a difference but
never invent one. The ranges are not confidence intervals (see "CO2e of a model estimate"), and
the lifespans behind the purchase counts are single estimates whose uncertainty is not in the
interval.

The figure has the boundary of the results it is built from: making the item only, cradle to gate
("Known simplifications"). It leaves out the energy used in use, which for an appliance can
reverse the order of the options. Today every result is a model estimate with one fixed
boundary; the subtraction does not compare boundaries, so the task that adds tier 1 or tier 2
must also withhold the figure when the two results cover different boundaries.

Worked examples, horizon 10 years, the non-stick pan (5 purchases) as the baseline against the
carbon steel pan (1 purchase); every figure in kg CO2e. These rows are required unit tests.

| Case | Baseline per unit | Baseline horizon | Option horizon | CO2e avoided |
|---|---|---|---|---|
| Separated | 4 to 6 | 20 to 30 | 8 to 11 | 9 to 22 |
| Overlapping | 2 to 4 | 10 to 20 | 1 to 15 | missing: the ranges overlap |
| Wholly above | 1 to 1.5 | 5 to 7.5 | 8 to 11 | missing: not below the baseline |

| Baseline label | Option label | Label on CO2e avoided |
|---|---|---|
| Benchmark estimate | AI synthetic estimate | AI synthetic estimate |
| AI synthetic estimate | Published figure | AI synthetic estimate |
| Published figure | Benchmark estimate | Benchmark estimate |
| Published figure | Published figure | Published figure |

## CO2e for scale

CO2e avoided, where it stands, gains a comparison anyone can picture, in kilometres in an average
new car, with the car figure's basis and source (`CO2E_FOR_SCALE` in `wording.py`). Only beside the
difference, never beside an option's own total: the difference is what a shopper acts on. It keeps
the line's confidence label.

Kilometres are kilograms × 1,000 ÷ 96.7 g CO2 per km, the average new car registered in the EU,
Norway and Iceland in 2025 (`CAR_CO2_GRAMS_PER_KM` in `config.py`, with its source: European
Environment Agency, June 2026, provisional until manufacturers have reviewed it). That is a test
(WLTP) value that counts the tailpipe only and averages in electric cars, so it gives more kilometres
per kilogram than a real drive would, which makes the difference look larger. It also sets
cradle-to-gate kg CO2e against tailpipe g CO2. So it is for scale only, not an equivalence, and the
line states that basis; the source it names is the car figure's alone, as the range is the app's own
estimate. The car chosen matters: about 2.5 times against the US EPA's average petrol car, about 244
g/km. The low end rounds down and the high end up, from the unrounded kilograms, to tens of km and
from 1,000 km to two significant figures. Under 10 km at the high end the comparison is left out
(`car_kilometres` in `calc/display.py`). Not used: trees, whose estimates run from 10 to 40 kg a year and which read as
offsetting (`eu_market.md`, "Environmental claims"), and phone charges, which depend on the grid.

These rows are required unit tests, in kg CO2e and km.

| CO2e avoided | Shown |
|---|---|
| 10 to 30 | 100 to 320 km |
| 5 to 37 | 50 to 390 km |
| 9.67 to 19.34 | 100 to 200 km |
| 0.1 to 0.967 | 0 to 10 km |
| 0.1 to 0.96 | left out |
| 150 to 300 | 1,500 to 3,200 km |

## CO2e of a model estimate

A tier 3 estimate (`lca.md`) is computed here from its inputs: the model gives each material's
mass and emission factor range and the manufacturing and assembly range, and code does the sum
(`docs/adr/0006-tier-3-returns-factors-code-multiplies.md`).

| Figure | Definition |
|---|---|
| Sum, low end | `sum(mass_kg * factor_low) + manufacturing_low` |
| Sum, high end | `sum(mass_kg * factor_high) + manufacturing_high` |
| Range | The sum when `high >= spread * low`; otherwise widened around the geometric midpoint to `sqrt(low * high / spread)` to `sqrt(low * high * spread)`, so high is exactly `spread` times low |

The spread is 2 (`LCA_MIN_SPREAD` in `config.py`; why 2 is in `lca.md`). It applies to the
total, not to each input: materials whose factors each span more than 2x can still give a
total under 2x when manufacturing is a narrow range.
Widening moves both ends, so the low end can fall below the low end of the sum (8 becomes 6 in
the third example below); that is intended. The range is a floor on the spread, not a
confidence interval, so it is never called a likely range.

Worked examples, factors in kg CO2e per kg, every figure in kg CO2e. These rows are required unit
tests.

| Case | Materials | Manufacturing | Sum | Range |
|---|---|---|---|---|
| At 2x | 1.5 kg at 2 to 4 | 1 to 2 | 4 to 8 | 4 to 8 |
| Above 2x | 1 kg at 1.5 to 4 | 0.5 to 1 | 2 to 5 | 2 to 5 |
| Below 2x | 2 kg at 3.5 to 4 | 1 to 1 | 8 to 9 | 6 to 12 |
| Materials over 2x, total under | 0.5 kg at 1 to 3, and 0.25 kg at 2 to 6 | 11.5 to 13 | 12.5 to 16 | 10 to 20 |

**Weight scaling.** When the linked product's page states a weight, the masses the model assumed
for bulk materials are scaled so that all masses add up to that weight. A sourced mass and the
mass of a separate component (electronics, a motor, a battery) are never scaled, assumed or
not. The scale is `(stated weight - fixed masses) / assumed bulk masses`. It is applied only when
it lies from 0.5 to 2, both included (`WEIGHT_SCALE_WINDOW` in `config.py`); otherwise, or when
there is no assumed bulk mass, every mass is kept and the LCA agent says so in the trail. A
scaled mass keeps its `model_estimate` source.

Worked example, a kettle: a stainless steel body of 0.6 kg and a polypropylene housing of 0.2 kg,
both assumed, and a heating element of 0.2 kg, an assumed separate component. A pan: a carbon
steel body of 1 kg stated on its page and a beech handle of 0.2 kg, assumed. These rows are
required unit tests.

| Product | Stated weight | Scale | Masses after |
|---|---|---|---|
| Kettle | 1.4 kg | 1.5 | body 0.9, housing 0.3, element 0.2 |
| Kettle | 1.8 kg | 2 | body 1.2, housing 0.4, element 0.2 |
| Kettle | 0.6 kg | 0.5 | body 0.3, housing 0.1, element 0.2 |
| Kettle | 2.2 kg | 2.5, outside | kept: body 0.6, housing 0.2, element 0.2 |
| Kettle | 0.5 kg | 0.375, outside | kept |
| Pan | 1.3 kg | 1.5 | body 1 (sourced, untouched), handle 0.3 |

## Changing the assumptions

The user can change the lifespan of any option, the horizon and the uses per year. Recalculation
is a pure function from options plus assumptions to a new comparison: no agent runs, no model is
called, nothing is fetched. The API exposes it so the frontend never does this math itself.

Assumptions hold only the horizon, the uses per year and per-option lifespan overrides. A product
option keeps its own sourced lifespan untouched; the lifespan used is the override when there is
one, otherwise the option's. A value the user set is therefore always marked, and restoring the
estimate is removing the override. Recalculation returns the new comparison and the new evidence
summary together, because a user-set lifespan changes the counts.

The API takes the complete assumptions within bounds set in `config.py`: a horizon of 1 to 30
years, 1 to 3,650 uses per year, and a lifespan override of 0.1 to 100 years
(`service_architecture.md`, "Errors"). It recalculates with the request's budget and the default
baseline, as the report itself was, and saves nothing.

## Rules

- **Money is `Decimal`.** Round only when formatting for display, never in between.
- **Unknown stays unknown.** A missing or non-positive lifespan or price gives a missing result
  for that option, with a reason. Never divide by zero and never substitute a default.
- **Unknown baseline id is an error.** A baseline named by the caller must be one of the
  options; otherwise `compare` raises `ValueError`. Models already reject a zero or negative
  lifespan, so the missing-result rule above guards values built without validation.
- **A set is one unit.** A product option sold as a set ("pan set", "screwdriver set") has one
  price, one lifespan and one footprint. Nothing is computed per piece.
- **Ranges stay ranges.** CO2e is carried as low and high end to end; do not collapse it to a
  midpoint.
- **Lifespan longer than the horizon** means one purchase. Horizon cost is then the full price,
  with no pro-rating; cost per year still uses the full lifespan. Both figures are shown.
- **Functions take plain values and return new models.** No function reads configuration or
  mutates its arguments.

## Display rounding

Every figure is computed unrounded and rounded only as it is written for display, once, in
Python: the page shows the words the API sends (`docs/adr/0008-api-sends-finished-lines.md`), so
it rounds nothing. `euros()`, `years()` and `kilograms()`, which writes masses and CO2e, are in
`calc/display.py`.

- **A single value rounds half up**, then drops ".00" or ".0": €0.125 is "€0.13", €12.995 is
  "€13", €12.50 stays "€12.50", and 2.96 years is "3". Money is to the cent, years to one decimal,
  masses and CO2e to two significant figures.
- **A positive amount under €0.005**, which would show as €0, shows "under €0.01"
  (`wording.UNDER_A_CENT`). Zero shows "€0".
- **The ends of a range round outward**, the low end down and the high end up, so the range shown
  holds the range computed: an option's CO2e, CO2e less than the baseline, and the typical
  lifespan of a type (1.25 to 2.25 years is "1.2 to 2.3"). A mass is a single value.
- **The trail's weight scale** rounds half up to two decimals without trailing zeros; a scale
  outside the window rounds away from it, so it never shows as the bound it is past (2.004 is
  "2.01, outside 0.5 to 2").
- A word that follows a number agrees with the number shown: 0.96 years is "1 year".

The edge cases below are required unit tests of the formatters.

| Value | Shown |
|---|---|
| €0.004 | "under €0.01" |
| €0.005 | "€0.01" |
| €0.125 | "€0.13" |
| €2.675 | "€2.68" |
| €9.996 | "€10" |
| €12.995 | "€13" |
| 0.04 years | "0" |
| 0.96 years | "1" |
| 2.25 years | "2.3" |
| 2.96 years | "3" |

## Evidence summary

The line at the top of a report is computed here, by counting, from the options and LCA results:
how many options have a sourced lifespan, and how many footprints are published (tier 1),
benchmark (tier 2), model estimates (tier 3) or missing. A value the user set counts as set by
the user, not as sourced. The function returns counts; formatting them into a sentence is
presentation. No model writes or adjusts this line.

## Known simplifications

State these in the README and, briefly, in the UI.

- No inflation, discounting or price changes: a replacement costs today's price.
- Consumables are included when a sourced yearly cost was found. Energy and water use and
  end-of-life are not included, which matters for appliances; requests classified as
  energy-heavy carry a caveat saying so.
- CO2e covers the item from cradle to gate, its materials and its manufacturing (for a model
  estimate, "cradle to gate: materials and manufacturing"; `lca.md`). It leaves out transport,
  packaging, the energy used in use, end of life and the item's consumables; for an appliance
  the energy used in use can be the largest part.
- Lifespan is a single estimate per option, with its source.
- The kilometres for scale set cradle-to-gate kg CO2e against a car's tailpipe test figure, electric
  cars averaged in ("CO2e for scale"): for scale only, not an equivalence.

## Open questions

Ask before deciding.

- Used items: which lifespan applies, the remaining life or the full life of the product?
- Used items: what CO2e is attributed. The candidate is the cut-off approach: a used item
  carries no added manufacturing CO2e (its manufacturing belongs to its first owner), and the
  report never claims that buying used "saves" CO2e, since buying used does not necessarily stop
  a new item being made. So a used item gets no CO2e avoided figure (missing, with its own
  reason), and is not shown as "0 kg CO2e", which would be a figure with no source and no
  confidence label; it gets a statement instead, such as "manufacturing attributed to the first
  owner (cut-off approach)". What is left out is named in full: shipping (often cross-border),
  packaging and any parts replaced before resale. Still open: whether replacements over the
  horizon are assumed new or used, which ties in with the remaining-life question above. Before
  it is built, `docs-researcher` checks it against the standards (ISO 14044, the GHG Protocol
  and PEF rules on allocation for reuse) and `lca-reviewer` reviews it.
- Whether to add energy and water costs for categories where they dominate.
- Sets: which lifespan a mixed set has (the first piece to fail, or the last), and whether the
  options for a set request must be sets of a comparable number of pieces. Until this is
  settled, a set request gets only sets, each with a quoted piece count on the product option
  (`option_research.md`, "What a product page sells").
- Energy-heavy requests: whether savings and CO2e avoided should be shown at all, since leaving
  out energy can change the order of the options. Today they are shown, and the caveat says so.
- Rent or borrow: whether to add a note for low usage when no rental price was found, and at how
  few uses a year.
