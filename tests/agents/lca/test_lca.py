"""The LCA agent's tier 3 estimate through its agent function, with a fake model.

The recorded reply is the large model's estimate of three kettles, the first a linked product
whose page states two materials and a weight (scripts/lca_probe.py, docs/findings/task_1.9.7.md).
Expected figures are worked out by hand from that reply's masses and factors.
"""

import asyncio
import json
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest

from fakes import fake_chat
from shopper.agents.bundle import LcaOutput
from shopper.agents.lca.agent import estimate_co2e
from shopper.llm import ChatModel, ChatRequest, ChatTimeoutError
from shopper.state import (
    TIER_3_BOUNDARY,
    Material,
    ProductOption,
    Source,
    SourceKind,
    TrailEntry,
    TrailKind,
    WarningCode,
)

RECORDED = json.loads(
    (Path(__file__).parent.parent.parent / "fixtures" / "nebius" / "lca-kettles.json").read_text(
        encoding="utf-8"
    )
)
MODEL = RECORDED["model"]
ESTIMATED = Source(kind=SourceKind.MODEL_ESTIMATE, reference=MODEL)
PAGE = Source(kind=SourceKind.URL, reference="https://shop.example/russell-hobbs-structure")
RUSSELL = ProductOption(
    id="option-link",
    name="Russell Hobbs Structure waterkoker 28081-70",
    brand="Russell Hobbs",
    materials=(
        Material(name="plastic", source=PAGE),
        Material(name="stainless steel", source=PAGE),
    ),
    weight_kg=Decimal("1.1"),
    weight_source=PAGE,
)
FELLOW = ProductOption(id="option-1", name="Fellow Corvo EKG", brand="Fellow")
BOSCH = ProductOption(id="option-2", name="Bosch TWK3A011", brand="Bosch")
KETTLES = (RUSSELL, FELLOW, BOSCH)


def recorded_reply() -> dict[str, Any]:
    reply: dict[str, Any] = json.loads(RECORDED["reply"])
    return reply


def changed(**options: dict[str, Any]) -> str:
    """The recorded reply with fields of the entries at the given positions (`first`, `second`,
    `third`) replaced."""
    reply = recorded_reply()
    for position, fields in options.items():
        reply["options"][("first", "second", "third").index(position)].update(fields)
    return json.dumps(reply)


def estimate(
    replies: list[str | Exception], options: tuple[ProductOption, ...] = KETTLES
) -> tuple[LcaOutput, list[ChatRequest]]:
    chat, requests = fake_chat(replies)
    return asyncio.run(estimate_co2e(options, chat)), requests


def ranges(output: LcaOutput) -> dict[str, tuple[Decimal, Decimal]]:
    return {result.option_id: (result.co2e_low, result.co2e_high) for result in output.results}


def summaries(trail: tuple[TrailEntry, ...]) -> list[str]:
    return [entry.summary for entry in trail]


# --- A full estimate ---


def test_the_recorded_estimate_gives_each_option_its_summed_range() -> None:
    output, requests = estimate([RECORDED["reply"]])

    assert requests[0].messages[1]["content"] == RECORDED["input"]
    assert requests[0].model == MODEL
    assert ranges(output) == {
        "option-link": (Decimal("2.35"), Decimal("6.45")),
        "option-1": (Decimal("2.175"), Decimal("5.975")),
        "option-2": (Decimal("2.575"), Decimal("7.025")),
    }
    assert output.warnings == ()


def test_each_result_is_a_model_estimate_with_its_inputs_and_manufacturing() -> None:
    output, _ = estimate([RECORDED["reply"]])

    bosch = output.results[2]
    assert (bosch.tier, bosch.source, bosch.boundary) == (3, ESTIMATED, TIER_3_BOUNDARY)
    assert [(item.name, item.form, item.mass_kg) for item in bosch.inputs] == [
        ("polypropylene", "primary", Decimal("0.65")),
        ("stainless steel", "primary", Decimal("0.5")),
        ("nichrome", "primary", Decimal("0.05")),
    ]
    heating_element = bosch.inputs[2]
    assert heating_element.component
    assert (heating_element.factor_low, heating_element.factor_high) == (Decimal(8), Decimal(25))
    assert heating_element.factor_source == ESTIMATED
    assert (bosch.manufacturing_low, bosch.manufacturing_high) == (Decimal("0.2"), Decimal("0.5"))
    assert bosch.manufacturing_source == ESTIMATED


def test_the_same_material_gets_the_same_factor_in_every_option() -> None:
    output, _ = estimate([RECORDED["reply"]])

    steel = {
        (item.factor_low, item.factor_high)
        for result in output.results
        for item in result.inputs
        if item.name == "stainless steel"
    }
    assert steel == {(Decimal(2), Decimal(6))}


def test_one_trail_entry_per_option_names_the_tier_and_model_and_what_was_estimated() -> None:
    output, _ = estimate([RECORDED["reply"]])

    estimated = [entry for entry in output.trail if entry.summary.startswith("LCA tier 3")]
    assert summaries(tuple(estimated)) == [
        'LCA tier 3 estimated "Russell Hobbs Structure waterkoker 28081-70": 3 materials and '
        "manufacturing and assembly",
        'LCA tier 3 estimated "Fellow Corvo EKG": 3 materials and manufacturing and assembly',
        'LCA tier 3 estimated "Bosch TWK3A011": 3 materials and manufacturing and assembly',
    ]
    assert {(entry.kind, entry.model_tier, entry.model) for entry in estimated} == {
        (TrailKind.DECIDED, "large", MODEL)
    }


def test_the_call_reasons_in_full_on_the_large_tier_with_its_own_limits() -> None:
    _, requests = estimate([RECORDED["reply"]])

    assert not requests[0].low_effort
    assert (requests[0].max_tokens, requests[0].timeout) == (16000, 60.0)


def test_no_option_needs_no_call() -> None:
    output, requests = estimate([], options=())

    assert output == LcaOutput()
    assert requests == []


# --- A linked product with page materials and weight ---


def test_the_page_materials_and_weight_go_in_as_numbered_fixed_inputs_with_their_url() -> None:
    _, requests = estimate([RECORDED["reply"]])

    assert (
        "   Fixed inputs from the product page:\n"
        "   [1] material: plastic (https://shop.example/russell-hobbs-structure)\n"
        "   [2] material: stainless steel (https://shop.example/russell-hobbs-structure)\n"
        "   [3] weight of the whole item: 1.1 kg (https://shop.example/russell-hobbs-structure)"
    ) in requests[0].messages[1]["content"]


def test_a_fixed_input_keeps_the_pages_name_and_source_and_the_models_mass() -> None:
    output, _ = estimate([RECORDED["reply"]])

    plastic, steel, element = output.results[0].inputs
    assert (plastic.name, plastic.material_source) == ("plastic", PAGE)
    assert (plastic.factor_low, plastic.factor_high) == (Decimal("1.5"), Decimal("3.5"))
    assert (plastic.mass_kg, plastic.mass_source) == (Decimal("0.6"), ESTIMATED)
    assert (steel.name, steel.material_source) == ("stainless steel", PAGE)
    assert (element.name, element.material_source) == ("nichrome", ESTIMATED)


def test_a_form_the_page_does_not_state_is_the_models() -> None:
    output, _ = estimate([RECORDED["reply"]])

    plastic, _, element = output.results[0].inputs
    assert (plastic.form, plastic.form_source) == ("primary", ESTIMATED)
    assert (element.form, element.form_source) == ("primary", ESTIMATED)


def test_a_form_the_page_states_is_kept_as_written_with_the_page_as_its_source() -> None:
    reply = recorded_reply()
    reply["factors"][1] = dict(reply["factors"][1], form="70% recycled")
    for entry in reply["options"]:
        entry["inputs"][1] = dict(entry["inputs"][1], form="70% recycled")
    stated = Material(name="stainless steel", form="70% recycled", source=PAGE)
    russell = RUSSELL.model_copy(update={"materials": (RUSSELL.materials[0], stated)})

    output, _ = estimate([json.dumps(reply)], options=(russell, FELLOW, BOSCH))

    steel = output.results[0].inputs[1]
    assert (steel.form, steel.form_source) == ("70% recycled", PAGE)


def test_a_mass_the_page_states_is_kept_with_its_source() -> None:
    weighed = Material(name="stainless steel", mass_kg=Decimal("0.5"), source=PAGE)
    russell = RUSSELL.model_copy(
        update={
            "materials": (RUSSELL.materials[0], weighed),
            "weight_kg": None,
            "weight_source": None,
        }
    )

    output, _ = estimate([RECORDED["reply"]], options=(russell, FELLOW, BOSCH))

    steel = output.results[0].inputs[1]
    assert (steel.mass_kg, steel.mass_source) == (Decimal("0.5"), PAGE)


def test_the_assumed_masses_follow_the_pages_weight_in_a_trail_entry_citing_it() -> None:
    russell = RUSSELL.model_copy(update={"weight_kg": Decimal("1.625")})

    output, _ = estimate([RECORDED["reply"]], options=(russell, FELLOW, BOSCH))

    plastic, steel, element = output.results[0].inputs
    assert (plastic.mass_kg, steel.mass_kg, element.mass_kg) == (
        Decimal("0.9"),
        Decimal("0.675"),
        Decimal("0.05"),
    )
    (scaled,) = [entry for entry in output.trail if entry.summary.startswith("Scaled")]
    assert scaled.summary == (
        'Scaled the assumed masses of "Russell Hobbs Structure waterkoker 28081-70" by 1.5 to '
        "the page's weight of 1.625 kg"
    )
    assert scaled.source == PAGE


def test_a_weight_too_far_from_the_assumed_masses_keeps_them_and_says_so() -> None:
    russell = RUSSELL.model_copy(update={"weight_kg": Decimal("3.2")})

    output, _ = estimate([RECORDED["reply"]], options=(russell, FELLOW, BOSCH))

    assert ranges(output)["option-link"] == (Decimal("2.35"), Decimal("6.45"))
    assert (
        'Kept the assumed masses of "Russell Hobbs Structure waterkoker 28081-70": the page\'s '
        "weight of 3.2 kg would scale them by 3, outside 0.5 to 2"
    ) in summaries(output.trail)


# The scale is (weight - 0.05 kg of the element) / 1.05 kg of assumed bulk masses.
@pytest.mark.parametrize(
    ("weight", "scale"),
    [("2.154", "2.01"), ("0.5745", "0.49")],
)
def test_a_scale_just_outside_the_window_never_shows_as_its_bound(weight: str, scale: str) -> None:
    russell = RUSSELL.model_copy(update={"weight_kg": Decimal(weight)})

    output, _ = estimate([RECORDED["reply"]], options=(russell, FELLOW, BOSCH))

    assert (f"weight of {weight} kg would scale them by {scale}, outside 0.5 to 2") in "\n".join(
        summaries(output.trail)
    )


def test_the_scale_rounds_half_up() -> None:
    russell = RUSSELL.model_copy(update={"weight_kg": Decimal("1.23125")})

    output, _ = estimate([RECORDED["reply"]], options=(russell, FELLOW, BOSCH))

    assert "by 1.13 to the page's weight of 1.23125 kg" in "\n".join(summaries(output.trail))


# --- One option declined ---


def test_a_declined_option_has_no_result_and_its_own_warning_and_trail_entry() -> None:
    reply = changed(
        third={
            "inputs": [],
            "manufacturing_low": None,
            "manufacturing_high": None,
            "declined_because": "I cannot tell which product this is",
        }
    )

    output, _ = estimate([reply])

    assert set(ranges(output)) == {"option-link", "option-1"}
    (warning,) = output.warnings
    assert (warning.code, warning.option_id) == (WarningCode.CO2E_UNAVAILABLE, "option-2")
    assert warning.message == (
        "We couldn't estimate the CO2e of making Bosch TWK3A011, so no CO2e figure is shown for it."
    )
    (declined,) = [entry for entry in output.trail if entry.kind is TrailKind.EXCLUDED]
    assert declined.summary == 'LCA tier 3 gave no estimate for "Bosch TWK3A011"'
    assert declined.reason == "the model declined it: I cannot tell which product this is"
    assert (declined.model_tier, declined.model) == ("large", MODEL)


def without_third() -> str:
    reply = recorded_reply()
    reply["options"] = reply["options"][:2]
    return json.dumps(reply)


def twice() -> str:
    reply = recorded_reply()
    reply["options"][2] = reply["options"][1]
    return json.dumps(reply)


def declined_reasons(output: LcaOutput) -> dict[str | None, str | None]:
    excluded = (entry for entry in output.trail if entry.kind is TrailKind.EXCLUDED)
    by_name = {option.name: option.id for option in KETTLES}
    return {by_name[entry.summary.split('"')[1]]: entry.reason for entry in excluded}


def test_a_missing_entry_is_a_decline() -> None:
    output, _ = estimate([without_third()])

    assert set(ranges(output)) == {"option-link", "option-1"}
    assert [warning.option_id for warning in output.warnings] == ["option-2"]
    assert declined_reasons(output) == {
        "option-2": "the model's answer has no entry for it in its place"
    }


def test_a_duplicate_entry_is_a_decline_for_both_places() -> None:
    output, _ = estimate([twice()])

    assert set(ranges(output)) == {"option-link"}
    assert [warning.option_id for warning in output.warnings] == ["option-1", "option-2"]
    assert declined_reasons(output) == {
        "option-1": "the model's answer gives it more than once",
        "option-2": "the model's answer has no entry for it in its place",
    }


def test_an_echoed_name_differing_only_in_case_and_spacing_still_matches() -> None:
    output, _ = estimate([changed(second={"name": "fellow corvo  EKG"})])

    assert set(ranges(output)) == {"option-link", "option-1", "option-2"}


def test_inputs_that_fail_a_check_are_a_decline_never_summed_as_zero() -> None:
    first = recorded_reply()["options"][0]
    zero_mass = [dict(first["inputs"][0], mass_kg=0), *first["inputs"][1:]]
    no_factor = [dict(first["inputs"][0], factor=9), *first["inputs"][1:]]
    wrong_fixed = [dict(first["inputs"][0], fixed_input=3), *first["inputs"][1:]]

    for inputs, reason in (
        (zero_mass, "its inputs failed a check: the mass of polypropylene is not above 0"),
        (
            no_factor,
            "its inputs failed a check: polypropylene points at factor 9, which is not in the "
            "table",
        ),
        # Fixed input 3 is the page's weight, so this row is no page material, and the one it
        # should have named is missing.
        (wrong_fixed, "its inputs failed a check: the page's material plastic was left out"),
    ):
        output, _ = estimate([changed(first={"inputs": inputs})])

        assert "option-link" not in ranges(output)
        assert [warning.option_id for warning in output.warnings] == ["option-link"]
        assert declined_reasons(output) == {"option-link": reason}


def test_a_pointer_at_no_page_material_is_ignored_and_the_row_stays_the_models_own() -> None:
    # Live, on 30 October: an option with no page materials, its rows at "fixed input 1".
    second = recorded_reply()["options"][1]
    stray = [dict(row, fixed_input=1) for row in second["inputs"]]

    output, _ = estimate([changed(second={"inputs": stray})])

    assert output.warnings == ()
    result = next(each for each in output.results if each.option_id == "option-1")
    plain, _ = estimate([RECORDED["reply"]])
    same = next(each for each in plain.results if each.option_id == "option-1")
    assert (result.co2e_low, result.co2e_high) == (same.co2e_low, same.co2e_high)
    assert all(each.material_source == ESTIMATED for each in result.inputs)
    assert all(each.mass_source == ESTIMATED for each in result.inputs)


def test_a_row_at_the_pages_weight_is_the_models_own_and_scaled_to_that_weight() -> None:
    second = recorded_reply()["options"][1]
    stray = [dict(row, fixed_input=1) for row in second["inputs"]]
    total = sum(row["mass_kg"] for row in stray)
    weighed = FELLOW.model_copy(
        update={"weight_kg": Decimal(str(total)) * Decimal("1.2"), "weight_source": PAGE}
    )

    output, _ = estimate(
        [changed(second={"inputs": stray})],
        (RUSSELL, weighed, BOSCH),
    )

    assert output.warnings == ()
    result = next(each for each in output.results if each.option_id == "option-1")
    assert all(each.material_source == ESTIMATED for each in result.inputs)
    assert all(each.mass_source == ESTIMATED for each in result.inputs)


def test_a_dropped_pointer_with_masses_far_above_the_pages_weight_is_a_decline() -> None:
    first = recorded_reply()["options"][0]
    whole_item = dict(first["inputs"][1], fixed_input=3, mass_kg=1.1)

    output, _ = estimate([changed(first={"inputs": [*first["inputs"], whole_item]})])

    assert declined_reasons(output) == {
        "option-link": "its inputs failed a check: a row may count the page's weight of 1.1 kg as "
        "a material"
    }


def test_an_input_must_name_the_material_and_form_of_its_factor() -> None:
    second = recorded_reply()["options"][1]
    misnamed = [dict(second["inputs"][0], name="aluminium", form="recycled"), *second["inputs"][1:]]

    output, _ = estimate([changed(second={"inputs": misnamed})])

    assert declined_reasons(output) == {
        "option-1": "its inputs failed a check: aluminium, recycled points at the factor of "
        "polypropylene"
    }


def test_a_page_material_must_name_the_material_and_form_of_its_factor_too() -> None:
    first = recorded_reply()["options"][0]
    misnamed = [dict(first["inputs"][0], name="aluminium"), *first["inputs"][1:]]

    output, _ = estimate([changed(first={"inputs": misnamed})])

    assert declined_reasons(output) == {
        "option-link": "its inputs failed a check: aluminium, primary points at the factor of "
        "polypropylene"
    }


def test_a_page_material_given_twice_is_a_decline() -> None:
    first = recorded_reply()["options"][0]
    doubled = [*first["inputs"], dict(first["inputs"][1])]

    output, _ = estimate([changed(first={"inputs": doubled})])

    assert declined_reasons(output) == {
        "option-link": "its inputs failed a check: the page's material stainless steel is given "
        "twice"
    }


def test_a_material_given_twice_in_the_factor_table_is_a_decline_where_used() -> None:
    reply = recorded_reply()
    reply["factors"].append(dict(reply["factors"][2], factor_low=5.0))

    output, _ = estimate([json.dumps(reply)])

    reason = "its inputs failed a check: the factor table gives nichrome, primary 2 times"
    assert declined_reasons(output) == {
        "option-link": reason,
        "option-1": reason,
        "option-2": reason,
    }


def test_a_factor_outside_the_plausible_bounds_is_a_decline_where_used() -> None:
    reply = recorded_reply()
    reply["factors"][2] = dict(reply["factors"][2], factor_high=25000.0)

    output, _ = estimate([json.dumps(reply)])

    assert output.results == ()
    assert set(declined_reasons(output).values()) == {
        "its inputs failed a check: the factor of nichrome is not a range within 0.05 to 500 kg "
        "CO2e per kg"
    }


def test_a_page_material_the_model_left_out_is_a_decline() -> None:
    first = recorded_reply()["options"][0]
    without_plastic = [dict(row) for row in first["inputs"] if row["fixed_input"] != 1]

    output, _ = estimate([changed(first={"inputs": without_plastic})])

    assert declined_reasons(output) == {
        "option-link": "its inputs failed a check: the page's material plastic was left out"
    }


def test_a_form_the_page_states_must_be_the_form_of_its_factor() -> None:
    recycled = Material(name="stainless steel", form="recycled", source=PAGE)
    russell = RUSSELL.model_copy(update={"materials": (RUSSELL.materials[0], recycled)})

    output, _ = estimate([RECORDED["reply"]], options=(russell, FELLOW, BOSCH))

    assert declined_reasons(output) == {
        "option-link": "its inputs failed a check: the page states recycled stainless steel, "
        "but its factor is for primary"
    }


def test_manufacturing_of_zero_is_a_decline_never_summed_as_zero() -> None:
    output, _ = estimate([changed(second={"manufacturing_low": 0.0, "manufacturing_high": 0.0})])

    assert declined_reasons(output) == {
        "option-1": "its inputs failed a check: the manufacturing range 0.0 to 0.0 kg CO2e is not "
        "a range above 0"
    }


def test_an_estimate_without_manufacturing_is_a_decline() -> None:
    output, _ = estimate([changed(second={"manufacturing_low": None})])

    assert declined_reasons(output) == {
        "option-1": "its inputs failed a check: no manufacturing range was given"
    }


# --- The call fails ---


def assert_one_report_warning(output: LcaOutput) -> None:
    assert output.results == ()
    (warning,) = output.warnings
    assert (warning.code, warning.option_id) == (WarningCode.CO2E_UNAVAILABLE, None)
    assert warning.message == (
        "We couldn't estimate the CO2e of making these products just now, so no CO2e figures are "
        "shown. Try again in a moment."
    )


def test_a_timeout_gives_no_result_and_one_warning_for_the_report() -> None:
    output, _ = estimate([ChatTimeoutError("no answer within 60 s")])

    assert_one_report_warning(output)
    (failed,) = output.trail
    assert failed.summary == "Could not estimate the CO2e of the options"
    assert failed.reason == "the model call failed (timeout)"
    assert (failed.model_tier, failed.model) == ("large", MODEL)


def test_invalid_output_twice_gives_no_result_and_one_warning_for_the_report() -> None:
    output, requests = estimate(['{"factors": []}', "not json"])

    assert len(requests) == 2
    assert_one_report_warning(output)
    (failed,) = output.trail
    assert failed.reason == "the model call failed (invalid_output)"


def test_invalid_output_once_is_retried_and_the_retry_is_used() -> None:
    output, _ = estimate(['{"factors": []}', RECORDED["reply"]])

    assert len(output.results) == 3


def slow(seconds: float) -> ChatModel:
    async def chat(request: ChatRequest) -> str:
        await asyncio.sleep(seconds)
        return str(RECORDED["reply"])

    return chat


def test_the_whole_estimate_stops_at_its_time_cap() -> None:
    output = asyncio.run(estimate_co2e(KETTLES, slow(1), time_cap=0.01))

    assert_one_report_warning(output)
    (stopped,) = output.trail
    assert stopped.kind is TrailKind.EXCLUDED
    assert stopped.reason == "the estimate took longer than 0.01 s"
    assert (stopped.model_tier, stopped.model) == ("large", MODEL)
