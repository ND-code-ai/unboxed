/**
 * The results page's data shaping (GLOSSARY.md, "Results page"): which options show under the
 * budget switch, the deck's order, the rows the label sheets line up, the savings that lead the
 * page, and each station's part of the trail. Every line comes from the API's `ReportLines`; this
 * only chooses and orders, and compares no figure itself.
 */

import type { Line, OptionLines, Report, TrailLine } from "./api/types";
import { lineText, shortLinks } from "./lines";
import type { Agent } from "./thread";
import {
  FACTOR_UNCONFIRMED,
  NOT_CONFIRMED_ON_PAGES,
  optionLetter,
  ROUGH_SAVINGS,
  TRAIL_PLAIN_WORDS,
} from "./wording";

/** The trail lines a station opens: its agent's, in the order they were written. */
export function trailPart(trail: TrailLine[], agent: Agent): TrailLine[] {
  return trail.filter((line) => line.agent === agent);
}

/** A trail line in the page's words: the API's own terms for a step, swapped for plain ones, and
 * without the kind of entry it opens with, as the words after it say what was done. */
export function plainTrail(line: Line): Line {
  return {
    ...line,
    parts: shortLinks(line).parts.map((part) =>
      part.kind === "text" ? { ...part, text: plainWords(part.text) } : part,
    ),
  };
}

function plainWords(text: string): string {
  return TRAIL_PLAIN_WORDS.reduce(
    (said, [term, words]) => said.replaceAll(term, words),
    text,
  ).replace(TRAIL_KIND, "");
}

const TRAIL_KIND = /^(found|decided|excluded): /;

/** What each shown option saves over the baseline. */
export function savingsOf(options: OptionLines[]): Line[] {
  return options.flatMap((option) => (option.savings === null ? [] : [option.savings]));
}

/** Each option's letter by its id, in the report's order, so a letter stays with its option
 * whichever the budget switch hides. */
export function lettersOf(options: OptionLines[]): Map<string, string> {
  return new Map(options.map((option, index) => [option.option_id, optionLetter(index)]));
}

/** The results' lead on a wide screen, set above the sheets: each shown option's savings with the
 * options named by their letters, as long names are hard to read twice in a sentence, and the note
 * on rough estimates once, under them, in place of at the end of each. */
export function leadOf(
  shown: OptionLines[],
  all: OptionLines[],
): { sentences: string[]; rough: string | null } {
  const letters = lettersOf(all);
  // The longest first, so a name inside another does not break it.
  const names = all
    .map((option) => [lineText(option.name), letters.get(option.option_id) ?? ""] as const)
    .toSorted(([one], [other]) => other.length - one.length);
  const sentences = savingsOf(shown).map((line) =>
    names.reduce((said, [name, letter]) => said.replaceAll(name, letter), lineText(line)),
  );
  return {
    sentences: sentences.map((said) => said.replace(ROUGH_SAVINGS, "").trim()),
    rough: sentences.some((said) => said.includes(ROUGH_SAVINGS)) ? ROUGH_SAVINGS : null,
  };
}

// The amount in a savings line (`COSTS_LESS` and `COSTS_MORE` in `wording.py`).
const SAVED_AMOUNT = /€[\d.,]*\d (?:less|more)/;

/** A savings sentence's words around its amount, for emphasis alone; missing when it holds none. */
export function amountIn(words: string): { before: string; amount: string; after: string } | null {
  const found = SAVED_AMOUNT.exec(words);
  return found === null
    ? null
    : {
        before: words.slice(0, found.index),
        amount: found[0],
        after: words.slice(found.index + found[0].length),
      };
}

/** The ids of the options within the budget, and of those over it; an option whose value is
 * unknown is in neither. */
function budgetOf(report: Report): { within: Set<string>; over: Set<string> } {
  const rows = report.comparison?.rows ?? [];
  const ids = (fits: boolean) =>
    new Set(rows.filter((row) => row.within_budget === fits).map((row) => row.option_id));
  return { within: ids(true), over: ids(false) };
}

/** "Hide options over my budget" is offered only when it would hide one option and keep another:
 * with no budget nothing is over, and with every option over it would hide them all. */
export function offersBudgetSwitch(report: Report): boolean {
  const { within, over } = budgetOf(report);
  return within.size > 0 && over.size > 0;
}

/** The options shown: all of them, or with the switch on, all but those over the budget. */
export function shownOptions(
  options: OptionLines[],
  report: Report,
  hideOver: boolean,
): OptionLines[] {
  if (!hideOver) {
    return options;
  }
  const { over } = budgetOf(report);
  return options.filter((option) => !over.has(option.option_id));
}

/** The deck's cards: the baseline first, then the others in the API's order. */
export function deckOrder(options: OptionLines[], report: Report): OptionLines[] {
  const baseline = report.comparison?.baseline_option_id ?? null;
  return [
    ...options.filter((option) => option.option_id === baseline),
    ...options.filter((option) => option.option_id !== baseline),
  ];
}

/** A figure of a sheet that has its own row. The name row also holds the marks, and the price
 * row the shipping and where the price was seen. */
export type Field =
  | "name"
  | "price"
  | "link"
  | "cost_per_year"
  | "cost_per_use"
  | "recurring_cost"
  | "purchases"
  | "horizon_cost"
  | "savings"
  | "lifespan"
  | "evidence"
  | "co2e"
  | "built_from"
  | "co2e_less"
  | "unconfirmed";

/** A heading the page gives a group whose figures no label of theirs names: what a lifespan rests
 * on, and the option's value for each factor the user answered. */
export type Heading = "evidence" | "answers";

/** One row of an option sheet (DESIGN.md, "Option Sheet"): a figure, or an option's value for one
 * factor.
 * `rule` opens a group; `heading` comes first in the row. */
export type SheetRow = { key: string; rule: boolean; heading: Heading | null } & (
  { field: Field; factorId?: never } | { field?: never; factorId: string }
);

/** A group of a sheet's figures, each with whether an option has it. */
type Group = [Field, (option: OptionLines) => boolean][];

// The groups of a sheet in order. The factors the user answered stand between the lifespan's
// group and the CO2e's.
const ALWAYS = () => true;
const TOP: Group = [
  ["name", ALWAYS],
  ["price", ALWAYS],
  ["link", (option) => option.link !== null],
];
const COST: Group = [
  ["cost_per_year", ALWAYS],
  ["cost_per_use", ALWAYS],
  ["recurring_cost", (option) => option.recurring_cost !== null],
  ["purchases", ALWAYS],
  ["horizon_cost", ALWAYS],
  ["savings", (option) => option.savings !== null],
];
const LIFESPAN: Group = [
  ["lifespan", ALWAYS],
  ["evidence", (option) => option.rests_on.length > 0 || option.rests_on_state.length > 0],
];
const CO2E: Group = [
  ["co2e", ALWAYS],
  ["built_from", (option) => option.built_from !== null],
  ["co2e_less", (option) => option.co2e_less !== null],
];

// The wide screen's sheets go from the price straight to what it comes to over the years: the name
// already opens the page, so the address has no row, and the savings lead the page instead.
const SHEET_TOP: Group = [
  ["name", ALWAYS],
  ["price", ALWAYS],
];
const SHEET_COST: Group = [
  ["cost_per_year", ALWAYS],
  ["horizon_cost", ALWAYS],
  ["purchases", ALWAYS],
  ["cost_per_use", ALWAYS],
  ["recurring_cost", (option) => option.recurring_cost !== null],
];

/** The factor an option's value could not confirm (`FACTOR_NOT_CONFIRMED` in `wording.py`). */
export function isUnconfirmed({ figure }: OptionLines["factor_values"][number]): boolean {
  return lineText(figure.value) === FACTOR_UNCONFIRMED;
}

/** The factors an option could not confirm, as one line in place of one row each; missing when it
 * confirmed them all. The full list stands on the check list. */
export function unconfirmedLine(option: OptionLines): string | null {
  const names = option.factor_values.filter(isUnconfirmed).map(({ figure }, index) => {
    const name = lineText(figure.label);
    return index === 0 ? name : name.toLowerCase();
  });
  return names.length === 0 ? null : `${names.join(", ")}: ${NOT_CONFIRMED_ON_PAGES}`;
}

/** What the model read of each option's durability on its product page, or else from its name, by
 * the option's id: the reason its trail line gives. The trail is the only place the page has it. */
export function judgementsOf(trail: TrailLine[], options: OptionLines[]): Map<string, string> {
  const said = trailPart(trail, "tco").map(({ line }) => plainWords(lineText(line)));
  const reasonOf = (name: string, how: string) => {
    const opening = `Judged "${name}" by its ${how}: `;
    const line = said.findLast((words) => words.startsWith(opening));
    return line?.slice(opening.length).match(JUDGED_REASON)?.[1];
  };
  return new Map(
    options.flatMap((option) => {
      const name = plainWords(lineText(option.name));
      const reason = reasonOf(name, "product page") ?? reasonOf(name, "name");
      return reason === undefined ? [] : [[option.option_id, reason] as const];
    }),
  );
}

// The reason in a judgement's trail line (`JUDGED` in `wording.py`): "long (its reason), the model's…".
const JUDGED_REASON = /^\w+ \((.+)\), the model's judgement/;

/** The rows of the wide screen's sheets (`rowsOf`), the true cost first. */
export function sheetRowsOf(options: OptionLines[]): SheetRow[] {
  return rowsOf(options, SHEET_TOP, SHEET_COST);
}

/** The rows of an option's card, or with other top and cost groups the sheets': every figure at
 * least one option has, in the sheet's order, so a figure stands level across the sheets and an
 * option without it leaves its row empty. */
export function rowsOf(options: OptionLines[], top = TOP, cost = COST): SheetRow[] {
  const present = (group: Group) =>
    group.filter(([, has]) => options.some(has)).map(([field]) => field);
  const opened = (fields: Field[]): SheetRow[] =>
    fields.map((field, index) => ({
      key: field,
      field,
      rule: index === 0,
      heading: field === "evidence" ? "evidence" : null,
    }));
  const confirmed = options.flatMap((option) =>
    option.factor_values.filter((value) => !isUnconfirmed(value)),
  );
  const factorIds = [...new Set(confirmed.map((value) => value.factor_id))];
  const folded = options.some((option) => unconfirmedLine(option) !== null);
  return [
    ...present(top).map((field) => ({ key: field, field, rule: false, heading: null })),
    ...opened(present(cost)),
    ...opened(present(LIFESPAN)),
    ...factorIds.map((factorId, index) => ({
      key: `factor:${factorId}`,
      factorId,
      rule: index === 0,
      heading: index === 0 ? ("answers" as const) : null,
    })),
    ...(folded
      ? [
          {
            key: "unconfirmed",
            field: "unconfirmed" as const,
            rule: factorIds.length === 0,
            heading: factorIds.length === 0 ? ("answers" as const) : null,
          },
        ]
      : []),
    ...opened(present(CO2E)),
  ];
}
