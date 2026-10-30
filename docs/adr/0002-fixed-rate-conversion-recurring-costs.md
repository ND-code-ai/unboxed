---
status: accepted
---

# Fixed-rate conversion for recurring costs only

Partly replaces `0001-euro-only.md`. Everything in 0001 still holds except where this ADR says
otherwise.

Web search in English often finds a product's running costs in dollars or pounds ("filters cost
$15 every 6 months"). Under 0001 such a cost is dropped, so the option's cost per year leaves out
consumables even though a source was found. A recurring cost is a smaller, already approximate
part of the cost per year, so converting it at a fixed rate is honest if the result is labelled.
Prices that decide the outcome are a different matter: a converted US or UK price is not what a
buyer in the Netherlands pays (VAT, range and pricing differ), so they stay euro only.

## Decision

| Value | Other currency found |
|---|---|
| Recurring cost of an option (consumables, parts) | Converted to EUR at a fixed rate, labelled as converted |
| Typical yearly cost on a recurring-cost factor | Converted to EUR at a fixed rate, labelled as converted in its line above the questions and on the report |
| Option price (new) | Not converted; as 0001: missing, with a warning |
| Budget | Not converted; as 0001: `budget_other_currency` |
| Used listing | Not converted; as 0001: dropped, with an `excluded` trail entry |
| Price on a pasted product link | Not converted; as 0001: missing, with a warning |

How the conversion works:

- **Fixed rates in `config.py`**, one per supported currency, each with the date and the source
  of the rate (the ECB euro reference rate of a stated day). Start with USD and GBP; an amount in
  any other currency is dropped as under 0001.
- **A pure function in `calc/`** converts an amount and currency code into EUR, rounded to the
  cent, or returns nothing for an unsupported currency. It runs at the edge, before the value
  reaches the cost figures, so `calc/` still works in one currency.
- **Labelled everywhere it shows.** The option's comparison row is flagged "recurring cost
  converted from <currency> at a fixed rate", beside the existing "recurring costs not found"
  flag. The trail keeps the original amount, the currency, the rate and its date.
- **Only for a sourced amount.** The original amount must be quoted from its source, as for any
  number from search; the conversion never applies to a model's guess.

The real fix for dollar results is better targeting, not conversion: searches for prices and
costs are aimed at the Netherlands (country boost, Dutch query terms, Dutch shops preferred), as
`data_sources.md` describes.

## Considered options

- **Dollar first, euro prices converted to dollars.** Rejected: the market is the Netherlands
  and the EU (eBay NL, DE and BE, EU energy prices, the energy label, EU claims rules, Digital
  Product Passports). A dollar display would either misstate what the user pays or need the
  whole market redone close to the deadline.
- **Convert every amount to euros at a fixed rate.** Rejected: a converted foreign price looks
  like a Dutch price but is not one, and the option price decides `within_budget`, the cost per
  year and the comparison.
- **Keep 0001 unchanged.** Rejected: it throws away sourced recurring costs that are close
  enough to be useful, and makes the comparison look cheaper than it is.

## Changing this later

The conversion function and the rate table are the seam. Live rates replace the table behind
the same function (a new external service, so ask first). Adding a currency is one row in the
table. Converting prices as well needs the `Money` type described in 0001, "Reversing this".
