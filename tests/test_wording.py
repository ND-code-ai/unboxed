import re
from datetime import date
from pathlib import Path

import pytest

from shopper import wording
from shopper.wording import (
    ConfidencePart,
    ControlPart,
    FigureLine,
    Line,
    LinkPart,
    TextPart,
    plain_text,
)

# The page's copies of an API code's words (web/lib/wording.ts), by the code they copy.
PAGE_COPIES = {
    "RUN_STOPPED": "run_stopped",
    "UNREACHABLE": "internal_error",
    "REPLY_TOO_LONG": "reply_too_long",
}
PAGE_WORDING = Path(__file__).parent.parent / "web" / "lib" / "wording.ts"


def text_line(text: str) -> Line:
    return Line(parts=(TextPart(text=text),))


def test_the_page_copies_of_an_api_code_have_its_words() -> None:
    constants = dict(
        re.findall(r'export const (\w+) =\s*"([^"]*)";', PAGE_WORDING.read_text(encoding="utf-8"))
    )
    for constant, code in PAGE_COPIES.items():
        assert constants[constant] == wording.ERRORS[code]


def test_a_decline_quotes_the_category_when_it_was_understood() -> None:
    # Quoted, a singular category reads right too ("battery", task 1.10).
    assert wording.request_not_run("not_a_product", "battery") == text_line(
        "This app covers durable products such as cookware, appliances and tools. "
        """It can't help with "battery"."""
    )
    assert wording.request_not_run("not_a_product", None) == text_line(
        "This app covers durable products such as cookware, appliances and tools."
    )


def test_an_unclear_request_with_a_link_asks_for_the_product_name() -> None:
    assert wording.request_not_run("unclear", None, has_link=True) == text_line(
        "We couldn't read the product at your link. "
        "Name the product to start, for example 'a frying pan, budget €50'."
    )
    assert wording.request_not_run("unclear", None) == text_line(wording.UNCLEAR)


def test_a_scope_that_runs_has_no_message() -> None:
    assert wording.request_not_run("tuned", "frying pan") is None


def test_too_many_sessions_says_when_to_try_again() -> None:
    assert wording.too_many_sessions(12) == (
        "Many sessions were started from this connection in the last hour, so no new one was "
        "started. Try again in 12 minutes."
    )
    assert wording.too_many_sessions(1).endswith("Try again in 1 minute.")


def test_the_understood_line_ends_in_the_edit_control() -> None:
    assert wording.understood("frying pan", "€50") == Line(
        parts=(TextPart(text="Looking for: frying pan · Budget: €50"), ControlPart(key="edit"))
    )


def test_the_understood_line_names_what_is_missing() -> None:
    assert wording.understood(None, None) == Line(
        parts=(
            TextPart(text="Looking for: the product at your link · Budget: none given"),
            ControlPart(key="edit"),
        )
    )


def test_the_box_label_is_the_category_and_the_budget_alone() -> None:
    assert wording.box_label("frying pan", "€50") == Line(
        parts=(TextPart(text="frying pan · €50"),)
    )


def test_the_box_label_of_a_request_with_no_budget_is_its_category() -> None:
    assert wording.box_label("kettle", None) == Line(parts=(TextPart(text="kettle"),))


def test_the_box_label_names_a_product_known_only_by_its_link() -> None:
    assert wording.box_label(None, "€50") == Line(
        parts=(TextPart(text="the product at your link · €50"),)
    )


def test_a_line_as_the_terminal_prints_it_has_its_words_and_no_control() -> None:
    line = Line(
        parts=(
            TextPart(text="Source: "),
            LinkPart(text="example.org", url="https://www.example.org/guide"),
            ControlPart(key="edit"),
        )
    )

    assert plain_text(line) == "Source: example.org"


def test_a_reply_that_asks_to_change_the_request_names_what_the_results_are_still_for() -> None:
    assert wording.reply_cannot_change_request("frying pan", "€50") == text_line(
        "A reply can't change what you're looking for or the budget, so the results are still "
        "for frying pan, budget €50. To change either, press Edit."
    )
    assert wording.reply_cannot_change_request(None, None) == text_line(
        "A reply can't change what you're looking for or the budget, so the results are still "
        "for the product at your link, budget none given. To change either, press Edit."
    )


def in_thread(
    *,
    asks_to_change_request: bool = False,
    changed_an_answer: bool = False,
    unanswered: bool = False,
) -> str | None:
    line = wording.reply_in_thread(
        "frying pan",
        "€50",
        asks_to_change_request=asks_to_change_request,
        changed_an_answer=changed_an_answer,
        unanswered=unanswered,
    )
    return None if line is None else plain_text(line)


def test_a_reply_that_changed_an_answer_has_no_line_in_the_thread() -> None:
    assert in_thread(changed_an_answer=True) is None


def test_a_reply_that_changed_no_answer_says_so() -> None:
    assert in_thread() == "Nothing you wrote changed an answer or added a requirement."


def test_a_reply_that_asks_to_change_the_request_says_so_whatever_else_it_did() -> None:
    expected = (
        "A reply can't change what you're looking for or the budget, so the results are still "
        "for frying pan, budget €50. To change either, press Edit."
    )
    assert in_thread(asks_to_change_request=True) == expected
    assert in_thread(asks_to_change_request=True, changed_an_answer=True) == expected


def test_a_reply_that_ended_unanswered_has_a_line_only_when_it_asked_to_change_the_request() -> (
    None
):
    assert in_thread(unanswered=True) is None
    assert in_thread(unanswered=True, asks_to_change_request=True) == (
        "A reply can't change what you're looking for or the budget. To change either, press Edit."
    )


def test_an_unanswered_reply_to_no_questions_asks_for_a_requirement() -> None:
    assert wording.reply_unanswered(has_questions=True) == (
        "Nothing in your reply answered the open questions, so nothing was run. "
        "Answer in your own words or with the choices."
    )
    assert wording.reply_unanswered(has_questions=False) == (
        "Nothing in your reply added a requirement, so nothing was run. "
        "Add one in your own words, or clear your reply and press Show my options."
    )


def test_a_line_from_the_reply_says_so() -> None:
    assert wording.stated_answer(
        "Hob compatibility", "Induction", "on induction", from_reply=True
    ) == text_line('From your reply: Hob compatibility: Induction ("on induction")')
    assert wording.stated_own("oven safe", from_reply=True) == text_line(
        'From your reply: "oven safe"'
    )
    assert wording.stated_usage("About once a week", 50, "weekly", from_reply=True) == text_line(
        'From your reply: About once a week, 50 uses a year ("weekly")'
    )
    assert wording.reply_not_sure("Hob compatibility", "no idea which hob") == text_line(
        'From your reply: Hob compatibility: not sure ("no idea which hob")'
    )


def test_a_typical_yearly_cost_links_its_site_and_labels_a_conversion() -> None:
    rtings = LinkPart(text="rtings.com", url="https://www.rtings.com/f")
    assert wording.typical_cost("Filters", "€20", "https://www.rtings.com/f", None) == Line(
        parts=(TextPart(text="Filters: typically €20 a year ("), rtings, TextPart(text=")."))
    )
    assert wording.typical_cost("Filters", "€20", "https://www.rtings.com/f", "GBP") == Line(
        parts=(
            TextPart(text="Filters: typically €20 a year ("),
            rtings,
            TextPart(text="), converted from GBP at a fixed rate."),
        )
    )


@pytest.mark.parametrize(
    ("url", "site"),
    [
        ("https://www.consumentenbond.nl/waterkoker/kopen", "consumentenbond.nl"),
        ("https://Example.org/guide?page=2", "example.org"),
        ("http://shop.example.co.uk:8080/kettles", "shop.example.co.uk"),
    ],
)
def test_the_site_name_is_the_host_of_a_url_without_www(url: str, site: str) -> None:
    assert wording.site_name(url) == site


@pytest.mark.parametrize(
    ("stated_by", "after"),
    [
        (None, ()),
        ("tester", ()),
        ("owner", ()),
        ("manufacturer", (TextPart(text=" (the manufacturer states)"),)),
        ("seller", (TextPart(text=" (the seller states)"),)),
    ],
)
def test_a_source_line_links_its_site_and_says_when_the_maker_or_a_seller_is_speaking(
    stated_by: str | None, after: tuple[TextPart, ...]
) -> None:
    assert wording.source_line("https://www.example.org/guide", stated_by) == Line(
        parts=(
            TextPart(text="Source: "),
            LinkPart(text="example.org", url="https://www.example.org/guide"),
            *after,
        )
    )


def test_each_no_options_wording_names_the_category() -> None:
    assert wording.no_options_found("nothing_found", "kettle") == (
        "We couldn't find a kettle with a price in euro, so there are no options to compare."
    )
    assert wording.no_options_found("searches_failed", "kettle") == (
        "The search for kettle options didn't work just now, so there are no options to compare. "
        "Try again in a moment."
    )
    assert wording.no_options_found("none_met_the_answers", "kettle", 5) == (
        "We found 5 products for kettle, but none met your answers; the reasons are in the "
        "evidence trail."
    )


BOL = LinkPart(text="bol.com", url="https://www.bol.com/nl/nl/p/fellow-corvo-ekg/1")
RTINGS = LinkPart(text="rtings.com", url="https://www.rtings.com/pan")
AI_ESTIMATE = ConfidencePart(text="AI synthetic estimate", basis="estimate")


def test_a_price_says_the_site_and_the_day_it_was_seen_with_the_month_in_english() -> None:
    assert wording.price_seen_at(BOL, None, date(2026, 3, 5)) == Line(
        parts=(TextPart(text="price seen at "), BOL, TextPart(text=" on 5 March 2026"))
    )


def test_a_price_on_a_comparison_site_names_the_shop_as_words_and_links_the_site() -> None:
    assert plain_text(wording.price_seen_at("beslist.nl", "Kookexpert.nl", date(2026, 10, 17))) == (
        "price seen at Kookexpert.nl via beslist.nl on 17 October 2026"
    )


def test_a_savings_line_says_less_or_more() -> None:
    assert wording.savings(10, "Carbon steel pan", "€60", "Non-stick pan", costs_less=True) == (
        text_line("Over 10 years: Carbon steel pan costs €60 less than Non-stick pan.")
    )
    assert wording.savings(10, "Cast iron pan", "€15", "Non-stick pan", costs_less=False) == (
        text_line("Over 10 years: Cast iron pan costs €15 more than Non-stick pan.")
    )


def test_a_savings_line_on_a_rough_estimate_says_so() -> None:
    assert wording.savings(
        10, "Carbon steel pan", "€60", "Non-stick pan", costs_less=True, rough=True
    ) == text_line(
        "Over 10 years: Carbon steel pan costs €60 less than Non-stick pan. A lifespan behind "
        "this is a rough estimate."
    )


def test_the_evidence_summary_leaves_out_every_part_with_a_zero_count() -> None:
    # The line on the stub agents, as docs/terminal_app.md gives it.
    assert wording.evidence_summary(
        sourced=0, total=2, user_set=0, published=0, benchmark=0, model_estimate=0, missing=2
    ) == text_line("Lifespan sourced for 0 of 2 options. CO2e to make: not found for 2.")


def test_the_evidence_summary_names_every_count_above_zero() -> None:
    assert wording.evidence_summary(
        sourced=2, total=4, user_set=1, published=1, benchmark=1, model_estimate=1, missing=1
    ) == text_line(
        "Lifespan sourced for 2 of 4 options, set by you for 1. CO2e to make: published for 1, "
        "benchmark estimate for 1, AI synthetic estimate for 1, not found for 1."
    )


def test_a_stated_usage_line_formats_its_uses_per_year() -> None:
    assert wording.stated_usage("Several times a day", 1000, "three times a day") == text_line(
        'From your request: Several times a day, 1,000 uses a year ("three times a day")'
    )


def test_a_co2e_line_carries_the_label_of_its_tier_as_a_confidence_part() -> None:
    assert wording.co2e("12", "25", 3, horizon=10, pieces=None) == Line(
        parts=(
            TextPart(text="12 to 25 kg CO2e to make, over 10 years ("),
            AI_ESTIMATE,
            TextPart(text=")"),
        )
    )


def test_a_co2e_line_of_tier_1_or_2_names_its_source_after_the_label() -> None:
    assert wording.co2e("4", "9", 2, horizon=None, pieces=None, source="pans-dataset, row 12") == (
        Line(
            parts=(
                TextPart(text="4 to 9 kg CO2e to make ("),
                ConfidencePart(text="benchmark estimate", basis="benchmark"),
                TextPart(text=", pans-dataset, row 12)"),
            )
        )
    )
    published = wording.co2e("4", "9", 1, horizon=None, pieces=None, source=RTINGS)
    assert published.parts[1:] == (
        ConfidencePart(text="published figure", basis="published"),
        TextPart(text=", "),
        RTINGS,
        TextPart(text=")"),
    )


def test_a_co2e_line_of_a_set_names_its_pieces_before_the_label() -> None:
    assert plain_text(wording.co2e("12", "25", 3, horizon=10, pieces=3)) == (
        "12 to 25 kg CO2e to make, over 10 years, for the set of 3 (AI synthetic estimate)"
    )
    assert plain_text(wording.co2e("4", "9", 1, horizon=None, pieces=5, source="d")) == (
        "4 to 9 kg CO2e to make, for the set of 5 (published figure, d)"
    )


def test_less_co2e_than_the_baseline_carries_the_label_of_its_tier() -> None:
    assert wording.co2e_less("10", "40", 3, 10) == Line(
        parts=(
            TextPart(text="About 10 to 40 kg CO2e less to make over 10 years ("),
            AI_ESTIMATE,
            TextPart(text=")"),
        )
    )


def test_the_comparison_for_scale_follows_the_difference_and_links_its_source() -> None:
    scale = wording.co2e_for_scale("100", "320", 2025, "https://www.eea.europa.eu/x")

    line = wording.co2e_less("10", "30", 3, 10, for_scale=scale)

    assert line.parts[1] == AI_ESTIMATE
    assert line.parts[3] == LinkPart(text="EEA", url="https://www.eea.europa.eu/x")
    assert wording.plain_text(line).endswith(
        "; for scale, about 100 to 320 km in an average new car in Europe, electric cars included "
        "(car figure: EEA, 2025, tailpipe test; real drives emit more)"
    )


def test_a_figure_is_its_template_split_at_its_first_colon() -> None:
    figure = wording.figure(wording.FACTOR_MEETS, factor="Lid", value="glass: tempered", site="x")

    assert figure == FigureLine(
        label=text_line("Lid"), value=text_line("glass: tempered (x)"), missing=False
    )


@pytest.mark.parametrize(
    ("stated_by", "after"),
    [(None, ")"), ("tester", ")"), ("seller", ") (the seller states)")],
)
def test_a_factor_value_says_who_is_speaking_after_its_linked_site(
    stated_by: str | None, after: str
) -> None:
    figure = wording.factor_value(
        wording.FACTOR_MEETS, "Hob compatibility", "works on induction", RTINGS, stated_by
    )

    assert figure.label == text_line("Hob compatibility")
    assert figure.value == Line(
        parts=(TextPart(text="works on induction ("), RTINGS, TextPart(text=after))
    )


def test_a_care_value_the_user_would_avoid_says_who_is_speaking_before_its_sentence() -> None:
    figure = wording.factor_value(
        wording.FACTOR_CARE_NEEDED, "Care", "hand wash only", "fonq.nl", "seller"
    )

    assert plain_text(figure.value) == (
        "hand wash only (fonq.nl) (the seller states). "
        "You said you'd rather avoid this; the lifespan shown assumes it is done."
    )


def test_a_value_that_could_not_be_confirmed_is_missing() -> None:
    figure = wording.factor_not_confirmed(wording.FACTOR_NOT_CONFIRMED, "Lid included")

    assert figure == FigureLine(
        label=text_line("Lid included"), value=text_line("could not be confirmed"), missing=True
    )


def test_a_finding_links_its_site_and_has_no_url_in_its_words() -> None:
    figure = wording.finding(
        wording.FINDING_OWNER_REPORT, "Handle came loose", RTINGS, rating="4.5/5", review_count=1234
    )

    assert figure.label == text_line("Owner report")
    assert figure.value == Line(
        parts=(
            TextPart(text="Handle came loose ("),
            RTINGS,
            TextPart(text="), overall rating 4.5/5 from 1,234 reviews"),
        )
    )


def test_a_typical_lifespan_names_its_type_and_who_is_speaking() -> None:
    figure = wording.typical_lifespan("non-stick pans", "2", "5", "tefal.nl", "manufacturer")

    assert plain_text(figure.label) == "Typical for non-stick pans"
    assert plain_text(figure.value) == "2 to 5 years (tefal.nl) (the manufacturer states)"


def test_a_recurring_cost_links_its_site_and_labels_a_conversion() -> None:
    line = wording.recurring_cost(
        "€12", "replacement filter", RTINGS, converted_from="USD", others_left_out=True
    )

    assert line == Line(
        parts=(
            TextPart(text="€12 a year, replacement filter ("),
            RTINGS,
            TextPart(text="), converted from USD at a fixed rate, other consumables not counted"),
        )
    )


def test_a_line_joins_its_parts_with_a_separator_and_keeps_them_parts() -> None:
    first = Line(
        parts=(
            TextPart(text="carbon steel ("),
            ConfidencePart(text="estimated", basis="estimate"),
            TextPart(text=")"),
        )
    )

    assert wording.joined((first, text_line("1.4 kg")), ", ") == Line(
        parts=(
            TextPart(text="carbon steel ("),
            ConfidencePart(text="estimated", basis="estimate"),
            TextPart(text="), 1.4 kg"),
        )
    )


def test_a_sentence_is_one_text_part_even_with_braces_in_it() -> None:
    assert wording.text_line('We couldn\'t read "{5o}"') == Line(
        parts=(TextPart(text='We couldn\'t read "{5o}"'),)
    )


def test_co2e_unavailable_names_the_option_or_the_products() -> None:
    assert wording.co2e_unavailable("Bosch TWK3A011") == (
        "We couldn't estimate the CO2e of making Bosch TWK3A011, so no CO2e figure is shown for it."
    )
    assert wording.co2e_unavailable(None) == (
        "We couldn't estimate the CO2e of making these products just now, so no CO2e figures are "
        "shown. Try again in a moment."
    )
