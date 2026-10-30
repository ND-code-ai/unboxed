# Findings from task 1.9.8: CO2e on the report, and the live run

Run on 21 October 2026 with `scripts/lca_live_run.py` (its docstring gives the command): the
terminal app with `--skip-all` and live sources on four requests, then one LCA call on the two
stub frying pans. Each LCA call's input, reply, time and tokens are recorded in
`tests/fixtures/nebius/lca-<name>.json`; the stub pans' reply is what the offline CLI tests use
(`tests/test_cli.py`, "CO2e: the real LCA agent on the stub pans"). Model:
`nvidia/Nemotron-3-Ultra-550b-a55b` (the large tier), reasoning in full, prompt with "typical" as
the default form. The prompt's naming of magnets and its "both above 0" for manufacturing were
added after the run, from the review below.

## Latency and tokens

| Request | Whole run | Options | LCA call | Prompt tokens | Completion tokens | Finish |
|---|---|---|---|---|---|---|
| "I need a new frying pan, budget 50 euro" | 159.5 s | 2 | 8.6 s | 857 | 2,252 | stop |
| "I need a new kettle" | 135.2 s | 2 | 9.6 s | 861 | 2,921 | stop |
| "I need a drill for putting up shelves" | 151.0 s | 1 | 34.4 s | 844 | 4,911 | stop |
| "a cordless screwdriver, budget 80 euro" | 181.8 s | 2 | 7.2 s | 872 | 1,648 | stop |
| The two stub pans (no run) | | 2 | 10.6 s | 833 | 2,332 | stop |

Every reply was valid on the first try, no option was declined, and no call came near
`LCA_TIME_CAP_SECONDS`. The LCA call is 5 to 23 % of a run; the drill's twelve inputs took
longest. No request had a pasted link, so no fixed input from a page (material, form, weight)
was exercised live.

## What the report showed

Every option got its range with the label and a "Built from:" line. The printed transcripts
mark "(estimated)" after each material; after the run the line was changed to one mark after
"Built from" when the model estimated every material, form and mass, as it did for every option
here. Per unit and over 10 years:

| Option | Mass | Per unit (kg CO2e) | Lifespan | Shown over 10 years |
|---|---|---|---|---|
| Tramontina Professional Fusion 10-Inch | 1.01 kg | 3.5 to 10.8 | 4 years | 10 to 33 |
| Demeyere Atlantis Proline | 1.60 kg | 5.6 to 16.4 | 20 years | 5.5 to 17 |
| Russell Hobbs Structure | 1.30 kg | 5.2 to 10.8 | 2 years | 25 to 55 |
| Cuisinart CPK-17P1 PerfecTemp | 1.99 kg | 9.2 to 18.8 | 3 years | 36 to 76 |
| Ryobi 18V ONE+ HP Compact Brushless Drill Driver | 1.54 kg | 9.0 to 18.1 (widened) | 4 years | 27 to 55 |
| Klein Tools 32305 15-in-1 screwdriver | 0.20 kg | 0.87 to 1.9 | 10 years | 0.86 to 2 |
| Wera Kraftform Plus 334/6 | 0.42 kg | 2.0 to 4.4 | 10 years | 2 to 4.4 |
| Stub non-stick pan | 1.01 kg | 5.3 to 13.1 | 2 years | 26 to 66 |
| Stub carbon steel pan | 1.4 kg | 2.3 to 4.7 (widened) | 30 years | 2.3 to 4.7 |

In every live pair the horizon ranges overlap, so no "Against" line was printed; the stub pans
give one ("About 21 to 63 kg CO2e less to make over 10 years"). Manufacturing came back between
0.3 and 3 kg CO2e, never 0. The "cordless screwdriver" request shortlisted two hand screwdrivers,
so the one cordless tool is the Ryobi drill, estimated as a bare tool: no battery input.

## Compared with a published figure

ADEME's kettle on Impact CO2 (https://impactco2.fr/outils/electromenager/bouilloire, from
ADEME's study of consumer goods and Base Empreinte): 9.91 kg CO2e to make one generic kettle,
cradle to gate plus distribution, against 31.6 kg in use over 6 years. The app's per-unit ranges
are 5.2 to 10.8 kg for the Russell Hobbs and 9.2 to 18.8 kg for the Cuisinart: ADEME's figure is
at the top of the one and the bottom of the other, the same order, with a slightly wider
boundary on ADEME's side. ADEME's overview page shows construction as 16 % of 37.8 kg (about
6 kg), which disagrees with its item page; the item page's figure is the one cited. The use phase
is three times the making for a kettle, which the "to make" in every line keeps apart.

## The LCA review (lca-reviewer)

Final verdict, after the fixes below: **PASS**. The deferrals are acceptable for this task: they
concern the quality of the model's estimates, and every figure carries its label, "(estimated)"
and "to make". Items 1 and 5, and the scaling guard of item 3, carry real risk until task 1.10.

First verdict: **NEEDS CHANGES** on the model's replies, not on the display. It recomputed all the
per-unit ranges from the fixtures and every displayed range matches, rounded outward. Findings,
and what this task did with each:

1. **Typical products, not the product.** The Tramontina Professional Fusion was given as
   stainless steel and aluminium; retail listings describe heavy-gauge aluminium with a non-stick
   coating and no induction base
   (https://www.walmart.com/ip/Tramontina-10-Inch-Restaurant-Fry-Pan-Pro-Fusion-3-6MM-Progrey-80114-516DS/196547196).
   The Russell Hobbs Structure's body is plastic with stainless inserts in one listing
   (https://dateks.lv/en/cenas/elektriskas-tejkannas/902209-russell-hobbs-28081-70-stainless-steel-black),
   stainless in others. Prompt rule 9 lets the model estimate a typical
   product of the kind, and nothing on the report says when it did. Deferred to task 1.10: a
   field for it, shown on "Built from" and in the trail.
2. **Factors differ between calls.** Stainless steel came back 2.5 to 6.5 in one call and
   "stainless steel 304" 2.0 to 4.0 in another, both in the form "typical"; Outokumpu puts the
   global average near 7 kg CO2e per kg
   (https://news.cision.com/outokumpu-oyj/r/outokumpu-s-annual-report-2023-published,c3938944),
   so both high ends sit below it. A printed circuit board came back 50 to 100 and 20 to 50.
   Aluminium "typical" 4 to 16 is plausible (IAI primary 15.1 t CO2e per t,
   https://international-aluminium.org/statistics/greenhouse-gas-emissions-primary-aluminium/);
   "aluminum die-cast" at 8 to 12 is likely high, since die-cast is mostly secondary alloy. As
   factors change from call to call, a what-if rerun can move a figure with no change in input.
   Deferred: pinning common materials in a table is tier 2's work; the "typical" default form is
   checked again in 1.10.
3. **A neodymium magnet (30 to 50) was not flagged a component**, so a page weight would scale
   it. Done here: prompt rule 4 names a magnet. A code guard that never scales a high-factor
   input is deferred.
4. **Manufacturing of 0 was accepted.** Done here: a range must be above 0, or the option is
   declined (`checks.py`), and the prompt says so.
5. **Missing parts are not disclosed**: no battery for the Ryobi, no base or cord as such for
   the kettles. Deferred to 1.10 with item 1.
6. **"Built from" is hard to read**: the drill lists carbon steel five times; components showed
   a form ("heating element, typical"). Done here: a component shows no form. Merging rows of the
   same material is left to the page (task 3.2).
7. **A set not labelled as one**: the Wera 334/6 is a six-piece set, but option research gave it
   no piece count. Deferred to 1.10.
8. **Wording**: no generic environmental claim; the label is the one `lca.md` gives; CO2e less
   than the baseline shows only for a positive interval. "Footprint" in the evidence summary
   could read as the whole life cycle; deferred to the tone pass (1.10).

Seen in passing, for option research: the Russell Hobbs Structure's price link is a toaster page
(variant "2 Slice"), and the Ryobi's is a hammer drill.

## The left-over items this run was to judge

- **Zero manufacturing**: none came back; the check now refuses it (above). The other direction,
  a bulk material marked a component, did not occur; the opposite did (the magnet).
- **Weight among the numbered fixed inputs**: not exercised, no pasted link.
- **Name echoes**: every echoed name matched its option; no option was declined.
