# Design brief: the chat page

What the design of the chat page (task 3.1.3) must know before Impeccable's direction round
runs. `PRODUCT.md` holds the product truth; this file holds what was settled for this one
surface in the Impeccable question rounds of 27 October 2026 and the review after them. The
surface brief Impeccable writes takes its content from here. Delete nothing from the earlier
rounds without reading this first.

## The job

The shopper types a need or pastes a link, checks the "Looking for" line, then answers up to
five questions by tapping chips, typing a reply in their own words, or both, or skips, and sees
what the app took from a typed reply ("From your reply: …") before the agents run. Then they
watch per-agent progress until the report, which opens as a second page with this same thread
beside it (to the right on desktop, below on a phone).

## Success

- The questions feel worth answering: each shows why it is asked and where that comes from, and
  at least one raises something the shopper had not thought of.
- The shopper always knows what the app understood and what it is doing, including during the
  20 to 30 s wait.
- A reply the app could not read keeps their text and lets them send again.

## Mode

Two modes on one page, recorded in the surface brief so later passes (`critique`, `polish`,
tasks 3.2.1 and 3.2.2) do not "correct" the opening back to a form:

- **The first viewport, before and just after the first message, is an Experience surface.**
  It is the product's opening for a first-time visitor and for a judge in the demo; it may
  commit a colour strategy (Committed or Drenched), a display face with a point of view, and one
  dominant element at large scale.
- **The questions, the composer and the progress below follow Operate rules.** Readable,
  restrained, built in code.

The direction round runs with `concept-seed --scope direction --mode experience`. An earlier
run with `--mode operate` (two rolls, 27 October 2026) gave form-like pages and was abandoned;
do not resume it.

## The memorable moment: the box

A plain product box is the page's one dominant element. The box is a fixed element of the
surface, not a candidate aesthetic: every direction dealt for this page carries it (open in the
first viewport, labels dropping in); directions vary the world around it, never whether it is
there, and a card that drops it is declined. It has three states:

1. **Labelling.** The box is marked with what the shopper is looking for ("FRYING PAN · €50").
   On Next the request stays on the face, faded (see "The opening" below); a blank label slides
   in from the face's top edge, over it, and settles just below it with a slight turn, a black
   marker at its start, hovering while the request is read. When what was understood arrives
   ("frying pan · €50": the category and the budget, or the category alone), the marker writes
   it on in capitals, left to right, and lifts away; the faded request stays in view. A request
   that could not be read gets "?", and the panel asks again (with reduced motion the label
   appears written). Each answer they give becomes a label stuck
   on the front face; on desktop a line briefly joins the answer's label in the thread to the
   same label on the box (the chip is gone by then, as the questions are asked one at a time),
   on a phone the labels simply stick to the box. On the box a label carries the answer alone,
   on one line, so five fit the face at phone width; a skipped question gives a dashed label
   ("dishwasher?"), so skipping is visible but not punished. When the questions are asked the
   face clears for their labels: its heading fades, and the request rises to the face's top, the
   first label with it (28 October 2026). A small count ("3 of 5 labelled"), printed in the face's
   top right corner beside the request, replaces any progress bar. Once the reply is read, each
   factor of the user's own the reader kept becomes a label too: its phrase, cut short with an
   ellipsis at about 30 characters on the box, whole in the panel. What the shopper wrote stays in
   the panel only: a closing step whose words add nothing gets no label.
2. **Sealed and scanned.** After "Show my options" the box is sealed: the labels close up at the
   top of the face, the request fading from under them (it comes back as the box opens), and a
   window in the front face shows the scan: the line of each agent still at work, as its `progress` event arrives,
   in the words of `STARTED` in `wording.py`; the route line under the box shows where the
   run is. It reads as an x-ray of the price, not a loading bar. The status line under the
   thread is the live region for progress ("The thread", below).
3. **Opened.** When the report lands, the lid opens and "See the comparison →" rises in the
   opening, as if pulled out of the box, the page's primary action, which opens the results page. Nothing else rises out of
   the box: every figure lives on the results page, where the true cost is laid out option by
   option (decided 29 October 2026, when task 3.2 was
   split; the brief first had the price, years, cost per year, CO2e and used options rise out
   as labelled parts).

Keep it off the retail look: the labels are the shopper's criteria, never an order, a price
tag with a buy button, a barcode, a tracking number or "shipped". Dashes mark a skipped answer
and nothing else: a control that cannot be used now fades, and keeps its solid line. Storyboard: the "Idea · The
box" artboard on the wireframe canvas (Cowork, 27 October 2026).

**The opening (28 October 2026).** Before the first send the field fills the page and the box's
front face is the composer: "What goes in the box?" as its heading (Archivo, about 30 px); under
it, a borderless, transparent text box in Archivo, ink, about 26 px and shrinking as a request
grows so it never scrolls (a phone keeps 16 px), above a faint baseline, its placeholder "a
product, and your budget (optional)" a step lighter than typed words (`#CDB8B1`), so the empty
face reads as empty; along the face's foot, "Or paste a product link." and "Next", a solid ink
button (on a phone both sit beside the heading, to leave the face to the request). The marker
writes only what the app writes. The examples are small paper labels under "Or try one",
slightly turned, by the face's right edge (in a row below the box on a phone); one tapped is
written onto the face. The route line is under the box, every station ahead.

On Next the request stays where it was typed and fades to muted, like pencil; the hint and the
button go, and the same words appear in the panel as the shopper's quote. On a wide screen the
panel's column opens beside the field and the box slides left with it, a layout change animated
over about 600 ms (`components/Thread.tsx`), not a jump; Start again and Edit run it back. The
panel shows "Reading your request…" once, with no composer, which returns with the questions under
its own label. With reduced motion the box snaps to its place.

**How it is built.** Flat faces drawn in code (SVG paths or CSS 3D faces), three layers in this
order: the back of the box, the labels and parts, the front face. Every part carries the same
2 px ink edge as the face. Flaps hinge on their edges (`transform-origin`). No WebGL, no SVG filters, no `foreignObject`, no backdrop blur. The box
drawing is `aria-hidden`; every label and status line is also plain HTML in the thread, so
screen readers lose nothing.

**Transitions.** One `state` prop (`labelling`, `sealed`, `open`) drives everything; the same
component animates both ways, with Framer Motion variants or CSS transitions on `transform`.
Nothing is a swap of pictures.

- A label drops in from above when its answer is given, passing behind the front face.
- Labelling → sealed, about half a second: the four flaps rotate inward in two pairs (the short
  flaps first, the long ones over them), the tape slides across the seam, and the scan window
  opens in the front face. The labels stay.
- Sealed → open: the reverse (tape lifts, flaps rotate outward), and once the flaps are clear
  "See the comparison →" rises once in the opening, about 300 ms; the focus moves to it and
  the status line says the comparison is ready.
- With reduced motion (`useReducedMotion`), flaps jump to their end position, "See the
  comparison →" appears without moving, and a short crossfade is acceptable.

**What the API gives today.** `progress` events per agent (started, finished, with their
lines). No per-station counts ("6 candidates", "3 priced") yet; the scan shows the agent's line
and its state, and a count field is a left-over item for task 3.1.4.

## References, not designs

- `docs/design/references/box-open.png`: a flat, matte, kraft-coloured box, generated for the
  geometry and the viewpoint only (front, slightly above; inside back wall visible; side flaps
  angled towards the viewer). The colour is not a decision; the world's palette replaces it.
- `docs/design/references/box-sealed.png`: the same box closed, flaps meeting in the middle
  under a tape strip, with the scan window cut into the front face. The end state of the
  labelling-to-sealed transition; the flaps are drawn as separate shapes so they can rotate
  between the two images, never a swap of pictures.
- A 21st.dev "bucket" component (Framer Motion chips dropping into a Figma-exported glass box,
  `motion/react`): a motion reference for the drop-in layering. Not shipped as is: glass, SVG
  filter stacks and `foreignObject` backdrop blur (unreliable in Safari), a 2 s auto-cycle with
  no reduced-motion check, two icon packages for four icons, and no licence header. Rebuild the
  mechanism; keep nothing else.

## The world, as locked (27 October 2026)

Total Design, coral, chosen on Impeccable's decision page. Tokens:

| Token | Value | Used for |
|---|---|---|
| field | `#EF6A4C` | the Experience half: the ground behind the box; on the results page, the ground behind the option sheets (task 3.2.1) |
| panel | `#FBF6F3` | every Operate surface: the questions, the composer, and beside the results the rounds read back |
| paper | `#FFFFFF` | the box's front face, labels, the current-question card; always with a 2 px ink border on the panel |
| ink | `#17100E` | type, borders, filled chips |
| muted | `#6B4A42` | reasons, source lines (7.3:1 on the panel) |
| flap back / sides / lip | `#F7C3B5` / `#FAD9CF` / `#FDEDE8` | tints of the field, the box's flaps |
| inside | `#5A1E14` | the box's inside |

Considered and dropped for the panel: cream `#FDF1EC` (fine, but less white than wanted), the
flap tint `#FBD3C8` (too fleshy), tan `#DCA892` and `#B49E97` (mid-tones; muted text fails
4.5:1), lighter coral `#F39079` (no longer calm), lime `#CEF7A0` (the eco palette).

## The interview panel

`docs/design/references/interview-panel.html` (and `.png`) is the chosen layout, rendered at
desktop and phone width; build to it, not to a description of it.

- **Answered questions become labels** at the top of the panel: a small-caps key ("HOB") over a
  bold value ("induction"), white with the ink border, slightly rotated; a skipped question is
  the same label dashed, in muted ("dishwasher?", as on the box). One component draws the label in
  the panel and on the box, where it carries the answer alone ("induction", or "dishwasher?"
  dashed), to fit five on the face; the factor names stay in the panel.
- **The current question** sits in a white card: the question in 21 px bold, the reason in
  muted, "Source: …" small and underlined, then the chips (white, ink border; the chosen one
  filled ink). A numeral beside the question ("2 of 5") is the progress cue; no bar.
- **Below the card**, one muted line: "2 more questions · or skip the rest"; "skip the rest"
  sends what was given so far.
- **"Something else" ends the chips** (28 October 2026): the same chip with a small pencil mark,
  solid like the others (a dash is a skipped answer only). Tapping it unfolds a field inside the
  card, focused, with "Next" under it; the words are the question's answer and its label. Tapping
  another chip folds the field and keeps its words, the chip being the answer then.
- **After the last question, one optional step:** "Anything else we should know?" in the same
  card, one field, then "Show my options", which sends. It is not counted in "n of N", and it is
  all a pause with no questions asks. No composer at the questions: no "Skip all", no Send.
- **One reply.** The page joins what was written into the one reply the API reads, each answer in
  the user's own words after `About "{question}": `, the closing step's words last; over 2,000
  characters it is not sent, and the step with the most words opens again with the
  `reply_too_long` words. When answers come back not applied (`reply_unread`,
  `reply_unanswered`, or another code that leaves the session waiting), every chip and word
  stays, and the step with the most words, or with none written the first question with no
  answer, opens again with the code's words under its field.
- **Earlier answers stay editable:** tapping a label reopens its question.
- The alternatives considered (an index sheet with large numerals, a ruled job ticket with
  checkboxes and footnotes) are in the same mock's history; the ticket is the fallback if live
  questions run much longer than the examples.

## The route line

The rule under the box is the process, drawn as a route diagram (28 October 2026; mock in
`docs/design/references/route-line.html` and `.png`). It is the modest form of the "live graph
view" in `docs/IDEAS.md`, and the one element that shows the app's side of the work while the
box shows the shopper's.

- **Four stations on one line, the agents in order:** your request (supervisor), questions
  (brief), options (TCO), CO2e (LCA). The second-hand agent is a stub in this version, so the page
  shows no station, progress or trail for it (30 October 2026). Their words are in
  `web/lib/wording.ts`, as every word the page holds is, chosen from the glossary's and the
  report's own terms.
- **States, from the stage and the `progress` events:** a finished station is a filled dot with
  a tick; the current one a ringed dot; a station ahead a hollow dot, its name lighter. The dot
  alone marks it: the agent's line is the status line's, shown once. Before the first send every
  station is ahead. "questions" stays current while the questions are answered, and until the
  options agent starts. A step cut
  off by a lost stream stays current while the session is read again.
- **Motion:** nothing moves along the line. The current station's ring breathes slowly (about
  2 s a cycle, growing 1.45 times as it fades, no colour change): the page's one looping "still
  working" signal, so the scan window has no sweep and the status line no dash. The one-shot
  transitions (label drops, sealing and opening, the marker, the leader line) stay. With
  reduced motion the ring is still.
- **The same line on the results page** (task 3.2.2), above the options with every station
  ticked, where each station opens that agent's part of the evidence trail. One element for
  progress, transparency and the trail's index.
- **Before the results page** (30 October 2026), during both waits and between them, at the
  questions and with the box open, each station opens a short fixed note in plain words on what its
  agent does in any run, with a cross to close it, and a hint under the line during a wait until
  one is pressed or the hint's own cross closes it. A real run
  takes minutes and the API sends no detail until an agent ends, so the notes describe the steps,
  not this run; showing this run's trail live would need a new stream event and a backend redeploy.
- **The sealed box's scan window** shows the detail of the current stations (each agent's line,
  later the counts of the 3.1.4 left-over item); the route line shows the position. The two do
  not repeat each other.
- **The brief agent's step** is the reason this exists: between the request and the questions,
  "questions" is lit and the status line carries one muted line under it on what it is doing
  ("Reading buying guides and care advice, then choosing up to five questions."), held in
  `web/lib/wording.ts`. It names what the category research really reads; tester
  reviews and owner reports come later, with the options.
- The "n of 5 labelled" count is printed small on the box's front face, top right, while the
  questions are open; the line is not a progress bar.
- Accessibility: the line is a list (`<ol>`) with the current station marked `aria-current`,
  so it reads as a list of steps; the dots are decoration.

## The thread

The panel's thread is grouped into rounds (28 October 2026), each under a small heading in the
overline style: **"Your request"**, and from the questions on **"Your answers"** (in
`web/lib/wording.ts`).

- **Within a round, the shopper's words come first**, as their quote, then what the app took
  from them: the "Looking for" line, any warnings and the request's own answers; or the answer
  labels, then the "From your reply" lines. While the questions are open the answers round holds
  the labels and the question card; once sent, the closing step's words, if any, are its quote.
- **Typical yearly costs** are small muted notes at the end of the request round.
- **Progress is one status line** under the rounds, the live region for it (`role="status"`):
  the started line of the step at work, with what category research reads under it, replaced as
  the next step starts and gone when the run ends. No "Finished …" lines; the route line keeps
  where the run is. Warnings and errors stay in their round, which is read out as it grows.
- **"Nothing you wrote changed an answer or added a requirement."** shows only when the reply
  added nothing at all: never beside a requirement of the user's own the reader kept.

## Tone of the thread

A case being built with the shopper (their words, the criteria they chose, the evidence coming
in), not a chat with a bot. Copy follows `docs/product.md` ("Tone") and the rules of `docs/wording.md`.

## What would feel wrong

- Eco-green clichés: leaf greens, earth tones, nature motifs; reads as a generic
  sustainability claim.
- A retail or checkout look: a shop, a deal site, a delivery tracker; the app sells nothing.
- AI-chatbot sameness: generic bubbles and gradients. The thread is this product's, not a
  ChatGPT clone.
- Playful or gamified: badges, confetti, scores; the app gives no scores and keeps a calm tone.
- Corporate office-software look: grey ribbons, dense toolbars, enterprise forms.
- Template-site chrome: a multi-link top menu, hero banner, sidebar widgets, big footer. Two
  screens, no site to navigate; chrome beyond the product name and "New search" is noise.
- Spectacle as decoration: gradient washes, glow, glass, near-black with one neon accent
  (the look of most agent demos), 3D scenes.

## Directions considered and dropped

- **Departures board** (dealt in the Operate round): too literal, and a small grey box between
  form fields as built.
- **Factory or production line:** the first picture anyone draws for a multi-agent app, close
  to a known 21st.dev showpiece, and about the machinery rather than the purchase. The box keeps
  what was good in it (the agents visibly at work, in the scan) without drawing machines.
- **Exploded view** of the price as a technical drawing: kept, inside the box's third state.

## Accessibility

WCAG 2.2 AA as a target without an audit: semantic HTML, contrast 4.5:1, visible focus,
`aria-live` for progress, reduced motion respected, every figure also as text.
