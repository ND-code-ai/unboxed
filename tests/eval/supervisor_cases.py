"""The supervisor evaluation cases (docs/architecture/supervisor.md, "Evaluation").

Used only in testing; the app never reads this. The cases live here and nowhere else. A held-out
case names the product term that must stay out of the supervisor's prompt; an offline test
enforces it. A failed case is fixed by rewording a definition in the prompt, never by adding the
product to it.
"""

from dataclasses import dataclass
from decimal import Decimal

from shopper.state import Scope, WarningCode


@dataclass(frozen=True)
class Case:
    input: str
    scope: Scope
    rule: str
    borderline: bool = False
    held_out_term: str | None = None
    category: str | None = None
    # Other names of the same category that also pass ("three dimensional printer").
    also_accepted: tuple[str, ...] = ()
    # The expected budget outcome: the warning that drops the budget, or the budget in euro.
    budget_outcome: WarningCode | Decimal | None = None


CORE = (
    Case("I need a new frying pan, budget 50 euro", Scope.TUNED, "tuned", category="frying pan"),
    Case(
        "a cordless drill for occasional DIY",
        Scope.TUNED,
        "tuned",
        category="cordless drill",
    ),
    Case("an office chair, around €200", Scope.GENERAL, "general", category="office chair"),
    Case("a new fridge, max 600 euro", Scope.ENERGY_HEAVY, "energy_heavy"),
    Case("a warm winter coat under 120 euros", Scope.CLOTHING, "clothing"),
)

HELD_OUT = (
    # The energy line, both sides, and the departures from the energy-label list.
    Case(
        "a small fan heater to put under my desk",
        Scope.ENERGY_HEAVY,
        "energy line: space heating of any kind",
        held_out_term="fan heater",
    ),
    Case(
        "Ik zoek een vaatwasser, maximaal 500 euro",
        Scope.ENERGY_HEAVY,
        "energy line: dishwashers; Dutch",
        held_out_term="vaatwasser",
        category="dishwasher",
    ),
    Case(
        "Ich brauche einen neuen Wäschetrockner",
        Scope.ENERGY_HEAVY,
        "energy line: laundry; German",
        held_out_term="wäschetrockner",
    ),
    Case(
        "an air fryer for two people",
        Scope.TUNED,
        "energy line: countertop cooking is not an energy-heavy group",
        held_out_term="air fryer",
        category="air fryer",
    ),
    Case(
        "a microwave, nothing fancy",
        Scope.TUNED,
        "energy line: small ovens are outside the oven group",
        held_out_term="microwave",
        category="microwave",
    ),
    Case(
        "a new television for the living room",
        Scope.GENERAL,
        "energy line: displays are left out on purpose",
        held_out_term="television",
    ),
    Case(
        "a laptop for studying, up to €700",
        Scope.GENERAL,
        "energy line: computers are general",
        held_out_term="laptop",
        category="laptop",
    ),
    # The clothing line.
    Case(
        "running shoes for wide feet",
        Scope.CLOTHING,
        "clothing line: footwear",
        held_out_term="running shoes",
    ),
    Case(
        "a leather backpack for work",
        Scope.GENERAL,
        "clothing line: bags are not clothing",
        held_out_term="backpack",
        category="backpack",
    ),
    # Durable or consumable.
    Case(
        "coffee capsules for my machine",
        Scope.NOT_A_PRODUCT,
        "consumable line: used up in use",
        held_out_term="capsules",
    ),
    Case(
        "an espresso machine for at home",
        Scope.TUNED,
        "consumable line: a durable product that uses consumables runs",
        held_out_term="espresso",
    ),
    # One product.
    Case(
        "a kettle and a toaster in the same colour",
        Scope.SEVERAL_PRODUCTS,
        "one-product line: two categories",
        held_out_term="toaster",
    ),
    Case(
        "a set of kitchen knives with a block",
        Scope.TUNED,
        "one-product line: a set is one product",
        held_out_term="kitchen knives",
    ),
    # A motor vehicle and a near neighbour that runs.
    Case(
        "a second-hand Volkswagen Golf, budget 8000 euro",
        Scope.NOT_A_PRODUCT,
        "motor vehicles are declined",
        held_out_term="volkswagen",
    ),
    Case(
        "een elektrische fiets voor woon-werkverkeer",
        Scope.GENERAL,
        "motor vehicles: a bicycle with a motor runs; Dutch",
        held_out_term="fiets",
    ),
)

DOES_NOT_RUN = (
    Case(
        "a kilo of old cheese",
        Scope.NOT_A_PRODUCT,
        "not_a_product: food",
        held_out_term="cheese",
    ),
    Case(
        "a blender or a food processor, not sure which",
        Scope.SEVERAL_PRODUCTS,
        "several_products",
        held_out_term="blender",
    ),
    Case("asdf qwer zxcv", Scope.UNCLEAR, "unclear"),
)

# A synonym pair, one of them not in English, that must give the same category; and a name
# that holds a digit.
CATEGORY = (
    Case(
        "a hoover for a small flat",
        Scope.TUNED,
        "category: a synonym gets the common name",
        held_out_term="hoover",
        category="vacuum cleaner",
    ),
    Case(
        "Ik zoek een stofzuiger tot €150",
        Scope.TUNED,
        "category: English whatever the language; Dutch",
        held_out_term="stofzuiger",
        category="vacuum cleaner",
    ),
    # A name with a digit in it, which the form check must not drop.
    Case(
        "a 3d printer for a beginner",
        Scope.GENERAL,
        "category: a digit that is part of the product's name stays",
        held_out_term="3d printer",
        category="3d printer",
        also_accepted=("3-d printer", "three dimensional printer", "three-dimensional printer"),
    ),
)

# A currency on no list, and a word after the amount that is not a currency. The products are
# core ones, so that only the budget is in question.
BUDGET_CURRENCY = (
    Case(
        "a frying pan, budget 10 dolla",
        Scope.TUNED,
        "budget currency: a misspelt currency on no list",
        budget_outcome=WarningCode.BUDGET_OTHER_CURRENCY,
    ),
    Case(
        "an office chair for 2000 pesos",
        Scope.GENERAL,
        "budget currency: a currency on no list, named in full",
        budget_outcome=WarningCode.BUDGET_OTHER_CURRENCY,
    ),
    Case(
        "a frying pan, 50 max",
        Scope.TUNED,
        "budget currency: a word after the amount that is not a currency",
        budget_outcome=Decimal("50"),
    ),
    Case(
        "a warm winter coat, 120 and not higher",
        Scope.CLOTHING,
        "budget currency: words after the amount that are not a currency",
        budget_outcome=Decimal("120"),
    ),
)

CASES = (*CORE, *HELD_OUT, *DOES_NOT_RUN, *CATEGORY, *BUDGET_CURRENCY)
# The English name of the synonym pair stays out of the prompt as well.
HELD_OUT_TERMS = (
    *(case.held_out_term for case in CASES if case.held_out_term is not None),
    "vacuum",
)
