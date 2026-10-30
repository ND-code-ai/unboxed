from decimal import Decimal

import pytest

from samples import seen_price
from shopper.calc.budget import (
    OTHER_CURRENCY_CODES,
    BudgetReading,
    CurrencyJudgement,
    nothing_within_budget_warning,
    read_budget,
    with_shipping,
)
from shopper.state import Listing, ProductOption, WarningCode


def option(option_id: str, price: str | None) -> ProductOption:
    return ProductOption(id=option_id, name=option_id, **seen_price(price))


def listing(price: str) -> Listing:
    return Listing(
        id="listing-1",
        title="Used pan",
        price=Decimal(price),
        condition="used",
        link="https://example.com/listing-1",
        country="NL",
        ships_to_nl=True,
        marketplace="EBAY_NL",
    )


OPTIONS = (option("non-stick", "15"), option("carbon-steel", "40"))


def test_a_budget_below_every_option_and_no_listing_gives_the_warning() -> None:
    warning = nothing_within_budget_warning(OPTIONS, (), Decimal("5"))

    assert warning is not None
    assert warning.code is WarningCode.NOTHING_WITHIN_BUDGET
    assert warning.message == "Nothing found within €5; the cheapest option is €15."


def test_amounts_with_cents_keep_them_in_the_message() -> None:
    warning = nothing_within_budget_warning((option("pan", "12.5"),), (), Decimal("9.99"))

    assert warning is not None
    assert warning.message == "Nothing found within €9.99; the cheapest option is €12.50."


def test_a_listing_within_budget_means_no_warning() -> None:
    assert nothing_within_budget_warning(OPTIONS, (listing("4"),), Decimal("5")) is None


def test_a_listing_over_the_budget_does_not_remove_the_warning() -> None:
    assert nothing_within_budget_warning(OPTIONS, (listing("8"),), Decimal("5")) is not None


def test_an_option_at_the_budget_means_no_warning() -> None:
    assert nothing_within_budget_warning(OPTIONS, (), Decimal("15")) is None


def test_an_option_within_the_budget_only_without_its_shipping_is_over_it() -> None:
    shipped = option("pan", "14").model_copy(update={"shipping": Decimal("2")})

    warning = nothing_within_budget_warning((shipped,), (), Decimal("15"))

    assert warning is not None
    assert warning.message == "Nothing found within €15; the cheapest option is €14."


@pytest.mark.parametrize(("shipping", "cost"), [("2.99", "17.98"), ("0", "14.99"), (None, "14.99")])
def test_what_buying_costs_is_the_price_plus_the_stated_shipping(
    shipping: str | None, cost: str
) -> None:
    stated = None if shipping is None else Decimal(shipping)

    assert with_shipping(Decimal("14.99"), stated) == Decimal(cost)


def test_no_budget_means_no_warning() -> None:
    assert nothing_within_budget_warning(OPTIONS, (), None) is None


def test_no_priced_option_means_no_warning() -> None:
    assert nothing_within_budget_warning((option("unpriced", None),), (), Decimal("5")) is None


# The rows of "Reading the phrase" in docs/architecture/supervisor.md.
@pytest.mark.parametrize(
    ("phrase", "amount"),
    [
        ("50", "50"),
        ("€50", "50"),
        ("50 euro", "50"),
        ("hasta 50 euros", "50"),
        ("50eur", "50"),
        ("50€", "50"),
        ("50,-", "50"),
        ("50.-", "50"),
        ("1.000", "1000"),
        ("1 000", "1000"),
        ("1 000", "1000"),
        ("1.234,56", "1234.56"),
        ("49,99", "49.99"),
    ],
)
def test_one_number_with_a_euro_marker_or_none_is_that_amount(phrase: str, amount: str) -> None:
    assert read_budget(phrase) == BudgetReading(amount=Decimal(amount))


@pytest.mark.parametrize("phrase", ["30-50", "tussen 30 en 50", "30 - 50 euro", "€30–€50"])
def test_two_numbers_give_the_higher_one_and_say_it_was_a_range(phrase: str) -> None:
    assert read_budget(phrase) == BudgetReading(amount=Decimal("50"), from_range=True)


@pytest.mark.parametrize(
    "phrase",
    ["1.2345", "1.5.5", "30, 40 or 50", "5o", "5o euro", "50k", "fifty", "vijftig", "٥٠", ""],
)
def test_a_phrase_that_is_not_one_amount_is_unreadable(phrase: str) -> None:
    assert read_budget(phrase) == BudgetReading(warning_code=WarningCode.BUDGET_UNREADABLE)


@pytest.mark.parametrize("phrase", ["£40", "40 dollar", "40 quid", "400 kr", "40usd", "40kr"])
def test_a_marker_of_another_currency_is_never_read_as_euros(phrase: str) -> None:
    assert read_budget(phrase) == BudgetReading(warning_code=WarningCode.BUDGET_OTHER_CURRENCY)


@pytest.mark.parametrize("phrase", ["0", "€0", "0,00", "-50", "-€50", "budget -50 euro"])
def test_zero_or_a_negative_amount_is_not_positive(phrase: str) -> None:
    assert read_budget(phrase) == BudgetReading(warning_code=WarningCode.BUDGET_NOT_POSITIVE)


# "When more than one applies, the first in the table wins."
def test_the_first_warning_in_the_table_wins() -> None:
    other_currency = BudgetReading(warning_code=WarningCode.BUDGET_OTHER_CURRENCY)
    unreadable = BudgetReading(warning_code=WarningCode.BUDGET_UNREADABLE)

    assert read_budget("£0") == other_currency
    assert read_budget("5o pounds") == unreadable
    assert read_budget("fifty pounds") == unreadable


@pytest.mark.parametrize("code", sorted(OTHER_CURRENCY_CODES))
def test_every_other_iso_code_is_another_currency(code: str) -> None:
    other_currency = BudgetReading(warning_code=WarningCode.BUDGET_OTHER_CURRENCY)

    assert read_budget(f"40 {code}") == other_currency
    assert read_budget(f"{code} 40") == other_currency
    assert read_budget(f"40{code.lower()}") == other_currency


def test_the_iso_codes_cover_the_named_currencies_and_leave_out_the_euro() -> None:
    assert {"GBP", "USD", "CHF", "NOK", "JPY", "TRY", "PLN", "SEK", "DKK", "CZK", "HUF", "RON"} <= (
        OTHER_CURRENCY_CODES
    )
    assert "EUR" not in OTHER_CURRENCY_CODES
    assert all(len(code) == 3 and code.isupper() for code in OTHER_CURRENCY_CODES)


# The symbols and names of "Other currencies" in docs/architecture/supervisor.md, by hand.
@pytest.mark.parametrize(
    "marker",
    [
        *("zł", "złoty", "zloty", "złote", "złotych", "kr", "krona", "kronor", "krone", "kroner"),
        *("Kč", "koruna", "koruny", "korun", "Ft", "forint", "forints", "leu", "lei"),
        *("£", "pound", "pounds", "pond", "ponden", "Pfund", "$", "dollar", "dollars", "Dollar"),
        *("Fr.", "franc", "francs", "frank", "franken", "Franken", "kroon", "kronen", "Kronen"),
        *("¥", "yen", "Yen", "₺", "lira", "lire", "Lira", "liras", "quid", "bucks"),
        *("zl", "zlote", "zlotych", "zlotys", "sterling", "sfr"),
    ],
)
def test_every_listed_symbol_and_name_is_another_currency(marker: str) -> None:
    other_currency = BudgetReading(warning_code=WarningCode.BUDGET_OTHER_CURRENCY)

    assert read_budget(f"40 {marker}") == other_currency
    assert read_budget(f"{marker} 40") == other_currency


# A lower-case code that is also a word counts only where an amount's marker stands.
@pytest.mark.parametrize("phrase", ["cup under 50", "a pen for max 20", "try 50 euro"])
def test_a_word_that_spells_an_iso_code_before_the_amount_is_ignored(phrase: str) -> None:
    assert read_budget(phrase).warning_code is None


def test_a_word_on_no_list_is_ignored_so_the_amount_is_read_as_euros() -> None:
    assert read_budget("40 doubloons") == BudgetReading(amount=Decimal("40"))


# The order of "Words on no list" in docs/architecture/supervisor.md, with the judgement given.
@pytest.mark.parametrize("judgement", ["eur", "other", "none_stated", None])
@pytest.mark.parametrize("phrase", ["£40", "40 dollar", "€50 (about $55)"])
def test_a_listed_other_currency_wins_whatever_the_model_said(
    phrase: str, judgement: CurrencyJudgement | None
) -> None:
    assert read_budget(phrase, judgement) == BudgetReading(
        warning_code=WarningCode.BUDGET_OTHER_CURRENCY
    )


@pytest.mark.parametrize("judgement", ["eur", "other", "none_stated", None])
@pytest.mark.parametrize("phrase", ["€50", "50 euro", "50eur"])
def test_a_euro_marker_is_read_as_euros_whatever_the_model_said(
    phrase: str, judgement: CurrencyJudgement | None
) -> None:
    assert read_budget(phrase, judgement) == BudgetReading(amount=Decimal("50"))


@pytest.mark.parametrize("phrase", ["10 dolla", "10 pesos", "10"])
def test_with_no_listed_marker_the_model_judging_another_currency_gives_the_warning(
    phrase: str,
) -> None:
    assert read_budget(phrase, "other") == BudgetReading(
        warning_code=WarningCode.BUDGET_OTHER_CURRENCY, judged_by_model=True
    )


@pytest.mark.parametrize("judgement", ["eur", "none_stated", None])
@pytest.mark.parametrize("phrase", ["50 max", "50 and not higher", "50"])
def test_with_no_listed_marker_any_other_judgement_is_read_as_euros(
    phrase: str, judgement: CurrencyJudgement | None
) -> None:
    assert read_budget(phrase, judgement) == BudgetReading(amount=Decimal("50"))


def test_the_model_judging_another_currency_keeps_the_order_of_the_warnings() -> None:
    assert read_budget("5o pesos", "other") == BudgetReading(
        warning_code=WarningCode.BUDGET_UNREADABLE
    )
    assert read_budget("0 pesos", "other") == BudgetReading(
        warning_code=WarningCode.BUDGET_OTHER_CURRENCY, judged_by_model=True
    )
