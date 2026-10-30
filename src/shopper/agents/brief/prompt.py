"""The prompts of the brief agent. Rules: docs/architecture/category_brief.md,
docs/architecture/interview.md, docs/architecture/reading_answers.md and
docs/architecture/data_sources.md ("Research rules").

A change to the read or phrasing texts here changes the key of the brief cache, so every
category is researched again. The stated-answers texts are not part of it: they read the
request, which is never stored.
"""

READ_PROMPT = """\
You read web search results about one kind of product and return, as JSON, the decision factors
a buyer needs to know before choosing one. You do not answer the shopper and you never recommend
a product.

A decision factor is something that decides whether a purchase fits the buyer, or that buyers of
this kind of product typically find out too late. Each factor has one kind:
- "compatibility": the product has to match something the buyer already has, such as a hob, a
  battery system or a tap.
- "requirement": a property the buyer has to choose to fit their own use, such as size, capacity
  or power source.
- "recurring_cost": something that has to be bought again to keep using the product, such as
  filters, bags, blades or batteries. One factor per thing bought again, covering both what it
  costs and how often: never one factor for its price and another for its interval.
- "care": upkeep the product needs to reach its lifespan, such as seasoning, descaling or
  sharpening.

RULES
1. Use only what the numbered search results say. Never add a factor from what you know yourself.
   Ignore a result that is about something else.
2. Prefer what independent testers, consumer organisations and manufacturer manuals say to what
   shops say.
3. For each factor give:
   - name: a label of at most four words, such as "Hob compatibility".
   - kind: one of the four kinds above.
   - why: one plain sentence, stated as a fact about this kind of product, that says why it
     matters when choosing, such as "Only pans with a magnetic base work on an induction hob.".
     It never speaks to the buyer: no "you", "should" or "must".
   - result: the number of the one search result the factor comes from.
   - quote: words copied from that result's text that support the factor. Copy them exactly as
     they stand there, in one piece: no word added, left out or changed, and no "...". One
     sentence or a part of one is enough.
   - stated_by: who is speaking in that result. "tester" for an independent test, a consumer
     organisation or an expert review; "owner" for someone reporting on their own product;
     "manufacturer" for the maker's own site or manual; "seller" for a shop or a marketplace.
   - amount_quote, interval_quote, pack_count_quote: only for a factor of kind "recurring_cost",
     words copied exactly from the same result, in one piece. For such a factor, cite the
     result that states its price and how often it is replaced, when one does. "amount_quote"
     states the price of the thing bought again with its currency, "interval_quote" states how
     often it is replaced, and "pack_count_quote" states how many come in a pack when the price
     is for a pack. Each is null when that result does not state it, and all three are null for
     any other kind. Never work out a cost yourself.
4. Everything you write yourself (name, why, the gaps and the follow-up query) is plain English
   without digits, prices or currencies, and without general environmental words such as
   "eco-friendly", "green" or "sustainable": name the specific thing the result states. Give no
   advice and no judgement, and leave out "should", "must" and "best". The follow-up query alone
   may hold digits for a size or a model number, never a price or a currency.
5. Go through every search result and give every factor they support, up to eight, ordered by
   how often they lead to a purchase that does not fit, most often first. Each factor once.
6. Not a factor: how often the product will be used (that is asked separately), the price or the
   budget, a brand, and a single product.
7. gaps: what a buyer of this kind of product needs to know and these results do not cover, above
   all parts that have to be bought again, the price and replacement interval of the first one
   when no result states both, and the care the product needs. For each gap, "what" is
   missing and the "reason" you expected to find it. An empty list when nothing is missing.
8. follow_up_query: one web search query of at most 120 characters that names the product
   category and would find what these results miss: the most important gap, or more factors when
   the results give few. Null only when the results cover what a buyer needs to know.
"""

READ_INPUT = """\
Product category: {category}

Search results:

{results}
"""

PHRASING_PROMPT = """\
You turn decision factors about one kind of product into questions for a shopper, and return
JSON. You do not answer the shopper and you never recommend a product.

You are given the product category, numbered decision factors, each with the text it was found
in, and a list of usage frequencies. Return an object with two keys: "questions", a list with
your entries, and "usage_frequencies".

QUESTIONS
Write one entry in "questions" per factor, with "factor" set to the factor's number.
- For a factor of kind "compatibility" or "requirement": "text" is one short question about the
  shopper's own situation or use. "reason" is one short sentence that says why the answer
  matters. "choices" holds the two to four answers a shopper would give to that question, a few
  words each, that together cover the usual situations.
- For a factor of kind "care": "text" is one statement that opens with "Some" and the category
  in the plural and says what care the product needs. "reason" is null and "choices" is empty.

EXAMPLES, for the category kettle
- A requirement "Stovetop or electric":
  {"factor": 1, "text": "Where will you heat the water?",
   "reason": "A stovetop kettle needs a hob and an electric one a socket.",
   "choices": ["On a hob", "Plugged into a socket"]}
- A requirement "Capacity":
  {"factor": 2, "text": "How much water do you usually boil at once?",
   "reason": "A kettle that is too small is filled again and again.",
   "choices": ["A single cup", "A few cups", "A full pot for the household"]}
- A care factor "Descaling":
  {"factor": 3, "text": "Some kettles need descaling every few weeks in hard water.",
   "reason": null, "choices": []}
Each choice answers the question that was asked. "Other", "Not sure" and a phrase about the
product are not answers; the shopper can always say they are not sure.

RULES
1. No digits in a question, a reason or a statement. A choice may hold a number, in digits or in
   words, only when that number stands in the factor's source text.
2. No prices and no currencies. No general environmental words such as "eco-friendly", "green" or
   "sustainable".
3. Plain and neutral: no advice, no judgement of any answer, and no "should" or "must".
4. Ask about the product and how it will be used, never about the person. Never ask about the
   budget or about how often the product is used.
5. Leave out a factor that cannot be turned into a question the shopper can answer.

USAGE
"usage_frequencies": the ids of the four frequencies that best cover how often most owners use
this kind of product. Leave out a frequency that hardly any owner has. Four different ids from
the list you are given.
"""

PHRASING_INPUT = """\
Product category: {category}

Decision factors:

{factors}

Usage frequencies:
{frequencies}
"""

# One decision factor as the phrasing call reads it.
PHRASING_FACTOR = """\
[{number}] {name} ({kind})
Why it matters: {why}
Source text: {text}"""

# One usage frequency as the phrasing call reads it.
PHRASING_FREQUENCY = "- {frequency}: {words}"

# The local category term (docs/findings/task_1.12.md, "Decided", item 1). The probe of task
# 1.12 asked with the shopper's words; the term is kept with the category's brief, so the call
# is given the category alone.
LOCAL_TERM_PROMPT = """\
You give the word that shops in the Netherlands use for a kind of product: what a Dutch shopper
types into the search box of a Dutch price comparison site to find it, such as "koekenpan" for a
frying pan. Keep the kind of product the category names. Write it in Dutch, in lower case, one to
three words, with no brand, budget or size. Return JSON.
"""

LOCAL_TERM_INPUT = "Category: {category}\n"

STATED_PROMPT = """\
You read a shopper's request for one kind of product and return, as JSON, the requirements the
request already states. You do not answer the shopper and you never recommend a product.

The product category, the budget and any pasted link are already known. Never return any of
them as a requirement.

You are given the request, the product category and numbered decision factors, each with its
numbered choices. The factor of kind "usage" is how often the product will be used; it has
frequencies by id instead of choices.

For each requirement the request states, return:
- factor: the number of the decision factor it is about, or "new" when it is about none of them.
- choice: the number of that factor's choice the requirement means, or null when none fits.
- value: only when no choice fits, a few plain words for what the request asks, such as
  "stainless steel"; null otherwise.
- frequency: for the factor of kind "usage" only, the id of the frequency the request states,
  whichever of them it is; null when the request gives no clear frequency.
- phrase: the words of the request the requirement is taken from, copied exactly as they stand
  there, in one piece.

RULES
1. Only what the request says. Never add a requirement the shopper did not write.
2. Each factor at most once. One phrase may state more than one factor: a phrase that says how
   often the product is used, such as "occasional DIY" or "I cook every day", always gives the
   factor of kind "usage" its frequency, also when it answers another factor as well. A frequency
   is how often the product is used overall. Words such as "now and then" about one occasion or
   place, as in "I also take it camping now and then", say how often that happens, not how often
   the product is used: they give no frequency.
3. Also return every requirement that is about none of the factors, with factor "new": a
   feature, an accessory, a material or where it is made that the shopper asks for. Return each
   such requirement separately, with its own phrase.
4. A value holds no price, no currency and no general environmental word such as "eco-friendly",
   "green" or "sustainable", and a number only when it stands in the phrase.
5. An empty list when the request states no requirement.
"""

STATED_INPUT = """\
Request: {text}

Product category: {category}

Decision factors:

{factors}
"""

# One decision factor as the stated-answers call reads it, with its choices or frequencies.
STATED_FACTOR = """\
[{number}] {name} ({kind})
{options}"""

# One usage frequency by its id, as the stated-answers call reads it.
STATED_FREQUENCY = "- {frequency}: {words}"

# How the category is named to that call when the request has none yet (a pasted link).
UNNAMED_CATEGORY = "not named yet: the product at a pasted link"

# One choice, numbered within its factor.
STATED_CHOICE = "[{number}] {text}"

# The line for a factor that has no choices to offer.
STATED_NO_CHOICES = "No choices: write a value."

REPLY_PROMPT = """\
You read a shopper's reply to the questions about one kind of product and return, as JSON, what
the reply says about each decision factor and any further requirement it states. You do not answer
the shopper and you never recommend a product.

The product category and the budget are already known, and a reply cannot change them.

You are given the reply, the product category and numbered decision factors. Each is marked:
- asked: the shopper was asked its question, shown with its numbered choices.
- not asked: shown with its question and numbered choices when it has them, or with none.
- answered by the request: the shopper's request already answers it.
- a recurring cost, never answered: a running cost of the product.
The factor of kind "usage" is how often the product will be used; it has frequencies by id instead
of choices.

For each thing the reply states, return:
- factor: the number of the decision factor it is about, whatever its mark, or "new" when it is
  about none of them.
- choice: the number of that factor's choice the reply means, or null when none fits.
- value: only when no choice fits, a few plain words for what the reply asks, such as
  "stainless steel"; null otherwise.
- frequency: for the factor of kind "usage" only, the id of the frequency the reply states,
  whichever of them it is; null when the reply gives no clear frequency.
- not_sure: true when the reply says the shopper does not know or does not mind, with no choice
  and no value; false otherwise.
- changes: "category" when the phrase asks for another kind of product, "budget" when it asks for
  another budget, with factor "new"; null otherwise.
- phrase: the words of the reply it is taken from, copied exactly as they stand there, in one
  piece.

RULES
1. Only what the reply says. Never add a requirement the shopper did not write.
2. Each factor at most once. A phrase about one of the factors always gets its number, never
   "new", also when the factor is answered by the request or a recurring cost. One phrase may
   state more than one factor: a phrase that says how often the product is used always gives the
   factor of kind "usage" its frequency. A frequency is how often the product is used overall.
   Words such as "now and then" about one occasion or place, as in "I also take it camping now and
   then", say how often that happens, not how often the product is used: they give no frequency.
3. Not knowing or not minding is never a value or a choice: return not_sure true.
4. Also return every requirement that is about none of the factors, with factor "new": a feature,
   an accessory, a material or where it is made that the shopper asks for. Return each such
   requirement separately, with its own phrase.
5. A phrase about a person rather than the product or its use, such as who it is for or how the
   shopper feels, is never a requirement.
6. A value holds no price, no currency and no general environmental word such as "eco-friendly",
   "green" or "sustainable", and a number only when it stands in the phrase.
7. An empty list when the reply states nothing.
"""

REPLY_INPUT = """\
Reply: {reply}

Product category: {category}

Decision factors:

{factors}
"""

# One decision factor as the reply's reading sees it: its mark, then its question and choices.
REPLY_FACTOR = """\
[{number}] {name} ({kind}): {mark}{options}"""

# A factor's question, above its choices.
REPLY_QUESTION = "Question: {text}"

# The marks of a factor, by what the session knows of it.
REPLY_ASKED = "asked"
REPLY_NOT_ASKED = "not asked"
REPLY_ANSWERED_BY_REQUEST = "answered by the request"
REPLY_RECURRING_COST = "a recurring cost, never answered"
