---
status: accepted
---

# LCA tier 3: the model returns factors, code multiplies

For an option with no published figure and no benchmark, the large model does not return a CO2e
range. It returns its inputs: one factor table per report (a range in kg CO2e per kg for each
material and form), each option's materials and masses pointing at that table, and a
manufacturing and assembly range per option. Code copies each factor into the option's inputs,
computes `co2e_low` as the sum of mass times low factor plus the low manufacturing figure (the
same for the high end), and then widens the total to at least the minimum spread (high at least
twice low, around the geometric midpoint).

Why: numbers shown to the user are computed in code (rule 1), and an agent extracts rather than
computes (`agents.md`, "Agent contract"). One factor table per report gives the same material
the same factor in every option, so a difference between options comes from the products, not
from noise between estimates. The inputs are visible ("Built from:" on the report), and tier 2
fills the same model with factors from its local table instead of the model's, so tier 2 plugs
in at the factor without changing the arithmetic.

The 2x spread is a floor, not a measured uncertainty: there is no benchmark yet to compare
with, and lca.md requires a model estimate to be wider than a benchmark would be. Revisit it
once tier 2 exists and the two can be compared on the same options.

Decided in the interview for task 1.9.1 (split into 1.9.1, 1.9.6, 1.9.7 and 1.9.8).

## Considered options

- **The model returns a CO2e range per option.** Rejected: the number shown would be the
  model's, the inputs behind it could not be checked, and two options could rest on different
  unstated factors for the same material.
- **Factors per option instead of per report.** Rejected: the same material could get a
  different factor in each option of one comparison.

## Consequences

- The boundary of a tier 3 result is fixed by code: "cradle to gate: materials and
  manufacturing". Tier 2's manufacturing line must come from an open dataset, never from the
  model; if no such row exists, tier 2's boundary is materials only and the mixed-boundary
  warning applies. The tier 2 tasks decide.
- A mass or factor that is missing, zero or negative gives the option no result and a warning;
  it is never summed as zero.
