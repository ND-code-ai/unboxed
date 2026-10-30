# Phone fixes, after the hackathon

From the critique of 30 October 2026 (task 3.10; its snapshot is gitignored, so this file stands on
its own). The wide
screen got these results-page changes for the submission; the phone view was left as it was, at the
user's call, to do afterwards. Nothing may be merged or deployed until judging ends (Wed 23 Dec 2026,
12:00 PT). All are page-only unless marked. Measurements are from a 390 x 844 viewport.

## Most important

- [ ] **The question arrives below the fold.** Only the card's title shows at the bottom of the
  screen, with the chips out of view, and the next question repeats this. In `QuestionCard`
  (`web/components/InterviewPanel.tsx`), below `lg`, scroll the card into view on mount and on a
  question change when its chips are not fully visible, with a scroll margin, instantly with reduced
  motion. The cost: the label dropping onto the box goes out of view while answering; the panel label
  still shows the answer. Decide this trade-off first.
- [ ] **The pinned figure contradicts the verdict.** The strip shows cost per year (€8 against €9),
  so the cheap pan looks better, while the sheet says the durable one costs €5.98 less over 10 years
  (4 whole purchases against 2, not plain division). The figure has no label either. In
  `web/components/OptionDeck.tsx`, show the cost over 10 years, as the wide screen's Cards view now
  does (drop the `lg:hidden` and `hidden lg:block` pair).
- [ ] **The true cost is not where anyone looks.** The savings line sits only on the durable option's
  card, and the deck opens on the cheap pan. Show the savings lead of `ReportHead`
  (`web/components/ResultsView.tsx`) below `lg` too, and drop the `lg:hidden` on the savings row in
  `OptionRows` (`web/components/OptionCell.tsx`).

## Results page, as the wide screen now has it

- [ ] The Option A, B, C letters: over the name and in the strip, drop the `hidden lg:block` pair in
  `OptionRows` and `OptionDeck`; on a card the savings line still spells out both long names, and the
  lead above would use `leadOf`.
- [ ] Order the card's rows as the sheets' are: `sheetRowsOf` in `web/lib/results.ts` puts the cost per
  year straight after the price, with no address row. Then `OptionDeck` can use it and `rowsOf`
  loses its parameters. The wide screen's Cards view gets this too, since it shares the deck.
- [ ] Set the cost per year a size larger: drop the `lg:` prefixes on `large` in `Figure`
  (`web/components/OptionCell.tsx`), and on `ownCase`, which keeps "CO2e" and the "Against …" key from
  being shouted in capitals.
- [ ] The evidence summary's weight: `font-semibold lg:font-normal` in `ReportHead`; regular once the
  savings lead above it.
- [ ] The check list runs about a phone screen of definitions and care tips. Fold a long group behind
  a `<details>` with its count, keeping the price check always open (the wide screen uses two columns
  instead).
- [ ] The results run about 2,700 to 3,000 px. The pinned strip stays on through the check list, where
  tapping it changes a card out of sight: unpin it past the deck.

## The questions and the wait

- [ ] After the last chip, `ClosingCard` autofocuses its text box, which on a phone will likely raise
  the keyboard over "Show my options" for an optional step. Skip the autofocus on `pointer: coarse` in
  `web/components/InterviewPanel.tsx`.
- [ ] During a run the status line is off-screen; only the box and the hint are in view. Show the
  current step's line near the box.
- [ ] The placeholder clips to "a product, and your budget", losing "(optional)", so the budget reads
  as required. Shorten the words or let it wrap (`web/components/FaceComposer.tsx`).
- [ ] The box moves about 14 px when the wait's hint closes, because the column is centred. Keep its
  space, or anchor the column at the top.
- [ ] "See the comparison →" is 242 px wide against a back rim of about 180 px, and the opening is
  about 35 px deep against a 52 px button, so it covers most of the opening. Try 16 px type at 44 px.

## Small type and targets

- [ ] Station names are 11 px bold on coral, and the hint and the privacy line 12 px; the privacy line
  is the smallest text on the face.
- [ ] On the box at this width, "Hob compatibility?" and "Usage frequency?" are 8 px and the marker's
  label 9.2 px.
- [ ] The text box measures 229 x 20 px, under the 24 px target size.
- [ ] The × on the notes is 32 px, under the 44 px usual for touch.
