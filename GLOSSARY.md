# True Cost Copilot

The language of a shopping assistant that shows what a durable product really costs over time, in
money and in CO2e, and what a better-value choice within budget would be.

## Language

### The request

**Input**:
The text the user typed or pasted, before the app has understood it.
_Avoid_: Query, prompt, raw text

**Session**:
One request followed from its questions through its report versions and conversation; a correction
to the request starts a new one.
_Avoid_: Run, thread (that is what the page shows of one), chat

**Thread**:
What the page shows of one session, as turns in order: the user's (the input, the reply, later the
messages about the report) and the app's (what it understood, progress, the questions with the
choices picked, a decline or rephrase message, the report). The page groups it into rounds, "Your
request" and "Your answers", the user's words first in each, and shows progress as one status line
under them. A correction to the request starts a new session, and with it an empty thread.
_Avoid_: Chat (that is the conversation about the report), session (a thread shows one),
conversation

**Box**:
The drawing of a plain product box the chat page is built around: its front face is the composer
before the first send, then keeps the request, faded (at its top once the questions are asked),
and is labelled while the questions are answered, sealed while the agents run, opened at the report. A drawing; everything shown on it is also in the thread.
_Avoid_: Package, parcel, order (the app sells nothing)

**Label**:
An answered question as the page shows it, on the box and above the open question: the name of
the factor it is drawn from over the answer (on the box the answer alone, or the factor's name
and "?" for "not sure"), dashed when the answer is "not sure" or when the answers were sent
without one. Once the reply is read, each factor of the user's own the reader kept is a label
too, its phrase alone; what the user wrote is never a label itself. The first label on the box carries the words of the "Looking for"
line. The example requests beside the box at the opening are labels too (starters): taking one
writes its words into the composer. Not the caption of a control (the composer's label), and not a
confidence label.
_Avoid_: Tag, sticker, chip (a chip is what is tapped to answer), badge

**Results page**:
The view a finished report opens into: the product options set against each other with every
figure, the report-wide lines above and below them, and the thread beside them.
_Avoid_: Dashboard, results screen, report page

**Option card**:
One product option's lines as a card in the results page's deck, which shows one card at a time.
_Avoid_: Product card, tile, spec card

**Option sheet**:
One product option's lines as a sheet in the results page's rows view, side by side with the
others, each figure level across them; the deck's option card is the same sheet, one at a time.
_Avoid_: Column, panel, label (a label is an answer stuck on the box)

**Request**:
What the user asked for: a need in their own words, optionally a link to one specific product, and
optionally a budget.
_Avoid_: Query, search, prompt

**Category**:
The kind of product a request is about, as the app understood it, such as "frying pan".
_Avoid_: Product, product type, product name

**Scope**:
The classification of a request, which decides only which caveats the report carries, that the
request is declined, that it names more than one product, or that it could not be understood.
_Avoid_: Category type, coverage (and never for what a CO2e figure covers; that is the boundary)

### The interview

**Decision factor**:
Something that matters when choosing a product in a category, such as hob compatibility for a
pan or filter cost for a vacuum cleaner. It is found in a web source or stated by the user in the
request; how often the product is used is the one the app always asks about, and has no source.
_Avoid_: Criterion, feature, spec, attribute

**Question**:
One thing the user is asked before any results are produced, drawn from a decision factor and
offered with a few choices.
_Avoid_: Prompt, field

**Answer**:
What is known about the user's position on one decision factor: chosen from a question's choices,
stated in the request itself or in the reply, not sure, or skipped. A decision factor has at most
one answer; one the user was never asked about and did not state has none. When more than one
says something about a factor, the request counts over a choice picked, a choice over the reply,
and the reply over a "not sure" picked.
_Avoid_: Response, preference, requirement

**Reply**:
What the user typed, in their own words, in answer to the questions, sent once beside any choices
they picked. On the page it is joined from the words under each question's "Something else",
each after the question it answers, and the closing step's. It can answer the questions and add
requirements of the user's own, but never changes the request; a correction starts a new
session.
_Avoid_: Response, free text, message (a message is the chat about the report)

**Usage frequency**:
One of the seven fixed how-often choices, each with its uses per year; four of them are offered
for a category.
_Avoid_: Rung, usage ladder, frequency scale, usage options

**Brief**:
What category research produced for one category: its researched decision factors, a question
drawn from each one that could be phrased, and the usage frequencies offered. It is kept,
so a category is researched once.
_Avoid_: Profile, research result

**Check-before-you-buy list**:
The decision factors about the product that have no chosen or stated answer, or that could not
be verified for a product option, each with its reason, and one reminder to confirm the current
price of every product option that has one, since prices change. How often the product is used
is never on it.
_Avoid_: Checklist, to-do list, open points

### Options and listings

**Candidate**:
A new product named on a comparison site's listing page. It becomes a product option only once
its own product page gives an accepted euro price and it is selected.
_Avoid_: Shortlisted product, possible option

**Buyable candidate**:
A candidate whose own product page offers it new, in euro and in stock, at a price for that item
or variant, and sells the item of the category itself, not a set, a part or another kind of
product, unless a set is asked for. An item out of stock, or sold without a part it needs to work,
is a candidate but not buyable: it is marked, and fills a slot only when no buyable candidate is
left.
_Avoid_: Usable priced product, valid product, in-stock option

**Offer price**:
The price of a candidate as an offer on its own product page gives it, for the item alone,
without shipping; the shipping the offer states is shown beside it. Every price on a report is an
offer price, or the linked product's page price.
_Avoid_: Confirmed price, verified price (verified belongs to factor values), search price

**Durable pick**:
The selected candidate the durability judgement ranks highest; it may cost more than the budget.
A name for the trail only, never a label on the report.
_Avoid_: Premium option, best option, recommended option, durable option

**Durable pick within budget**:
The selected candidate within the budget that the durability judgement ranks highest, other than
the durable pick. A name for the trail only, never a label on the report.
_Avoid_: Best-evidenced pick, best option, top pick, value pick

**Product option**:
A new product the report proposes for the request: a selected candidate, or the linked product.
_Avoid_: Product, item, alternative

**Linked product**:
The product option made from the page at the link the user pasted. It is the first of the at
most three product options on the report, so at most two selected candidates stand beside it.
_Avoid_: Pasted product, link product, the user's product

**Factor value**:
What a product option offers for one answered decision factor, with its fit: it meets the answer
or fails it, each shown by a quote from a page that names the product, or it is unverified.
_Avoid_: Spec, attribute, match

**Listing**:
A used or refurbished item offered for sale on a marketplace. It may be a used copy of a product
option.
_Avoid_: Offer, used option, second-hand option

**Listing page**:
A comparison site's or shop's page that lists several new products, each linked to its own
product page. It names products; it is no product's page, and its lowest price is no offer.
_Avoid_: Category page, search page, listing (that is a used item)

### The numbers

**Assumptions**:
The values the user may change after seeing a report: the horizon, the uses per year, and the
lifespan of any product option.
_Avoid_: Settings, parameters (and never for what a CO2e estimate was built from; those are inputs)

**Recalculation**:
A report's comparison and evidence summary computed again with other assumptions, with no agent
run and nothing saved; the report keeps its own assumptions.
_Avoid_: What-if report, new version (a version comes only from a rerun)

**Comparison**:
The computed figures for each product option over the horizon, set against a baseline option.
_Avoid_: Results, table, analysis

**Baseline**:
The product option the others are compared against; the cheapest by offer price unless another
is named. An option marked out of stock, or sold without a part it needs to work, is never the
baseline.
_Avoid_: Reference option, default

### Evidence

**Durability evidence**:
What supports a product option's lifespan: warranty, repairability, the material that wears, the
care it needs, the lifespan typical for its type (shown as typical for the kind of product its
quote names, never as its own lifespan), and findings.
_Avoid_: Quality data, reviews

**Sourced lifespan**:
A product option's lifespan taken from a quoted statement of how many years the product, or its
product line, typically lasts.
_Avoid_: Real lifespan, verified lifespan

**Estimated lifespan**:
A product option's lifespan given by a model from the durability evidence or, when none was
found, from what it knows of the product type. Always shown as a rough estimate.
_Avoid_: Guess, AI lifespan, model estimate (that is the kind of its source)

**Recurring cost**:
What a product option costs to keep running each year in consumables or parts, such as filters,
bags or a replacement battery; never energy or water. For each option it is found, not found, or
not looked for when the category has no consumables to look for.
_Avoid_: Running cost, upkeep, typical yearly cost (that one is the category's, on a decision
factor)

**Typical yearly cost**:
What a category's main consumable typically costs a year, found in the source of a decision
factor about a recurring cost. It is shown as one line above the questions and on the report,
never asked about, and never used in the figures of a product option, which use the option's
own recurring cost.
_Avoid_: Recurring cost (that one is the option's), category cost

**Durability judgement**:
The model's own view, from how a candidate is made, of whether it lasts longer than, about as
long as, or shorter than most products of its kind (`long`, `medium`, `short`), or `unknown`
when the model does not know the product. It orders candidates in selection; it is never a
lifespan and never on the report, only in the trail. Durability evidence is researched only for
product options.
_Avoid_: Durability estimate, durability score, durability rating

**Finding**:
One thing a tester or an owner reported about how a product option holds up, labelled as a test
or an owner report. A test is only what a source says it found by using or testing the product.
_Avoid_: Review, rating, feedback

**Finding summary**:
What a finding says, in the app's own words: one report about one unit or one test, never a copy
of the source's text. The quote behind it is checked but never shown.
_Avoid_: Review text, excerpt, quote (that is what the summary is checked against)

**Overall rating**:
A score a source gives a product as a whole, kept exactly as the source writes it, with its
review count when owners gave it. It is never a durability score.
_Avoid_: Durability rating, score, stars

**Evidence summary**:
The counts of how many lifespans and CO2e figures on a report are sourced, estimated, set by the
user or missing.
_Avoid_: Confidence score, quality score

**Inputs**:
The materials, weights and emission factors a CO2e estimate was built from. An input whose
material or weight is a model's guess is shown as estimated. In code, one `LcaInput` per material:
its mass and emission factor range, each with a source.
_Avoid_: Assumptions

**Trail**:
The ordered record of what each agent found, decided or excluded, with its source and the model
tier that produced it.
_Avoid_: Log, history, audit log

**Source**:
Where a stated value came from: a web page, a row in a reference dataset, a model estimate, or the
user.
_Avoid_: Citation, reference, provenance

**Category research**:
Finding the decision factors of a category in web sources, before the user has been asked
anything.
_Avoid_: Brief research, background research

**Option research**:
Finding product options that fit the answers and the budget, and the evidence for each, in web
sources.
_Avoid_: Product search, product research

**Local category term**:
The word shops in the market use for the category ("koekenpan" for a frying pan), found in
category research. It fills search queries and is looked for in product names; it is never shown
as the category.
_Avoid_: Dutch search term, search term, translated category

**Search query**:
The text sent to the web search to research a category or a product option. It is never the
user's input.
_Avoid_: Query (alone), search term, prompt

**Search result**:
One web page returned for a search query. It becomes a source only when a stated value cites it.
_Avoid_: Hit, source (before a value cites it), page

**Search purpose**:
Why a search is made (category, consumables and care, listing pages, evidence, findings). It
sets the country boost, the excluded domains and how long a cached result lasts; `SearchPurpose`
in `config.py`.
_Avoid_: Search type, search mode

**Fixture twin**:
The stand-in for an external service that answers from recorded responses in `tests/fixtures/`,
chosen with `SHOPPER_SOURCES=fixtures` and used by the default test run.
_Avoid_: Mock, stub (a stub is an agent placeholder)

**Boundary**:
The part of a product's life cycle that a CO2e figure covers, such as manufacturing only or cradle
to gate.
_Avoid_: Scope, coverage

**Confidence label**:
The words shown with a figure that say how it was obtained: "published figure", "benchmark
estimate" or "AI synthetic estimate" on a CO2e figure, "rough estimate" on a lifespan, and
"estimated" on a material, form or mass. Each has a basis: published, benchmark or estimate. The
user sees the words, never the tier number, and never as a seal, a colour or a badge.
_Avoid_: Tier (on the report), confidence score, quality rating

**Caveat**:
A fixed statement on a report that follows from the request's scope and says what the result does
not account for.
_Avoid_: Disclaimer, warning

**Warning**:
A statement that something specific to this request or result could not be used, found or
verified, and why.
_Avoid_: Caveat, error

**Line**:
One finished line the app shows, such as what was understood, the source under a question or a
"From your reply" line, made of parts: words, a link to a source, a confidence label, or one of the page's controls.
Code fills it from a fixed template, so the terminal app and the page show the same words; the
terminal prints its words and leaves out its controls.
_Avoid_: Text, string (a line can hold a link or a control)

**Figure line**:
A figure of a product option as the app shows it: its label, such as "Cost per year", and its
value, or, when the figure is missing, why. Both are lines.
_Avoid_: Cell, stat, metric, figure (alone, that is the computed number)
