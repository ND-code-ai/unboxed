---
status: accepted, partly replaced by 0002 (recurring costs)
---

# Euro only, no currency conversion

Every amount of money in the app is in EUR, held as a bare `Decimal` with no currency attached to
the amount. Prices in other currencies can turn up (a listing from a non-euro marketplace, a
pasted product link, a budget stated in pounds), and converting them would need an exchange-rate
service, a dated and sourced rate on every converted figure, and an "approximate" label wherever
one is shown. That is too much for a three-week solo build whose first marketplaces (`EBAY_NL`,
`EBAY_DE`, `EBAY_BE`) are all in euro countries, so the app does not convert at all.

## What happens to a non-EUR amount

It is never reinterpreted as euros and never converted. The value is left missing and the report
carries a warning that says what was left out and why.

| Where it turns up | Result |
|---|---|
| Budget in the request | The budget is missing; the request runs as if no budget was given, with the warning `budget_other_currency` |
| Price on a pasted product link | The product option's price is missing, so its comparison figures are missing with a reason, with a warning |
| Used listing | The listing is dropped, with a warning and an `excluded` trail entry that names it and links to it |

## Considered options

- **A `Money` type (amount and currency) on every price, with conversion.** Rejected for now: it
  needs a rate source, which is a new external service, and it promises a display-currency choice
  that nothing in the roadmap builds.
- **A `Money` type without conversion.** Rejected: it lets a non-EUR amount reach `calc/`, which
  would then have to refuse mixed currencies everywhere.
- **Keep the non-EUR listing as display text only.** Rejected: it would be shown beside listings
  that were checked against the budget while itself unchecked.

## Reversing this

The cost is in the number of fields, not in the design. To add conversion later:

1. Replace the EUR `Decimal` price fields in `src/shopper/state.py` with a type that carries the
   amount and its currency. The request, product option and listing each have a `currency` field
   fixed to `EUR` today, which marks the places to change.
2. Add an exchange-rate tool behind an interface in `tools/`. This is a new external service and
   needs approval first.
3. Convert at the edge, before anything reaches `calc/`, so the math keeps working in one
   currency. Store the rate, its date and its source with each converted value, and show it as
   approximate.
4. Replace the three behaviours in the table above; each one has its own warning code, which
   finds every place a value is dropped today.
