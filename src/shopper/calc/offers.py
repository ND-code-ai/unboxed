"""Which offer on a product page stands, and its item price without shipping.

The rule is in docs/architecture/option_research.md ("The offer on a product page"): new offers
in euro only, a price that includes its shipping has the shipping taken off, a low outlier
against the other offers is dropped, then the cheapest in stock wins, counted with its stated
shipping; with none in stock, the cheapest.
"""

from collections.abc import Sequence
from decimal import Decimal
from statistics import median

from shopper.calc.budget import with_shipping
from shopper.state import DomainModel

NEW_CONDITION = "NewCondition"


class SeenOffer(DomainModel):
    """One offer as the page states it: its price and shipping in euro (missing when not stated in
    euro), whether it is in stock (missing when not stated) and its schema.org condition."""

    price: Decimal | None = None
    shipping: Decimal | None = None
    in_stock: bool | None = None
    condition: str | None = None


class ChosenOffer(DomainModel):
    """The offer that stands, by its position: its price without shipping, the shipping it states
    (missing when it states none) and whether it is in stock (missing when not stated)."""

    index: int
    item_price: Decimal
    shipping: Decimal | None
    in_stock: bool | None


class OfferChoice(DomainModel):
    """The offer that stands, missing when none can, and the positions of the offers dropped as
    low outliers."""

    chosen: ChosenOffer | None = None
    outliers: tuple[int, ...] = ()


def chosen_offer(
    offers: Sequence[SeenOffer],
    *,
    price_includes_shipping: bool,
    no_condition_is_new: bool,
    outlier_share: Decimal,
    min_others: int,
) -> OfferChoice:
    """The offer that stands among a page's offers.

    Only a new offer with a euro price counts; one with no condition counts as new only when
    `no_condition_is_new` (a site that offers new items only). When the page's price includes
    shipping, the stated shipping is taken off it, and an offer with no euro shipping is passed
    over. An offer in stock that costs under `outlier_share` of the median of the offers, when
    there are at least `min_others` others, is dropped. Of the rest, the cheapest in stock wins,
    counted with its shipping; with none in stock, the cheapest. Ties go to the earlier offer.
    """
    usable = {
        index: chosen
        for index, each in enumerate(offers)
        if _is_new(each, no_condition_is_new)
        for chosen in (_with_item_price(index, each, price_includes_shipping),)
        if chosen is not None
    }
    outliers = tuple(
        index
        for index, each in usable.items()
        if each.in_stock and _is_outlier(each, usable, outlier_share, min_others)
    )
    kept = [each for index, each in usable.items() if index not in outliers]
    in_stock = [each for each in kept if each.in_stock]
    pool = in_stock or kept
    chosen = min(pool, key=lambda each: (_cost(each), each.index), default=None)
    return OfferChoice(chosen=chosen, outliers=outliers)


def _is_new(offer: SeenOffer, no_condition_is_new: bool) -> bool:
    if offer.condition is None:
        return no_condition_is_new
    return offer.condition == NEW_CONDITION


def _with_item_price(
    index: int, offer: SeenOffer, price_includes_shipping: bool
) -> ChosenOffer | None:
    """The offer at its price without shipping; missing when it has no euro price, or its price
    includes shipping it does not state in euro."""
    if offer.price is None:
        return None
    if price_includes_shipping and offer.shipping is None:
        return None
    item_price = offer.price - offer.shipping if price_includes_shipping else offer.price
    return ChosenOffer(
        index=index, item_price=item_price, shipping=offer.shipping, in_stock=offer.in_stock
    )


def _cost(offer: ChosenOffer) -> Decimal:
    return with_shipping(offer.item_price, offer.shipping)


def _is_outlier(
    offer: ChosenOffer, usable: dict[int, ChosenOffer], share: Decimal, min_others: int
) -> bool:
    """Under the share of the median of every offer, itself included, so a pair at one low price
    counts in the median that judges it; only with enough others to tell."""
    costs = [_cost(each) for each in usable.values()]
    return len(costs) - 1 >= min_others and _cost(offer) < share * median(costs)
