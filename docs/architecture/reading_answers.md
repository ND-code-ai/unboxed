# Reading answers in words

Read this when working on how the brief agent reads answers the user writes in words: the
requirements the request already states, and the reply to the questions. The questions those
answers settle are in `interview.md`; the factors they are mapped onto in `category_brief.md`.

## Stated answers

After the factors are known, from research or from the brief store, one medium-model call with
little reasoning per request (`agents/brief/stated.py`) reads what the request already states.
It is not cached: the brief store holds the category's brief, never a request. The call sees
the request text, the category and every factor numbered, each with its question's choices,
and the factor of kind `usage` with all seven usage frequencies by id. It is told the category
and the budget are already known. Per requirement it returns the factor's number (or "new"),
the number of the choice when one fits, a value when none fits, the frequency id for usage, and
the exact phrase. One phrase may state more than one factor; one that says how often always gives
usage its frequency (task 1.10: "occasional DIY" was read as the tasks question alone). A frequency
is how often the product is used overall: "I also take it camping now and then" gives none (task
3.10: it was read as a few times a year, which set the cost per use of the whole report).

Code then checks each requirement:

- **The phrase must stand in the request**, after the same normalisation the budget phrase and
  the quote check use (`find_phrase` in `agents/shared/phrases.py`). The answer keeps the words
  as the request has them. A phrase not found goes to the trail only (`excluded`).
- **A choice that fits** gives a `stated` answer with that choice's id and its text as the value,
  so a later search query can use the choice.
- **No choice fits:** a `stated` answer with the model's value as free text. The value is checked
  like a choice: no currency marker or generic environmental term, and a number only when it
  stands in the phrase; otherwise the requirement goes to the trail only. The factor gets no
  question either way. A care factor takes only one of its two choices: a value of the model's
  own goes to the trail only, and its question stays.
- **Usage** maps onto any of the seven frequencies, not only the four offered; code copies the
  uses per year from the frequency. With no frequency, or an id that is not one of the seven,
  the usage question is asked.
- **A requirement about no factor** ("new", or a number that was not shown) becomes a factor of
  the user's own: kind `requirement`, a source of kind `user`, an id prefixed `user-`, the phrase
  as its name and the fixed `why` "You asked for this." (`USER_FACTOR_WHY` in `wording.py`). A `stated` answer with
  the phrase as its value settles it, so it gets no question and is not on the check-before-you-buy
  list. At most three are kept (`MAX_USER_FACTORS` in `state.py`), not counted toward the eight
  researched, and the reply shares them ("The reply"); one past them goes to the trail only, and
  so does one whose phrase repeats an earlier one. Code refuses a phrase that is part of the pasted link, that holds a currency
  marker or a generic environmental term (`model_text.py`; a number is allowed, as the words are
  the user's), or that holds the budget's amount, which is how code knows the budget phrase: the
  request keeps the amount, not the phrase (so "a 28 cm pan" with a budget of €28 is refused too,
a rare case that only costs a trail entry). A refused one goes to the trail only (`excluded`) and
  takes no place.
- At most one answer per factor: the first counts.

A stated answer frees its question's place: the brief keeps every phrased question, and the
four asked are the first four whose factor the request does not settle.

When the call fails twice, nothing is stated, every question is asked, and the warning
`stated_answers_unavailable` is raised. A timeout or a service error is tried once more; invalid
output is retried once with its validation error, as every structured call is (`agents.md`,
"Agent contract").

Stated answers are shown above the questions and on the report, one line each (`wording.stated_answer`, `stated_usage` and `stated_own`), such as "From your request: Hob compatibility: Induction ("for induction")"
and, for usage, "From your request: Every day, 365 uses a year ("I cook every day")". A factor
of the user's own shows its phrase alone: "From your request: "with a spare battery"". The
user's own factors stand after the researched ones and before the usage factor.

The brief keeps every question it phrased, asked or not (`phrased_questions` in the state, never
on a report or the API), so an answer to a factor not asked is still read against its question's
choices, by the reply's reader, by the check of the reply's answers and by option research, which
is given every phrased question and the usage question: a `care-avoid` the request states for a
care factor not asked is judged like one picked.

## The reply

The user can answer the questions in their own words in the page's chat thread (task 3.1.2): the
**reply**, sent once beside any choices picked (`GLOSSARY.md`). One round: the questions are asked
once and the reply is read once; a follow-up question belongs to the conversation. The page
writes it from the words under each question's "Something else", each after
`About "{question}": `, and the closing step's (`docs/design/chat_page_brief.md`, "One reply").

The reply is read before the graph resumes, never in a node, by the reply's reader in the agent
bundle (`read_reply` in `agents/brief/reply.py`), reached through `resume_with_reply` in
`graph/sessions.py` (`sessions.md`, "The pause"). That loads the saved factors, the questions
asked, every phrased question, the stated answers and the local category term. A blank reply is
none. A paused session with no questions still has its reply read, for factors of the user's own.
The terminal app sends no reply.

One medium-model call with little reasoning, the same as for the request (`models.md`), sees the
reply, the category and every factor numbered and marked, and code applies what it returns by the
mark:

| Mark | A phrase about the factor gives |
|---|---|
| Asked, with its question and choices | A `stated` answer in its question's place, with the choice when one fits, or "not sure" |
| Not asked, with its question and choices when the brief phrased one | A `stated` answer as from the request, with the choice when one fits |
| Not asked, with no question | A `stated` value of the model's own, checked as from the request |
| Answered by the request | The trail only ("the request already answers it") |
| A recurring cost | The trail only |

A phrase about one of them never becomes a factor of the user's own. Usage takes any of the seven
frequencies, with the usage question's choice when it offers that frequency. Code checks each
phrase as it checks the request's ("Stated answers"), and also:

- **Where it was said.** Each answer has `stated_in: reply` (`request` by default). The trail
  entries name the reply, and a phrase not in the reply goes to the trail with a fixed summary
  that does not repeat it.
- **Not sure.** A question asked can be answered "not sure": a `not_sure` answer that keeps its
  phrase. Uncertainty or indifference is never a value; "not sure" about a factor not asked goes
  to the trail.
- **Care.** A care factor takes only one of its two choices, as for the request.
- **The request does not change.** The reading marks a phrase that asks for another category or
  budget (`changes`); it goes to the trail, and the result says the reply asked to change the
  request (task 2.5.6 shows the line).
- **Factors of the user's own** follow the request's rules: `user-N` continues the request's
  numbering, the three places are shared with the request's own factors, and one past them, or one
  repeating an earlier one, goes to the trail only. Code also refuses one whose phrase holds a
  link (a scheme, `www.` or a host name), is only a number, or holds the category or the local
  category term; the pasted link is refused only when it stands in the reply.
- **People.** A phrase about a person, not the product or its use, is never a requirement (a rule
  of the prompt).

The full reply is not saved; its kept phrases are, on the answers and the trail, as the request's
are.

**Which answer counts**, strongest first: the request's `stated`, a `chosen` choice, the reply's
(`stated` or `not_sure`), a `not_sure` picked, `skipped`. `complete_answers` (`graph/interview.py`)
places them: the request's stated answers, the reply's answers to factors not asked (its own
factors' first), then one per question. A reply's answer that loses to a choice or to the request
goes to the trail. The combined set is checked before the graph resumes, the reply's choices
against every phrased question.

**When it does not go on.** A reading that fails twice raises `ReplyUnreadError`. With no answer
picked (neither a choice nor "not sure") and nothing the reply gave (everything lost to the
request included), the result is a `ReplyUnanswered`. Either way the graph does not resume, the
session stays paused, nothing more is spent, and it can be answered again. When answers were
picked and the reply changed no answer, the run goes on and one trail entry says why: nothing in
it answers a factor, or a choice picked or the request answers all it answers.
