# Findings from task 1.15: price wording and the live run

Run on 24 October 2026 against the live services: Tavily, Firecrawl and the Nebius models of
`docs/architecture/models.md`, through the terminal app with `--skip-all`. The three requests
are the ones the offline tests use (`tests/test_cli.py`, "OPTIONS").

**Result:** each tuned category gives three product options in the terminal app, live, every
price from an offer on a comparison site's product page.

| Category | Request | Options (price, seller via site) |
|---|---|---|
| frying pan | "I need a new frying pan, budget 50 euro" | GreenChef Diamond €23.99 plus €2.99 shipping (bol. via kieskeurig.nl), DeBuyer Mineral B Pro €44.95 (bol.com via beslist.nl), Tefal Renew ON €35.99 (Coolblue.nl via kieskeurig.nl) |
| kettle | "a kettle that boils quickly, around 60 euros" | Midea €27.99 (Amazon.nl via beslist.nl), Seeger SGR100BK €34.99 (bol.com via beslist.nl), CREATE Retro €39.95 (bol.com via beslist.nl) |
| drill | "a cordless drill for occasional DIY at home, max 120 euro" | Aerotec pneumatic €48.99 (bol. Plaza via kieskeurig.nl), Bosch GSR 120-LI €97.10 (Galaxus.nl via beslist.nl), Makita DHP 490 Z €86.99, sold without battery and charger (bol. via kieskeurig.nl) |

The full reports are not committed: they hold page text and model output of the day. The price
lines read, for example, "Price: €23.99, plus €2.99 shipping, price seen at bol. via
kieskeurig.nl on 24 October 2026"; the Makita's block ends "Sold without a part it needs to work,
so no savings or CO2e against Aerotec Pneumatische boormachine 6.3 bar are shown".

**Credits:** about 31 Tavily (three runs, two runs again after fixes, and 12 searches recorded
for the fixtures), 36 Firecrawl (the runs, the wok page and the WMF page), and the Nebius calls
of five runs plus a probe of 9 calls to the local-term prompt.

## What the live run broke, and what was fixed in this task

1. **The local term came back as "...".** The frying pan's first run got `...` from the
   local-term call, which passed `local_term_fault`; "... kopen" found kieskeurig.nl's PC page,
   the search with "frying pan" named no product, so the PCs stood as candidates and nothing was
   read within the budget. A probe of 9 calls (3 per category) gave "..." once more, for the
   kettle. `LocalTerm` now rejects a term with no letter, so the call is asked again
   (`agents/brief/models.py`); the rerun gave "koekenpan".
2. **The kettle search found no listing page.** All 8 results of "waterkoker kopen" were
   beslist.nl lists filtered on a search word or a brand (`/r/…`, `/c/merk~…`), which the URL
   rules skip, and none was on kieskeurig.nl. Every one of them sits under the category's own
   listing page (`…/huishoudelijke_apparatuur_19968034_19970345`, the page task 1.12 read). A
   beslist.nl filtered list now stands for its category, cut before `/r/` or `/c/`
   (`category_cut` in `config.py`). kieskeurig.nl product pages are not cut: the recorded
   "drill kopen" results would have given `/voetbal`, `/speelgoedgereedschap` and
   `/lasaccessoires`. The rerun read the kettle category and gave three options.
3. **The WMF's sale is real.** The WMF Profi Resist page (beslist.nl, EAN 4000530649843) still
   offered €44.99 at bol.com and Joybuy.nl, in stock, two days after task 1.13 recorded it,
   beside nine shops at €76.95 to €95.90: 58% of the median, under the 60% outlier share. The
   share is now 50%: the Metabo's €32.95 (37% of its median) is still dropped. Offline, the WMF
   now takes the frying pan's third slot at €44.99.

## The evidence search with the search name

With the search name (`search_name`: the first part of the name, cut at " - ", brand in front,
sizes out) in place of the whole JSON-LD name, the evidence searches found:

| Search name | Results |
|---|---|
| GreenChef Diamond Inductie Koekenpan | 3 (was 0) |
| de Buyer Mineral B Element Koekenpan | 8 (was 8) |
| DeBuyer Mineral B Pro | 8 |
| Tefal Renew ON Keramische Koekenpan | 3 (was 2) |
| WMF Profi Resist | 8 |
| Midea Roestvrijstalen waterkoker | 4 (was 0) |
| Inventum HW817D Waterkoker | 0 (was 0) |
| Severin WK 9342 Waterkoker | 0 (was 0) |
| SEEGER SGR100BK | 8 |
| CREATE Waterkoker Retro RVS BPA vrij Elektrisch Antikalk Sage Kettle Retro | 0 |
| Bosch EasyDrill 18V-38 | 8 (was 0) |
| Einhell Power X-Change | 8 |
| Bosch Professional Accu-boormachine GSR | 8 |
| Aerotec Pneumatische boormachine 6.3 bar | 0 (was 0) |
| Makita DHP 490 Z Accu Klopboormachine | 0 |
| Powerplus Compacte 4-in-1 … POWXBOX001 incl. batterij en 2.0Ah lader | 0 |

10 of 16 found something, against 2 of 9 with the whole names in task 1.13. A name with no
" - " is kept whole (CREATE, the POWXBOX), and a Dutch category word beside the English template
words may still find nothing (Inventum, Severin, Makita). No lifespan was sourced in any of the
three live reports: the reads cited few results, and the quotes they cited stated no years or
did not name the product.

## The left-over items judged on the live run

- **Slots.** The trail reads right: "Chose … as the cheapest; reason: €26.98 with its stated
  shipping", the durable pick "ordered by the model's judgement: long (bare iron construction
  that can be re-seasoned and has no coating to wear), not a sourced figure", and "Filled the
  slots by price" for the kettle and the drill, whose judgement by page told no candidate apart.
  The Makita took the durable pick within budget "it is sold without a part it needs to work, and
  no buyable candidate was left". No option failed an answer (every run skipped the questions),
  so the refill has still not run live.
- **The missing-part word.** The one `incomplete` reading live was the Makita DHP 490 Z
  ("Solo (Without Battery/Charger)"), right; no pan or kettle was read as incomplete. The guard
  stays as it is.
- **An offer that states no stock.** All 128 offers on the 27 product pages read live state
  their availability (86 on beslist.nl, 42 on kieskeurig.nl). The rule has no live case.

## Seen in the live run, for other tasks

- **No questions for the frying pan.** The phrasing call wrote no question for any of the five
  factors ("No question about the factor …; reason: the model wrote none"), and the usage
  frequencies fell back to the default.
- **Two different pans merged.** "Tefal Trattoria Braadpan - 24 cm - Zwart - Inductie" and
  "Tefal - So Expert - Koekenpan - Zwart - Aluminium - Antiaanbaklaag" were kept once: the only
  shared word besides the brand is the colour "zwart", which `names_product` counts.
- **Page reads dropped for their quote.** 4 of the kettle's 8 page reads and 2 of the drill's
  were left out because "what the page sells is not quoted from the page" (two Russell Hobbs
  kettles, the Bosch EasyDrill among them).
- **The local term against compound names.** "boormachine" does not stand in
  "Klopboor-/schroefmachine" or "Schroefmachine", so the Makita DHP458Z, the Power X-Change and
  the Makita DF001DW were dropped as not naming a drill.
- **A pneumatic drill for a cordless request.** The Aerotec, which needs a compressor, is the
  drill's cheapest option, as in task 1.12.
- **"Ø24 cm" is no size.** The GreenChef's page got "states no size or variant" though its name
  says "Ø24 cm": "ø24" is not read as a measure.
- **The Bosch GSR 120-LI's CO2e.** 150 to 320 kg over 10 years, 4 purchases, against 24 to 50 kg
  for the Makita body: about 40 to 80 kg to make one 12 V drill with battery and charger.
