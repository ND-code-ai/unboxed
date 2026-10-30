"""Which offer on a product page stands; values written from the rules in
docs/architecture/option_research.md ("The offer on a product page")."""

from decimal import Decimal

from shopper.calc.offers import ChosenOffer, SeenOffer, chosen_offer

NEW = "NewCondition"
OUTLIER_SHARE = Decimal("0.6")
MIN_OTHERS = 3


def choose(
    *offers: SeenOffer, price_includes_shipping: bool = False, no_condition_is_new: bool = True
) -> ChosenOffer | None:
    return chosen_offer(
        offers,
        price_includes_shipping=price_includes_shipping,
        no_condition_is_new=no_condition_is_new,
        outlier_share=OUTLIER_SHARE,
        min_others=MIN_OTHERS,
    ).chosen


def offer(
    price: str | None,
    shipping: str | None = None,
    *,
    in_stock: bool | None = True,
    condition: str | None = NEW,
) -> SeenOffer:
    return SeenOffer(
        price=None if price is None else Decimal(price),
        shipping=None if shipping is None else Decimal(shipping),
        in_stock=in_stock,
        condition=condition,
    )


def test_the_cheapest_offer_in_stock_with_its_shipping_stands() -> None:
    chosen = choose(offer("29.95", "4.95"), offer("31.00", "0"), offer("27.00", in_stock=False))

    assert chosen == ChosenOffer(
        index=1, item_price=Decimal("31.00"), shipping=Decimal("0"), in_stock=True
    )


def test_an_offer_with_no_shipping_stated_counts_at_its_price_alone() -> None:
    chosen = choose(offer("30.00", "2.00"), offer("31.00"))

    assert chosen == ChosenOffer(index=1, item_price=Decimal("31.00"), shipping=None, in_stock=True)


def test_a_price_that_includes_shipping_has_its_shipping_taken_off() -> None:
    # kieskeurig.nl's GreenChef at bol.: €26.98 is €23.99 plus €2.99 shipping.
    chosen = choose(offer("26.98", "2.99"), offer("52.94", "6.95"), price_includes_shipping=True)

    assert chosen == ChosenOffer(
        index=0, item_price=Decimal("23.99"), shipping=Decimal("2.99"), in_stock=True
    )


def test_a_price_that_includes_shipping_with_no_shipping_stated_is_passed_over() -> None:
    chosen = choose(offer("20.00"), offer("30.00", "3.00"), price_includes_shipping=True)

    assert chosen is not None
    assert chosen.index == 1


def test_used_and_refurbished_offers_are_passed_over() -> None:
    chosen = choose(
        offer("10.00", condition="UsedCondition"),
        offer("12.00", condition="RefurbishedCondition"),
        offer("25.00"),
    )

    assert chosen is not None
    assert chosen.index == 2


def test_an_offer_with_no_condition_is_new_only_where_the_site_offers_new_items_only() -> None:
    offers = (offer("20.00", condition=None), offer("25.00"))

    assert choose(*offers, no_condition_is_new=True) == ChosenOffer(
        index=0, item_price=Decimal("20.00"), shipping=None, in_stock=True
    )
    chosen = choose(*offers, no_condition_is_new=False)
    assert chosen is not None
    assert chosen.index == 1


def test_an_offer_under_sixty_percent_of_the_median_of_three_others_is_dropped() -> None:
    # The Metabo SBE 650 at €32.95 against €63.27 to €114.94 (docs/findings/task_1.12.md).
    choice = chosen_offer(
        (offer("32.95"), offer("63.27"), offer("70.00"), offer("114.94")),
        price_includes_shipping=False,
        no_condition_is_new=True,
        outlier_share=OUTLIER_SHARE,
        min_others=MIN_OTHERS,
    )

    assert choice.outliers == (0,)
    assert choice.chosen is not None
    assert choice.chosen.item_price == Decimal("63.27")


def test_two_offers_at_one_low_price_count_in_the_median_that_judges_them() -> None:
    # kieskeurig.nl's GreenChef: bol. and Amazon at €26.98, Fietsweb.nl and Kaufland far above.
    choice = chosen_offer(
        (offer("26.98"), offer("26.98"), offer("52.94"), offer("77.90")),
        price_includes_shipping=False,
        no_condition_is_new=True,
        outlier_share=OUTLIER_SHARE,
        min_others=MIN_OTHERS,
    )

    assert choice.outliers == ()
    assert choice.chosen is not None
    assert choice.chosen.index == 0


def test_a_low_offer_with_only_two_others_is_not_an_outlier() -> None:
    chosen = choose(offer("32.95"), offer("63.27"), offer("70.00"))

    assert chosen is not None
    assert chosen.item_price == Decimal("32.95")


def test_with_none_in_stock_the_cheapest_stands_and_says_it_is_not() -> None:
    chosen = choose(offer("52.00", in_stock=False), offer("48.00", in_stock=False))

    assert chosen == ChosenOffer(
        index=1, item_price=Decimal("48.00"), shipping=None, in_stock=False
    )


def test_an_offer_that_states_no_stock_comes_after_one_in_stock_and_keeps_its_stock_unknown() -> (
    None
):
    offers = (offer("40.00", in_stock=None), offer("45.00"))

    in_stock = choose(*offers)
    unknown = choose(offer("40.00", in_stock=None), offer("38.00", in_stock=False))

    assert in_stock is not None
    assert in_stock.index == 1
    assert unknown == ChosenOffer(
        index=1, item_price=Decimal("38.00"), shipping=None, in_stock=False
    )


def test_with_no_offer_in_euro_none_stands() -> None:
    assert choose(offer(None), offer("20.00", condition="UsedCondition")) is None
