---
version: 1
slug: "web-app-page-tsx"
primary_target: "web/app/page.tsx"
related_targets: ["web/components/Thread.tsx","web/components/ResultsView.tsx"]
---

# Surface brief: the chat page

Source: `docs/design/chat_page_brief.md` (settled 27 October 2026), including "The world, as
locked" and "The interview panel". Where the two differ, that file wins and this one is
corrected. Tokens live in `DESIGN.md` once the documenter writes it.

## Scope and mode

The chat page (`web/app/page.tsx`, the thread in `web/components/`). Two modes on one page:

- **The first viewport, before and just after the first message, is Experience.** The coral
  field and the box at large scale.
- **The questions, the composer and the progress follow Operate rules** on the panel colour, in
  the same type and palette, calmer.

Later passes (`critique`, `polish`, tasks 3.2.1 and 3.2.2) keep this split and do not turn the opening back
into a form.

## Job and success

The shopper types a need or pastes a link, checks the "Looking for" line, answers up to five
questions one at a time by tapping chips (or types a reply, or skips), then watches per-agent
progress until the report. Success: the questions feel worth answering; the shopper always knows
what the app understood and is doing, including the wait and a lost stream being picked up; a
reply the app could not read keeps its text.

## The memorable moment: the box (pinned)

The box is a fixed element of the surface, not a candidate aesthetic. Every dealt direction must
carry it (open in the first viewport, labels dropping in); directions vary the world around it,
never whether it is there. Decline any card that drops it. States and build rules: the source
file, "The memorable moment".

## The interview panel (locked)

Build to `docs/design/references/interview-panel.html`. Answered questions become labels at the
top of the panel (key over value, white, 2 px ink border, slightly rotated; "not sure" dashed and
muted); one label component draws them in the panel and on the box, where a label carries the
answer alone ("dishwasher?" dashed for not sure) and the face clears its heading for them, the
request moving to its top and the count beside it. Once the reply is read, each factor of the
user's own the reader kept is a label too (its phrase; about 30 characters on the box, whole in
the panel). The current question sits in
a white card with "2 of 5" beside it, its reason, its source, its chips, the last "Something
else" (a pencil mark; it unfolds a field in the card, with Next). Below it: "{n} more questions ·
or skip the rest"; "skip the rest" sends now; no line on the last question. Tapping a label
reopens its question. When every question has an answer the same card asks "Anything else we
should know?", one field and "Show my options", which sends; no composer, no Skip all.

## Constraints

- Words come from the API's lines and `web/lib/wording.ts`; fixed words follow
  `docs/wording.md`. No generic environmental claims, no scores, badges or certification looks.
- Coral is kept away from sale signs: no price-tag shapes, starbursts or "deal" wording, and
  every price in plain type.
- Chrome is the product name and, at most, "New search".
- WCAG 2.2 AA as a target: contrast 4.5:1, visible focus, `aria-live` for progress.

## Direction contract

THESIS: The purchase set like a Dutch public information system: a coral field owns the opening,
one open box is its object, and the shopper's criteria become labels stuck on it. It refuses the
AI-chat column of bubbles under a centred input.

OWN-WORLD: Total Design, coral. Coral field, warm off-white panel, white paper with 2 px ink
borders, square corners, a visible tick grid of twelve columns at the top; Archivo, expanded and
heavy in lowercase for the wordmark and the opening question, normal width and bold for the labels
(a small-caps key over a lowercase value, as the locked panel reference sets them) and in the
panel. State is line form: dashed for not sure or pending, solid for done; what is moving now
inverts (the agent at work in the scan window). No gradients, shadows, glass, price tags or
starbursts.

STORY: The shopper sees one open box asking what goes in it, writes it on the box's face, watches
it stay there in pencil while the app's marker labels the box, then the box gets labelled with
their own criteria, sealed while the agents scan the price, and opened when the
answer is ready. They come away believing the result was built from what they said.

FIRST VIEWPORT: Desktop: before the first send the coral field fills the page, wordmark top
left, ticks along the top; the open box, as large as the height allows, every part with the same
2 px ink edge, on its route line with every station ahead, and its front face as the composer:
"What goes in the box?" as a heading, the request typed in Archivo on a faint baseline, "Or paste
a product link." and "Next", solid ink. By the face's right edge, under "Or try one", the three
examples as small paper labels, slightly turned. On Next the request stays on the face, faded,
the panel's column opens over the right three eighths, as the locked panel reference sets them,
the box slides left into the field's five eighths, and a blank label slides in over the request
for the marker (28 October 2026). Phone: the same face, the examples in a row below the box, the
route line under them; the thread joins below once the request is sent.
Signature interaction: a label drops in from above, behind the box's front lip, onto the face when
its chip is tapped; labelling → sealed → open in one component, CSS transitions on transform,
reduced motion jumps.

FORM: Dutch modernist identity programmes (Total Design, PTT), position 5 of 7 on the ordered
list, repainted coral after round one; seed:6856289740088cb4.

FINISH: unreviewed and undocumented is unfinished; this build ends with the finish review, the
verdict, DESIGN.md, and every shipping raster carrying its provenance

## The results view (task 3.2.1)

A view of the same page, Operate mode, in the world above (the spec is the task's roadmap entry).
Layout locked on 29 October 2026 from three dealt structures: "Each option a label sheet", with
the user's changes (options on the coral field, no heading that repeats a figure's label, answer
labels wrapping inside the thread column, the empty band kept for 3.2.2's route line).

THESIS: Each option is a white label sheet on the coral field, every figure a small key over its
value, the rows lined up across the sheets, so three options compare at a glance. It refuses the
retail product grid of photos, stars and a "best pick" badge.

OWN-WORLD: The chat page's world. Coral field behind the options; white sheets with 2 px ink
edges, square; keys in the label key style (small capitals, muted) over values in body type; a
2 px ink rule between a sheet's groups; the thread column stays on the panel colour.

STORY: The report lands and the box gives way to the sheets: the shopper reads the evidence
summary, compares cost per year and lifespan across the sheets, sees what each lifespan rests on
and its CO2e with its label, and checks the list before they buy.

FIRST VIEWPORT: Wide: columns 1 to 8 on coral, the wordmark, an empty band where the route line
will stand, "Your options" with the budget switch and the Rows / Cards control beside it, a paper
block of the evidence summary, caveats and warnings, then three sheets side by side (subgrid
rows); columns 9 to 12 on the panel, the rounds read-only, "Start again" at their foot. Phone:
the deck, one card at a time under a pinned strip of each option's name and cost per year, with
previous and next.
Signature interaction: the deck's card slides in from the side it was stepped or swiped to;
reduced motion swaps it.

FORM: Each option a label sheet, position 1 of 7 on the ordered list (dealt in place of a
stacked-strips layout the spec rules out); seed:242f6a88fb99ce18.

FINISH: unreviewed and undocumented is unfinished; this build ends with the finish review, the
verdict, DESIGN.md, and every shipping raster carrying its provenance

## Unresolved

- "See the comparison" on the opened box waits for task 3.2.2, which puts the opened box in front
  of the results view. Nothing rises out of the opened box: every figure lives on the results page
  (29 October 2026).
