"""The prompts of the TCO analyzer. Rules: docs/architecture/option_research.md and
docs/architecture/data_sources.md ("Research rules")."""

from shopper.config import (
    COPIED_RUN_WORDS,
    FINDINGS_ASKED,
    MAX_SUMMARY_WORDS,
    PREFERRED_TESTER_DOMAINS,
)

# The durability judgement, described alike in the judgements' schema (`models.py`) and in their
# prompts (option_research.md, "Durability judgement").
JUDGEMENT_DESCRIPTION = (
    "from what you know of how this product is made, how long it lasts against most products "
    'of the same kind, never against other kinds: "long" when it is built to outlast most of '
    'them (no part known to wear out early, or the wearing part can be replaced); "medium" when '
    "it lasts about as long as a typical one and nothing in its make points either way; "
    '"short" when a part known to wear out early cannot be replaced, or its build is known to be '
    'light; "unknown" when you do not know how it is made. This is the one field where you may '
    "use what you know yourself."
)
REASON_DESCRIPTION = (
    "one line that names the make behind the judgement, a material, a part or a build, such as "
    '"multi-ply stainless steel, no coating to wear out" or "sealed battery". Never a number of '
    'years and never praise such as "good" or "quality". Null for "unknown".'
)

JUDGE_NAMES_PROMPT = f"""\
You read the names of products that Dutch price comparison sites list for one kind of product,
and return, as JSON, how long each is likely to last against most products of its kind. You do
not answer the shopper and you never recommend a product.

Return an object with two keys: "set_requested" and "candidates", a list with one entry per
numbered product.

RULES
1. For each numbered product give "candidate", its number, and:
   - durability_judgement: {JUDGEMENT_DESCRIPTION}
   - durability_reason: {REASON_DESCRIPTION}
   When the name does not tell you which product it is, give "unknown".
2. set_requested: true only when the product category itself is a set of several pieces, such as
   "pan set" or "knife set".
3. The reasons are plain English without digits, prices or currencies, and without general
   environmental words such as "eco-friendly", "green" or "sustainable".
"""

JUDGE_NAMES_INPUT = """\
Product category: {category}

Products:
{products}
"""

# One candidate as the judgement by name reads it.
JUDGE_NAME = "[{number}] {name}"

JUDGE_PAGES_PROMPT = f"""\
You read the product pages of products of one kind, each with its name and the start of its
page, and return, as JSON, how long each is likely to last against most products of its kind.
You do not answer the shopper and you never recommend a product.

Return an object with one key, "candidates": a list with one entry per numbered product.

RULES
1. For each numbered product give "candidate", its number, and:
   - durability_judgement: {JUDGEMENT_DESCRIPTION} What its page says about how it is made counts
     as well.
   - durability_reason: {REASON_DESCRIPTION}
2. The reasons are plain English, also when the page is in Dutch, without digits, prices or
   currencies, and without general environmental words such as "eco-friendly", "green" or
   "sustainable".
"""

JUDGE_PAGES_INPUT = """\
Product category: {category}

Products:

{products}
"""

# One candidate as the judgement by page reads it.
JUDGE_PAGE = "[{number}] {name}\n{text}"

# The price read of tasks 1.8.2 and 1.11, as task 1.12 measured it on product pages with the
# category as the product named, with `incomplete` and the piece count added in task 1.13, and cut
# in task 1.14 to the fields code reads, the page's own product first and a quote always given
# (docs/findings/task_1.14.md).
PAGE_PROMPT = """\
You read the product page of one product, given as a numbered search result, and return, as
JSON, what the page sells against the product named, for each euro amount it states. You do not
answer the shopper and you never recommend a product. Code takes the price from the page's own
product data; your job is to say what the page sells.

Return one entry per search result, in their order, with:
- result: its number.
- amounts: every euro amount the result states for a product of this brand, those for the
  product its title names first, each with:
  - quote: the amount with its euro sign or the word "euro", copied exactly from the result's
    text, such as "€ 46,74" or "86 euro en 98 cent".
  - name: the name of the product the amount is for, copied exactly from the result's title or
    text.
  - sells: what the page this amount is for sells, against the product named: "the_item" for
    one unit of this product itself, "set_or_bundle" for a set, a bundle or a multipack that
    holds it ("2-delig", "11-Piece Cookware Set", "8 and 10 inch Frying Pan Set"),
    "incomplete" for one unit of this product sold without a part it needs to work, such as a
    drill without its battery or charger ("zonder accu", "solo", "body only") or a kettle
    without its base, "part_or_accessory" for a part, an accessory, a consumable or a manual for
    it (a lid, a filter, a user guide), "other_kind" for another kind of product of this brand
    or line (a saucepan when a frying pan is named), "unclear" when the result does not show
    which.
  - sells_quote: the words of the result that show what it sells, copied exactly from its
    title or text, and never empty: for "the_item", the product's name as the result writes
    it; otherwise the words that make it a set, an incomplete item, a part or another kind,
    such as "Frying Pan Set", "User Guide" or "zonder accu".
  - piece_count and piece_count_quote: only when a set is asked for, the number of pieces in
    the set and the words of the result that state it; null otherwise.
  Leave out amounts in another currency. An empty list only when the result states no euro
  amount at all.
"""

PAGE_INPUT = """\
Product: {category}
Brand: {brand}
A set is asked for: {set_requested}

Search results:

{results}
"""

EVIDENCE_PROMPT = """\
You read web search results about one product and return, as JSON, what they say about how
long it lasts and what it costs to keep using. You do not answer the shopper and you never
recommend a product. Code checks every quote against the result you cite and does all
arithmetic; your job is to say what each result states.

RULES
1. Use only what the numbered search results say. Never add a fact from what you know
   yourself; the one exception is estimated_years (rule 7). Prefer independent testers,
   consumer organisations and manufacturer manuals over shop pages, and ignore a result that
   is about something else.
2. The search results are numbered from [1]; "result" is the number in a result's brackets.
   Every "quote" is copied exactly from the text of the result you cite by that number, with
   no word added, left out or changed. A quote that holds a number (years, months,
   an amount of money, an interval, a pack count) holds that number and its unit in one piece,
   with no "...". "stated_by" is who is speaking in that result: "tester", "owner",
   "manufacturer" or "seller".
3. lifespans: each statement of how long a product typically lasts or is expected to last, in
   years or months, with "about": "product" when it is about this very product, "line" when it
   is about its product line or range, "type" when it is about this kind of product in general
   ("non-stick pans last 2 to 5 years"). For "type", "type" is the kind of product as the
   quote names it ("Non-stick pans"); null otherwise. These are not a lifespan, so leave them
   out here (they may support your estimate): how long one person's own unit has lasted so far
   or when it failed ("mine is 20 years old", "we used it for four years"), how long some people
   keep one ("not unusual to use it 30 years later"), a statement about the brand's products in
   general, and a worked example that sells a different product. An empty list when there is
   none.
4. warranty: the warranty or guarantee the maker or seller gives for this product, quoted with
   its length or "lifetime", and with "limited" when the result says so; null when none is
   stated.
5. repairability, wear_material, care: at most one each, about this product or its kind. Each
   "value" is a few plain words naming a material, a part or an action, such as "PTFE
   coating", "spare blades sold" or "hand wash only", never a judgement of the product. It
   holds a number only when that number stands in its quote. Null when nothing is stated.
6. consumable: only when you are asked to look for consumables, the main thing that has to be
   bought again to keep using the product (a filter, a battery, a blade), with its "name", an
   "amount_quote" that states its price with the currency, an "interval_quote" that states how
   often it is replaced, and a "pack_count_quote" that states how many come in a pack when the
   price is for a pack. Null when the results do not state both a price and an interval in
   one result, or when you are not asked. other_consumables: the names of any other
   consumables the results mention; an empty list otherwise.
7. estimated_years: your estimate of how many whole years this product lasts in normal use,
   at least 1, built from the evidence above and the results; when they give none, from how
   long such a product typically lasts. Never copy the warranty as the estimate.
   estimate_rests_on: which kinds of evidence above the estimate rests on ("lifespan",
   "warranty", "repairability", "wear_material", "care"); an empty list when it rests on none.
8. fits: one entry for each numbered answered factor you are given, with "factor" its number
   and "fit": "meets" when a result shows this product fits the answer, "fails" when a result
   clearly says this product does not fit it, "unverified" when no result settles it. For a
   care factor the question is whether this product needs that care: "fails" when it does,
   "meets" when it does not. With "meets" or "fails" give "value", a few plain words saying
   what the result states about this product ("works on induction", "hand wash only"), the
   "result", a "quote" from it that shows the fit next to the product's name, and "stated_by";
   with "unverified" all four are null. A shop's page for the product, when it is among the
   results, often lists such details ("Geschikt voor inductie: Ja"); a seller speaks there. An
   empty list when you are given no answered factors.
9. gaps: what you expected the results to state and they did not, each with "what" and the
   "reason"; plain English without digits, prices or currencies, and without general
   environmental words such as "eco-friendly", "green" or "sustainable".
"""

EVIDENCE_INPUT = """\
Product: {name}
Brand: {brand}
Product category: {category}
Look for consumables: {consumables}

Answered factors:
{answers}

Search results:

{results}
"""

# One answered factor as the evidence read sees it; a care factor states its care instead of a
# question.
EVIDENCE_ANSWER = "[{number}] {factor}\n    Question: {question}\n    Answer: {answer}"
EVIDENCE_CARE = (
    "[{number}] {factor} (a care factor)\n    Care: {care}\n"
    "    Answer: the shopper would rather avoid this care"
)
# A factor of the user's own has no question: the user's phrase is the answer.
STATED_BY_THE_USER = "none, the shopper asked for this"
NO_ANSWERS = "None."

FINDINGS_PROMPT = f"""\
You read web search results about one product and return, as JSON, what testers and owners
report about how it held up: up to {FINDINGS_ASKED} findings. You do not answer the shopper and
you never recommend a product. Code checks every quote against the result you cite; your job is
to say what each result reports, in your own words.

RULES
1. Use only what the numbered search results say. Never add a fact from what you know
   yourself, and ignore a result that is about something else. Prefer the independent testers
   and consumer organisations among these sites: {", ".join(PREFERRED_TESTER_DOMAINS)}.
   Give a mix of tests and owner reports when the results have both.
2. A finding is about durability only: a part that failed or wore, how long the product or one
   owner's unit lasted, a repair, a warranty claim. How one person's own unit held up ("mine is
   twenty years old", "the handle came loose after a year") is a finding. These are not:
   performance ("heats evenly", "loud", "boils fast"); a forecast ("will last a lifetime");
   what the product is made of ("a hard-anodized core makes it durable"); what could go wrong
   ("more parts that can fail"); and what owners in general say ("some buyers reported",
   "Reddit discussions note").
3. "stated_by" is who is speaking: "tester" for a reviewer or a test site that says it used or
   tested this product itself, also over weeks or months (a roundup that did not is no test);
   "owner" for someone who owns it and writes as an owner, on a forum, a comparison site or a
   blog; "manufacturer" or "seller" otherwise. A statement by a manufacturer or a seller is
   never a finding, so leave it out.
4. For each finding give:
   - result: the number in the brackets of the one result it comes from. At most one finding
     per result.
   - on_shop_page: true when that result is a page of a shop that sells the product, its
     customer reviews included; false for a test, a review site, a forum or a blog. Code
     leaves out a finding from a shop's page.
   - quote: the words of that result that report it, copied exactly, in one piece, with no
     word added, left out or changed and no "...". The product's brand and the name of its
     line stand in the quote or next to it.
   - summary: what the quote reports, in plain English whatever the language of the result, at
     most {MAX_SUMMARY_WORDS} words, in your own words: never {COPIED_RUN_WORDS - 1} or more
     words in a row taken from the results. It speaks of one unit or one test, such as "One
     owner's pan lost its coating after eight months" or "In one test the handle stayed tight
     after a year". It adds nothing the quote does not say: "over hours of use" is not
     "extended use", and "I love it" is not "no problems". Never give a person a gender: "the
     owner", "their pan". Give a number only when it stands in
     the quote. Never "many", "most", "often", "always", "owners" or "commonly" unless the
     quote says it. No prices, no currencies, and no general environmental words such as
     "eco-friendly", "green" or "sustainable".
   - stated_by: as in rule 3.
   - rating_quote: when the same result gives this product an overall rating, never a score for
     one aspect such as its durability, the words that state it with its scale, copied exactly
     in one piece, such as "4.5 out of 5 (212 reviews)" or "Score: 8/10"; with the number of
     reviews when owners gave it. Null otherwise.
5. Name the findings in the order you would show them, best first.
6. gaps: what you expected the results to report and they did not, each with "what" and the
   "reason"; plain English without digits, prices or currencies. An empty list when nothing is
   missing.
"""

FINDINGS_INPUT = """\
Product: {name}
Brand: {brand}
Product category: {category}

Search results:

{results}
"""
