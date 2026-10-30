# Findings from task 1.8.2: candidates, prices and selection on the real model

Run on 17 October 2026 with the live sources and the medium tier, little reasoning, for both the
shortlist and the price reads. Two kinds of run:

- **The terminal app**, `uv run python -m shopper.cli --skip-all "<request>"` for "I need a new
  kettle", "I need a new frying pan" and "I need a cordless drill": the proof of the task. The
  first runs used the first price prompt (one list of amounts for all results); the last ones,
  in "The proof on the final code" below, the code as committed.
- **The measured runs**, `uv run python scripts/option_research_run.py run kettle "frying pan"
  drill`: the TCO analyzer alone after a skip-all interview, with the price read that was kept
  (one entry per search result, below). Every model call, its input and its reply are stored in
  `.cache/live/run_1_8_2/<category>.json`; `show` prints them. The measures below come from these
  runs.

The discovery searches came from the cache of task 1.8, so they cost nothing. **21 Tavily
credits** in all on the day: the follow-up discovery searches and the price searches.

## The price read returned nothing for most candidates

With one list of amounts for all results, the read answered `{"prices": []}` for 11 of 14
candidates in a measured run, also where the results plainly hold a euro price for the product
("Fissler Original Profi Collection Koekenpan Ø 24cm ; Galaxus.nl. €109,80" on beslist.nl). The
same inputs, read again:

| Price read | Reads with no amount, of 14 |
|---|---|
| One list, the first prompt | 11 |
| One list, the prompt asking for every amount of the brand, little reasoning | 8 |
| The same, full reasoning | 10 |
| One entry per search result, little reasoning (two runs) | 3 and 3 |

The three left empty with one entry per result are the DeWalt Atomic 20-Volt Max (a US model),
the DeWalt DCD801QQ2 (one result, with no price) and the Legend Copper Core, whose results hold no
euro amount for it. So the read now returns one entry per search result, each with its amounts
(`PriceReading` in `agents/tco/models.py`), and stays on little reasoning: full reasoning was no
better and took longer.

Reading every amount brought a second problem: a shop page that shows a second product. bol.com's
page for the Russell Hobbs 28081-70 Structuur also holds "Russell Hobbs inspire Black Kettle ...
36 euro en 99 cent". The name check is therefore made on the name the read gives for each amount,
not on the whole result, so an amount for another product of the brand is rejected ("it is for
another product").

## The measures per category

Counted on the measured runs. "Cheap" uses the yardsticks of task 1.8 (€25 frying pan, €30
kettle, €60 drill); the app's own baseline is the cheapest priced candidate.

| Measure | Frying pan | Kettle | Drill |
|---|---|---|---|
| Candidates named by the shortlist | 6 | 6 | 6 |
| Kept by the checks | 4 | 5 | 6 |
| With an accepted price | 1 (Fissler Original Profi, €109.80) | 3 | 3 |
| A cheap one | no | no (cheapest: Russell Hobbs Structure, €49.70) | yes: Bosch PSB 1800, €49.95 |
| Price searches that came back empty | 0 of 4 | 0 of 5 | 1 of 6 (Kobalt KXDD 1424A-03) |
| Product options | 1, with `one_option_only` | 3 | 2 |
| Durability hints kept | 0 | 3, on 2 candidates | 2, on 2 candidates |
| Hints about another product, checked by hand | - | 1 of 3 | 0 of 2 |

**7 of 15 kept candidates got an accepted price**, against 7 of 18 by hand in task 1.8. One of
them, the drill's Makita DHP482RTWJ, was another model's price (below); with the model-number
rule added since, it is 6 of 15. The terminal-app runs with the first prompt gave 2, 2 and 1
options (frying pan, kettle, drill); the measured runs gave 1, 3 and 2.

**An empty price search is rare: 1 of 15**, and it was a US model (Kobalt, sold at Lowe's). The
left-over item from task 1.8 asked to revisit a retry without a country only if it is common; it
is not, so there is no retry.

**The hint about another product** is the Secura's "The warranty lasts two years." in the
Consumer Reports result: it ends the paragraph before the Secura's heading, so it is about the
kettle above it. The two drill warranties and the Cuisinart's two warranty hints are about their
product.

## What the model got wrong

- **Few hints.** The shortlist kept 5 hints across 15 candidates, where task 1.8 found a quoted
  hint for every one of 18 candidates by hand. The durable pick was empty for the frying pan and
  the drill. The frying pan results do hold hints (task 1.8 quoted a wear-material hint for each
  of its six frying pans from the same two searches), so this is the read, not the results.
- **Category pages taken for one product.** The Cuisinart CPK-17P1's €220.75 comes from
  beslist.nl's "200 watt - Waterkoker kopen?" page and the Skil PWRCORE's €129 from a Bauhaus
  category page (`/c/` in its URL); the read did not mark either as listing several products.
- **A neighbouring model passed the name check on generic words.** The Makita DHP482RTWJ was
  priced from amazon.nl's DHP482RFWJ (€219.53) in a measured run, and in a terminal-app run from
  bol.com's DHP482ZJW, a body-only model, at €25.95, which then stood as the cheapest option. The
  names share "Makita", "18V", "Li-ion" and "Combi". Since then a name with a model number needs
  one of its model numbers in the shop's name (`names_product` in `agents/tco/checks.py`).
- **Category words in the name.** The shortlist kept "Kettle" and "frying pan" in names
  ("Russell Hobbs Structure Kettle", "GreenPan Stanley Tucci Ceramic Nonstick frying pan")
  although the prompt asks it not to; the GreenPan's price search then found no euro amount.
- **Imported US models** (Cuisinart CPK-17P1, OXO Brew Cordless Glass) are priced at about twice
  their US price on amazon.com.be and beslist.nl. The rule accepts them: they are euro prices of
  shops.
- **Names not in the cited result.** "Tramontina Professional Nonstick Fry Pan" and "COSORI Glass
  Electric Kettle" were left out because the model cited another result than the one that names
  them.

## The proof on the final code

The terminal app on the committed code, all searches but three from the cache:

| Category | Options printed, each with "price seen at" and its link | Warning |
|---|---|---|
| Kettle | Russell Hobbs Structure Kettle €49.70 (bol.com), Cuisinart CPK-17P1 €220.75 (beslist.nl), OXO Brew Cordless Glass €216.93 (amazon.com.be) | none |
| Frying pan | Fissler Original Profi €16.99 (amazon.de), Tramontina Professional Fusion €68.20 (amazon.nl) | none |
| Drill, first run | none | `no_options_found`, "We couldn't find a drill with a price in euro, ..." |
| Drill, second run | Bosch PSB 1800 €75.99 (bol.com) | `one_option_only` |

Every candidate left out and every empty slot has its reason in the printed trail. The runs show
how much the model varies from one run to the next on the same cached searches:

- the drill's shortlist named mostly US models in the first run (DeWalt Atomic, Milwaukee M18,
  Kobalt), so no candidate got a euro price; the second named the Bosch PSB 1800 again;
- the Bosch was read at €49.95 in a measured run and at €75.99 in the second drill run, from the
  same cached bol.com page;
- the Fissler's €16.99 comes from an amazon.de search page (`/s?` in its URL) that the read did
  not mark as listing several products; in the measured run it was €109.80 from beslist.nl.

## Timing

The terminal-app runs on the final code took 15.5 s (kettle), 23.5 s (frying pan), and 21.1 s and
22.4 s (drill) from start to report, with the category research from the brief store and the
discovery searches from the cache; the first runs took 21.5 s, 22.6 s and 36.4 s. The price
reads run at the same time.
