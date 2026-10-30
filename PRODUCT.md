# Product

<!-- impeccable:product-schema 1 -->

The record of product truth for design work on the page. It summarises; the detail, and the
final word, are in `docs/product.md` (the experience, principles, tone, scope),
`docs/wording.md` (how fixed messages and labels are written; their words are in
`src/shopper/wording.py` and `web/lib/wording.ts`) and `docs/eu_market.md`
(market, claims, personal data). Where this file and those docs differ, the docs win and this
file is corrected.

## Platform

web

## Stack

- Next.js (App Router) in `web/`, TypeScript strict, ESLint and Prettier
  (`docs/code_conventions.md`, "Next.js"). Server components by default; client components only
  where state, effects or browser APIs need them.
- Styling: Tailwind CSS (task 3.1.3); the world's tokens live in its theme.
- Components: shadcn/ui, restyled through the tokens (`DESIGN.md`); its Radix primitives come in
  with the components that need them (the button and text box use none).
- Data from the Python API only (FastAPI, `docs/service_architecture.md`): types generated from
  its OpenAPI schema with `openapi-typescript`, every call through `web/lib/api`, runs streamed
  as Server-Sent Events over `POST`.
- Undecided: where the frontend is hosted (task 3.5).

## Users

Shoppers in Europe, the Netherlands first, who are about to buy a durable product (cookware, a
small household appliance, a tool, or any other durable item except a motor vehicle) and want to
weigh a few options before they buy it elsewhere. They arrive with a product link or a need,
often with a budget ("I need a new frying pan, budget €50"). Their job is to decide with
confidence which option is the better buy over its life, in money first and in footprint second.

Hackathon judges (Nebius x NVIDIA, "Best Apps and Agents") see the product through a
three-minute demo video and the public URL. They are a second audience, not the one the page is
designed around.

## Product Purpose

True Cost Copilot shows the real cost of a purchase and a better option that still fits the
budget. It first asks up to five questions about what matters for that kind of product, then
returns, for up to three options side by side: price, cost per year, cost per use, an expected
lifespan with the evidence it rests on, a CO2e range with its confidence label, and a 10-year
comparison of one durable item against the cheap replacements it avoids. Used listings within
budget are shown when the durable option is over budget new. After the report the user can
change the assumptions and talk to it.

The app sells nothing and has no checkout: it links out to shops. Success is a shopper who
understands the comparison, trusts where each figure came from, and buys the right thing once.

## Positioning

Wallet first and never preachy: sustainability is the bonus of the better-value choice. Every
number shown is computed in code from sourced inputs, never written by a model; every lifespan
shows what it rests on (warranty, repairability, materials, care, owner and tester reports); every
environmental figure carries its source and a confidence label ("Published figure", "Benchmark
estimate", "AI synthetic estimate"); and unknown is shown as unknown. It asks what matters before
it searches. It gives no scores, grades or ratings of its own.

## Operating Context

- The flow is one chat thread from the first message. The first message is a link or a need,
  optionally with a budget → what the app understood ("Looking for: frying pan · Budget: €50 ·
  Edit") with any warnings → the questions arrive as one turn and are asked one at a time, each
  with its reason, its choices as chips, "not sure" and "something else", an answered one
  becoming a label on the box, with "skip the rest"; the user taps chips or writes their own
  words under "something else", adds anything else at a closing step, and sends once with "Show
  my options" → the next turn shows what was read from the reply
  ("From your reply: …") → live progress per agent → the report opens as a second page, with the
  same thread beside it (to the right on desktop, below on a phone) → changing assumptions → the
  chat continues there. For the submission the chat offers two starter actions, a lower budget
  and leaving out one option, each giving a new report version with a "what changed" note;
  explaining answers and what-ifs come after the submission (`docs/ROADMAP_OPTIONAL.md`), so no
  space is designed for them now.
- The first screen is also the product's opening: a first-time visitor, and a judge in the demo,
  decides there whether the app is worth their time.
- A run takes tens of seconds and can take a few minutes; progress is streamed per agent and
  stays available afterwards as an evidence trail (which agent found what, from which source).
- A session can be found again after a dropped connection; a run that stops reads as
  interrupted and offers to start again with the text kept.
- Used on desktop and on a phone. Interface in English; the user may type in any language;
  prices in EUR. Listings and product pages are shown in their original language.
- The 10-year comparison is the centrepiece and must be understandable from a screenshot with no
  explanation.

## Capabilities and Constraints

- Scope: any durable physical product except motor vehicles; tuned and tested for cookware,
  small household appliances and tools (the frying pan is the reference example). Food,
  consumables, services, digital goods, living things, property and motor vehicles are declined
  with a friendly message; unclear input is asked to be rephrased; several products are asked to
  be narrowed to one.
- The budget is a hard constraint and never asked about in the interview. An option over it is
  shown only as the reference the used listings are measured against, always marked "Over your
  budget", never as the pick; a "Hide options over my budget" switch filters on the API's value.
  With no budget, nothing is marked and the switch is not shown.
- The page computes no figures: cost and impact numbers come from the API, and the page formats
  and displays them.
- Fixed messages and labels use the exact words in `wording.py` and `web/lib/wording.ts`.
- An evidence summary line tops every report, counts only ("Lifespan sourced for 3 of 3
  options"), never a score or colour rating; on a wide screen the savings stand over it in the same
  block.
- Settled: the page's fixed words come as finished lines from the API, plus
  `web/lib/wording.ts` for the page's own (`docs/adr/0008-api-sends-finished-lines.md`).
- Open decisions: a Dutch interface; the frontend's hosting; the repository's open-source
  licence.

## Brand Commitments

- Name: Unboxed, tagline "The price tag is only the start" (the page; the README, the docs and the
  API's title still say True Cost Copilot, `left_over_tasks.md`).
- Voice (`docs/product.md`, "Tone"): plain, specific, calm; lead with money, follow with impact.
  No "should", "must", guilt, shame, lectures or exclamation marks, and no claim of more
  precision than the data supports. No generic environmental claims ("eco-friendly", "green",
  "sustainable") about a product: give the specific, sourced figure instead, as EU rules on
  environmental claims require (`docs/eu_market.md`).
- When something does not go to plan: say what happened, what the app did, and what the user
  can do next; no apology, blame or guess, and none of "invalid", "error", "wrong" or "failed"
  (`docs/wording.md`).
- No logo or other brand asset exists yet.

## Evidence on Hand

- Recorded real research in `tests/fixtures/` (searches, product pages, model replies) for
  frying pans, kettles, drills and others; measured live runs in `docs/findings/`.
- Five demo moments the design should make easy to show (`docs/product.md`, "Demo moments").
- No users, testimonials, customer quotes, press, savings statistics or ratings of the app
  exist. Do not invent any.

## Product Principles

1. Clarity and trust in the comparison come before everything else; the page is for deciding,
   not for converting.
2. Wallet first: the budget is a hard limit, and money leads every sentence.
3. Honest about uncertainty: every figure shows its source and confidence, and unknown stays
   unknown.
4. Show the work: every figure traces to an agent, a source and an assumption the user can
   change.
5. Buy the right thing once: help the user learn what matters before they search.

## Accessibility & Inclusion

Aim for WCAG 2.2 AA without a formal audit, and claim no conformance: semantic HTML, accessible
components (shadcn/ui, on Radix where a component needs it), a palette that passes contrast,
visible focus, `aria-live` for streamed progress, a table beside every chart, and reduced motion
respected.
