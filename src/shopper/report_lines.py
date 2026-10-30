"""The lines of a report, section by section and option by option, built by the line functions of
wording.py: every figure a label and a value (docs/adr/0008-api-sends-finished-lines.md).

The API sends them beside the report and the terminal app prints their text, so the page needs no
numeric field of `Report` to show a figure. Every number here is one `calc/` produced; this
module only formats. They are built when they are shown and never saved.
"""

from collections.abc import Sequence
from decimal import ROUND_CEILING, ROUND_FLOOR, Decimal
from urllib.parse import urlparse

from shopper import wording
from shopper.calc.comparison import lifespan_in_use
from shopper.calc.display import car_kilometres, euros, kilograms, years
from shopper.calc.evidence import options_counted
from shopper.config import CAR_CO2_GRAMS_PER_KM, CAR_CO2_SOURCE_URL, CAR_CO2_YEAR
from shopper.state import (
    Agent,
    Answer,
    AnswerStatus,
    Assumptions,
    CheckReason,
    ComparisonRow,
    DecisionFactor,
    DomainModel,
    DurabilityEvidence,
    FactorKind,
    FactorValue,
    Figure,
    FindingKind,
    FindingsState,
    Fit,
    LcaInput,
    LcaResult,
    ProductOption,
    RecurringCostState,
    Report,
    Request,
    Source,
    SourceKind,
    StatedIn,
    TrailEntry,
    WarningCode,
    WarrantyTerm,
)
from shopper.wording import (
    FigureLine,
    Line,
    LinkPart,
    Site,
    filled,
    text_line,
)

WEB_SCHEMES = frozenset({"http", "https"})


class FactorFigure(DomainModel):
    """An option's value for one decision factor."""

    factor_id: str
    figure: FigureLine


class WarningLine(DomainModel):
    """A warning's message as one text part, with its code and the option it is about."""

    code: WarningCode
    option_id: str | None = None
    line: Line


class OptionLines(DomainModel):
    """One option's block, in the terminal's order. `shipping` and `price_seen` are there only
    for a price from a web page; `savings` only for an option set against the baseline."""

    option_id: str
    name: Line
    price: FigureLine
    shipping: Line | None = None
    price_seen: Line | None = None
    link: FigureLine | None = None
    factor_values: tuple[FactorFigure, ...] = ()
    lifespan: FigureLine
    rests_on: tuple[FigureLine, ...] = ()
    rests_on_state: tuple[Line, ...] = ()
    recurring_cost: FigureLine | None = None
    cost_per_year: FigureLine
    cost_per_use: FigureLine
    purchases: FigureLine
    horizon_cost: FigureLine
    co2e: FigureLine
    built_from: FigureLine | None = None
    co2e_less: FigureLine | None = None
    marks: tuple[Line, ...] = ()
    over_budget: Line | None = None
    savings: Line | None = None


class CheckGroup(DomainModel):
    """The open factors under one label, each item one line."""

    label: Line
    items: tuple[Line, ...]


class CheckLines(DomainModel):
    """The check-before-you-buy list, report-wide; an empty group is left out, and
    `confirm_price` is none when no price is to be confirmed."""

    groups: tuple[CheckGroup, ...] = ()
    confirm_price: Line | None = None


class TrailLine(DomainModel):
    """One trail entry: `by` names the agent, its tier and its model; `line` is the rest."""

    agent: Agent
    by: Line
    line: Line


class ReportLines(DomainModel):
    """The lines of a report. A request that does not run has its decline only."""

    declined: Line | None = None
    evidence_summary: Line | None = None
    caveats: tuple[Line, ...] = ()
    warnings: tuple[WarningLine, ...] = ()
    stated: tuple[Line, ...] = ()
    typical_costs: tuple[Line, ...] = ()
    options: tuple[OptionLines, ...] = ()
    check: CheckLines = CheckLines()
    trail: tuple[TrailLine, ...] = ()


def report_lines_of(report: Report) -> ReportLines:
    """The lines of a `report` event and of a finished view."""
    declined = declined_line(report.request)
    if declined is not None:
        return ReportLines(declined=declined)
    return ReportLines(
        evidence_summary=evidence_summary_lines_of(report),
        caveats=caveat_lines_of(report),
        warnings=warning_lines_of(report),
        stated=stated_lines_of(report),
        typical_costs=typical_cost_lines_of(report.factors),
        options=option_lines_of(report),
        check=check_lines_of(report),
        trail=trail_lines_of(report),
    )


def declined_line(request: Request) -> Line | None:
    """The decline or the rephrase message of a request that does not run; none for one that
    runs."""
    has_link = request.product_url is not None
    return wording.request_not_run(request.scope, request.category, has_link=has_link)


def evidence_summary_lines_of(report: Report) -> Line:
    """The counts as one line. Thin evidence is shown, so a report with no options has it too."""
    counts = report.evidence_summary
    return wording.evidence_summary(
        sourced=counts.lifespans_sourced,
        total=options_counted(counts),
        user_set=counts.lifespans_user_set,
        published=counts.footprints_published,
        benchmark=counts.footprints_benchmark,
        model_estimate=counts.footprints_model_estimate,
        missing=counts.footprints_missing,
    )


def caveat_lines_of(report: Report) -> tuple[Line, ...]:
    return tuple(text_line(wording.CAVEATS[caveat.code]) for caveat in report.caveats)


def warning_lines_of(report: Report) -> tuple[WarningLine, ...]:
    return tuple(
        WarningLine(code=warning.code, option_id=warning.option_id, line=text_line(warning.message))
        for warning in report.warnings
    )


def stated_lines_of(report: Report) -> tuple[Line, ...]:
    return stated_answer_lines(report.answers, report.factors)


def stated_answer_lines(
    answers: Sequence[Answer], factors: Sequence[DecisionFactor]
) -> tuple[Line, ...]:
    """One line per answer the request states, as above the questions and on the report, then
    one per answer the reply gave, "not sure" included."""
    by_id = {factor.id: factor for factor in factors}
    worded = [answer for answer in answers if answer.factor_id in by_id and _has_phrase(answer)]
    return tuple(
        _stated_line(by_id[answer.factor_id], answer)
        for stated_in in (StatedIn.REQUEST, StatedIn.REPLY)
        for answer in worded
        if answer.stated_in is stated_in
    )


def typical_cost_lines_of(factors: Sequence[DecisionFactor]) -> tuple[Line, ...]:
    """One line per factor with a typical yearly cost, as above the questions and on the
    report; the figure is never used in an option's figures."""
    return tuple(
        wording.typical_cost(
            factor.name,
            euros(factor.typical_yearly_cost),
            factor.typical_yearly_cost_source.reference,
            factor.typical_yearly_cost_converted_from,
        )
        for factor in factors
        if factor.typical_yearly_cost is not None and factor.typical_yearly_cost_source is not None
    )


def option_lines_of(report: Report) -> tuple[OptionLines, ...]:
    """One block per option, in report order."""
    if report.comparison is None:
        return ()
    rows = {row.option_id: row for row in report.comparison.rows}
    savings = _savings(report)
    return tuple(
        _option(option, rows[option.id], report, savings.get(option.id))
        for option in report.options
    )


def check_lines_of(report: Report) -> CheckLines:
    """One item per open factor under its label, then one line, for every option, when any
    price is to be confirmed. The list is report-wide: an item goes on naming an option the
    page's budget switch hides."""
    groups = (
        CheckGroup(label=text_line(label), items=_open_factors(report, reason))
        for label, reason in (
            (wording.NOT_YET_KNOWN, CheckReason.UNANSWERED),
            (wording.NOT_CONFIRMED, CheckReason.UNVERIFIED),
        )
    )
    priced = any(item.reason is CheckReason.PRICE for item in report.check_before_you_buy)
    return CheckLines(
        groups=tuple(group for group in groups if group.items),
        confirm_price=wording.confirm_price() if priced else None,
    )


def trail_lines_of(report: Report) -> tuple[TrailLine, ...]:
    """One line per entry, in the order the agents wrote them."""
    return tuple(trail_line_of(entry) for entry in report.trail)


def trail_line_of(entry: TrailEntry) -> TrailLine:
    """Agent, tier and model; then kind, summary, and the reason and the source when present. A
    web source is a link whose words are its whole reference."""
    by = wording.trail_by(entry.agent.value, entry.model_tier, entry.model)
    source = None if entry.source is None else _web_link(entry.source.reference, entry.source)
    line = wording.trail_entry(entry.kind.value, entry.summary, reason=entry.reason, source=source)
    return TrailLine(agent=entry.agent, by=by, line=line)


def source_site(source: Source) -> Site:
    """The site a claim came from: its name linked to its source for a web address, else the
    name as words."""
    return _web_link(wording.site_name(source.reference), source)


def _web_link(text: str, source: Source) -> Site:
    """The words, linked to the source when it is a web address."""
    return LinkPart(text=text, url=source.reference) if _is_web(source) else text


def _is_web(source: Source) -> bool:
    return source.kind is SourceKind.URL and _is_web_address(source.reference)


def _is_web_address(url: str) -> bool:
    return urlparse(url).scheme in WEB_SCHEMES


def _has_phrase(answer: Answer) -> bool:
    """A stated answer, or a "not sure" read in the reply: an answer in the user's own words."""
    return answer.status is AnswerStatus.STATED or answer.stated_in is StatedIn.REPLY


def _stated_line(factor: DecisionFactor, answer: Answer) -> Line:
    phrase = answer.stated_phrase or ""
    value = answer.stated_value or ""
    from_reply = answer.stated_in is StatedIn.REPLY
    if answer.status is AnswerStatus.NOT_SURE:
        return wording.reply_not_sure(factor.name, phrase)
    if factor.kind is FactorKind.USAGE and answer.uses_per_year is not None:
        return wording.stated_usage(value, answer.uses_per_year, phrase, from_reply=from_reply)
    if _is_own(factor):
        return wording.stated_own(phrase, from_reply=from_reply)
    return wording.stated_answer(factor.name, value, phrase, from_reply=from_reply)


def _is_own(factor: DecisionFactor) -> bool:
    """A factor of the user's own, named by their phrase, which its lines quote (task 1.10)."""
    return factor.source is not None and factor.source.kind is SourceKind.USER


def _names(report: Report) -> dict[str, str]:
    """Each option's name by its id."""
    return {option.id: option.name for option in report.options}


def _open_factors(report: Report, reason: CheckReason) -> tuple[Line, ...]:
    """A factor's name and why, once per factor, with the options its items concern appended."""
    names = _names(report)
    items = [item for item in report.check_before_you_buy if item.reason is reason]
    return tuple(
        _open_factor(
            factor,
            [
                names[item.option_id]
                for item in items
                if item.factor_id == factor.id and item.option_id is not None
            ],
        )
        for factor in report.factors
        if any(item.factor_id == factor.id for item in items)
    )


def _open_factor(factor: DecisionFactor, options: Sequence[str]) -> Line:
    return wording.check_item(factor.name, factor.why, options, own=_is_own(factor))


def _savings(report: Report) -> dict[str, Line]:
    """Each option set against the baseline, by its id; none for savings missing or zero."""
    comparison = report.comparison
    if comparison is None or comparison.baseline_option_id is None:
        return {}
    names = _names(report)
    baseline_id = comparison.baseline_option_id
    rough = {option.id for option in report.options if _is_rough(option, report.assumptions)}
    return {
        row.option_id: wording.savings(
            report.assumptions.horizon_years,
            names[row.option_id],
            euros(abs(row.savings)),
            names[baseline_id],
            costs_less=row.savings > 0,
            rough=bool(rough & {row.option_id, baseline_id}),
        )
        for row in comparison.rows
        if row.option_id != baseline_id and row.savings
    }


def _option(
    option: ProductOption, row: ComparisonRow, report: Report, savings: Line | None
) -> OptionLines:
    """A missing figure keeps its line and shows the reason `calc/` gave for it.

    A missing price is that reason for cost per year, and a missing lifespan for the purchases.
    """
    horizon = str(report.assumptions.horizon_years)
    footprint = next((each for each in report.lca_results if each.option_id == option.id), None)
    row = _with_lifespan_reason(option, row, report.assumptions)
    rests_on, rests_on_state = _rests_on(option, report)
    priced, shipping, seen = _price(option)
    purchases = None if row.purchases is None else text_line(str(row.purchases))
    return OptionLines(
        option_id=option.id,
        name=_name(option),
        price=_figure(wording.PRICE_LABEL, priced, row, Figure.COST_PER_YEAR),
        shipping=shipping,
        price_seen=seen,
        link=_link(option),
        factor_values=_factor_values(option, report.factors),
        lifespan=_figure(
            wording.LIFESPAN_LABEL, _lifespan(option, report.assumptions), row, Figure.PURCHASES
        ),
        rests_on=rests_on,
        rests_on_state=rests_on_state,
        recurring_cost=_recurring_cost(option),
        cost_per_year=_figure(
            wording.COST_PER_YEAR_LABEL, _money(row.cost_per_year), row, Figure.COST_PER_YEAR
        ),
        cost_per_use=_figure(
            wording.COST_PER_USE_LABEL, _money(row.cost_per_use), row, Figure.COST_PER_USE
        ),
        purchases=_figure(
            filled(wording.PURCHASES_LABEL, horizon=horizon), purchases, row, Figure.PURCHASES
        ),
        horizon_cost=_figure(
            filled(wording.HORIZON_COST_LABEL, horizon=horizon),
            _money(row.horizon_cost),
            row,
            Figure.HORIZON_COST,
        ),
        co2e=_figure(
            wording.CO2E_LABEL,
            _co2e(option, row, footprint, report.assumptions.horizon_years),
            row,
            Figure.HORIZON_CO2E,
        ),
        built_from=_built_from(footprint),
        co2e_less=_co2e_less(row, report),
        marks=_marks(option, report),
        over_budget=text_line(wording.OVER_BUDGET) if row.within_budget is False else None,
        savings=savings,
    )


def _figure(
    label: str | Line, value: Line | None, row: ComparisonRow, blocked: Figure
) -> FigureLine:
    """The figure's label and value, or why it is missing."""
    label_line = text_line(label) if isinstance(label, str) else label
    if value is None:
        missing = wording.missing_figure(row.missing_reasons[blocked])
        return FigureLine(label=label_line, value=missing, missing=True)
    return FigureLine(label=label_line, value=value)


def _name(option: ProductOption) -> Line:
    """The option's name, linked to its page when it has one."""
    return _page_line(option.name, option.link)


def _link(option: ProductOption) -> FigureLine | None:
    """The option's page, its whole address the link's words."""
    if option.link is None:
        return None
    return FigureLine(
        label=text_line(wording.LINK_LABEL), value=_page_line(option.link, option.link)
    )


def _page_line(text: str, link: str | None) -> Line:
    """The words, linked to the option's page when it has a web address."""
    if link is None or not _is_web_address(link):
        return text_line(text)
    return Line(parts=(LinkPart(text=text, url=link),))


def _marks(option: ProductOption, report: Report) -> tuple[Line, ...]:
    """Out of stock, and sold incomplete with the baseline it is not set against."""
    stock = (text_line(wording.OUT_OF_STOCK),) if option.out_of_stock else ()
    if not option.incomplete:
        return stock
    baseline_id = None if report.comparison is None else report.comparison.baseline_option_id
    baseline = None if baseline_id is None else _names(report)[baseline_id]
    return (*stock, wording.sold_incomplete(baseline))


def _factor_values(
    option: ProductOption, factors: Sequence[DecisionFactor]
) -> tuple[FactorFigure, ...]:
    """One figure per factor value of the option, in the order of the decision factors."""
    values = {value.factor_id: value for value in option.factor_values}
    return tuple(
        FactorFigure(factor_id=factor.id, figure=_factor_value(factor, values[factor.id]))
        for factor in factors
        if factor.id in values
    )


def _factor_value(factor: DecisionFactor, value: FactorValue) -> FigureLine:
    """A `fails` on a care factor marks the option; on any other factor it is the linked
    product's mismatch, since every other option that fails an answer is removed."""
    own = _is_own(factor)
    if value.fit is Fit.UNVERIFIED or value.value is None:
        template = wording.FACTOR_NOT_CONFIRMED_OWN if own else wording.FACTOR_NOT_CONFIRMED
        return wording.factor_not_confirmed(template, factor.name)
    if value.fit is Fit.MEETS:
        template = wording.FACTOR_MEETS_OWN if own else wording.FACTOR_MEETS
    elif factor.kind is FactorKind.CARE:
        template = wording.FACTOR_CARE_NEEDED
    else:
        template = wording.FACTOR_MISMATCH_OWN if own else wording.FACTOR_MISMATCH
    source = value.source
    return wording.factor_value(
        template, factor.name, value.value, source_site(source), source.stated_by
    )


def _with_lifespan_reason(
    option: ProductOption, row: ComparisonRow, assumptions: Assumptions
) -> ComparisonRow:
    """With no lifespan, the figures it blocks say the evidence could not be read, so the user
    can set one: the evidence read is what gives every option a lifespan."""
    if lifespan_in_use(option, assumptions) is not None:
        return row
    blocked = row.missing_reasons.get(Figure.PURCHASES)
    reasons = {
        figure: wording.LIFESPAN_NOT_READ if reason == blocked else reason
        for figure, reason in row.missing_reasons.items()
    }
    return row.model_copy(update={"missing_reasons": reasons})


def _rests_on(
    option: ProductOption, report: Report
) -> tuple[tuple[FigureLine, ...], tuple[Line, ...]]:
    """What the lifespan rests on, one figure per item with its site, then the findings; and the
    lines for no evidence or no findings."""
    evidence = option.durability_evidence
    items = _evidence_items(evidence)
    findings = _findings(evidence)
    state = _findings_state(evidence)
    if not items and not findings and _is_rough(option, report.assumptions):
        return (), _bare_estimate(evidence, state)
    return (*items, *findings), state


def _bare_estimate(evidence: DurabilityEvidence, state: tuple[Line, ...]) -> tuple[Line, ...]:
    """A rough estimate with no item and no finding: one line says so, in place of the findings
    line when the reports were looked up; a failed search found nothing because nothing was
    looked at, so its line follows."""
    no_evidence = text_line(wording.NO_DURABILITY_EVIDENCE)
    if evidence.findings_state is FindingsState.NONE_FOUND:
        return (no_evidence,)
    return (no_evidence, *state)


def _evidence_items(evidence: DurabilityEvidence) -> tuple[FigureLine, ...]:
    """One figure per durability evidence item, with its site, then the type's typical
    lifespan."""
    warranty = evidence.warranty
    items: list[tuple[str, str, Source]] = []
    if warranty is not None:
        items.append((wording.WARRANTY_LABEL, _warranty(warranty.value), warranty.source))
    for label, item in (
        (wording.WEARS_LABEL, evidence.wear_material),
        (wording.REPAIRS_LABEL, evidence.repairability),
        (wording.CARE_LABEL, evidence.care),
    ):
        if item is not None:
            items.append((label, item.value, item.source))
    figures = [
        wording.evidence_item(label, value, source_site(source), source.stated_by)
        for label, value, source in items
    ]
    typical = evidence.typical_lifespan
    if typical is not None:
        # With no type its quote names, none is named: the category may be wider than the quote.
        figures.append(
            wording.typical_lifespan(
                typical.value.type or wording.UNNAMED_TYPE,
                years(typical.value.low, ROUND_FLOOR),
                years(typical.value.high, ROUND_CEILING),
                source_site(typical.source),
                typical.source.stated_by,
            )
        )
    return tuple(figures)


def _findings(evidence: DurabilityEvidence) -> tuple[FigureLine, ...]:
    """Tests first, then owner reports, each with its site."""
    ordered = sorted(evidence.findings, key=lambda each: each.kind is not FindingKind.TEST)
    return tuple(
        wording.finding(
            wording.FINDINGS_BY_KIND[each.kind],
            each.summary,
            source_site(each.source),
            rating=each.rating,
            review_count=each.review_count,
        )
        for each in ordered
    )


def _findings_state(evidence: DurabilityEvidence) -> tuple[Line, ...]:
    """With no findings, whether they were looked up."""
    if evidence.findings:
        return ()
    if evidence.findings_state is FindingsState.NONE_FOUND:
        return (text_line(wording.NO_FINDINGS_FOUND),)
    if evidence.findings_state is FindingsState.NOT_SEARCHED:
        return (text_line(wording.FINDINGS_NOT_SEARCHED),)
    return ()


def _warranty(term: WarrantyTerm) -> str:
    if term.years is None:
        return wording.LIMITED_LIFETIME_WARRANTY if term.limited else wording.LIFETIME_WARRANTY
    return _counted_years(term.years)


def _counted_years(value: Decimal) -> str:
    return wording.counted_years(years(value))


def _recurring_cost(option: ProductOption) -> FigureLine | None:
    """The recurring cost, only when it was looked for."""
    if option.recurring_cost_state is RecurringCostState.NOT_LOOKED_FOR:
        return None
    label = text_line(wording.RECURRING_COST_LABEL)
    cost, source = option.recurring_cost_per_year, option.recurring_cost_source
    if cost is None or source is None:
        not_found = text_line(wording.RECURRING_COSTS_NOT_FOUND)
        return FigureLine(label=label, value=not_found, missing=True)
    value = wording.recurring_cost(
        euros(cost),
        source.label or "",
        source_site(source),
        converted_from=option.recurring_cost_converted_from,
        others_left_out=option.other_consumables_left_out,
    )
    return FigureLine(label=label, value=value)


def _money(amount: Decimal | None) -> Line | None:
    return None if amount is None else text_line(euros(amount))


def _price(option: ProductOption) -> tuple[Line | None, Line | None, Line | None]:
    """The price and the size or variant it was quoted for; from a web page, also the shipping
    its offer states and where and when it was seen (its source's label names the shop)."""
    if option.price is None:
        return None, None, None
    shown = wording.price_shown(euros(option.price), option.price_variant)
    source, seen_on = option.price_source, option.price_seen_on
    if source is None or source.kind is not SourceKind.URL or seen_on is None:
        return shown, None, None
    seen = wording.price_seen_at(source_site(source), source.label, seen_on)
    return shown, text_line(_shipping(option.shipping)), seen


def _shipping(shipping: Decimal | None) -> str:
    if shipping is None:
        return wording.SHIPPING_NOT_STATED
    if not shipping:
        return wording.FREE_SHIPPING
    return wording.SHIPPING.format(amount=euros(shipping))


def _lifespan(option: ProductOption, assumptions: Assumptions) -> Line | None:
    """The lifespan the figures used: set by the user, a model estimate still in use marked as
    rough, or a sourced one with its site."""
    in_use = lifespan_in_use(option, assumptions)
    if in_use is None:
        return None
    shown = _counted_years(in_use)
    if option.id in assumptions.lifespan_overrides:
        return wording.lifespan_set_by_you(shown)
    if _is_rough(option, assumptions):
        return wording.rough_lifespan(shown)
    source = option.lifespan_source
    if source is not None and source.kind is SourceKind.URL:
        return wording.sourced_lifespan(shown, source_site(source), source.stated_by)
    return text_line(shown)


def _is_rough(option: ProductOption, assumptions: Assumptions) -> bool:
    """A model estimate the user has not replaced."""
    return (
        option.id not in assumptions.lifespan_overrides
        and option.lifespan_source is not None
        and option.lifespan_source.kind is SourceKind.MODEL_ESTIMATE
    )


def _co2e(
    option: ProductOption, row: ComparisonRow, footprint: LcaResult | None, horizon: int
) -> Line | None:
    """The range over the horizon with the label of its tier; with no lifespan, the range of
    making one with the result's. A figure of tier 1 or 2 names its source."""
    if footprint is None:
        return None
    pieces = (
        option.piece_count if option.piece_count is not None and option.piece_count > 1 else None
    )
    low, high, tier = row.horizon_co2e_low, row.horizon_co2e_high, row.horizon_co2e_tier
    horizon_shown: int | None = horizon
    if low is None or high is None or tier is None:
        low, high, tier, horizon_shown = (
            footprint.co2e_low,
            footprint.co2e_high,
            footprint.tier,
            None,
        )
    source = None if tier == 3 else source_site(footprint.source)
    return wording.co2e(
        kilograms(low, ROUND_FLOOR),
        kilograms(high, ROUND_CEILING),
        tier,
        horizon=horizon_shown,
        pieces=pieces,
        source=source,
    )


def _built_from(footprint: LcaResult | None) -> FigureLine | None:
    """The materials an estimate was built from, each part the model estimated marked; when it
    estimated every part, one mark after the label. Factors are never shown."""
    if footprint is None or not footprint.inputs:
        return None
    materials = [_parts(each) for each in footprint.inputs]
    every = all(estimated for parts in materials for _, estimated in parts)
    value = wording.built_from(
        [
            [
                wording.material_part(text, marked=estimated and not every)
                for text, estimated in parts
            ]
            for parts in materials
        ]
    )
    return FigureLine(label=wording.built_from_label(all_estimated=every), value=value)


def _parts(item: LcaInput) -> list[tuple[str, bool]]:
    """Name, form when there is one, and mass, each with whether the model estimated it. A
    component's form says nothing ("heating element, typical"), so it is left out."""
    form = (
        [(item.form, _estimated(item.form_source))]
        if item.form is not None and item.form_source is not None and not item.component
        else []
    )
    mass = wording.mass(kilograms(item.mass_kg))
    return [
        (item.name, _estimated(item.material_source)),
        *form,
        (mass, _estimated(item.mass_source)),
    ]


def _estimated(source: Source | None) -> bool:
    return source is not None and source.kind is SourceKind.MODEL_ESTIMATE


def _co2e_less(row: ComparisonRow, report: Report) -> FigureLine | None:
    """How much less the option takes to make than the baseline, only when that figure exists,
    with the weaker label of the two."""
    low, high, tier = row.co2e_avoided_low, row.co2e_avoided_high, row.co2e_avoided_tier
    comparison = report.comparison
    if low is None or high is None or tier is None or comparison is None:
        return None
    # A figure against the baseline exists only when there is a baseline.
    assert comparison.baseline_option_id is not None
    baseline = _names(report)[comparison.baseline_option_id]
    kilometres = car_kilometres(low, high, CAR_CO2_GRAMS_PER_KM)
    less = wording.co2e_less(
        kilograms(low, ROUND_FLOOR),
        kilograms(high, ROUND_CEILING),
        tier,
        report.assumptions.horizon_years,
        for_scale=(
            None
            if kilometres is None
            else wording.co2e_for_scale(*kilometres, CAR_CO2_YEAR, CAR_CO2_SOURCE_URL)
        ),
    )
    return FigureLine(label=filled(wording.AGAINST_LABEL, baseline=baseline), value=less)
