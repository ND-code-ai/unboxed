"""The report as plain lines for the terminal app: one pure function per section, each the text
of the section's lines in `report_lines.py`.

A section with nothing to show gives no lines. Order and words: docs/terminal_app.md ("The
report").
"""

from collections.abc import Iterable

from shopper import wording
from shopper.report_lines import (
    OptionLines,
    caveat_lines_of,
    check_lines_of,
    evidence_summary_lines_of,
    option_lines_of,
    stated_lines_of,
    trail_line_of,
    trail_lines_of,
    typical_cost_lines_of,
    warning_lines_of,
)
from shopper.state import Report, TrailEntry
from shopper.wording import FigureLine, Line, plain_text

# What goes before an indented line of an option block, and before an item of the check list.
INDENT = "  "
ITEM = "- "


def printed_report(report: Report) -> tuple[str, ...]:
    """Every section in its fixed order, with an empty line between those that have lines."""
    return _separated(
        section(report)
        for section in (
            evidence_summary_lines,
            caveat_lines,
            warning_lines,
            stated_lines,
            typical_cost_lines,
            option_lines,
            savings_lines,
            check_lines,
            trail_lines,
        )
    )


def evidence_summary_lines(report: Report) -> tuple[str, ...]:
    return (plain_text(evidence_summary_lines_of(report)),)


def caveat_lines(report: Report) -> tuple[str, ...]:
    return _texts(caveat_lines_of(report))


def warning_lines(report: Report) -> tuple[str, ...]:
    return tuple(plain_text(warning.line) for warning in warning_lines_of(report))


def stated_lines(report: Report) -> tuple[str, ...]:
    return _texts(stated_lines_of(report))


def typical_cost_lines(report: Report) -> tuple[str, ...]:
    return _texts(typical_cost_lines_of(report.factors))


def option_lines(report: Report) -> tuple[str, ...]:
    """One block of labelled lines per option, with an empty line between the blocks."""
    return _separated(_option_block(option) for option in option_lines_of(report))


def savings_lines(report: Report) -> tuple[str, ...]:
    """One line per option set against the baseline, in option order."""
    return tuple(
        plain_text(option.savings)
        for option in option_lines_of(report)
        if option.savings is not None
    )


def check_lines(report: Report) -> tuple[str, ...]:
    """Each group's label and its items, then the line on prices; nothing for an empty list."""
    check = check_lines_of(report)
    lines = (
        *(
            line
            for group in check.groups
            for line in (plain_text(group.label), *_items(group.items))
        ),
        *_items(() if check.confirm_price is None else (check.confirm_price,)),
    )
    return (wording.CHECK_HEADING, *lines) if lines else ()


def trail_lines(report: Report) -> tuple[str, ...]:
    """One line per entry, in the order the agents wrote them."""
    lines = tuple(_trail_text(line.by, line.line) for line in trail_lines_of(report))
    return (wording.TRAIL_HEADING, *lines) if lines else ()


def trail_line(entry: TrailEntry) -> str:
    """One trail entry as a line: agent, tier and model, kind, summary, reason and source."""
    line = trail_line_of(entry)
    return _trail_text(line.by, line.line)


def _trail_text(by: Line, line: Line) -> str:
    return f"{plain_text(by)} {plain_text(line)}"


def _option_block(option: OptionLines) -> tuple[str, ...]:
    """The option's lines in the terminal's order; the shipping and where the price was seen
    follow the price."""
    price = ", ".join(
        plain_text(line)
        for line in (option.price.value, option.shipping, option.price_seen)
        if line is not None
    )
    return (
        plain_text(option.name),
        f"{plain_text(option.price.label)}: {price}",
        *_figures(option.link),
        *(_figure(value.figure) for value in option.factor_values),
        _figure(option.lifespan),
        *(INDENT + _figure(figure) for figure in option.rests_on),
        *(INDENT + plain_text(line) for line in option.rests_on_state),
        *_figures(option.recurring_cost),
        _figure(option.cost_per_year),
        _figure(option.cost_per_use),
        _figure(option.purchases),
        _figure(option.horizon_cost),
        _figure(option.co2e),
        *(INDENT + line for line in _figures(option.built_from)),
        *_figures(option.co2e_less),
        *_texts(option.marks),
        *_texts(() if option.over_budget is None else (option.over_budget,)),
    )


def _figure(figure: FigureLine) -> str:
    return f"{plain_text(figure.label)}: {plain_text(figure.value)}"


def _figures(figure: FigureLine | None) -> tuple[str, ...]:
    return () if figure is None else (_figure(figure),)


def _texts(lines: Iterable[Line]) -> tuple[str, ...]:
    return tuple(plain_text(line) for line in lines)


def _items(lines: Iterable[Line]) -> tuple[str, ...]:
    return tuple(ITEM + plain_text(line) for line in lines)


def _separated(sections: Iterable[tuple[str, ...]]) -> tuple[str, ...]:
    """The sections that have lines, with one empty line between them."""
    filled = [section for section in sections if section]
    return tuple(
        line
        for index, section in enumerate(filled)
        for line in (section if index == 0 else ("", *section))
    )
