---
name: Unboxed
description: What a durable product really costs over time, and a better option within budget.
colors:
  field: "#EF6A4C"
  panel: "#FBF6F3"
  paper: "#FFFFFF"
  ink: "#17100E"
  muted: "#6B4A42"
  faint: "#CDB8B1"
  flap-back: "#F7C3B5"
  flap-side: "#FAD9CF"
  lip: "#FDEDE8"
  inside: "#5A1E14"
typography:
  overline:
    fontFamily: "Archivo, system-ui, sans-serif"
    fontSize: "0.8125rem"
    fontWeight: 600
    lineHeight: 1.2
    letterSpacing: "0.08em"
  headline:
    fontFamily: "Archivo, system-ui, sans-serif"
    fontSize: "1.625rem"
    fontWeight: 800
    lineHeight: 1
    letterSpacing: "-0.01em"
    fontVariation: "\"wdth\" 125"
  title:
    fontFamily: "Archivo, system-ui, sans-serif"
    fontSize: "1.3125rem"
    fontWeight: 700
    lineHeight: 1.375
  body:
    fontFamily: "Archivo, system-ui, sans-serif"
    fontSize: "1rem"
    fontWeight: 400
    lineHeight: 1.5
  body-small:
    fontFamily: "Archivo, system-ui, sans-serif"
    fontSize: "0.875rem"
    fontWeight: 400
    lineHeight: 1.43
  label-key:
    fontFamily: "Archivo, system-ui, sans-serif"
    fontSize: "0.6875em"
    fontWeight: 600
    letterSpacing: "0.06em"
  label-value:
    fontFamily: "Archivo, system-ui, sans-serif"
    fontSize: "1rem"
    fontWeight: 700
    lineHeight: 1.25
  hand:
    fontFamily: "Permanent Marker, Archivo, cursive"
    fontSize: "1.15em"
    fontWeight: 400
    lineHeight: 1.25
  face-question:
    fontFamily: "Archivo, system-ui, sans-serif"
    fontSize: "1.875rem"
    fontWeight: 700
    lineHeight: 1.15
    letterSpacing: "-0.01em"
  face-request:
    fontFamily: "Archivo, system-ui, sans-serif"
    fontSize: "1.625rem"
    fontWeight: 400
    lineHeight: 1.3
rounded:
  none: "0px"
spacing:
  xs: "8px"
  sm: "12px"
  md: "16px"
  lg: "24px"
  xl: "32px"
  2xl: "48px"
  panel-top: "96px"
components:
  button-solid:
    backgroundColor: "{colors.ink}"
    textColor: "{colors.paper}"
    rounded: "{rounded.none}"
    padding: "8px 20px"
    height: "44px"
  button-solid-hover:
    backgroundColor: "{colors.inside}"
    textColor: "{colors.paper}"
  button-outline:
    backgroundColor: "{colors.paper}"
    textColor: "{colors.ink}"
    rounded: "{rounded.none}"
    padding: "8px 20px"
    height: "44px"
  button-outline-hover:
    backgroundColor: "{colors.lip}"
    textColor: "{colors.ink}"
  button-small:
    backgroundColor: "{colors.paper}"
    textColor: "{colors.ink}"
    rounded: "{rounded.none}"
    padding: "4px 12px"
    height: "36px"
  chip:
    backgroundColor: "{colors.paper}"
    textColor: "{colors.ink}"
    rounded: "{rounded.none}"
    padding: "8px 20px"
    height: "44px"
  chip-pressed:
    backgroundColor: "{colors.ink}"
    textColor: "{colors.paper}"
  button-link:
    textColor: "{colors.ink}"
    padding: "0px"
  textarea:
    backgroundColor: "{colors.paper}"
    textColor: "{colors.ink}"
    rounded: "{rounded.none}"
    padding: "12px 14px"
    height: "96px"
  label-panel:
    backgroundColor: "{colors.paper}"
    textColor: "{colors.ink}"
    typography: "{typography.label-value}"
    rounded: "{rounded.none}"
    padding: "6px 12px"
  question-card:
    backgroundColor: "{colors.paper}"
    textColor: "{colors.ink}"
    rounded: "{rounded.none}"
    padding: "16px 20px 20px"
  scan-window:
    backgroundColor: "{colors.inside}"
    textColor: "{colors.lip}"
    rounded: "{rounded.none}"
---

# Design System: Unboxed

This file records the world as the chat page shipped it (task 3.1.3). Later surfaces, starting
with the results page of tasks 3.2.1 and 3.2.2, inherit this world: read this file first. For the box's states and
behaviour, `docs/design/chat_page_brief.md` wins over this file. For every fixed word on screen,
`wording.py` and `web/lib/wording.ts` win, written by the rules of `docs/wording.md`; nothing here
sets copy. The tokens live in `web/app/globals.css`
(Tailwind's `@theme`); the frontmatter above mirrors them.

## Overview

**Creative North Star: "The Labelled Box"**

The purchase is set like a Dutch public information system (Total Design, PTT), painted coral.
One open box sits on a coral field. The shopper's criteria become white labels stuck on its
front. The box is sealed while the agents work and opened when the answer is ready, empty but for
the way to the comparison. Beside it,
on a calm off-white panel, the thread does the reading and answering. Before the first message
the field fills the page and the box's face is the composer; on Next the request stays on it,
faded like pencil, and the app's marker writes what it understood on a label over it.

The page has two modes. The coral half is Experience: large, spare, one object. The panel half
is Operate: the same type and palette, smaller and quieter, built for reading and tapping. Every
working surface is white paper with a 2 px ink border, square at the corners. State is shown
with lines: a dash marks a skipped answer and nothing else, solid is the rule, whatever is moving
right now is inverted, and a control that cannot be used now fades.

The world refuses the AI-chat column of bubbles under a centred input, eco-green palettes and
nature motifs, retail and deal-site looks, scores and badges, and spectacle (gradients, glow,
glass, shadows).

**Key Characteristics:**
- A coral field with one drawn object, beside an off-white working panel.
- White paper, 2 px ink borders, square corners, no shadows but the one on the opened box's button.
- Archivo throughout: expanded and extra bold in lowercase for the wordmark, normal width for
  work; a marker hand only for what the app writes on the box.
- State as line form: solid, inverted, and a dash only for a skipped answer.
- Labels slightly turned, as if stuck on by hand.

## Colors

One saturated colour, its own tints, and a warm near-black. Everything else is white or the
panel.

### Primary
- **Signal Coral** (field): the ground of the Experience half, behind the box, and the tape that
  seals it. Ink type on it reaches about 6:1. It never sits behind a price.

### Secondary
- **Box Tints** (flap-back, flap-side, lip): three tints of the field, used for the box's flaps
  from darkest at the back to lightest at the front lip. Outside the box, the lip tint is the
  hover fill for outline buttons, chips and labels, and the fill of a line still at work in the
  scan window.
- **Box Inside** (inside): the dark red-brown inside the open box and the ground of the scan
  window. Also the hover fill of the solid button.

### Neutral
- **Ink** (ink): all type, every border, filled chips, the solid button, focus rings, text
  selection, scrollbar thumb. Warm, not pure black.
- **Paper** (paper): the box's front face, labels, the question card, the text box, outline
  buttons and chips. On the panel it always carries the 2 px ink border.
- **Panel** (panel): the ground of every Operate surface: the thread, the composer, and beside the
  results the rounds read back. Locked by the user; a detector ignore in `.impeccable/config.json`
  records that. The results page's options stand on the field instead, each on its white sheet
  (the user's call, 29 October 2026).
- **Muted Brown** (muted): reasons, source lines, the "n of 5" count, "more questions", label
  keys, not-sure labels, placeholders, the face's hint (7.3:1 on the panel).
- **Faint** (faint): the placeholder on the box's face only, a step lighter than typed words so
  an empty face reads as empty (the user's call, 28 October 2026). It is 1.9:1 on paper, under
  AA; the visible heading "What goes in the box?" carries the meaning, and `impeccable detect`
  reports it as an advisory, left standing rather than silenced for the whole page.

### Named Rules
**The One Coral Rule.** Coral is the field and the tape, nothing else. Buttons, chips, links and
borders are ink. No coral type, no coral buttons, no coral behind a figure: on the results page
the field is the ground between the sheets, and every figure sits on paper.

**The Tints Stay Home Rule.** The flap tints belong to the box. Off the box, only the lip tint
appears, and only as a hover or working fill.

## Typography

**Display Font:** Archivo, self-hosted via `next/font` with its width axis (fallback system-ui,
sans-serif)
**Body Font:** Archivo, normal width
**Hand Font:** Permanent Marker, self-hosted via `next/font`, for what the app writes on the box
only

**Character:** One grotesque in two cuts. The expanded cut (width 125) at extra bold, in
lowercase, is the public-sign voice of the wordmark; the normal cut does all the work, the
shopper's own words on the box's face included. One second voice, kept to what the app writes on
the box: what was understood ("frying pan · €50") is written on the first label in a marker hand,
as a box is labelled by hand; the answer labels stay printed.

### Hierarchy
- **Face question** (700, line height 1.15, -0.01em): "What goes in the box?" heading the face,
  sized with the box (about 30 px at 1280 by 800, never under 15 px).
- **Face request** (400, line height 1.3): what goes in the box, typed on the face, in ink; about
  26 px at 1280 by 800, shrinking with its length so it never scrolls, never under 16 px (which a
  phone keeps). Once sent it stays, in muted.
- **Hand** (Permanent Marker 400, in capitals): the first label, what the app understood or "?".
- **Overline** (600, 0.08em, uppercase): "Or try one" over the examples, in ink, 13 px; the
  thread's round headings, a sheet's group headings and the check list's heading (the
  `heading-overline` utility). Once the thread starts, the composer's label in the panel is
  semibold body size.
- **Headline** (800, 1.375rem to 1.625rem, line height 1, -0.01em, expanded, lowercase): the
  wordmark, "unboxed." with its full stop, top left of the field.
- **Tagline** (400, 0.875rem to 1rem, normal width, ink): one line under the wordmark.
- **Title** (700, 1.3125rem, line height 1.375, balanced): the current question in its card.
- **Body** (400, 1rem, line height 1.5): the thread, reasons, the text box. Turns break long
  words anywhere so a pasted link never overflows.
- **Body small** (400, 0.875rem): source lines, "more questions", small buttons, the tracing
  notice. The count on the box is semibold capitals in muted, sized with the box. The route
  line's station names are bold (lighter while ahead), 0.6875rem on a phone and 0.9375rem from
  1024 px.
- **Label key** (600, 0.6875em of the label, 0.06em, uppercase, muted): the factor's name on a
  label in the panel, over its value.
- **Label value** (700, lowercase, line height 1.25): the answer on a label. Not-sure labels
  drop to 600.
- **Buttons** use semibold (600) at body size.

### Named Rules
**The Expanded Is For Signs Rule.** The expanded cut is only for the wordmark. Labels, questions
and the thread use the normal width.

**The One Hand Rule.** The marker face is for what the app writes on the box and nothing else:
the first label. The shopper's own words are never in it, and it is never used for the panel, a
heading or a figure.

**The Lowercase Sign Rule.** The wordmark and label values are set in lowercase (the first label
is written in capitals, as above). Uppercase is only the label key and the overline.

## Layout

A twelve-column grid (four on a phone), inset 16 px on a phone and 32 px from 1024 px; it is not
drawn. (Ticks along the page's top edge marked it until 30 October 2026, when the user removed them
as a convention no shopper would read.)

Before the first send the field fills the page: the box with the composer on its face, and from
1024 px the examples by the face's right edge, the box no wider than the height leaves room for
and narrowing to leave the examples room either side; on a phone the examples come in a row below
the box (The Opening Move, below). From the first send the page is two columns. The coral field takes the left part, full height and sticky; the panel takes the right
and scrolls. They split 5 to 3 (62.5% to 37.5%), as the
user-locked panel reference (`docs/design/references/interview-panel.html`) sets them. On a phone the field comes first, the panel below it.

On the field: the wordmark top left with the tagline under it, then the box centred in the remaining height, spanning the
field's width from flap tip to flap tip but, from 1024 px, no wider than the height leaves room
for (at most (100dvh - 15.5rem) × 928 / 600, at least 40rem), over the route line: a 2 px ink line as wide as the
box with the agents as stations on it. The line never crosses into the panel. The answered
count is printed in the face's top right corner, beside the request, while the questions are
open.

On the panel: a single column. Padding 16 px on a phone; 48 px at the sides and 96 px at the top
from 1024 px. Turns sit 20 px apart, blocks 24 to 32 px apart; controls in a row sit 8 px apart.

When the report lands the box opens on "See the comparison", and pressing it puts the results
page in the field's place (tasks 3.2.1 and 3.2.2), opened at its top with the focus on it: from
1024 px the field spans the grid's columns 1 to 8, and the panel 9 to 12 with the rounds read back and "Start again" at their foot; the field is no longer sticky, and
the page scrolls as one. Under the wordmark, as far below it as under the box, the route line with
every station ticked, and under it the parts of the evidence trail the stations opened. Then "Your
options" with the budget switch and the view control, the report head, the options (sheets from
1024 px, the deck below it) and the check list, 24 px apart. On a phone the rounds fold under the
options.

Spacing steps in use: 8, 12, 16, 24, 32, 48, and 96 px for the panel's top.

## Elevation & Depth

Flat. No shadows but one. Depth comes from the drawing of the box (the dark inside behind the
paler flaps, the front lip over the labels) and from the labels' small turns. A label drops in
behind the lip, so layering is told by the object, not by blur or shadow. The one shadow is on
"See the comparison →", the thing pulled out of the box: hard ink, 4 px, no blur, 2 px on hover and
press (the user's call, 30 October 2026). Labels keep none.

### Named Rules
**The Flat Paper Rule.** Surfaces separate by a 2 px ink border or a change of ground, never by
a shadow, glow or blur; "See the comparison →" alone has its hard offset.

## Shapes

Square corners everywhere (0 px). Every working surface is a rectangle with a 2 px ink border.
The box is drawn in flat polygons, every one with the same 2 px ink edge. Labels are plain
rectangles turned between -1.5 and 1.5 degrees, the turn set by their place in the row, so the
same label sits the same way on the box and in the panel. A user's own message is marked by a 3
px ink rule on its left.

Line form carries state: a dashed border is a skipped answer and nothing else; a solid border is
the rule; an inverted fill is chosen or running. A control that cannot be used now keeps its
line and fades to 40%.

### Named Rules
**The Line Form Rule.** State is a border style or an inversion, never a colour code. Dashed is a
skipped answer only, inverted is chosen or at work; unavailable fades.

## Components

### Buttons
Square, firm, quiet until pressed.
- **Shape:** square (0 px), 2 px border, semibold, 44 px tall (36 px small; 52 px at 18 px type,
  large, for "See the comparison →" only).
- **Solid:** ink fill, paper type. The step forward only: "Next" on the face and under an answer
  in the user's own words, "Show my options" at the closing step. Hover fills with the box
  inside.
- **Outline (default):** paper fill, ink border and type. Start again, controls inside a line
  (small size). Hover fills with the lip tint.
- **Link:** no border or padding, underlined 1 px at 3 px offset; hover thickens the underline
  to 2 px. "skip the rest".
- **Disabled:** the button keeps its look at 40% opacity, with a not-allowed cursor; no hover. On
  the field it keeps its paper instead, its border and words in muted.
- **Focus:** a 3 px ink outline 3 px outside the element, for every focusable thing but the results
  page itself, focused only so reading starts there, where it would frame the whole field.
- **Motion:** colour changes over 150 ms.

### Chips
- **Style:** the outline button, left-aligned and wrapping: paper, 2 px ink border.
- **State:** hover fills with the lip tint; the chosen one (`aria-pressed`) is filled ink with
  paper type. "Not sure" is a chip like the choices.
- **Something else:** the last chip, a 14 px pencil mark (1.75 px stroke, in the type's colour)
  before its words; solid, never dashed. Chosen, it unfolds a field in the card.

### Labels
One component draws a label on the box and in the panel.
- **Style:** paper, ink border (2 px in the panel; scaled with the box on it), a small key over
  a lowercase value, turned slightly.
- **On the box:** the value alone, on one line, then an ellipsis, so five labels fit the face at
  phone width; the panel keeps the keys.
- **Not sure or skipped:** the same label with a dashed border, muted type, semibold value, reading
  its key and "?" ("dishwasher?") on the box and in the panel alike.
- **In the user's own words:** the same label, its value as written (lowercase), at most 16 em
  wide and two lines (one on the box, about 30 characters), then an ellipsis.
- **Added by the reply:** each factor of the user's own the reader kept, once the reply is read:
  its phrase alone, no key; on the box on one line, cut with an ellipsis at 16 em (about 30
  characters), in the panel whole. What the shopper wrote is never a label itself.
- **In the panel:** a row at the top of the questions. Tapping one reopens its question; hover
  fills it with the lip tint. Once the answers are sent they stop being buttons and show the
  answer whole, wrapping inside the column.
- **Starters** (`components/Starters.tsx`): the example requests as the same labels, bold
  0.9375rem on one line, under the "Or try one" overline. At the opening they stand by the
  face's right edge, level with its foot, stacked and nudged unevenly; in a row below the box on
  a phone, and under the panel's composer when it opens empty again. Tapping one writes it into the
  composer. No hole or eyelet: a label beside a price is never a tag.

### Cards / Containers
- **Question card:** paper, 2 px ink border, 0 px corners, padding 16 px top, 20 px sides and
  bottom. The question as title, the "n of 5" count in muted small type beside it, the reason
  in muted, the source line small, then the chips 16 px below. No progress bar. "Something
  else" unfolds a text box 12 px below the chips, then "Next".
- **Closing step:** the same card after the last question: "Anything else we should know?" as
  its title and the label of its text box, then "Show my options". No count.
- **A step's message:** why answers were not sent or not applied, in semibold ink under the text
  box of the step opened again for it (under the chips when it has none).
- **Under the card:** one muted small line ending in the "skip the rest" link; none on the last
  question.

### Inputs / Fields
- **Text box:** paper, 2 px ink border, 0 px corners, padding 12 px by 14 px, at least 96 px
  tall (80 px in a card) and growing with its content. Placeholder in muted. The panel's
  composer, when a request does not run; the field under "Something else"; the closing step's.
- **Focus:** the shared 3 px ink outline.
- **Disabled:** faded to 40%, not-allowed cursor.
- **The face** (`components/FaceComposer.tsx`): "What goes in the box?" as its heading; below
  it the request in the face request type, borderless and transparent, over a 2 px baseline of
  ink at 18%; the placeholder, "a product, and your budget (optional)", in faint (the starters
  carry the examples). Focus darkens the baseline to ink in
  place of the outline. Along the foot, "Or paste a product link." in muted small type and
  "Next"; on a phone both beside the heading. Once sent the request stays where it was typed,
  fading to muted over 700 ms, its baseline gone; the hint and Next go. Once the questions are
  asked the face clears for their labels: the heading fades (200 ms) and the request rises to
  the face's top, the labels with it (500 ms, expo ease-out). The count takes the top right
  corner, the request's first line wrapping round it; the corner stays kept once the count goes,
  so the request never moves under its labels.

- **Asking for a budget** (`components/AskBudget.tsx`): a request with no number in it, and no link,
  sent for the first time stays where it is, with a note: small type on paper with the 2 px ink
  border, not turned, fading in over 150 ms. On the face it floats just under the baseline, clear of
  Next, on a phone reaching past the face over the examples; in the panel it stands under the text
  box. It goes when a number is typed. Sent again, the request goes as it is. In either composer
  Enter sends and Shift and Enter start a new line.

### Option Sheet
One option on the results page as a sheet, the layout the user chose as "label sheets"
(`components/OptionSheets.tsx`, `OptionCell.tsx`): paper,
2 px ink border, square. From 1024 px its letter ("Option A", in the report's order, in the overline
style) over its name, so the lead can name it short. Its name in bold body type, linked to its page, with "Over your budget"
under it as a plain paper tag on a 2 px ink edge (semibold, not turned, no fill: a mark, never a
badge), and any mark (out of stock, sold incomplete) as a line. Every figure is a key over its
value: the key in the label key style (600, 11 px, 0.06em, uppercase, muted), the value in body
type with tabular numerals, semibold for the headline figures (the price, the cost figures, the
lifespan, the CO2e) and regular for the rest, muted with its reason when missing. From 1024 px the
sheet goes from the price straight to the cost per year, the number the app is built around and the
one figure set larger (700, 1.625rem), then the cost over the horizon, purchases and cost per use.
The name opens the page, so a sheet has no address row and its savings lead the page instead; the
keys that name CO2e or an option keep their capitals as written. On a card the old order stands, the
link showing its site alone, such as "beslist.nl", never the whole address (phone follow-ups:
`docs/design/phone_fixes_after_hackathon.md`). Under "Durability evidence", what the model read of
the product ("carbon steel, no coating to wear out") under the key "The model's reading, not a sourced
figure". Answers that could not be confirmed fold into one muted line per option ("Interior material,
temperature control: not confirmed on the pages read"), with the full list on the check list. One sheet
per option: groups (cost, lifespan, the user's answers, CO2e) open on a thin 1 px rule at 25% ink. A group gets a heading in the overline style only where no
figure's own label names it: "Durability evidence" under the lifespan, "Your answers" over the
factor values; never a heading that repeats a label. On a wide screen the sheets stand side by
side and share the grid's rows (subgrid), so a figure is level across them and a sheet without it
leaves its row empty; a sheet the budget switch hides leaves its column empty, so the others keep
their width.

### Deck
The results on a phone, and on a wide screen when the view control says Cards
(`components/OptionDeck.tsx`): one option sheet at a time as its option card, the baseline first, then
the API's order. Above it the **strip**, pinned to the top of the viewport on the field: one paper
button per option with its name (semibold, small, two lines at most) over its cost per year in
body type, or from 1024 px that figure's label (12 px) over its cost over the horizon; the card
shown is inverted. A swipe across the card, a tap on the strip, or Previous
option and Next option under the card, with "1 of 3" between them, change the card (a step that
cannot be taken keeps its paper and turns muted, since on the field a fade would let the coral
through); it slides in
from the side it came from (280 ms, expo ease-out) and, stepped from its foot, is scrolled to just
under the strip. With reduced motion it swaps.

### Results Controls
- **Budget switch:** "Hide options over my budget", shown only when one option is over the budget
  and another within it. A 44 by 24 px paper track with a 2 px ink border and an ink knob; on, the
  track inverts and the knob slides right (150 ms). Starts off, not remembered.
- **View control:** Rows and Cards as small chips, the pressed one inverted; from 1024 px only.
  Starts on Rows, not remembered.
- **Tip button:** a 24 px paper square with a 2 px ink border and "?" beside every shipping line,
  inverted while its note is open below the line; a tap, Enter or Space opens it, Escape closes
  it. Inline in a line, it is smaller than a button, at the 24 px target minimum.
- **Report head and check list:** paper blocks with the 2 px ink border. The head holds the
  evidence summary in semibold, then caveats and warnings; from 1024 px the options' savings lead it
  as sentences at 18 px regular, only the amount in bold (a title it is not), naming the options by
  letter ("Option B costs €5 more than Option A") with the note on rough estimates once in muted
  body type, over a 2 px ink rule, with the summary regular under them. From 1024 px a check
  list group's items stand in two columns. The check list has "Check before you
  buy" in the overline style, each group's label in semibold over square ink bullets, and under a 2
  px ink rule, in muted body type, what the request stated and the typical yearly costs.

### Navigation
None. The only chrome is the wordmark with its tagline and, at most, "New search".

### The Box (signature)
An SVG drawing (viewBox 928 by 600) that fills the field's width, with an HTML layer for labels
and the scan window. Three states: open, its face the composer before the first send;
labelling, where on Next the request stays on the face, faded, and a blank first label slides in
from the face's top edge, from under the lip, over the request, and settles just below it with
its turn (650 ms from 300 ms, expo ease-out; the request is measured, so it stays in view at any
length); a black marker (flat SVG: ink barrel, a white band, a muted collar, an ink tip, no
brand) floats in at its start, bobbing while the request is read, then writes what was
understood (the category and the budget the API sends, or "?" for a request that could not be
read) in the hand face, the ink revealed just behind its tip (45 ms a character, linear), and
lifts away; the marker rides in a copy of the first label's
place laid over the lip, so the lip never hides it. When the questions are asked the face clears:
its heading fades and the request rises to the top, the first label with it. Each answered label
drops in from above behind the front lip (520 ms, expo
ease-out); sealed, where the short flaps fold, the long ones close over them, coral tape runs
across, the labels shrink to 72% at the top of the face, the request fading from under them
(220 ms; it returns as the box opens), and the scan window opens below them.
The scan window is the inside colour with the lines of the agents still at work, inverted (lip
fill, inside type); a finished agent leaves it, and the route line shows where
the run is. Opening runs the same steps in reverse, about
half a second. The opened box holds no figures: the only thing to rise out of it is its one control,
"See the comparison →", which opens the results page, where every figure lives (decided 29 October
2026, task 3.2.2). It is the page's primary action, the outline button at the large size with the
one hard shadow, standing in the opening so it reads as pulled out of the box
(`components/SeeTheComparison.tsx`); on a phone, where the opening is shallower than the button, it
stands on the opening's front edge and overlaps the back flap. It rises once
the flaps are clear (300 ms from 560 ms) and takes the focus, as the button that sent the answers is
gone, while the status line says the comparison is ready. With reduced motion every state jumps and
the button simply appears. Behaviour and states:
`docs/design/chat_page_brief.md`, "The memorable moment".

### The Opening Move
On Next, on a wide screen, the page's columns go from all field (1fr 0fr) to field and panel (5fr
3fr) as a transition of `grid-template-columns`, 600 ms, expo ease-out (`components/Thread.tsx`):
the panel's column grows from the right, its content already at its final width so nothing
reflows, and the box, centred in the narrowing field, slides left and shrinks with it, a layout
change rather than a picture of one; the examples go. Start again and Edit run it back. On a
phone the panel simply follows the field; under reduced motion the box snaps to its place.

### Leader Line
On wide screens with motion allowed, a 2 px ink line runs from a new label in the panel, out
across the field and into the same label on the box: it draws in about half a second, holds,
and fades by 1.5 s. A drawing only, hidden from assistive tech.

### Route Line
The rule under the box, drawn as the agents' stations (`components/RouteLine.tsx`): an `<ol>` of
four, in the order they run, with the current one marked `aria-current="step"`. A 2 px ink line
through 16 px dots: done is an ink dot with a field-coloured tick, current a paper dot inside a
2 px ink ring, ahead a hollow dot on the field with a lighter name. The current station's ring
breathes (out to 1.45 times its size as its opacity falls from 1 to 0.2, about 2 s a cycle), the
page's one looping "still working" signal; it is still under reduced motion. Nothing moves along
the line. The dot alone marks a station: the agent's line is the status line's, shown once. On the
results page every station is ticked and is a button that opens its agent's part of the evidence
trail: its name underlined 1 px at 3 px offset (2 px on hover), inverted while its part is open;
pressed again, it closes. From the first send to the results page, during both waits and between
them, the stations are the same buttons (`components/RunRoute.tsx`), each opening one fixed note in
plain words on what its agent does, laid over the box just above the line, with a cross in its top
right corner; Escape closes it too. During a wait a hint under the line says so, until a station is
pressed or its own cross closes it. Behaviour:
`docs/design/chat_page_brief.md`, "The route line".

### Evidence Trail
Under the route line on the results page (`components/TrailPanel.tsx`): one part per station,
in the route's order. Each station opens and closes its own part, so any of them can be open at
once, and with every part open the panel shows the whole trail; the route line is its index. A part
is a paper sheet with the 2 px ink border, 12 px from the next, under its station's name in the
overline style, holding its agent's trail lines in the order they were written, 12 px apart, in
small type: what was found, decided or left out, in ink, long addresses broken anywhere. No agent,
tier or model is named: the station says whose part it is, in plain words. A part
longer than about 32rem (60% of the viewport's height on a short screen) scrolls inside its sheet,
so the options stay near, and its list can take the focus, so it scrolls from the keyboard too. A
part opened below the fold is scrolled into view.

### Thread
The panel's turns in rounds (`components/TurnView.tsx`), 40 px apart, each a section under a
small heading in the overline style (600, 13 px, 0.08em, uppercase, ink): "Your request", then
"Your answers". In a round, 20 px apart: the shopper's quote (a 3 px ink rule on its left), then
what the app took from it. Typical yearly costs are notes in small muted type at the end of the
request round. Under the rounds, one status line in body type, the step at work, with category
research's detail under it in small muted type; it is replaced, never logged, and empty between
runs. Beside the results the rounds are read back: the "Looking for" line drops its Edit, and the
report is not a turn. Behaviour: `docs/design/chat_page_brief.md`, "The thread".

## Do's and Don'ts

### Do:
- **Do** put every working surface on paper with a 2 px ink border and square corners.
- **Do** show state with line form: solid as the rule, inverted for chosen or at work, dashed
  for a skipped answer only; fade what cannot be used now.
- **Do** keep coral to the field and the tape; use ink for every control.
- **Do** set the wordmark in expanded Archivo, extra bold, lowercase; set everything else at
  normal width.
- **Do** use the shared 3 px ink focus outline at a 3 px offset.
- **Do** make every motion jump to its end state under reduced motion.
- **Do** keep every price and figure in plain body type.

### Don't:
- **Don't** add shadows, beyond the one on "See the comparison →", glows, blur, glass or colour
  gradients.
- **Don't** round corners.
- **Don't** use leaf greens, earth tones or nature motifs.
- **Don't** shape anything like a price tag or a starburst, or put coral behind a price; labels
  are plain rectangles with no hole or point.
- **Don't** add a progress bar, score, badge or confetti; the "n of 5" numeral is the progress
  cue.
- **Don't** set the thread as chat bubbles; a user's turn is plain text behind a 3 px ink rule.
- **Don't** add chrome beyond the wordmark and "New search".
