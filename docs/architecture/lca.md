# Life-cycle estimates (LCA)

Read this when working on the LCA agent, the reference data in `src/shopper/data/`, or anything
that shows a CO2e figure.

## The cascade

Step down until a tier produces a result, then stop. Record which tier it was.

| Tier | Name | How | Label shown to the user |
|---|---|---|---|
| 1 | Direct match | Tavily search for the product's Environmental Product Declaration or the maker's sustainability report | "Published figure" |
| 2 | Benchmark | Materials and weight, multiplied by published emission factors from a local table of open data | "Benchmark estimate" |
| 3 | Model estimate | The large model gives each material's mass and an emission factor range, and a manufacturing and assembly range; code sums them and widens the total (`calculations.md`, "CO2e of a model estimate"; ADR 0006) | "AI synthetic estimate" |

## What every result carries

| Field | Meaning |
|---|---|
| `co2e_low`, `co2e_high` | Range in kg CO2e per unit. Never a single falsely precise number |
| `tier` | 1, 2 or 3 |
| `source` | URL for tier 1, dataset name and entry for tier 2, "model estimate" for tier 3 |
| `boundary` | What the figure covers, e.g. manufacturing only, or cradle to gate. Not called scope: that word is the request's classification. For tier 3 it is fixed by code: "cradle to gate: materials and manufacturing" |
| `inputs` | For tiers 2 and 3, one `LcaInput` per material: name, form, mass in kg, emission factor low and high in kg CO2e per kg, each with its source (a page can state a material and leave its form to the model), and whether it is a separate component (electronics, a motor, a battery). Mass and factor are above 0. Not called assumptions: those are the values the user can edit. The report lists name, form and mass on its "Built from:" line, never the factors |
| `manufacturing_low`, `manufacturing_high`, `manufacturing_source` | The manufacturing and assembly range in kg CO2e, with its source; all three or none. Always given for tier 3; tier 2 may have none (see the rules) |

## Rules

- **Tier 1 must be about this product or product line.** A figure for a different product is not
  a direct match; drop to tier 2.
- **Tier 2 arithmetic is code.** The agent extracts materials and weights; a function multiplies
  them by emission factors. The model does not do the multiplication.
- **Tier 3 arithmetic is code too.** The large model returns factors and masses, never a CO2e
  figure; code sums mass times factor plus manufacturing at each end
  (`docs/adr/0006-tier-3-returns-factors-code-multiplies.md`). A missing, zero or negative mass,
  factor or manufacturing range gives the option no result and the warning `co2e_unavailable`; it is never summed
  as zero.
- **Tier 3 is one call for every option** (`agents/lca/`). The large model returns one factor
  table for the report and, per option in the order given with its name echoed, its inputs
  pointing at that table and a manufacturing range, or a decline with its reason. Code matches
  entries by position; an entry that is missing, names another option or appears twice is a
  decline. The linked product's page materials and weight go in as numbered fixed inputs: an
  input that is one keeps the page's material name, form when stated, mass when stated, and
  the page as their source. A row pointing at anything else, the page's weight or a number the
  option does not list, is the model's own material, its pointer dropped: on 30 October that slip
  took the CO2e of whole reports. With a pointer dropped, masses summing to 1.5 times the page's
  weight or more are a decline, as a row may hold that weight. A check fails on a page material
  left out or given twice, a form
  the page states that differs from the factor row's, an input whose material and form are not
  its factor row's, a material and form given twice in the table, and a factor outside
  `LCA_FACTOR_BOUNDS` (0.05 to 500 kg CO2e per kg, against a slip of units). A factor covers
  the material as produced, before forming, which belongs to manufacturing; packaging is left
  out. A material's form is "typical", the mix of primary and recycled material it is usually
  made from as bought, unless the page states one ("recycled", "70% recycled"), which the
  factor row then keeps as written. The model declines only when it cannot tell the product or knows
  nothing of its materials; a set is estimated whole, as sold. Each decline, and each option
  whose inputs fail a check, gets its own `co2e_unavailable`; a failed call, or an estimate past
  `LCA_TIME_CAP_SECONDS`, gets one for the report. One trail entry per option names the tier
  and the model and says what was estimated or declined.
- **Tier 3 widens the range.** A model estimate must report a wider range than a benchmark would,
  and always carries its label. Code widens the total so that high is at least twice low, around
  its geometric midpoint (`LCA_MIN_SPREAD` in `config.py`). Why 2: there is no benchmark yet to
  measure a model estimate's error against, so the spread cannot be measured, and the rule above
  needs it wider than a benchmark's would be. 2x is a floor chosen for that, not a measured
  uncertainty (ADR 0006); revisit it once tier 2 exists and the two can be compared on the same
  options.
- **Masses follow a stated weight.** When the linked product's page states a weight, the masses
  the model assumed for bulk materials are scaled to it, within limits
  (`calculations.md`, "Weight scaling"); a sourced mass and a separate component are never
  scaled.
- **Tier 2's manufacturing line comes from an open dataset.** Never from the model. If no such
  row exists, tier 2's boundary is materials only, and the mixed-boundary rule below applies
  (ADR 0006).
- **Do not mix boundaries silently.** If two options have figures with different boundaries, say
  so in the report warnings.
- **No result is acceptable.** If no tier gives a defensible range, return none and add a warning.
  The option then has no LCA result at all; a result that exists always has a range, a tier, a
  source and a boundary.

## Tier 2 reference data

Tier 2 multiplies materials and weights by emission factors (kg CO2e per kg). The factors live in
a local table in `src/shopper/data/`, built from open datasets whose licences allow commercial
use with attribution. The app may be sold later, so non-commercial data is not acceptable.

| Dataset | Publisher | Licence | Use for | Caveat |
|---|---|---|---|---|
| GHG conversion factors, "Material use" | UK government (DESNZ) | Open Government Licence v3.0 | The default: metals, plastics, glass, wood, paper; primary and recycled; cradle to gate | UK, not EU; factors are per tonne |
| Base Carbone / Base Empreinte | ADEME (France) | Licence Ouverte 2.0 | Gaps in the default, and product-level factors where they exist | In French; confirm coverage of the category before relying on it |

Not used, and not to be added without asking:

- Idemat (CC BY-NC) and EXIOBASE: non-commercial licences.
- EU Environmental Footprint datasets: licence limited to official footprint studies.
- US EPA spend-based factors: US prices and economy, and a different method. When materials are
  unknown, tier 3 applies instead of a spend-based guess.
- Paid emission-factor APIs or datasets.

If a needed material is in neither dataset, do not invent a factor and do not reach for another
source: drop to tier 3 for that product and say so in the report warnings.

Rules for the table:

- One row per material and form (e.g. aluminium, primary), with: factor, unit, scope, dataset,
  dataset year, region, licence and source link. Convert per-tonne factors to per-kg in the
  table, not in code.
- Every factor is copied from the published file, never recalled from memory or estimated.
- Start with the materials common in household goods: aluminium, stainless steel, carbon steel,
  cast iron, common plastics, glass, cotton, polyester, wood.
- Copy only the rows needed, with attribution as each licence requires. Do not commit a whole
  dataset.
- **Prefer one dataset per comparison.** If two options in the same report use factors from
  different datasets, add a warning, because their boundaries differ.
- The `source` field of a tier 2 result names the dataset, year and row actually used.
- The table sits behind the tier 2 interface, so the data source can be replaced later without
  touching the agent.
