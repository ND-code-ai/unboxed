# Ideas beyond the cut line

Ideas for after the conversation agent and the submission, collected on 26 October 2026 to
make the demo memorable. None is planned; feasibility (APIs, licences, model support) is
unchecked unless a line says otherwise. An idea that is taken up becomes a task in
`ROADMAP_OPTIONAL.md` with its own grilling; the rules of `product.md` (wallet first, never
preachy, honest about uncertainty) and `CLAUDE.md` rule 2 (ask before a new external service)
apply to every one of them.

Effort: S = a day or less, M = a few days, L = a week or more, all with the current setup.

## Make the numbers real: EU data

- **EPREL energy labels (M).** The EU's energy-label database (EPREL) has a public API, free
  with a registered key, to check. For an `energy_heavy` option, read the label's kWh per year
  and put the electricity cost into `calc/` with the user's or a default EU price per kWh. The
  cost per year then rests on the EU label, not an estimate, and the label class can show
  beside the option. New external service: ask first.
- **Repairability index (S–M).** France publishes the scores of its repairability index as
  open government data (it is being succeeded by a durability index), to check for the
  licence and the product groups covered. Show the score as a badge with its source, and let it
  feed the durability evidence of `option_evidence.md`. Belgium has adopted the same index.
- **Read a Digital Product Passport (M).** `product.md` says the app is ready for them. Prove
  it: accept a passport link or QR code, read its footprint, materials and repair fields, and
  show a tier-1 "Published figure" taken from the passport. A sample passport serves the demo
  until real ones exist for these categories.

## Show the agents working

- **Live graph view (M).** Render the real LangGraph graph (its Mermaid export, not a drawing)
  on the page and light up each node as the progress events of task 2.5 arrive, with the trail
  entries streaming beside it. "Agents by design" becomes something the jury watches.
- **Receipt for the run (S).** Under every report: how long it took, how many model calls on
  which tier, how many search and page credits, and the cost in cents. The ledger and the trail
  hold the data already. Infrastructure-minded judges notice cost-awareness.

## New kinds of agent

- **Skeptic agent (M).** Before a report is shown, a critic on a different tier reviews it
  against the evidence rules and the EU claims rules (`eu_market.md`): a lifespan resting on one
  owner report, an unsubstantiated "eco" claim in a source, a figure with no source. Flags go on
  the report and in the trail. Greenwashing detection applied to the app's own output, and one
  more agent with a different job.
- **"Keep what you have", option zero (M–L).** Ask what the user owns now and what is wrong
  with it. A repair agent estimates the repair cost (spare-part prices from search, repair
  guides) and adds "repair it" as the first option of the comparison. Not buying is often the
  best outcome; wallet first keeps it from being a lecture. iFixit's content is
  non-commercial-licensed, so a source for guides needs checking.
- **Durability over time (L).** Cluster owner and tester reports by product age ("fails after
  about 18 months", "still fine after five years") into a lifespan range with its spread,
  instead of one estimated number. Shows the uncertainty honestly and uses the findings of
  task 1.8.4.

## The showstopper

- **In-store mode (L).** On a phone, photograph a shelf label or a box; a vision model (check
  which ones Nebius Token Factory hosts) reads the product name and price, and the analysis runs
  from there, with the chat on the phone while the user stands in the shop. If the demo video
  opens in a real shop, the jury remembers it. Personal data: the photo never leaves the request
  and is not stored.

## Smaller sparks

- **Voice input (S).** The browser's speech API, in any language, as the supervisor already
  accepts any language.
- **Shareable decision card (S–M).** One page per report with a preview image for links,
  "checked on <date>", every figure labelled, and the evidence summary. Easy for a judge to
  open from the submission.
- **Electricity contract (S).** Let the user set their price per kWh; `energy_heavy` figures
  update through the recalculation endpoint.
- **Deep links to the marketplaces (S).** Hand the user over to eBay or a comparison site with
  the search and filters pre-filled, so the "links out, sells nothing" stance is visible.

## If only three

EPREL (the numbers become real and EU-sourced), the skeptic agent (agent diversity plus the
EU claims angle) and the live graph view (multi-agent made visible). In-store mode only once
the rest is done, but it is the one the video would open with.
