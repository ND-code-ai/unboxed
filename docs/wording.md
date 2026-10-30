# Fixed wording

Read this before writing or changing a caveat, a warning, a decline or any other message whose
words are fixed. The tone these follow, and the principles behind them, are in `product.md`
("Principles", "Tone").

None of these messages is written by a model. The words live in code, and the code is their only
copy (`docs/adr/0009-wording-lives-in-code.md`):

| File | Holds |
|---|---|
| `src/shopper/wording.py` | Every line the terminal app prints or the API sends: declines, error codes, caveats, warnings, labels, progress lines, the interview's fixed lines, report lines, the trail's words, CO2e, what a lifespan rests on, factor values. Each template sits beside the function that picks and fills it |
| `web/lib/wording.ts` | The few lines the page holds itself, because no answer from the API carries them: the words of its controls, its section headings and its tooltips |

The API sends a line finished, as a `Line` of parts (`docs/adr/0008-api-sends-finished-lines.md`),
so the CLI and the page show the same words. To find a message, search either file for a word of
it.

## When something does not go to plan

Every message here says three things, in this order, and leaves out whatever does not apply:

1. what happened, in the user's own terms, quoting what they wrote when that helps;
2. what the app did as a result;
3. what the user can do next.

No apology, no blame and no guess. Avoid "invalid", "error", "wrong", "failed" and "please enter
a valid ...". Never say the app assumed something the user did not write.

| Situation | Do | Don't |
|---|---|---|
| Not covered: not a durable product (food, a service), or a motor vehicle | "This app covers durable products such as cookware, appliances and tools. It can't help with "groceries"." | "Sorry, that is not a valid product." |
| The input could not be understood | "We couldn't tell what you're looking for. Try naming one product, for example 'a frying pan, budget €50'." | "Invalid input. Please try again." |
| More than one product named | "That looks like more than one product. Name one to start, for example 'a frying pan, budget €50'." | "Error: multiple products detected." Or picking one of the two and running with it. |
| A budget that could not be used | "We couldn't read "5o euro" as an amount, so no budget is applied. To set one, start again with an amount in euro, such as "budget €50"." | "Invalid budget." Or "Assuming you meant €50." |
| Nothing found within budget | "Nothing found within €15; the cheapest option is €22." | "Your budget is too low for a decent pan." |
| An option over the budget | "Over your budget", on an option shown as the reference the used listings are measured against | "Worth stretching your budget for." Or any wording that presents it as the pick. |
| A category the app is not tuned for | "This category is not one the app is tuned for; check the sources." | "Results for this category may be unreliable." Or "This category is not supported." |
| Category research gave no decision factors | "We couldn't research "kettle", so the questions and the check list are shorter than usual." | "Research failed." Or questions written from what a model remembers. |
| The questions could not be prepared | "We couldn't prepare the questions for "kettle". What they would have asked about is on the check-before-you-buy list." | "Question generation error." Or leaving the decision factors out of the report. |

## Filling a template

Placeholders are written the same way in both files: `{phrase}`, `{category}`. What fills them
is always written by code:

- **Amounts** arrive formatted and without a sign; a sentence says "less" or "more". Counts are
  formatted too ("1,000", "1,234").
- **Ranges** are rounded outward (`architecture/calculations.md`, "Display rounding").
- **A site** is cut from its URL by code: the host in lower case, without "www.". On the page it
  is a link to its source, a `link` part.
- **A date** is written with the month in English ("17 October 2026"), never the locale's.
- **The user's own words** (`{phrase}`) are quoted exactly as they stand in the request or reply.
- **A string a model wrote** (a summary, a factor value, a judgement's reason) is checked like
  every string a model writes (`agents/shared/model_text.py`) before it fills a template.
- A figure that is missing shows its reason from `calc/`, never a 0.

A sentence that tells the user to press a button names it with the page's label for it, as
`wording.ts` holds it ("Edit", "Show my options"). The terminal app's lines name its keys instead.

## Adding or changing a message

1. The task that needs the message writes its words into the task itself (its spec in
   `ROADMAP.md`), so they are agreed before the code.
2. The words go into `wording.py`, or into `wording.ts` when only the page holds the line. A
   line both the API and the page show stays in `wording.py`; when the page must also hold the
   same words (an API code's message, for a stream that was lost), its constant in `wording.ts`
   says which code it copies.
3. A test covers the logic around the words (which wording applies, what is left out, how a value
   is written), not the words themselves.
