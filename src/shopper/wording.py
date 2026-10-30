"""Every fixed message, as a template: the only copy of its words (docs/wording.md says how they are
written, docs/adr/0009-wording-lives-in-code.md why they live here).

This module imports nothing from the package, so `calc/`, the agents and the entry points can all
use it. Codes and scopes are therefore plain strings here.

A line the terminal app prints and the page shows is a `Line` of parts, filled from its template
(docs/adr/0008-api-sends-finished-lines.md); warnings, error messages and progress lines stay
strings.
"""

from collections.abc import Sequence
from datetime import date
from string import Formatter
from typing import Annotated, Literal
from urllib.parse import urlparse

from pydantic import BaseModel, ConfigDict, Field

# What left no product option, as `no_options_found` words it.
NoOptionsReason = Literal["nothing_found", "searches_failed", "none_met_the_answers"]
# The page's controls a line can end in, a closed list; each has its words in web/lib/wording.ts.
ControlKey = Literal["edit"]
# What a figure's confidence label rests on: a published figure, a benchmark, or an estimate.
ConfidenceBasis = Literal["published", "benchmark", "estimate"]


class _LineModel(BaseModel):
    # As `DomainModel` in state.py, which this module cannot import: frozen, and every field
    # required in the schema the API publishes, so the page's generated types narrow.
    model_config = ConfigDict(
        frozen=True, extra="forbid", json_schema_serialization_defaults_required=True
    )


class TextPart(_LineModel):
    """Words, with no markup."""

    kind: Literal["text"] = "text"
    text: str


class LinkPart(_LineModel):
    """Words that link to a source, such as a site's name to the page it was read on."""

    kind: Literal["link"] = "link"
    text: str
    url: str


class ConfidencePart(_LineModel):
    """A figure's confidence label: always its words, styled neutrally, never as a seal."""

    kind: Literal["confidence"] = "confidence"
    text: str
    basis: ConfidenceBasis


class ControlPart(_LineModel):
    """One of the page's controls, which only ends a line; the terminal app leaves it out."""

    kind: Literal["control"] = "control"
    key: ControlKey


Part = Annotated[TextPart | LinkPart | ConfidencePart | ControlPart, Field(discriminator="kind")]


class Line(_LineModel):
    """A finished line as parts the page lays out; the terminal app prints their text."""

    parts: tuple[Part, ...]


class FigureLine(_LineModel):
    """A "Label: value" line of the report as its two halves; the terminal app prints
    "label: value". `missing` when the value says why the figure is not there."""

    label: Line
    value: Line
    missing: bool = False


# A site as words, or as its name linked to its source.
Site = str | LinkPart
# What fills a placeholder: words, a part, or a line whose parts it takes in.
Filling = str | LinkPart | ConfidencePart | Line


def filled(template: str, **values: Filling) -> Line:
    """A template filled into a Line: a string joins the words around it, a part stays a part,
    and a line gives its parts."""
    parts: list[Part] = []
    for words, name, _, _ in Formatter().parse(template):
        parts = _with_text(parts, words)
        if name is None:
            continue
        parts = _with_filling(parts, values[name])
    return Line(parts=tuple(parts))


def figure(template: str, *, missing: bool = False, **values: Filling) -> FigureLine:
    """A "Label: value" template filled as a figure, split at its first ": "."""
    label, value = template.split(": ", 1)
    return FigureLine(label=filled(label, **values), value=filled(value, **values), missing=missing)


def text_line(text: str) -> Line:
    """A finished sentence, such as a warning's message, as one text part; nothing in it is
    read as a placeholder."""
    return Line(parts=(TextPart(text=text),))


def joined(lines: Sequence[Line], separator: str) -> Line:
    """The lines as one, with the separator's words between them."""
    parts: list[Part] = []
    for index, line in enumerate(lines):
        parts = _with_filling(_with_text(parts, separator if index else ""), line)
    return Line(parts=tuple(parts))


def ended_by(line: Line, key: ControlKey) -> Line:
    """The line with a control after its last part."""
    return Line(parts=(*line.parts, ControlPart(key=key)))


def plain_text(line: Line) -> str:
    """The line as the terminal app prints it: its parts' words, without its controls."""
    return "".join(part.text for part in line.parts if not isinstance(part, ControlPart))


def _with_filling(parts: list[Part], value: Filling) -> list[Part]:
    if isinstance(value, str):
        return _with_text(parts, value)
    if isinstance(value, Line):
        for part in value.parts:
            parts = _with_filling(parts, part.text if isinstance(part, TextPart) else part)
        return parts
    return [*parts, value]


def _with_text(parts: list[Part], text: str) -> list[Part]:
    """The parts with the text after them: joined to the last part when that is words too."""
    if not text:
        return parts
    if parts and isinstance(parts[-1], TextPart):
        return [*parts[:-1], TextPart(text=parts[-1].text + text)]
    return [*parts, TextPart(text=text)]


NOT_COVERED = "This app covers durable products such as cookware, appliances and tools."
NOT_COVERED_CATEGORY = (
    "This app covers durable products such as cookware, appliances and tools. "
    """It can't help with "{category}"."""
)
SEVERAL_PRODUCTS = (
    "That looks like more than one product. "
    "Name one to start, for example 'a frying pan, budget €50'."
)
UNCLEAR = (
    "We couldn't tell what you're looking for. "
    "Try naming one product, for example 'a frying pan, budget €50'."
)
LINK_UNREADABLE_ENDED = (
    "We couldn't read the product at your link. "
    "Name the product to start, for example 'a frying pan, budget €50'."
)

INPUT_TOO_LONG = (
    "That is more text than the app can read. Try naming one product in a sentence or two."
)
MODEL_CALL_FAILED = (
    "The app couldn't read your request just now, so nothing was run. Try again in a moment."
)
# The message beside each code the API answers with when a session cannot go on, by the code.
# `invalid_request` answers a body FastAPI's own validation rejects, which the page should never
# send; `internal_error` anything unexpected before a stream starts, such as a database error.
ERRORS = {
    "session_not_found": "We couldn't find this session. Start again with your request.",
    "session_running": (
        "This session is already running, so nothing new was started. Wait for it to finish."
    ),
    "session_not_paused": (
        "This session is not waiting for answers, so nothing was run. "
        "Start again with your request."
    ),
    "invalid_answers": (
        "Some of these answers don't fit the questions, so nothing was run. "
        "Answer the questions again."
    ),
    "invalid_request": (
        "The app couldn't read what the page sent, so nothing was run. "
        "Reload the page and start again."
    ),
    "input_too_long": INPUT_TOO_LONG,
    "internal_error": "The app couldn't answer just now. Try again in a moment.",
    "model_call_failed": MODEL_CALL_FAILED,
    "run_stopped": "The run stopped before your report was ready. Start again with your request.",
    # The codes of the user's reply to the questions; each leaves the session paused, and the page
    # shows the words in the step it opens again.
    "reply_too_long": (
        "That is more text than the app can read, so nothing was sent. Answer in a sentence or two."
    ),
    "reply_unread": (
        "The app couldn't read your reply just now, so nothing was run. "
        "Send it again, or answer with the choices."
    ),
    "reply_unanswered": (
        "Nothing in your reply answered the open questions, so nothing was run. "
        "Answer in your own words or with the choices."
    ),
    # The codes of task 2.5.2. `{wait}` is the time until the oldest session counted against the
    # limit leaves the hour, in whole minutes rounded up.
    "too_many_sessions": (
        "Many sessions were started from this connection in the last hour, so no new one was "
        "started. Try again in {wait}."
    ),
    # The site-wide ceiling of task 3.5, not about this connection and with no wait to name.
    "too_many_sessions_today": (
        "Many sessions were started on this app in the last day, so no new one was started. "
        "Try again tomorrow."
    ),
    "no_report_yet": (
        "This session has no report yet, so nothing was recalculated. "
        "Change the assumptions once the report is ready."
    ),
    "no_options": (
        "This report has no options, so there is nothing to recalculate. "
        "Start again with your request."
    ),
    "unknown_option": (
        "A lifespan was set for an option that is not on this report, so nothing was "
        "recalculated. Set the lifespans again."
    ),
    "invalid_assumptions": (
        "Some of these assumptions are outside what the app can calculate, so nothing was "
        "recalculated. Change them and try again."
    ),
}


# The second wording of `reply_unanswered`, for a session that paused with no questions.
REPLY_UNANSWERED_NO_QUESTIONS = (
    "Nothing in your reply added a requirement, so nothing was run. "
    "Add one in your own words, or clear your reply and press Show my options."
)


def too_many_sessions(minutes: int) -> str:
    """The `too_many_sessions` message, with the whole minutes until a session can start."""
    wait = "1 minute" if minutes == 1 else f"{minutes} minutes"
    return ERRORS["too_many_sessions"].format(wait=wait)


CAVEATS = {
    "energy_heavy": (
        "Energy and water use are not included in these figures. For this kind of product they "
        "are a large part of the cost, so the order of these options can change once they are "
        "counted."
    ),
    "clothing": (
        "Fit and style are not assessed, and how long clothing lasts depends mostly on wear and "
        "care."
    ),
    "not_tuned": "This category is not one the app is tuned for; check the sources.",
}

# `{phrase}` is the budget exactly as the user wrote it; `{currency}` the currency code the product
# page states, such as "GBP".
WARNINGS = {
    "budget_unreadable": (
        'We couldn\'t read "{phrase}" as an amount, so no budget is applied. '
        'To set one, start again with an amount in euro, such as "budget €50".'
    ),
    "budget_other_currency": (
        'This app works in euro only, so "{phrase}" is not applied as a budget. '
        "To set one, start again with an amount in euro."
    ),
    "budget_not_positive": 'A budget of "{phrase}" can\'t be used, so no budget is applied.',
    "nothing_within_budget": (
        "Nothing found within {budget}; the cheapest option is {cheapest price}."
    ),
    "link_unreadable": (
        "We couldn't read the product at your link, so it is not among the options below. "
        "These are options for {category}."
    ),
    "link_price_other_currency": (
        "The price at your link is in {currency}. This app works in euro only, so that price is "
        "not used and the figures that depend on it are not shown."
    ),
    "research_unavailable": (
        """We couldn't research "{category}", so the questions and the check list are """
        "shorter than usual."
    ),
    "questions_unavailable": (
        """We couldn't prepare the questions for "{category}". """
        "What they would have asked about is on the check-before-you-buy list."
    ),
    "stated_answers_unavailable": (
        "We couldn't pick out the requirements in your request, so only your answers to the "
        "questions are applied."
    ),
    "one_option_only": (
        "Only one option is left, so there is nothing to compare it against; the reasons are in "
        "the evidence trail."
    ),
}
# The three wordings of `no_options_found`, by what happened (option_research.md, "Warnings").
NO_OPTIONS_FOUND: dict[NoOptionsReason, str] = {
    "nothing_found": (
        "We couldn't find a {category} with a price in euro, so there are no options to compare."
    ),
    "searches_failed": (
        "The search for {category} options didn't work just now, so there are no options to "
        "compare. Try again in a moment."
    ),
    "none_met_the_answers": (
        "We found {n} products for {category}, but none met your answers; the reasons are in the "
        "evidence trail."
    ),
}
# The two wordings of `co2e_unavailable`: one option, or the whole estimate (lca.md, "Rules").
CO2E_UNAVAILABLE = {
    "option": (
        "We couldn't estimate the CO2e of making {name}, so no CO2e figure is shown for it."
    ),
    "report": (
        "We couldn't estimate the CO2e of making these products just now, so no CO2e figures are "
        "shown. Try again in a moment."
    ),
}

# The labels of an option's figures on the report, each in front of its value ("Price: €20").
PRICE_LABEL = "Price"
LINK_LABEL = "Link"
LIFESPAN_LABEL = "Lifespan"
WARRANTY_LABEL = "Warranty"
WEARS_LABEL = "Wears"
REPAIRS_LABEL = "Repairs"
CARE_LABEL = "Care"
RECURRING_COST_LABEL = "Recurring cost"
COST_PER_YEAR_LABEL = "Cost per year"
COST_PER_USE_LABEL = "Cost per use"
PURCHASES_LABEL = "Purchases over {horizon} years"
HORIZON_COST_LABEL = "Cost over {horizon} years"
CO2E_LABEL = "CO2e"
BUILT_FROM_LABEL = "Built from"
# When the model estimated every part, the mark follows the label once.
BUILT_FROM_ESTIMATED_LABEL = "Built from ({estimated})"
MARKED_ESTIMATED = "{part} ({estimated})"
MASS = "{mass} kg"
# Between the parts of one material (name, form, mass), and between materials.
PART_SEPARATOR = ", "
MATERIAL_SEPARATOR = "; "
AGAINST_LABEL = "Against {baseline}"
# The terminal app's headings; the page names its sections in web/lib/wording.ts.
CHECK_HEADING = "Check before you buy"
TRAIL_HEADING = "Trail"
# One item of the check list; a factor of the user's own is quoted, and the options an item
# concerns follow it.
CHECK_ITEM = "{factor}: {why}"
CHECK_ITEM_OWN = '"{factor}": {why}'
CHECK_ITEM_OPTIONS = " ({options})"
# One trail entry: who wrote it, then what it says. `{produced_by}` is the tier and the model.
TRAIL_BY = "{agent} [{produced_by}]"
TRAIL_PRODUCED_BY_SEPARATOR = ", "
TRAIL_ENTRY = "{kind}: {summary}"
TRAIL_REASON = "; reason: {reason}"
TRAIL_SOURCE = "; source: {source}"
OVER_BUDGET = "Over your budget"
OUT_OF_STOCK = "Out of stock when the price was seen"
SOLD_INCOMPLETE = "Sold without a part it needs to work"
NOT_AGAINST_BASELINE = ", so no savings or CO2e against {baseline} are shown"
HIDE_OVER_BUDGET = "Hide options over my budget"
UNDERSTOOD = "Looking for: {category} · Budget: {budget}"
NO_BUDGET = "none given"
BOX_LABEL = "{category} · {budget}"

BOX_LABEL_NO_BUDGET = "{category}"
NO_CATEGORY = "the product at your link"
NOT_YET_KNOWN = "Not yet known"
NOT_CONFIRMED = "Could not be confirmed"
MISSING_FIGURE = "not available ({reason})"
UNDER_A_CENT = "under €0.01"
ROUGH_ESTIMATE = "rough estimate"
YEARS = "{n} years"
ONE_YEAR = "{n} year"
PRICE_VARIANT = "{price} ({variant})"
LIFESPAN_ROUGH = "{years} ({rough})"
LIFESPAN_SET_BY_YOU = "{years} (set by you)"
LIFESPAN_SOURCED = "{years} ({site})"
# A rough lifespan and a part of a CO2e estimate the model made are marked as estimates.
ROUGH = ConfidencePart(text=ROUGH_ESTIMATE, basis="estimate")
# A price from a web page reads "€39.95, plus €4.95 shipping, price seen at Kookexpert.nl via
# beslist.nl on 17 October 2026": the shipping, then where and when. `{shop}` is the seller the
# offer names, none on a shop's own page. Shipping is never added to the price shown
# (eu_market.md, "Market").
PRICE_SEEN_AT = "price seen at {site} on {date}"
PRICE_SEEN_AT_SHOP = "price seen at {shop} via {site} on {date}"
SHIPPING = "plus {amount} shipping"
FREE_SHIPPING = "free shipping"
SHIPPING_NOT_STATED = "shipping not stated"
CONFIRM_PRICE = "Confirm the current price"
PRICES_CHANGE = "Prices change after the day each was seen."
# The months as a date on the report names them; never the locale's.
MONTHS = (
    "January",
    "February",
    "March",
    "April",
    "May",
    "June",
    "July",
    "August",
    "September",
    "October",
    "November",
    "December",
)

# The line shown as each agent starts, by the agent's name. The supervisor's is shown once, as the
# request is read, not again when it assembles the report; the pause for the answers has no line.
STARTED = {
    "supervisor": "Reading your request...",
    "brief": "Researching what to ask about...",
    "tco": "Finding options and their prices...",
    "lca": "Estimating the CO2e of making each option...",
    "second_hand": "Checking for used options...",
}
# The line the API sends as each agent finishes, by the agent's name; the terminal app prints none
# and the page shows none. It says the work is done, never how it turned out.
FINISHED = {
    "supervisor": "Finished.",
    "brief": "Finished researching what to ask about.",
    "tco": "Finished looking for options and their prices.",
    "lca": "Finished estimating the CO2e of making each option.",
    "second_hand": "Finished checking for used options.",
}
# The brief agent's lines as it reads the user's reply to the questions, only when there is one.
READING_REPLY = "Reading your reply..."
FINISHED_READING_REPLY = "Finished reading your reply."
USAGE_QUESTION = "How often will you use it?"
USAGE_REASON = "It sets the cost per use."
USAGE_FACTOR_NAME = "Usage frequency"
# The usage frequencies: the words of each, by its id. The uses per year are in usage_frequency.py.
USAGE_FREQUENCIES = {
    "several_times_a_day": "Several times a day",
    "every_day": "Every day",
    "a_few_times_a_week": "A few times a week",
    "about_once_a_week": "About once a week",
    "about_once_a_month": "About once a month",
    "a_few_times_a_year": "A few times a year",
    "about_once_a_year": "About once a year",
}
CARE_CLOSING_QUESTION = "Is that fine with you?"
CARE_FINE = "That's fine"
CARE_AVOID = "I'd rather avoid it"
TYPICAL_COST = "{factor}: typically {amount} a year ({site})."
SOURCE = "Source: {site}"
# Who is speaking, when it is not an independent tester or an owner (docs/eu_market.md).
SOURCE_STATED_BY = {
    "manufacturer": "Source: {site} (the manufacturer states)",
    "seller": "Source: {site} (the seller states)",
}
# After the site of a claim a manufacturer or a seller made, on the report.
STATED_BY_SUFFIX = {
    "manufacturer": "(the manufacturer states)",
    "seller": "(the seller states)",
}
USER_FACTOR_WHY = "You asked for this."
# `{value}` is the choice the requirement was mapped onto, or the value the model wrote when no
# choice fits; a factor of the user's own is named by its phrase, so its line shows the phrase
# alone. On the report the request's lines come first, then the reply's, then any typical yearly
# cost.
STATED_ANSWER = 'From your request: {factor}: {value} ("{phrase}")'
STATED_USAGE = 'From your request: {frequency}, {n} uses a year ("{phrase}")'
STATED_OWN = 'From your request: "{phrase}"'
REPLY_ANSWER = 'From your reply: {factor}: {value} ("{phrase}")'
REPLY_USAGE = 'From your reply: {frequency}, {n} uses a year ("{phrase}")'
REPLY_OWN = 'From your reply: "{phrase}"'
REPLY_NOT_SURE = 'From your reply: {factor}: not sure ("{phrase}")'
# The lines the page shows in its thread once the reply is read; never on the report.
# Whether it answered nothing, or only what a choice picked or the request already answers.
REPLY_ADDED_NOTHING = "Nothing you wrote changed an answer or added a requirement."
REPLY_CANNOT_CHANGE_REQUEST = (
    "A reply can't change what you're looking for or the budget, so the results are still for "
    "{category}, budget {budget}. To change either, press Edit."
)
# A reply that ended unanswered ran nothing, so there are no results to name.
REPLY_CANNOT_CHANGE_UNANSWERED = (
    "A reply can't change what you're looking for or the budget. To change either, press Edit."
)
KEYS = (
    "Type the number of a choice, n for not sure, or press Enter to skip. "
    "Type skip all to skip the rest."
)
ASK_AGAIN = "Type a number from 1 to {n}, n for not sure, or press Enter to skip."

# The confidence label of a CO2e figure, by its tier, with what it rests on; the tier number is
# never shown. It is written in lower case inside a sentence ("AI" stays). `{low}` and `{high}`
# arrive rounded to two significant figures, outward. A figure of tier 1 or 2 names its source
# after its label; a model estimate's label names its source.
CO2E_LABELS = {
    1: ConfidencePart(text="published figure", basis="published"),
    2: ConfidencePart(text="benchmark estimate", basis="benchmark"),
    3: ConfidencePart(text="AI synthetic estimate", basis="estimate"),
}
CO2E_OVER_HORIZON = "{low} to {high} kg CO2e to make, over {horizon} years ({label})"
CO2E_PER_ITEM = "{low} to {high} kg CO2e to make ({label})"
CO2E_SET = ", for the set of {n}"
CO2E_SOURCED = "{label}, {source}"
CO2E_LESS = "About {low} to {high} kg CO2e less to make over {horizon} years ({label})"
# It states its basis (a comparison must; eu_market.md), and the source is the car figure's alone:
# the range is the app's own estimate. The car chosen matters: about 2.5 times against the US EPA's
# average petrol car.
CO2E_FOR_SCALE = (
    "; for scale, about {low} to {high} km in an average new car in Europe, electric cars included "
    "(car figure: {source}, {year}, tailpipe test; real drives emit more)"
)
CAR_FIGURE_SOURCE = "EEA"
# The mark on a part of a CO2e estimate the model made; its brackets are the template's words.
ESTIMATED = "estimated"
ESTIMATED_MARK = ConfidencePart(text=ESTIMATED, basis="estimate")

# `{type}` is the kind of product the quote names, as it stands in it ("Non-stick pans"), or
# UNNAMED_TYPE when it names none: the request's category may be wider than the quote. Tests come
# before owner reports.
LIFETIME_WARRANTY = "lifetime"
LIMITED_LIFETIME_WARRANTY = "limited lifetime"
TYPICAL_LIFESPAN = "Typical for {type}: {low} to {high} years ({site})"
UNNAMED_TYPE = "this kind of product"
# One line per durability evidence item, under the lifespan: "Warranty: lifetime (tefal.nl)".
EVIDENCE_ITEM = "{item}: {value} ({site})"
NO_DURABILITY_EVIDENCE = "No durability evidence found"
LIFESPAN_NOT_READ = "durability evidence could not be read; set a lifespan to see it"
RECURRING_COST = "{amount} a year, {consumable} ({site})"
CONVERTED = "converted from {currency} at a fixed rate"
OTHER_CONSUMABLES = "other consumables not counted"
RECURRING_COSTS_NOT_FOUND = "recurring costs not found"
FINDING_TEST = "Test: {summary} ({site})"
FINDING_OWNER_REPORT = "Owner report: {summary} ({site})"
# Each kind of finding, by its value in state.py.
FINDINGS_BY_KIND = {"test": FINDING_TEST, "owner_report": FINDING_OWNER_REPORT}
FINDING_RATING = ", overall rating {rating}"
FINDING_REVIEW_COUNT = " from {count} reviews"
NO_FINDINGS_FOUND = "No owner or tester reports found"
FINDINGS_NOT_SEARCHED = "Owner and tester reports not looked up"

# One line per factor value of an option, in the order of the decision factors; `{value}` is the
# short value the evidence read wrote.
FACTOR_MEETS = "{factor}: {value} ({site})"
FACTOR_NOT_CONFIRMED = "{factor}: could not be confirmed"
FACTOR_CARE_NEEDED = (
    "{factor}: {value} ({site}). "
    "You said you'd rather avoid this; the lifespan shown assumes it is done."
)
FACTOR_MISMATCH = "Does not match your answer for {factor}: {value} ({site})"
# A factor of the user's own is named by their phrase, so its lines quote it (task 1.10).
FACTOR_MEETS_OWN = 'You asked for "{factor}": {value} ({site})'
FACTOR_MISMATCH_OWN = 'Does not match what you asked for, "{factor}": {value} ({site})'
FACTOR_NOT_CONFIRMED_OWN = 'You asked for "{factor}": could not be confirmed'

# The trail's words for the durability judgement, which is never on the report.
JUDGED = "{judgement}, the model's judgement, not a sourced figure"
DURABLE_PICK = "ordered by the model's judgement: {judgement}, not a sourced figure"
FILLED_BY_PRICE = "Filled the slots by price"
FILLED_BY_PRICE_WHY = "the durability judgement did not tell the candidates apart"

# An option with savings of zero, or with savings missing, gets no savings line.
COSTS_LESS = "Over {horizon} years: {option} costs {amount} less than {baseline}."
COSTS_MORE = "Over {horizon} years: {option} costs {amount} more than {baseline}."
ROUGH_SAVINGS = " A lifespan behind this is a rough estimate."
EVIDENCE_LIFESPANS = "Lifespan sourced for {n} of {total} options."
EVIDENCE_LIFESPANS_USER_SET = ", set by you for {k}"
# The two evidence sentences make one line. "CO2e to make": every figure is the making only, never
# the life cycle (task 1.10).
EVIDENCE_FOOTPRINTS = (
    "CO2e to make: published for {a}, benchmark estimate for {b}, "
    "AI synthetic estimate for {c}, not found for {d}."
)


def request_not_run(scope: str, category: str | None, *, has_link: bool = False) -> Line | None:
    """The message for a request whose scope means nothing runs; missing for one that runs.

    An unclear request with a link is one whose link was fetched and gave no product.
    """
    if scope == "not_a_product":
        if category is None:
            return filled(NOT_COVERED)
        return filled(NOT_COVERED_CATEGORY, category=category)
    if scope == "unclear" and has_link:
        return filled(LINK_UNREADABLE_ENDED)
    template = {"several_products": SEVERAL_PRODUCTS, "unclear": UNCLEAR}.get(scope)
    return None if template is None else filled(template)


def budget_warning(code: str, phrase: str) -> str:
    """The message for a budget that was not applied, quoting it as the user wrote it."""
    return WARNINGS[code].format(phrase=phrase)


def link_unreadable(category: str) -> str:
    """The message when the product at the link could not be read and the session goes on."""
    return WARNINGS["link_unreadable"].format(category=category)


def link_price_other_currency(currency: str) -> str:
    """The message when the product page states its price in a currency other than euro."""
    return WARNINGS["link_price_other_currency"].format(currency=currency)


def research_unavailable(category: str) -> str:
    """The message when category research gave no decision factor."""
    return WARNINGS["research_unavailable"].format(category=category)


def questions_unavailable(category: str) -> str:
    """The message when there are decision factors and no question could be phrased from them."""
    return WARNINGS["questions_unavailable"].format(category=category)


def stated_answers_unavailable() -> str:
    """The message when the requirements the request states could not be picked out."""
    return WARNINGS["stated_answers_unavailable"]


def one_option_only() -> str:
    """The message when exactly one product option is left to show."""
    return WARNINGS["one_option_only"]


def no_options_found(what_happened: NoOptionsReason, category: str, candidates: int = 0) -> str:
    """The message when no product option is left; `what_happened` picks the wording, and
    `candidates` counts the candidates whose product page was read."""
    return NO_OPTIONS_FOUND[what_happened].format(category=category, n=candidates)


def price_seen_at(site: Site, shop: str | None, seen_on: date) -> Line:
    """Where and when a price was seen: the site of its page, and the shop that sells it there
    when that is another (an offer on a comparison site)."""
    if shop is None:
        return filled(PRICE_SEEN_AT, site=site, date=written_date(seen_on))
    return filled(PRICE_SEEN_AT_SHOP, shop=shop, site=site, date=written_date(seen_on))


def written_date(day: date) -> str:
    """A day as the report writes it: "17 October 2026"."""
    return f"{day.day} {MONTHS[day.month - 1]} {day.year}"


def nothing_within_budget(budget: str, cheapest_price: str) -> str:
    """The message when nothing is within the budget; both amounts arrive formatted."""
    return WARNINGS["nothing_within_budget"].format(
        **{"budget": budget, "cheapest price": cheapest_price}
    )


def understood(category: str | None, budget: str | None) -> Line:
    """The line that shows what was understood, ended by the control that edits it; the budget
    arrives formatted."""
    line = filled(UNDERSTOOD, category=category or NO_CATEGORY, budget=budget or NO_BUDGET)
    return ended_by(line, "edit")


def box_label(category: str | None, budget: str | None) -> Line:
    """What was understood as the page's box carries it on its first label: the category and the
    budget alone, or the category alone when there is no budget; the budget arrives formatted."""
    if budget is None:
        return filled(BOX_LABEL_NO_BUDGET, category=category or NO_CATEGORY)
    return filled(BOX_LABEL, category=category or NO_CATEGORY, budget=budget)


def missing_figure(reason: str) -> Line:
    """What a missing figure shows in place of its value; the reason comes from `calc/`."""
    return filled(MISSING_FIGURE, reason=reason)


def ask_again(choices: int) -> str:
    """The line shown when what was typed is not one of a question's keys."""
    return ASK_AGAIN.format(n=choices)


def care_question(statement: str) -> str:
    """A care question: the statement about the care, then the question that closes it."""
    return f"{statement} {CARE_CLOSING_QUESTION}"


def typical_cost(factor: str, amount: str, url: str, converted_from: str | None) -> Line:
    """A category's typical yearly cost for a consumable, its site linked to its source and
    labelled when it was converted, shown above the questions and on the report; the amount
    arrives formatted."""
    if converted_from is None:
        template = TYPICAL_COST
    else:
        template = f"{TYPICAL_COST.removesuffix('.')}, {CONVERTED}."
    return filled(
        template, factor=factor, amount=amount, site=site_link(url), currency=converted_from or ""
    )


def stated_answer(factor: str, value: str, phrase: str, *, from_reply: bool = False) -> Line:
    """A requirement the request states, shown above the questions and on the report, or one
    the reply states, in the thread and on the report."""
    template = REPLY_ANSWER if from_reply else STATED_ANSWER
    return filled(template, factor=factor, value=value, phrase=phrase)


def stated_own(phrase: str, *, from_reply: bool = False) -> Line:
    """A requirement the request or the reply states that fits no decision factor: its words are
    its name."""
    return filled(REPLY_OWN if from_reply else STATED_OWN, phrase=phrase)


def stated_usage(
    frequency: str, uses_per_year: int, phrase: str, *, from_reply: bool = False
) -> Line:
    """How often the request or the reply says the product is used; the uses per year are
    code's."""
    template = REPLY_USAGE if from_reply else STATED_USAGE
    return filled(template, frequency=frequency, n=f"{uses_per_year:,}", phrase=phrase)


def reply_not_sure(factor: str, phrase: str) -> Line:
    """A question the reply answers "not sure", in the thread and on the report."""
    return filled(REPLY_NOT_SURE, factor=factor, phrase=phrase)


def reply_cannot_change_request(category: str | None, budget: str | None) -> Line:
    """Why a reply that asked for another category or budget left the request as it was; the
    budget arrives formatted, and a missing one is worded as in the "Looking for" line."""
    return filled(
        REPLY_CANNOT_CHANGE_REQUEST, category=category or NO_CATEGORY, budget=budget or NO_BUDGET
    )


def reply_in_thread(
    category: str | None,
    budget: str | None,
    *,
    asks_to_change_request: bool,
    changed_an_answer: bool,
    unanswered: bool,
) -> Line | None:
    """The line the thread shows once the reply is read, after its "From your reply" lines; none
    for a reply that changed an answer or added a factor of the user's own, and asked for nothing
    else. A reply that ended unanswered ran nothing, so it has a line only when it asked to change
    the request."""
    if unanswered:
        return filled(REPLY_CANNOT_CHANGE_UNANSWERED) if asks_to_change_request else None
    if asks_to_change_request:
        return reply_cannot_change_request(category, budget)
    if changed_an_answer:
        return None
    return filled(REPLY_ADDED_NOTHING)


def reply_unanswered(*, has_questions: bool) -> str:
    """The `reply_unanswered` message; the second wording is for a session that paused with no
    questions, where a reply can only add a requirement."""
    return ERRORS["reply_unanswered"] if has_questions else REPLY_UNANSWERED_NO_QUESTIONS


def site_name(url: str) -> str:
    """The name of the website a URL is on: its host in lower case, without "www."."""
    return (urlparse(url).hostname or url).removeprefix("www.")


def site_link(url: str) -> LinkPart:
    """The name of the website a URL is on, linked to the URL."""
    return LinkPart(text=site_name(url), url=url)


def spoken(template: str, stated_by: str | None) -> str:
    """The template with who is speaking after its "({site})", when it matters: words after the
    site's link, never inside it."""
    suffix = STATED_BY_SUFFIX.get(stated_by or "")
    return template if suffix is None else template.replace("({site})", f"({{site}}) {suffix}")


def evidence_item(item: str, value: str, site: Site, stated_by: str | None) -> FigureLine:
    """One durability evidence item with its site, and who is speaking when it matters."""
    return figure(spoken(EVIDENCE_ITEM, stated_by), item=item, value=value, site=site)


def counted_years(shown: str) -> str:
    """Years as shown with their word, singular when they show as 1 ("1 year", "1.7 years")."""
    return (ONE_YEAR if shown == "1" else YEARS).format(n=shown)


def price_shown(price: str, variant: str | None) -> Line:
    """A price with the size or variant it was quoted for; the price arrives formatted."""
    if variant is None:
        return text_line(price)
    return filled(PRICE_VARIANT, price=price, variant=variant)


def rough_lifespan(years: str) -> Line:
    """A lifespan that is still a model's estimate, marked as rough."""
    return filled(LIFESPAN_ROUGH, years=years, rough=ROUGH)


def lifespan_set_by_you(years: str) -> Line:
    return filled(LIFESPAN_SET_BY_YOU, years=years)


def built_from_label(*, all_estimated: bool) -> Line:
    """The label of the materials line; marked once when the model estimated every part."""
    if all_estimated:
        return filled(BUILT_FROM_ESTIMATED_LABEL, estimated=ESTIMATED_MARK)
    return text_line(BUILT_FROM_LABEL)


def material_part(text: str, *, marked: bool) -> Line:
    """A material's name, form or mass, marked when the model estimated it."""
    return (
        filled(MARKED_ESTIMATED, part=text, estimated=ESTIMATED_MARK) if marked else text_line(text)
    )


def mass(shown: str) -> str:
    """A mass in kg; it arrives rounded."""
    return MASS.format(mass=shown)


def built_from(materials: Sequence[Sequence[Line]]) -> Line:
    """The materials, each its parts, as the value of the "Built from" line."""
    return joined([joined(parts, PART_SEPARATOR) for parts in materials], MATERIAL_SEPARATOR)


def sold_incomplete(baseline: str | None) -> Line:
    """The mark of an option sold without a part it needs, naming the baseline it is not set
    against when there is one."""
    if baseline is None:
        return text_line(SOLD_INCOMPLETE)
    return filled(SOLD_INCOMPLETE + NOT_AGAINST_BASELINE, baseline=baseline)


def check_item(factor: str, why: str, options: Sequence[str], *, own: bool) -> Line:
    """An open factor on the check list, quoted when it is the user's own, with the options it
    concerns."""
    template = (CHECK_ITEM_OWN if own else CHECK_ITEM) + (CHECK_ITEM_OPTIONS if options else "")
    return filled(template, factor=factor, why=why, options=", ".join(options))


def confirm_price() -> Line:
    """The check list's one line for every price, to confirm before buying."""
    return filled(CHECK_ITEM, factor=CONFIRM_PRICE, why=PRICES_CHANGE)


def trail_by(agent: str, tier: str | None, model: str | None) -> Line:
    """Who wrote a trail entry: the agent, with its tier and model when it has them."""
    produced_by = TRAIL_PRODUCED_BY_SEPARATOR.join(part for part in (tier, model) if part)
    return (
        filled(TRAIL_BY, agent=agent, produced_by=produced_by) if produced_by else text_line(agent)
    )


def trail_entry(kind: str, summary: str, *, reason: str | None, source: Site | None) -> Line:
    """What a trail entry says: its kind and summary, then its reason and its source."""
    template = (
        TRAIL_ENTRY
        + ("" if reason is None else TRAIL_REASON)
        + ("" if source is None else TRAIL_SOURCE)
    )
    return filled(template, kind=kind, summary=summary, reason=reason or "", source=source or "")


def sourced_lifespan(years: str, site: Site, stated_by: str | None) -> Line:
    """A sourced lifespan with its site, and who is speaking when it matters."""
    return filled(spoken(LIFESPAN_SOURCED, stated_by), years=years, site=site)


def typical_lifespan(
    kind: str, low: str, high: str, site: Site, stated_by: str | None
) -> FigureLine:
    """The lifespan typical for a kind of product: the kind its quote names, or the category."""
    return figure(spoken(TYPICAL_LIFESPAN, stated_by), type=kind, low=low, high=high, site=site)


def recurring_cost(
    amount: str, consumable: str, site: Site, *, converted_from: str | None, others_left_out: bool
) -> Line:
    """A recurring cost found, with whether it was converted and whether others were left out;
    the amount arrives formatted."""
    template = ", ".join(
        (
            RECURRING_COST,
            *((CONVERTED,) if converted_from is not None else ()),
            *((OTHER_CONSUMABLES,) if others_left_out else ()),
        )
    )
    return filled(
        template, amount=amount, consumable=consumable, site=site, currency=converted_from or ""
    )


def finding(
    template: str, summary: str, site: Site, *, rating: str | None, review_count: int | None
) -> FigureLine:
    """A test or an owner report with its site, then the source's overall rating as it states
    it, with its review count when owners gave it."""
    rated = "" if rating is None else FINDING_RATING
    counted = "" if rating is None or review_count is None else FINDING_REVIEW_COUNT
    count = "" if review_count is None else f"{review_count:,}"
    return figure(
        template + rated + counted, summary=summary, site=site, rating=rating or "", count=count
    )


def factor_value(
    template: str, factor: str, value: str, site: Site, stated_by: str | None
) -> FigureLine:
    """A factor value of an option in one of the templates that name a site, with who is
    speaking after the site when it matters."""
    return figure(spoken(template, stated_by), factor=factor, value=value, site=site)


def factor_not_confirmed(template: str, factor: str) -> FigureLine:
    """A factor value no source settled: a figure that is missing."""
    return figure(template, missing=True, factor=factor)


def source_line(url: str, stated_by: str | None) -> Line:
    """The line under a researched question: the site, linked to its source, and who is speaking
    when it matters."""
    return filled(SOURCE_STATED_BY.get(stated_by or "", SOURCE), site=site_link(url))


def savings(
    horizon_years: int,
    option: str,
    amount: str,
    baseline: str,
    *,
    costs_less: bool,
    rough: bool = False,
) -> Line:
    """One option set against the baseline; the amount arrives formatted and without a sign.
    `rough` when a lifespan behind it is a rough estimate."""
    template = (COSTS_LESS if costs_less else COSTS_MORE) + (ROUGH_SAVINGS if rough else "")
    return filled(
        template, horizon=str(horizon_years), option=option, amount=amount, baseline=baseline
    )


def evidence_summary(
    *,
    sourced: int,
    total: int,
    user_set: int,
    published: int,
    benchmark: int,
    model_estimate: int,
    missing: int,
) -> Line:
    """The evidence summary line from its counts; a part with a zero count is left out."""
    lifespans = EVIDENCE_LIFESPANS.format(n=sourced, total=total)
    if user_set:
        set_by_user = EVIDENCE_LIFESPANS_USER_SET.format(k=user_set)
        lifespans = f"{lifespans.removesuffix('.')}{set_by_user}."
    # The footprint sentence is one template; its parts are cut from it here.
    counts = {"a": published, "b": benchmark, "c": model_estimate, "d": missing}
    label, parts = EVIDENCE_FOOTPRINTS.removesuffix(".").split(": ")
    kept = [
        part.format(**counts)
        for part, count in zip(parts.split(", "), counts.values(), strict=True)
        if count
    ]
    if not kept:
        return text_line(lifespans)
    return text_line(f"{lifespans} {label}: {', '.join(kept)}.")


def co2e(
    low: str,
    high: str,
    tier: int,
    *,
    horizon: int | None,
    pieces: int | None,
    source: Site | None = None,
) -> Line:
    """An option's CO2e range with the label of its tier: over the horizon, or for one item when
    there is no horizon figure; a set names its pieces, and a figure of tier 1 or 2 its source.
    The ends arrive formatted."""
    template = CO2E_PER_ITEM if horizon is None else CO2E_OVER_HORIZON
    if pieces is not None:
        # The set is named before the bracket of the label, which ends both templates.
        template = template.replace(" ({label})", CO2E_SET + " ({label})")
    if source is not None:
        template = template.replace("{label}", CO2E_SOURCED)
    return filled(
        template,
        low=low,
        high=high,
        horizon=str(horizon),
        n=str(pieces),
        label=CO2E_LABELS[tier],
        source=source or "",
    )


def co2e_less(low: str, high: str, tier: int, horizon: int, for_scale: Line | None = None) -> Line:
    """How much less CO2e an option takes to make than the baseline, with a comparison for scale
    when it has one; the ends arrive formatted."""
    return filled(
        CO2E_LESS + ("" if for_scale is None else "{for_scale}"),
        low=low,
        high=high,
        horizon=str(horizon),
        label=CO2E_LABELS[tier],
        for_scale=for_scale or "",
    )


def co2e_for_scale(low: str, high: str, year: int, source_url: str) -> Line:
    """The same difference as kilometres in a car, its source a link; the ends arrive formatted."""
    return filled(
        CO2E_FOR_SCALE,
        low=low,
        high=high,
        year=str(year),
        source=LinkPart(text=CAR_FIGURE_SOURCE, url=source_url),
    )


def co2e_unavailable(name: str | None) -> str:
    """The warning for an option with no CO2e estimate, or for an estimate that did not run."""
    if name is None:
        return CO2E_UNAVAILABLE["report"]
    return CO2E_UNAVAILABLE["option"].format(name=name)
