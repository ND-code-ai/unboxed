# Findings from task 1.8: the option research experiment

Run with `scripts/option_research_experiment.py` (its docstring lists the commands). The
responses are in `.cache/live/experiment_1_8/`, one file per label; the fixtures the next tasks
use are trimmed copies in `tests/fixtures/tavily/`.

## Design, fixed before the first search

**Who reads.** No model. The results were read by hand in the session; every quote and amount
taken from them was checked with the app's own code (`find_phrase`, `parse_amount`) through the
script's `check` command. This measures what the results hold; task 1.8.2 measures the model.

**Discovery grid, 24 searches.** Per category (the brief categories: frying pan, kettle, drill),
each with the discovery parameters:

| Label | Search query | Netherlands boost |
|---|---|---|
| general | "best {category} tested" | no |
| general-nl | the same | yes |
| answers | "best {category} {choice}", the choice's text as written | no |
| answers-nl | the same | yes |
| budget | "best budget {category}" | no |
| budget-nl | the same | yes |
| testers | "best {category} tested Which? Consumentenbond RTINGS" | no |
| dutch-nl | "beste {Dutch category} getest" (koekenpan, waterkoker, accuboormachine) | yes |

The choices, from the cached briefs: frying pan "No, I prefer plain metal", kettle "Yes, for
tea or coffee", drill "Drilling into masonry or concrete". The budget shape holds no number: a
query with the budget amount would break the research rules (no digit or currency marker, no
user input in a search query).

**Price searches, 18.** Six candidates per category from the winning pair, ranked as rule 1
below ranks them (hinted first, then by first appearance), always including the cheapest-looking
one; only names with a brand and a model. Search query "{product} prijs", price parameters. If a
pair names fewer than six, the ones there are are priced and the shortfall is recorded.

**Recurring cost, 2.** One drill from discovery: "{drill} vervangende accu prijs" and
"{drill} replacement battery price", both with the evidence parameters (Netherlands boost).

**Measures, per category.**

- Candidates: named products with brand and model, in a result that holds the name.
- Durability hints: candidates with at least one quote, found by `find_phrase` in a result that
  names them, of one kind (lifespan, warranty, wear material, repairability, care).
- Accepted euro price: the price rule then in `data_sources.md`, now in `architecture/option_research.md` ("When a price is accepted"); the
  "from", instalment, used, accessory and variant judgement made by hand.
- Cheap: an accepted price at or below €25 (frying pan), €30 (kettle) or €60 (drill). These
  ceilings are a yardstick for this experiment only; the app's baseline stays "the cheapest
  priced candidate", which works for any category.
- Recurring cost survives: a quoted amount in EUR, USD or GBP with a quoted interval.

**Decision rule.** Discovery in task 1.8.2 runs two template searches, so a *pair* of variants
is chosen, scored on the union of its results, per category, and the choice holds for all three:

1. Most candidates with at least one durability hint, up to six.
2. A cheap candidate is present.
3. Most distinct candidates named.
4. On a tie, the simpler setting: no Netherlands boost, no testers named, English.

The Netherlands boost or the Dutch query is adopted only when it beats the English, no-boost
version by at least two hinted candidates in two of the three categories. Each variant ran once;
a margin of two can be noise, so a choice that rests on it is marked tentative.

## Results

Run on 16 October 2026. **44 Tavily credits**: 24 discovery, 18 price, 2 recurring cost, each
search 1 credit (the roadmap estimated about 24 before the price pass was widened to six
candidates per category). No model was called.

### Discovery: the variants

Hinted candidates are capped at six, as rule 1 counts them. "Budget-labelled" means a result
calls a named product the budget, cheap or value pick, the only sign of a cheap candidate before
the price searches.

| Variant | Frying pan | Kettle | Drill |
|---|---|---|---|
| general | 8 results; 6+ hinted; budget-labelled (Goldilocks, Tramontina) | 8; 5 hinted; Amazon Basics | 8; 2 hinted (the two Consumer Reports warranties); Skil, Kobalt |
| general-nl | as general (7 of 8 results the same) | **0 results** | as general, plus Wirecutter; 2 hinted |
| answers | 8; 6+ hinted, all plain metal (lifetime and 25-year guarantees) | 8; 4 hinted, mostly gooseneck coffee kettles | 8; **0 drills**: drill bits and how-to pages |
| answers-nl | **0 results** | **0 results** | **0 results** |
| budget | 8; 5 hinted; many budget-labelled | 7; 4 hinted; Russell Hobbs, Hamilton Beach, Chefman | 8; 4 hinted (brushed motors that wear, "genuine longevity"); half the results are drill presses |
| budget-nl | 8; 6 hinted, UK prices in GBP | 7; 5 hinted | 8; 2 hinted; US prices |
| testers | 8; 6+ hinted; Which? appeared once (members only) | 8; **off topic**: central-heating boilers ("ketel"), a milk frother, speakers | 8; **off topic**: healthcare papers |
| dutch-nl | 8; 6 hinted; Consumentenbond and Dutch sites, euro prices in the snippets (Xtrema € 138,95) | 8; 2 hinted; euro prices (Smeg € 129,55, Tefal € 60,79) | 8; 1 hinted; Consumentenbond, Parkside at "80 euro"; snippets one line long |

What this shows:

- **The Netherlands boost does not help discovery and can empty it.** It never added two hinted
  candidates, and 4 of its 12 discovery searches returned nothing at all (every answers-nl, and
  the kettle's general-nl). It also emptied one price search (Fissler Original-Profi).
- **Naming testers in the query breaks it.** For the kettle and the drill the tester names
  outweighed the category; for the frying pan it brought Which?, whose results are for members.
  The names were tried on the general shape only, without the boost (the agreed grid), so this
  rests on one search per category.
- **The choice text does not work as a search term.** "best drill Drilling into masonry or
  concrete" finds drill bits; "best kettle Yes, for tea or coffee" leans to coffee gear.
- **A Dutch query finds Dutch sources and EU models with euro prices, but few hints.** Dutch
  pages give one-line snippets, and Consumentenbond's results are behind its paywall.
- **"best budget drill" is read as a drill press.** The category the supervisor writes
  ("drill") is too short for this template.

### The choice: general + budget, English, no country

By the decision rule: the pair general + budget has six hinted candidates in all three
categories (rule 1) and a budget-labelled candidate in each (rule 2). It is the only pair that
reaches six hinted candidates for the drill: general + budget-nl reaches four, and every pair
with the answers, testers or Dutch variant three or fewer, so rules 3 and 4 were not needed.
The boost and the Dutch query fail the adoption bar in every category, so the choice does not
rest on a margin of two and is not tentative.

The search queries for task 1.8.2: **"best {category} tested"** and **"best budget {category}"**,
with the discovery parameters and no country.

### The six candidates and their prices

Six candidates per category from that pair, each with a hint quote that `find_phrase` found in
a result that names it. Price search "{product} prijs", Netherlands boost. A price is accepted
by the rule in `data_sources.md` with the "from", instalment, used or third-party, accessory and
variant judgement made by hand, and with "holds the product's name" read by meaning. The last
column says whether `find_phrase` finds the candidate's full name in that result, which is how
code would check it.

| Category | Candidate | Hint (kind) | Accepted euro price | Full name found by code |
|---|---|---|---|---|
| Frying pan | Fissler Original-Profi | stainless steel (wear material) | none: the price search returned 0 results | - |
| | Legend Copper Core | stainless steel (wear material) | none: no result names the pan | - |
| | Demeyere Atlantis | no seasoning or maintenance (care) | none: only pots, lids and a "series from" price; the Atlantis line has no frying pan, its pan is the Proline | - |
| | GreenPan Valencia Pro | passed America's Test Kitchen's durability test (lifespan) | none: every amount is for a saucepan, a sauté pan or a set | - |
| | GreenPan Stanley Tucci | nonstick durability score (lifespan) | € 158,95 (beslist.nl) | no: "GreenPan - Stanley Tucci" |
| | Tramontina Professional | "relatively durable" coating (wear material) | € 42,66 (amazon.com.be, 30 cm) | yes |
| Kettle | Fellow Corvo EKG | "material and durability compromises" (wear material) | € 86,98 (bol.com) | yes |
| | OXO Brew Adjustable Temperature Kettle | stainless steel (wear material) | none: € 232,22 on amazon.com.be is about twice the US price, so taken as a third-party offer | no |
| | Hario Buono | no electronics to break (repairability) | € 46,74 (Klarna, lowest of 3 shops; knibble.nl the same) | yes, at knibble.nl ("De Hario Buono V60 is nu 46,74 euro"); not at Klarna ("Hario V60 Buono") |
| | Cuisinart CPK-17P1 | three-year warranty (warranty) | none: US model, dollar prices only | - |
| | Russell Hobbs Structure | removable limescale filter (care) | € 26,99 (bol.com) | no: "Russell Hobbs 28081-70 Structuur" |
| | Chefman Glass Electric Kettle | owners report failure (lifespan) | none: the € 123,18 result does not hold the name | no |
| Drill | DeWalt DCD801QQ2 | three-year warranty (warranty) | none: the one result shows no price | - |
| | Makita GFD02D | five-year warranty (warranty) | none: only replacement batteries (accessories) | - |
| | Titan TTI884COM | brushed motor (wear material) | none: no price shown | - |
| | Black+Decker BCD700S1K-GB | brushes wear down (wear material) | € 101,95 (Klarna) | no: "Black & Decker" |
| | Erbauer ECCD18-Li | "genuine longevity" (lifespan) | none: UK shops, GBP only | - |
| | Ryobi R18PD3-215GZ | brushed motor (wear material) | € 106 on a scraped page that is not a shop; the rule accepts it | yes |

### The measures per category

| Measure | Frying pan | Kettle | Drill |
|---|---|---|---|
| Candidates named by the pair, counted by hand | over 20 | about 20 | about 20, several of them drill presses |
| Of six, with a quoted durability hint | 6 | 6 | 6 |
| Of six, with an accepted euro price (by hand) | 2 | 3 | 2 |
| Of those, with the full name found by code | 1 | 2 | 1 |
| A cheap one (≤ €25, €30, €60) | no (cheapest € 42,66) | yes by hand: Russell Hobbs Structure, € 26,99; code would reject its name | no (cheapest € 101,95) |
| Recurring costs that survive | not searched (the agreed design searched the drill only) | not searched (as for the frying pan) | 0 of 2 |

**Durability hints are not the bottleneck; prices are.** Every category had six hinted
candidates, so selection can rest on hints from discovery (the left-over item from the 1.8
grilling is answered). But only 7 of 18 candidates got an accepted euro price by hand, because
the English roundups name US and UK models (Cuisinart CPK-17P1, Makita GFD02D, Erbauer, Titan)
and product lines rather than products (Demeyere Atlantis, GreenPan Valencia Pro). With six
candidates, expect two or three priced options per category, and sometimes one.

**The app's checks would accept only 4 of those 7.** Shop pages write a product's name their
own way, so the full-name check fails three of them:

- "GreenPan - Stanley Tucci", "Russell Hobbs 28081-70 Structuur" and "Black & Decker
  BCD700S1K-GB" do not hold the candidate's name as a phrase; Hario Buono passes only because
  a second shop writes "Hario Buono V60". The model number alone, or the brand and the line in
  any order, would be found.
- bol.com writes "De prijs van dit product is 86 euro en 98 cent.86,98." The amount next to the
  euro marker reads as 86; the full amount "86,98" stands without a marker. This hits two of the
  seven (Fellow Corvo EKG, Russell Hobbs Structure).

### Recurring cost

"Ryobi R18PD3-215GZ vervangende accu prijs" returned the drill kit at € 156,81 (amazon.nl) and
no battery price. "Ryobi R18PD3-215GZ replacement battery price" returned a spare battery at
£80 on ebay.co.uk and a Facebook post, neither excluded by the evidence purpose. Neither gives an
interval, so no recurring cost survives: a battery has a price but no replacement interval in a
shop or listing text. Recurring costs from search will mostly be "not found" unless the
evidence read finds a quoted interval elsewhere.

### Fixtures

26 trimmed copies in `tests/fixtures/tavily/`: for each category `<category>-discovery-general`
and `<category>-discovery-budget`, the six `<category>-price-<product>` responses (including the
empty Fissler one), and `drill-recurring-dutch` and `drill-recurring-english`. Each keeps every
result's URL and title; the content is cut to the sentences that hold a candidate's name, a hint
or an amount. Every hint quote and accepted price above is still found in them. The other 16
responses stay in `.cache/live/experiment_1_8/`.
