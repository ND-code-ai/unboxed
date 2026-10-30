# The interview

Read this when working on the questions shown to the user, the usage question, how answers shape
the results, or the "check before you buy" list. Where the decision factors come from is in
`category_brief.md`; how the request and the reply are read for answers is in
`reading_answers.md`.

## Purpose

Shoppers often discover late what they should have checked first: the pan does not work on
induction, the vacuum needs filters every year. The app surfaces those factors before any search,
asks the few questions that matter, and uses the answers. Buying the right thing once is the most
effective way to avoid an early replacement.

## Flow

Questions come first. Results are produced only after the user answers or skips.

1. **Brief.** For the product category, the brief agent researches the decision factors: what
   matters when choosing, and what buyers typically find out too late.
2. **Interview.** The app asks up to four questions drawn from those factors (two for a pasted
   link), and how often the product will be used.
3. **Pause.** The graph stops and waits for the answers.
4. **Analysis.** The other agents run with the answers as requirements.

## Questions

- **At most five questions:** at most four about researched factors, one per factor in research
  order, and the usage question last. Only factors of kind `compatibility`, `requirement` and
  `care` are asked about; a factor that could not be phrased is skipped and stays on the
  check-before-you-buy list. A recurring-cost factor is never asked about and takes no place
  (`category_brief.md`, "Recurring costs are factors"). With a pasted link that was read, fewer are asked (see
  "Pasted product link").
- **One question is always usage frequency** ("How often will you use it?"), asked last, with
  choices that map to uses per year. It feeds cost per use. Its choices are four of the seven
  usage frequencies (below).
- Each question has: the question, the one-line reason and two to four answer choices. "Not
  sure" is always offered beside them; it is an answer status, not one of the stored choices.
- **A compatibility or requirement question** is written by the model: the question, its reason
  and two to four choices. Every number in a choice must stand in the search result the factor
  cites, and a choice is at most `MAX_CHOICE_CHARACTERS` long (`config.py`). The limit was set so
  a choice could fill search queries; the experiment of task 1.8 found that a choice's text does
  not work as a search term, so option research does not search with it (`docs/findings/task_1.8.md`).
- **A care question** is one statement the model writes, which opens "Some {category}s ...";
  code adds the closing question "Is that fine with you?" and the choices "That's fine" and
  "I'd rather avoid it" (`CARE_FINE` and `CARE_AVOID` in `wording.py`), whose ids are always `care-fine` and `care-avoid`. Its
  reason is the factor's `why`.
- **The typical yearly cost line** is written by code alone from fixed words (`wording.typical_cost`): the factor's name, the typical yearly cost, the site it was quoted from and,
  when it was converted, "converted from {currency} at a fixed rate". The phrasing call never
  sees a recurring-cost factor. The line is shown with a pasted link too, and when the phrasing
  call failed, since it asks nothing.
- **Not phrased.** A question counts as not phrased when the model wrote none for the factor,
  when its question, reason or statement holds what a model may not write, when a care
  statement does not open with "Some" and the category in the plural, when it has fewer than two
  or more than four different choices, or when a choice is empty, too long, or holds a number, in
  digits or in words, that its source does not. The trail records which.
- **Always skippable.** Every question can be skipped: "Not sure", or in the page's thread
  "skip the rest" for all that are left. Skipping never blocks results.
- **No questions.** A session can pause with nothing to ask, when the request already answers
  every question it would get, the usage question included. The pause is still shown: the
  "Looking for" line, the warnings, the "From your request" lines and the typical yearly costs.
  In the page's thread only the closing step is asked ("Anything else we should know?"): "Show
  my options" with nothing written resumes the session with nothing added, and words written
  there are the reply, read for factors of the user's own (`reading_answers.md`, "The reply"); a reply that adds none
  is `reply_unanswered`, in its wording for a session with no questions (`wording.reply_unanswered`).
- **Never ask what the user already said.** If the request states the budget or a requirement,
  do not ask again. A requirement stated in the request ("for induction", "I cook every day") is
  recorded by the brief agent as an answer with the status `stated`, holding the value and the
  exact phrase it was taken from. No question is created for that factor. How it is read is in
  `reading_answers.md`.
- **No personal data.** Questions are about the product and its use, never about the person.
- Tone follows `docs/product.md`: plain, no judgement of any answer.

## The usage question

The seven usage frequencies (`GLOSSARY.md`) are a code constant; the model never writes uses
per year.

| Frequency | Uses per year |
|---|---|
| Several times a day | 1,000 |
| Every day | 365 |
| A few times a week | 150 |
| About once a week | 50 |
| About once a month | 12 |
| A few times a year | 4 |
| About once a year | 1 |

In the phrasing call the model picks four frequencies by id for the category. A valid pick is
four different known ids, which may skip frequencies, and is shown most often first. Otherwise, and when
there are no researched factors, code offers every day, a few times a week, about once a week
and about once a month (365, 150, 50 and 12). The words of each frequency are `USAGE_FREQUENCIES` in `wording.py`.

## How answers are used

There is at most one answer per decision factor, with a status: `chosen` (picked from a
question's choices), `stated` (said in the request or the reply), `not_sure` (picked, or said in
the reply) or `skipped`; which counts when more than one says something is in `reading_answers.md` ("Which answer counts"). The
other agents treat `stated` exactly like `chosen`, wherever it was said. A factor that got no question and was not stated in the
request has no answer; `skipped` is only for a question the user was shown.

| Answer | Effect |
|---|---|
| A requirement or compatibility answer, or a factor of the user's own | Options that a quoted source shows do not meet it are excluded (a listing is a used copy of an option, so it is not judged again), with the reason kept in the evidence trail; the linked product is kept with a mismatch line. An option no source settles is `unverified` and goes on the "check before you buy" list |
| Usage frequency | Sets uses per year for cost per use. Unanswered, cost per use is missing with its reason; it is not put on the "check before you buy" list |
| "Not sure", skipped, or no answer | The factor goes on the "check before you buy" list, and no option is excluded on it |
| Care requirement declined (`care-avoid`) | Options a quoted source shows need that care are kept but marked, since the lifespan shown assumes the care is done; an option no source settles goes on the "check before you buy" list |
| Care accepted (`care-fine`) | Nothing: no factor value, and not on the list |

Who judges the fit, and the quote check that makes it stand, are in `option_evidence.md`
("Evidence", "Answers"). Each option shows its value for the factors the user answered, so the
report reflects what this user said they care about.

## Check before you buy

A short list on the report: the factors that were unanswered or could not be verified for an
option, each with its one-line reason, and one "Confirm the current price" line for every option
with a price, since prices change after the day they were seen (task 1.15; `option_research.md`,
"Warnings"). It is the answer to "what will I wish I had known?".

## Pasted product link

The product is already chosen, so the interview is shorter. The brief agent is given the linked
product (`agents/bundle.py`, `BriefAgent`) and the brief is researched and cached as for any
request of the category; only which questions are asked changes.

- **At most three questions:** at most two researched questions and the usage question last.
  The two are the first two not settled by the request whose factor is of kind `compatibility`
  or `requirement`, in research order. Care questions are not asked; their factors are on the
  check-before-you-buy list like any unasked factor. A stated answer frees its place for the next
  one that fits, as above. The phrased questions left unasked get one `decided` trail entry.
- **About the user's situation, never a claim about the product.** The questions are the
  category's phrased questions ("Which hob do you cook on?"); the phrasing call never sees the
  linked product, so no question says what the product is or does.
- **A link that could not be read** gives no linked product, so it gets the full interview of
  its category (`data_sources.md`, "An unreadable link").

Comparing the linked product with an answer is not part of the interview: the evidence read
finds the mismatch in task 1.8.6 (`option_evidence.md`, "Evidence", "Answers") and the report
shows it beside the product, with its source; the product is never excluded.

## Open questions

- **"It doesn't matter to me" is not an answer.** A user who does not care about a factor can
  say "not sure" or skip, and either puts the factor on the check-before-you-buy list. Whether a
  third status is worth adding, one that excludes no option and keeps the factor off the list,
  is open.
- **Rent or borrow** is not built: the app shows cost per use and leaves the conclusion to the
  user. The optional task in `docs/ROADMAP_OPTIONAL.md` holds the intent.
