"""What code does with a model reply. These prove nothing about how the model classifies."""

import asyncio
from decimal import Decimal

import pytest

from fakes import extraction, fake_chat
from shopper.agents.supervisor.agent import (
    MAX_INPUT_CHARACTERS,
    SUPERVISOR_PROMPT,
    InputTooLongError,
    ModelCallError,
    ParsedRequest,
    parse_request,
    read_product_name,
)
from shopper.llm import ChatError, ChatTimeoutError
from shopper.state import Agent, Request, Scope, TrailKind, WarningCode

SMALL_MODEL = "nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B"


def parse(text: str, *replies: str | Exception) -> ParsedRequest:
    chat, _ = fake_chat(replies)
    return asyncio.run(parse_request(text, chat))


def test_a_need_with_a_budget_becomes_a_request() -> None:
    text = "I need a new frying pan, budget 50 euro"
    chat, requests = fake_chat([extraction("frying pan", "tuned", "50 euro", 50)])

    parsed = asyncio.run(parse_request(text, chat))

    assert parsed.request.original_text == text
    assert parsed.request.category == "frying pan"
    assert parsed.request.scope is Scope.TUNED
    assert parsed.request.budget == Decimal("50")
    assert parsed.request.product_url is None
    assert parsed.warnings == ()
    assert requests[0].temperature == 0
    assert requests[0].model == SMALL_MODEL
    assert requests[0].messages[0] == {"role": "system", "content": SUPERVISOR_PROMPT}
    assert requests[0].messages[-1] == {"role": "user", "content": text}


def test_the_tier_can_be_set() -> None:
    chat, requests = fake_chat([extraction()])

    parsed = asyncio.run(parse_request("a frying pan", chat, "medium"))

    assert requests[0].model == "nvidia/nemotron-3-super-120b-a12b"
    assert parsed.trail[0].model_tier == "medium"


# --- The trail ---


def test_each_parse_writes_one_decided_entry_with_the_tier_and_model() -> None:
    parsed = parse("a frying pan, budget 50 euro", extraction("frying pan", "tuned", "50 euro", 50))

    (entry,) = parsed.trail
    assert entry.agent is Agent.SUPERVISOR
    assert entry.kind is TrailKind.DECIDED
    assert entry.summary == "Understood as: frying pan; scope tuned; budget €50"
    assert entry.model_tier == "small"
    assert entry.model == SMALL_MODEL


def test_a_dropped_budget_writes_an_excluded_entry_with_the_code_and_phrase() -> None:
    parsed = parse("a frying pan, budget 5o euro", extraction("frying pan", "tuned", "5o euro"))

    understood, excluded = parsed.trail
    assert understood.summary == "Understood as: frying pan; scope tuned; no budget"
    assert excluded.kind is TrailKind.EXCLUDED
    assert excluded.reason == "budget_unreadable"
    assert "5o euro" in excluded.summary


def test_a_range_is_read_as_its_higher_amount_and_the_trail_notes_it() -> None:
    parsed = parse(
        "een koekenpan tussen 30 en 50 euro",
        extraction("frying pan", "tuned", "tussen 30 en 50 euro", 50),
    )

    assert parsed.request.budget == Decimal("50")
    assert parsed.warnings == ()
    assert [entry.kind for entry in parsed.trail] == [TrailKind.DECIDED, TrailKind.DECIDED]
    assert "tussen 30 en 50 euro" in parsed.trail[1].summary


# --- Finding the phrase: the four steps ---


def test_a_phrase_is_widened_by_the_currency_marker_beside_it() -> None:
    parsed = parse("a frying pan for 40 pounds", extraction("frying pan", "tuned", "40", 40))

    assert parsed.request.budget is None
    (warning,) = parsed.warnings
    assert warning.code is WarningCode.BUDGET_OTHER_CURRENCY
    assert warning.message == (
        'This app works in euro only, so "40 pounds" is not applied as a budget. '
        "To set one, start again with an amount in euro."
    )


def test_a_phrase_inside_a_number_is_widened_to_the_whole_token() -> None:
    parsed = parse("a drill, max €150", extraction("drill", "tuned", "50", 150))

    assert parsed.request.budget == Decimal("150")
    assert parsed.warnings == ()


def test_an_amount_the_model_and_code_read_differently_is_unreadable() -> None:
    parsed = parse("a drill, max €150", extraction("drill", "tuned", "50", 50))

    assert parsed.request.budget is None
    (warning,) = parsed.warnings
    assert warning.code is WarningCode.BUDGET_UNREADABLE
    assert '"€150"' in warning.message


def test_a_phrase_that_holds_something_else_too_is_unreadable() -> None:
    parsed = parse(
        "28 cm pan under 20 euro",
        extraction("frying pan", "tuned", "28 cm pan under 20 euro", 20),
    )

    assert parsed.request.budget is None
    assert [warning.code for warning in parsed.warnings] == [WarningCode.BUDGET_UNREADABLE]


def test_a_phrase_is_found_whatever_its_case_and_spacing() -> None:
    parsed = parse(
        "A frying pan, BUDGET 50  Euro please",
        extraction("frying pan", "tuned", "budget 50 euro", 50),
    )

    assert parsed.request.budget == Decimal("50")


def test_the_warning_quotes_the_input_not_the_model() -> None:
    parsed = parse("a frying pan, Budget  5O Euro", extraction("frying pan", "tuned", "5o euro"))

    (warning,) = parsed.warnings
    assert '"5O Euro"' in warning.message


def test_a_phrase_that_is_not_in_the_input_means_no_budget_and_no_warning() -> None:
    parsed = parse("a frying pan, not too pricey", extraction("frying pan", "tuned", "50 euro", 50))

    assert parsed.request.budget is None
    assert parsed.warnings == ()
    _, repair = parsed.trail
    assert repair.kind is TrailKind.DECIDED
    assert "50 euro" in repair.summary
    assert repair.reason == "the budget phrase is not in the input"


@pytest.mark.parametrize(
    ("text", "phrase"),
    [
        ("a pan, budget 40–50 euro", "40-50 euro"),
        ("a pan, BUDGET  50 euro, no more", "budget 50 euro."),
        ("a pan, budget “50 euro”", 'budget "50 euro"'),
    ],
)
def test_a_budget_phrase_is_found_whatever_its_case_spacing_dashes_quote_marks_and_edges(
    text: str, phrase: str
) -> None:
    parsed = parse(text, extraction("frying pan", "tuned", phrase, 50))

    assert parsed.request.budget == Decimal("50")


def test_no_phrase_means_no_budget_and_code_does_not_look_for_one() -> None:
    parsed = parse("my €30 pan broke, I need a new one", extraction("frying pan"))

    assert parsed.request.budget is None
    assert parsed.warnings == ()
    assert len(parsed.trail) == 1


@pytest.mark.parametrize(
    ("text", "phrase", "amount", "code", "quoted"),
    [
        ("a pan, budget 5o euro", "5o euro", None, WarningCode.BUDGET_UNREADABLE, "5o euro"),
        ("a pan, budget 0", "0", 0, WarningCode.BUDGET_NOT_POSITIVE, "0"),
        ("a pan, budget -50", "50", -50, WarningCode.BUDGET_NOT_POSITIVE, "-50"),
        ("a pan, budget £40", "£40", 40, WarningCode.BUDGET_OTHER_CURRENCY, "£40"),
        ("a pan, budget £0", "0", 0, WarningCode.BUDGET_OTHER_CURRENCY, "£0"),
        ("a pan, 40 Fr. at most", "40", 40, WarningCode.BUDGET_OTHER_CURRENCY, "40 Fr."),
    ],
)
def test_a_budget_that_cannot_be_used_is_left_missing_with_its_warning(
    text: str, phrase: str, amount: float | None, code: WarningCode, quoted: str
) -> None:
    parsed = parse(text, extraction("frying pan", "tuned", phrase, amount))

    assert parsed.request.budget is None
    assert parsed.request.scope is Scope.TUNED
    (warning,) = parsed.warnings
    assert warning.code is code
    assert f'"{quoted}"' in warning.message


def test_a_full_stop_after_the_marker_is_not_quoted() -> None:
    parsed = parse("A pan for 5o euro.", extraction("frying pan", "tuned", "5o", None))

    (warning,) = parsed.warnings
    assert '"5o euro"' in warning.message


# --- Words on no list: the model's judgement of the currency ---


def test_a_currency_on_no_list_is_dropped_on_the_models_judgement_and_the_trail_says_so() -> None:
    parsed = parse(
        "a frying pan, budget 10 dolla",
        extraction("frying pan", "tuned", "10 dolla", 10, "other"),
    )

    assert parsed.request.budget is None
    (warning,) = parsed.warnings
    assert warning.code is WarningCode.BUDGET_OTHER_CURRENCY
    assert warning.message == (
        'This app works in euro only, so "10 dolla" is not applied as a budget. '
        "To set one, start again with an amount in euro."
    )
    excluded = parsed.trail[1]
    assert excluded.kind is TrailKind.EXCLUDED
    assert excluded.reason == "budget_other_currency (judged by the model)"


def test_a_listed_currency_is_dropped_by_code_and_the_trail_does_not_name_the_model() -> None:
    parsed = parse(
        "a frying pan for 40 pounds", extraction("frying pan", "tuned", "40 pounds", 40, "other")
    )

    assert parsed.trail[1].reason == "budget_other_currency"


@pytest.mark.parametrize("currency", ["eur", "none_stated", None])
def test_a_word_after_the_amount_that_is_no_currency_leaves_a_euro_budget(
    currency: str | None,
) -> None:
    parsed = parse("a frying pan, 50 max", extraction("frying pan", "tuned", "50", 50, currency))

    assert parsed.request.budget == Decimal("50")
    assert parsed.warnings == ()


def test_a_euro_marker_is_read_as_euros_whatever_the_model_judged() -> None:
    parsed = parse(
        "a frying pan, budget 50 euro", extraction("frying pan", "tuned", "50", 50, "other")
    )

    assert parsed.request.budget == Decimal("50")
    assert parsed.warnings == ()


def test_no_budget_is_read_for_a_request_that_does_not_run() -> None:
    parsed = parse("a pizza for £10", extraction("pizza", "not_a_product", "£10", 10))

    assert parsed.request.scope is Scope.NOT_A_PRODUCT
    assert parsed.request.category == "pizza"
    assert parsed.request.budget is None
    assert parsed.warnings == ()


# --- Category and repairs ---


def test_the_category_is_trimmed_lower_cased_and_its_whitespace_collapsed() -> None:
    parsed = parse("a pan", extraction("  Frying \n Pan "))

    assert parsed.request.category == "frying pan"


@pytest.mark.parametrize("scope", ["unclear", "several_products"])
def test_a_category_on_a_reply_whose_scope_carries_none_is_dropped(scope: str) -> None:
    parsed = parse("a pan and a kettle", extraction("frying pan", scope))

    assert parsed.request.scope.value == scope
    assert parsed.request.category is None
    _, repair = parsed.trail
    assert repair.kind is TrailKind.DECIDED
    assert "frying pan" in repair.summary
    assert repair.model == SMALL_MODEL


@pytest.mark.parametrize("category", ["3d printer", "4k monitor", "mp3 player"])
def test_a_category_with_one_digit_inside_a_word_is_kept(category: str) -> None:
    parsed = parse("one of those", extraction(category, "general"))

    assert parsed.request.category == category
    assert parsed.request.scope is Scope.GENERAL
    assert len(parsed.trail) == 1


@pytest.mark.parametrize(
    "category",
    [
        "a very large cast iron frying pan",
        "frying pan 28 cm",
        "iphone 15",
        "360 camera",
        "28cm frying pan",
        "65w charger",
        "wh1000xm4 headphones",
        "galaxy s23",
        "2-in-1 laptop",
        "3d 4k printer",
    ],
)
def test_a_category_that_fails_the_form_check_twice_is_dropped(category: str) -> None:
    link = "https://shop.example/p/123"
    parsed = parse(link, extraction(category, "tuned"), extraction(category, "tuned"))

    assert parsed.request.category is None
    assert parsed.request.scope is Scope.TUNED
    assert parsed.request.product_url == link
    _, repair = parsed.trail
    assert repair.kind is TrailKind.DECIDED
    assert repair.summary == f'Dropped the category "{category}"'
    assert repair.reason == (
        "a category has at most 4 words and at most one digit, inside a word; "
        f'the second try gave "{category}"'
    )


def test_a_category_that_passes_the_form_check_makes_one_model_call() -> None:
    chat, requests = fake_chat([extraction("frying pan")])

    parsed = asyncio.run(parse_request("frying pan 28 cm", chat))

    assert parsed.request.category == "frying pan"
    assert len(requests) == 1


def test_a_category_on_a_scope_that_carries_none_gets_no_second_try() -> None:
    chat, requests = fake_chat([extraction("frying pan 28 cm", "several_products")])

    parsed = asyncio.run(parse_request("a frying pan 28 cm and a kettle", chat))

    assert parsed.request.category is None
    assert len(requests) == 1


def test_only_the_category_of_the_second_try_is_used() -> None:
    parsed = parse(
        "frying pan 28 cm, budget 50 euro",
        extraction("frying pan 28 cm", "tuned", "50 euro", 50),
        extraction("frying pan", "general", "28 cm", 28),
    )

    assert parsed.request.category == "frying pan"
    assert parsed.request.scope is Scope.TUNED
    assert parsed.request.budget == Decimal("50")
    assert parsed.warnings == ()


def test_a_second_try_that_gives_no_category_drops_the_first() -> None:
    link = "https://shop.example/p/123"
    parsed = parse(link, extraction("frying pan 28 cm", "tuned"), extraction(None, "unclear"))

    assert parsed.request.category is None
    assert parsed.request.scope is Scope.TUNED
    _, repair = parsed.trail
    assert repair.summary == 'Dropped the category "frying pan 28 cm"'
    assert repair.reason == (
        "a category has at most 4 words and at most one digit, inside a word; "
        "the second try gave no category"
    )


@pytest.mark.parametrize(
    ("second_replies", "kind"),
    [
        ([ChatTimeoutError("no answer within 60 s")], "timeout"),
        (["not json", "still not json"], "invalid_output"),
    ],
)
def test_a_second_try_whose_model_call_fails_raises_and_there_is_no_request(
    second_replies: list[str | Exception], kind: str
) -> None:
    chat, _ = fake_chat([extraction("frying pan 28 cm", "tuned"), *second_replies])

    with pytest.raises(ModelCallError) as raised:
        asyncio.run(parse_request("frying pan 28 cm", chat))

    assert raised.value.failure.kind == kind


def test_a_category_that_fails_the_form_check_gets_a_second_try() -> None:
    text = "frying pan 28 cm, budget 50 euro"
    chat, requests = fake_chat(
        [extraction("frying pan 28 cm", "tuned", "50 euro", 50), extraction("frying pan")]
    )

    parsed = asyncio.run(parse_request(text, chat))

    assert parsed.request.category == "frying pan"
    assert parsed.request.scope is Scope.TUNED
    assert parsed.request.budget == Decimal("50")
    understood, second_try = parsed.trail
    assert understood.summary == "Understood as: frying pan; scope tuned; budget €50"
    assert second_try.kind is TrailKind.DECIDED
    assert second_try.summary == (
        'Asked again for the category: "frying pan 28 cm" became "frying pan"'
    )
    assert second_try.reason == (
        "a category has at most 4 words and at most one digit, inside a word"
    )
    assert second_try.model == SMALL_MODEL
    first, second = requests
    assert second.model == first.model
    assert second.temperature == 0
    assert second.messages[-1] == {"role": "user", "content": text}
    correction = second.messages[0]["content"].removeprefix(SUPERVISOR_PROMPT)
    assert '"frying pan 28 cm"' in correction
    assert "at most 4 words and at most one digit, inside a word" in correction


def test_a_scope_that_runs_with_no_category_and_no_link_becomes_unclear() -> None:
    parsed = parse("something nice, budget 50 euro", extraction(None, "general", "50 euro", 50))

    assert parsed.request.scope is Scope.UNCLEAR
    assert parsed.request.budget is None
    assert parsed.warnings == ()
    understood, repair = parsed.trail
    assert understood.summary == "Understood as: no category; scope unclear; no budget"
    assert repair.kind is TrailKind.DECIDED
    assert "general" in repair.summary


def test_a_category_dropped_after_two_tries_with_no_link_leaves_the_request_unclear() -> None:
    chat, requests = fake_chat(
        [extraction("frying pan 28 cm", "tuned"), extraction("frying pan 28cm", "tuned")]
    )

    parsed = asyncio.run(parse_request("frying pan 28 cm", chat))

    assert parsed.request.category is None
    assert parsed.request.scope is Scope.UNCLEAR
    assert len(requests) == 2
    assert len(parsed.trail) == 3


def test_a_declined_request_may_have_no_category() -> None:
    parsed = parse("something to eat", extraction(None, "not_a_product"))

    assert parsed.request.scope is Scope.NOT_A_PRODUCT
    assert len(parsed.trail) == 1


# --- Input the model never sees ---


@pytest.mark.parametrize("text", ["", "   \n\t "])
def test_empty_input_is_unclear_without_a_model_call(text: str) -> None:
    chat, requests = fake_chat([])

    parsed = asyncio.run(parse_request(text, chat))

    assert requests == []
    assert parsed.request.scope is Scope.UNCLEAR
    assert parsed.request.original_text == text
    (entry,) = parsed.trail
    assert entry.kind is TrailKind.DECIDED
    assert entry.reason == "the input is empty"
    assert entry.model is None


def test_two_different_links_are_several_products_without_a_model_call() -> None:
    chat, requests = fake_chat([])

    parsed = asyncio.run(
        parse_request("https://shop.example/pan-a or https://shop.example/pan-b?", chat)
    )

    assert requests == []
    assert parsed.request.scope is Scope.SEVERAL_PRODUCTS
    assert parsed.request.product_url is None
    (entry,) = parsed.trail
    assert entry.reason == "the input holds more than one link"


def test_the_same_link_twice_is_one_link_and_the_model_sees_it() -> None:
    text = "https://shop.example/pan-a, again: https://shop.example/pan-a."
    chat, requests = fake_chat([extraction("frying pan")])

    parsed = asyncio.run(parse_request(text, chat))

    assert len(requests) == 1
    assert requests[0].messages[-1]["content"] == text
    assert parsed.request.scope is Scope.TUNED
    assert parsed.request.product_url == "https://shop.example/pan-a"


def test_punctuation_after_a_link_is_not_part_of_it() -> None:
    parsed = parse("What about (http://shop.example/pan?id=1&x=2)!", extraction("frying pan"))

    assert parsed.request.product_url == "http://shop.example/pan?id=1&x=2"


def test_input_over_the_limit_is_refused_before_any_model_call() -> None:
    chat, requests = fake_chat([])

    with pytest.raises(InputTooLongError):
        asyncio.run(parse_request("a" * (MAX_INPUT_CHARACTERS + 1), chat))

    assert requests == []
    assert MAX_INPUT_CHARACTERS == 2000


def test_input_at_the_limit_is_read() -> None:
    parsed = parse("a frying pan".ljust(MAX_INPUT_CHARACTERS, "."), extraction())

    assert parsed.request.scope is Scope.TUNED


# --- When the model call fails ---

# A reply without budget_currency: the field is required, like the other four.
FOUR_FIELDS_ONLY = (
    '{"category": "frying pan", "scope": "tuned", "budget_phrase": null, "budget_amount": null}'
)


@pytest.mark.parametrize(
    ("replies", "kind"),
    [
        ([ChatTimeoutError("no answer within 60 s")], "timeout"),
        ([ChatError("503 unavailable")], "error"),
        (["not json", "still not json"], "invalid_output"),
        (['{"category": null, "scope": "furniture"}'] * 2, "invalid_output"),
        ([FOUR_FIELDS_ONLY] * 2, "invalid_output"),
        ([extraction("frying pan", "tuned", "50", 50, "dollars")] * 2, "invalid_output"),
    ],
)
def test_a_failed_model_call_raises_and_there_is_no_request(
    replies: list[str | Exception], kind: str
) -> None:
    chat, _ = fake_chat(replies)

    with pytest.raises(ModelCallError) as raised:
        asyncio.run(parse_request("a frying pan", chat))

    assert raised.value.failure.kind == kind


# --- The product name read from a pasted link ---

LINK_ONLY = Request(
    original_text="https://shop.example/p/123 budget 60 euro",
    product_url="https://shop.example/p/123",
    budget=Decimal("60"),
    scope=Scope.GENERAL,
)
PAN_NAME = "De Buyer Mineral B koekenpan 28 cm"


def named(*replies: str | Exception) -> ParsedRequest:
    chat, _ = fake_chat(replies)
    return asyncio.run(read_product_name(LINK_ONLY, PAN_NAME, chat))


def test_the_product_name_gives_the_category_and_scope_and_keeps_the_rest() -> None:
    chat, requests = fake_chat([extraction("frying pan", "tuned")])

    parsed = asyncio.run(read_product_name(LINK_ONLY, PAN_NAME, chat))

    assert parsed.request == LINK_ONLY.model_copy(
        update={"category": "frying pan", "scope": Scope.TUNED}
    )
    assert requests[0].messages[-1] == {"role": "user", "content": PAN_NAME}
    assert requests[0].model == SMALL_MODEL
    (entry,) = parsed.trail
    assert entry.agent is Agent.SUPERVISOR
    assert entry.summary == (
        f'Named the category from the product "{PAN_NAME}": frying pan; scope tuned'
    )
    assert entry.model_tier == "small"


def test_a_product_name_that_is_not_a_product_declines_the_request() -> None:
    parsed = named(extraction("car", "not_a_product"))

    assert parsed.request.scope is Scope.NOT_A_PRODUCT
    assert parsed.request.category == "car"


def test_a_category_from_the_name_that_fails_the_form_check_gets_its_second_try() -> None:
    parsed = named(extraction("frying pan 28 cm", "tuned"), extraction("frying pan", "tuned"))

    assert parsed.request.category == "frying pan"
    assert [entry.summary for entry in parsed.trail][1] == (
        'Asked again for the category: "frying pan 28 cm" became "frying pan"'
    )


def test_a_name_that_gives_no_category_leaves_the_request_running_without_one() -> None:
    parsed = named(extraction(None, "general"))

    assert parsed.request.category is None
    assert parsed.request.scope is Scope.GENERAL


def test_a_failed_call_for_the_product_name_raises() -> None:
    with pytest.raises(ModelCallError):
        named(ChatError("down"))
