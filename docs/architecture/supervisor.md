# Supervisor: parsing the request

Read this when working on how the input becomes a request: the scope classification, the
category, the budget, and what happens when the user made a mistake. The graph, the data model
and the rules every agent follows are in `agents.md`.

The supervisor is three graph nodes: `parse_request` turns the input into a request, `read_link`
reads a pasted link (`agents.md`, "The graph"), and `assemble_report` builds the report at the end.
This doc covers the first. Assembly is plain
code with no model; it is in `agents.md` ("Data model", "One report shape").

Parsing itself is one function in `agents/supervisor/agent.py` that knows nothing of the graph: it
takes the input, the model client and a tier (small unless told otherwise) and returns the
request, its warnings and its trail entries, or raises one of the errors described below. The
`parse_request` node only calls it and writes the three results into the state.

## What code does and what the model does

| Step | Done by |
|---|---|
| Refuse over-long input; reject empty input | Code, before any model call |
| Find the product URL | Code |
| Name the category, classify the scope, point at the budget phrase and judge its currency | Small model |
| Read the amount and currency from the budget phrase | Code (`calc/budget.py`) |
| Repair output that cannot be a request | Code |
| Name the category again when the first one fails the form check | Small model, asked once more by code |

**Extraction schema.** The model fills five fields and nothing else: `category` (optional),
`scope`, `budget_phrase` (optional, copied exactly as written), `budget_amount` (optional) and
`budget_currency` (`eur`, `other`, `none_stated` or null; see "Reading the phrase"). Like the
other four it is required and nullable in the schema, because the schema is sent as strict. It
returns no URL and no stated requirements. Anything else the user wrote
("for induction", "it is a gift") reaches the other agents through the request's original text,
which is kept verbatim; the brief agent records requirements from it (see `reading_answers.md`).

**Temperature.** The supervisor's call is made at temperature 0, to keep the scope and category
of the same input as steady as the model allows. It does not make them identical every time:
the models reason before answering and the reasoning varies (`docs/findings/task_1.5.md`). The category is a cache key, so a category that varies costs a cache miss.

**Input the model never sees.**

- Empty or whitespace-only input gets the scope `unclear`, with a trail entry giving the reason.
- Input with two or more different URLs gets the scope `several_products`, with a trail entry.
  The same URL pasted twice is one URL, and punctuation after a URL is not part of it.
- Input over 2,000 characters is refused before a request exists: parsing raises a typed error
  and there is no report. It is not `unclear`, because the message for `unclear` would not tell
  the user that length was the cause. The words are in `wording.py`.

**The URL.** Code takes the first `http` or `https` URL as the product URL. The text goes to the
model with the URL still in it, so the model can take the category from the URL.

**Language.** The input may be in any language. Every value the model returns is in English,
except the budget phrase (see `docs/eu_market.md`, "Market").

**When the model call fails.** A timeout, a service error or output that is invalid twice raises
a typed error from the graph. No report exists, because nothing has run. The CLI prints one line
and exits with a non-zero status; the API returns an error status. It is not reported as
`unclear`: that would tell the user their text could not be understood, which is not what
happened. The same holds when the second try for a category fails this way (see "Repairs").

## Scope

While parsing, the supervisor sets `scope` to one of:

| Scope | Meaning | Effect |
|---|---|---|
| `tuned` | Cookware and kitchen tools; portable plug-in household appliances; hand, power and garden tools | Full flow |
| `general` | Any other durable product: furniture, electronics, bicycles, bags, toys | Full flow, plus the "not tuned" caveat |
| `energy_heavy` | Household appliances whose energy or water use is a large part of their cost (defined below) | Full flow, plus the energy caveat |
| `clothing` | Garments and footwear worn on the body. Bags, bedding and other textiles are `general` | Full flow, plus the clothing caveat |
| `not_a_product` | Anything the app does not cover: things that are not durable physical products (food and drink, consumables used up in use such as shampoo, batteries or printer ink, services, subscriptions, digital goods, living things, property), and motor vehicles | Decline politely; no other agent runs |
| `several_products` | The input names more than one product (see "One product") | Ask the user to name one; no other agent runs |
| `unclear` | The input could not be understood | Ask the user to rephrase; no other agent runs |

Apart from motor vehicles, the classification never blocks a durable product; it only selects
caveats. Caveat wording is in `wording.py`.

**Motor vehicles are out of scope.** A vehicle driven by an engine or motor and registered for
road use (a car, a motorcycle, a moped, a motor scooter) is declined as `not_a_product`, although
it is a durable product: fuel, tax and insurance are most of what it costs, and none of them is
in the figures. Bicycles, e-bikes and electric kick scooters are `general`. Tools with an engine
(a petrol lawn mower, a chainsaw) stay `tuned`.

**Precedence.** When a request clearly fits more than one scope, the first in this order wins:
`unclear`, `several_products`, `not_a_product`, `energy_heavy`, `clothing`, `tuned`, `general`. A
scope that carries a caveat wins over `tuned`, because a missing caveat is the worse mistake: a
portable electric heater is `energy_heavy`, not `tuned`.

**When unsure.** Precedence settles a request that fits two scopes; it does not settle doubt.

- Unsure between `tuned` and `general`: choose `general`.
- Unsure between `not_a_product` and a scope that runs: run it, as `general`. A wrong decline
  leaves the user with nothing to do next.
- A durable product that uses consumables is the durable product: a printer or an electric
  toothbrush runs; printer ink or brush heads alone are declined.

**What is energy-heavy.** These household product groups:

- refrigeration: fridges and freezers;
- dishwashers;
- laundry: washing machines, washer-dryers and tumble dryers;
- built-in and freestanding cooking appliances: ovens, hobs and range hoods;
- space and water heating of any kind, including portable electric heaters;
- air conditioning, including portable air conditioners.

The starting point is the list of product groups that carry an EU energy label under Regulation
(EU) 2017/1369, as published by the European Commission
(https://energy-efficient-products.ec.europa.eu/product-list_en, read 2026-10-11). The scope
departs from that list in three places, on purpose:

- **Added: electric space heaters and hobs.** Both have ecodesign requirements but no energy
  label (the labelling rules for local space heaters exclude electric ones). They are included
  because heating and cooking are among the largest energy uses in a home.
- **Left out: displays, light sources, smartphones and tablets.** They carry a label and are
  `general`, as are computers. This is a deliberate cut to keep the scope to large household
  appliances; energy use is not in the figures for these either.
- **Left out: tyres.** They carry a label and are not a household appliance.

Not energy-heavy, and `tuned`: microwaves, countertop ovens, air fryers, kettles, hair dryers and
vacuum cleaners. None of them is in a labelled group; microwaves and small ovens are outside the
oven rules.

**A request that does not run carries no message of its own.** The report holds only the scope,
and the CLI and the page apply the wording from `wording.py` when it is shown, the
same way as for caveats.

### No lookup table

Scope and category are the model's judgement against the definitions above. Do not add a
product list, lookup table or taxonomy without asking. The prompt's worked examples illustrate
the definitions; they are not a list to match against. To keep them from becoming one:

- **At most three examples per scope**, each with its reason from the definition ("a fridge:
  refrigeration is an energy-heavy group"), not only its verdict.
- **A failed evaluation case is fixed by rewording a definition**, never by adding that product
  to the prompt. If an example is added for another reason and names a held-out product, that
  case is replaced with a new one.
- **Held-out products stay out of the prompt**, and a test enforces it (see "Evaluation").

### Evaluation

A set of cases checks that the model applies the definitions. It is used only in testing; the app
never reads it. The cases live in `tests/eval/` and nowhere else: this doc names the boundaries
they cover but not the products, so that drafting the prompt from this doc cannot leak them.

About 28 cases, each tagged with the rule it tests, so a failure points at a definition:

| Group | Cases | What it holds |
|---|---|---|
| Core | 5 | One clear product for each scope that runs, plus the frying pan. These may appear in the prompt |
| Held-out boundaries | About 14 | One case on each side of the energy line, the clothing line, the durable-or-consumable line and the one-product line; the departures and exclusions named under "What is energy-heavy"; a motor vehicle and a near neighbour that runs. At least three are in Dutch or German |
| Does not run | 3 | `not_a_product`, `several_products`, `unclear` |
| Category | 3 | A synonym pair, one of them not in English, that must give the same category; a name that holds a digit |
| Budget currency | 4 | A currency on no list (a misspelt one and one named in full), and a word after the amount that is not a currency (two wordings of "and no more"). Checks `budget_currency` only |

Each case gives the input, the expected scope, whether it is borderline, the product term to
keep out of the prompt if it is held-out, and the expected category where that is unambiguous.

How it runs and passes:

- It is a live test (marked `live`, so it spends credits only when asked), run at the
  supervisor's own temperature and tier.
- It runs twice. Both runs must return the expected scope, and the same scope as each other,
  for every case.
- Both runs must return the expected category on every case that states one: the frying pan,
  the synonym pair and the other cases whose name is unambiguous. On the remaining cases the
  category may differ between runs. The models are not repeatable at temperature 0 and choose
  between near-synonyms ("clothes dryer", "tumble dryer"); the cost is a miss in the brief
  cache, not a wrong result (`docs/findings/task_1.5.md`).
- A case may list other names of the same category that also pass, such as a digit written
  out ("three dimensional printer" for "3d printer"); a wider category ("printer") still fails.
- `tuned` returned as `general` is accepted only on a case marked borderline. A clear tuned
  product, the frying pan among them, must return `tuned`.
- A caveat scope (`energy_heavy`, `clothing`) returned as `tuned` or `general` always fails, as
  does a product that runs returned as `not_a_product`.
- Both runs must give the expected budget outcome on the budget currency cases: the
  `budget_other_currency` warning, or a euro ceiling with no warning.
- A timeout or service error marks the case "not evaluated", and the run is repeated; it is not
  a wrong answer.
- Run it again whenever the prompt or the small tier's model changes.
- If the small model fails it, run it on the medium tier before changing the definitions, and
  record the result in `models.md`: `uv run pytest -m live tests/eval --supervisor-tier medium`.

An offline test in the default run, which spends nothing, fails when the product term of a
held-out case appears in the prompt, compared without regard to case.

**What the offline tests prove.** Tests with a fake model reply prove what code does with a
reply: repairs, the budget, routing, trail entries. They prove nothing about how the model
classifies. Only the evaluation and a live run of the CLI do.

### One product

One category name is one product. Two category names, or two named models, are more than one
product, and the scope is `several_products`.

| Input | Outcome |
|---|---|
| "a frying pan and a spatula" | `several_products`: two categories |
| "a frying pan or a sauté pan" | `several_products`: two categories |
| "Tefal X vs WMF Y" | `several_products`: two named models |
| "a pan set" | One product; the category is "pan set" |
| "a drill with a spare battery" | One product; the category is "drill", and the spare battery is a stated requirement |

A product whose own name joins two words ("washer-dryer", "fridge freezer", "salt and pepper
mill") is one product.

A set is one unit everywhere after this: one price, one lifespan, one footprint, never per piece
(see `calculations.md`, "Rules"). An accessory is never part of the category; it is a `stated`
answer, like "for induction".

## Category

The supervisor also names the category: the most common everyday English name of what the user
is looking for, generic, singular and lower case ("frying pan"), whatever language the request
is in.

- **What is not part of it.** Brand, material and size, unless one of them makes it a different
  product: "cast iron frying pan" and "skillet" are both "frying pan". A noun that exists only
  in the plural stays plural ("jeans", "scissors").
- **A power source the user names is part of it.** "cordless", "corded" and "petrol" stay:
  "cordless drill" stays "cordless drill". The category fills the listing search, and a corded or
  pneumatic drill is no option for a cordless request (decided in task 1.10). A request that names
  none gets none: "a drill" is "drill".
- **Requirements are not part of it.** "For induction" becomes a `stated` answer (see
  `reading_answers.md`), not part of the category.
- **Two uses.** It is shown back to the user above the questions and it is the key of the brief
  cache. With no lookup table, one product can still get two names; the rules above and
  temperature 0 reduce that but do not prevent it, and the evaluation checks a synonym pair.
- **Normalised and checked by code.** Code trims it, lower-cases it and collapses its
  whitespace. A category of more than four words is not a category. Nor is one with more than
  one digit, or with a digit in a word that has no letter: see "Repairs". So "3d printer" and
  "4k monitor" pass, and a bare number ("frying pan 28 cm", "iphone 15"), an attached size
  ("28cm frying pan") and a model number ("wh1000xm4 headphones") do not. The check exists
  because the category is a cache key and fills the web search queries, so it must hold nothing
  the user typed beyond the kind of product. It cannot tell a one-digit size or model name
  ("5l backpack", "galaxy s9") from "4k"; those pass, at the cost of a cache miss and a
  narrower search, and keeping them out is the prompt's job, as singular and English are.
- **Ambiguous requests get the likeliest meaning.** The user corrects it from what is shown
  back; there is no clarifying question.
- **Missing when scope is `unclear` or `several_products`.** For `not_a_product` it is filled
  when it was understood, so the decline can name it.
- **Pasted link with no text.** The supervisor takes the category from the URL if it can.
  Otherwise it stays missing until the page has been read. The name read from the page then
  goes to the model with the same prompt (`read_product_name`), and the graph replaces the
  request with a copy that has the category and the scope of that reading; the budget, the text
  and the link stay. The form check and its second try apply as above. A reading that gives no
  category leaves the request running without one, shown as "the product at your link"; so
  does one with the scope `unclear`, which becomes `general`, because the page named a product.
  An `unclear` request with a link is read the same way (`agents.md`, "The graph"). A failed
  call raises the same typed error as the parsing call (see "When the model call fails").

**Repairs.** Output that cannot be a request is repaired by code, and each repair writes a trail
entry. Only a category that fails the form check is retried, once.

- A category on an `unclear` or `several_products` reply is dropped, with no second try.
- A category that fails the form check gets a second try: the model is asked once more (one
  structured call, which like any other may repeat itself once on invalid output), with
  the same input and the same prompt plus a correction that names the category it gave and the
  rule that one broke (`CATEGORY_CORRECTION` in `agents/supervisor/prompt.py`). Only the
  category of the second reply is used; the scope and the budget stay those of the first. The
  trail entry reads `Asked again for the category: "frying pan 28 cm" became "frying pan"`.
- A second try that fails the form check again, or gives no category, drops the category as
  before. The trail entry's reason says what the second try gave.
- A second try whose model call fails raises the same typed error as the first call (see "When
  the model call fails"). Dropping the category instead would, with no link, end as `unclear`
  for a service failure.
- A scope that runs with no category and no URL becomes `unclear`.

The second try shows the user nothing new. They confirm the category the usual way, from what
is shown back above the questions. A category that passes the form check makes one model call.

## Budget

A budget that cannot be used is left missing, with a warning, and the request runs as if no
budget was given. It is never reinterpreted: "5o euro" is not read as 50.

| Stated budget | Warning code |
|---|---|
| Cannot be read as an amount ("5o euro") | `budget_unreadable` |
| In a currency other than EUR (`docs/adr/0001-euro-only.md`) | `budget_other_currency` |
| Zero or negative | `budget_not_positive` |

When more than one applies, the first in the table wins: "£0" is `budget_other_currency`. Each
message quotes the phrase the user wrote; the wording is in `wording.py`.

No budget is read for a request that does not run.

### Finding the phrase

The model's only job is to point at the phrase: the shortest part of the input that holds the
amount and its currency marker, or the number alone when there is no marker. Code then does four
things.

1. **Find it loosely.** The phrase and the input are compared after the normalisation every
   copied phrase gets (`find_phrase` in `agents/shared/phrases.py`, shared with a stated
   requirement's phrase and the quote check): case, whitespace (a non-breaking space counts as
   a space), curly quotes, the kind of hyphen or dash, and punctuation at the phrase's two ends
   when it is not found with it. The matching part is taken from the input itself, so what is
   quoted later is what the user wrote.
2. **Widen it to whole tokens.** A phrase that starts or ends inside a run of digits or letters
   is widened to the whole token: "50" inside "€150" becomes "€150". Then one token to each side
   is added when it is a currency marker: "40" from "40 pounds" becomes "40 pounds". A minus sign
   attached in front is added too, so "50" from "budget -50" becomes "-50".
3. **Read it** with `read_budget` (see below).
4. **Compare with the model's amount.** When the two differ, the budget is left missing with
   `budget_unreadable`, quoting the widened phrase. Code's reading is not trusted over the
   model's here: a disagreement means the phrase holds something else, as in "28 cm pan under
   20 euro".

A phrase that is still not in the input after step 1 means no budget and a trail entry, with no
warning, because there are no words of the user's to quote. When the model returns no phrase
there is no budget and no warning; code does not look for one, so "my €30 pan broke" is not a
budget.

### Reading the phrase

`read_budget(phrase)` in `calc/budget.py` is a pure function that returns a `BudgetReading`: the
amount or the warning code, whether the amount came from a range, and whether another currency
was the model's judgement (see "Words on no list"). It reads only numerals and currency markers; every other word is ignored, in any
language. The list of other currencies is a constant beside it.

| Phrase | Result |
|---|---|
| One number, with a euro marker or none ("50", "€50", "50 euro", "hasta 50 euros") | That amount, as a ceiling |
| A marker attached to the number ("50eur", "50€", "40usd", "40kr") | Split first, then read as the two tokens |
| A trailing ",-" or ".-" ("50,-") | Ignored |
| Two numbers, with or without a hyphen between them ("30-50", "tussen 30 en 50") | The higher one; the trail notes it |
| A leading minus ("-50") | Negative, so `budget_not_positive` |
| Thousands and decimals ("1.000", "1 000", "1.234,56", "49,99") | A separator followed by exactly three digits is thousands; by one or two digits, decimals |
| Any other separator pattern ("1.2345"), or three or more numbers | `budget_unreadable` |
| A marker from the list of other currencies ("£40", "40 dollar", "40 quid", "400 kr") | `budget_other_currency` |
| A token mixing digits and letters that is not a number with a marker ("5o", "50k") | `budget_unreadable` |
| No numeral at all ("fifty", "vijftig"), or digits other than 0 to 9 | `budget_unreadable` |
| Zero or negative | `budget_not_positive` |

**Other currencies.** The list is fixed and each entry is tested:

- every three-letter ISO 4217 code of a currency other than EUR; the fund codes and the codes
  for metals and testing (such as CHE, XAU, XXX) are left out. Many codes are also words ("cup", "pen",
  "try", "all"), so a code counts in upper case anywhere in the phrase ("USD 40"), and in lower
  or mixed case only directly after the number ("40 usd", "40usd");
- the currencies of EU countries outside the euro area, with their symbols and names: Polish
  złoty (zł), Swedish and Danish krona and krone (kr), Czech koruna (Kč), Hungarian forint (Ft),
  Romanian leu (lei);
- pound (£), dollar ($), Swiss franc (CHF, Fr.), Norwegian krone, yen (¥) and lira (₺), with
  their names in English, Dutch and German, singular and plural;
- the slang "quid" and "bucks".

**Words on no list.** A list of currencies is never complete ("10 dolla", "10 pesos"), and a
rule that warns on any unknown word after the amount misreads plain phrasing ("50 max", "50 and
not higher"). So the lists are a floor and the model judges the rest, through its
`budget_currency` field. Code decides in this order:

1. A marker from the list of other currencies: `budget_other_currency`, whatever the model said
   and also when the phrase holds a euro marker too ("€50 (about $55)").
2. Otherwise a euro marker in the phrase: read as euros, whatever the model said.
3. Otherwise the model's `budget_currency`: `other` gives `budget_other_currency`; `eur`,
   `none_stated` or no value is read as euros.

`read_budget` takes the model's judgement as an optional second argument and stays a pure function, so the
order is unit-tested with the judgement given. The guarantee is therefore in two parts: a budget
with a listed other-currency marker is never read as euros; any other currency rests on the
model's judgement, which the evaluation checks ("Budget currency"). When the model misjudges an
unknown currency as euros, the result is a budget in the wrong unit with no warning; when it
misjudges a plain word as a currency, the budget is left missing with a warning.

A budget that parses but is mistyped (€5 for €50) cannot be caught here, and there is no
threshold for an implausible budget. It surfaces later as the `nothing_within_budget` warning
from `calc/` (see `calculations.md`).

## Trail

`parse_request` writes:

- one `decided` entry per parse ("Understood as: frying pan; scope tuned; budget €50"), with the
  tier and model;
- one `excluded` entry for a budget that was dropped, with the warning code as its reason and
  the phrase in its summary; when the other currency was the model's judgement and not a listed
  marker, the reason reads `budget_other_currency (judged by the model)`;
- one `decided` entry each time code overrode or repaired the model's output, the second try
  for a category included, whether it gave a category or not.

`assemble_report` writes none, because it decides nothing.

## Corrections

A request is fixed once its session starts. To correct a mistyped product or budget, the user
starts a new session with their text pre-filled. That is cheap: starting a session runs only the
supervisor and the brief, and the brief is cached per category.

Warnings raised while parsing are in the state from the start, so they are shown with the
questions, before any report exists.
