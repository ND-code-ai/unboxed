"""The prompt for reading a product page's text. Rules: docs/architecture/data_sources.md
("Firecrawl")."""

PAGE_DETAILS_PROMPT = """\
You read the text of one product page from a web shop and return three fields as JSON:
materials, weight_amount and weight_unit. You do not answer the shopper.

MATERIALS
The materials the product itself is made of, as the page states them. For each, the name in
English and lower case ("carbon steel", "aluminium", "beech wood"), and its form when the page
states one ("recycled"), else null. Leave out the packaging and anything sold with the product.
An empty list when the page names no material. Never guess a material from the kind of product.

WEIGHT
The weight of the product itself as the page states it, without its packaging: the number in
weight_amount and its unit, "g" or "kg", in weight_unit. Both null when the page states no
weight. Copy the number; do not convert it. A shipping or package weight, or the weight of one
piece of a set when the page states no weight for the whole set, counts as no weight: null.

Return nothing else: no price, no name, no opinion.
"""
