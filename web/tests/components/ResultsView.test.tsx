import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, test } from "vitest";

import { OptionSheets } from "../../components/OptionSheets";
import { ResultsView } from "../../components/ResultsView";
import type { FigureLine, Line, ReportLines, TrailLine } from "../../lib/api/types";
import { deckOrder, plainTrail } from "../../lib/results";
import {
  ANSWERS_HEADING,
  EVIDENCE_HEADING,
  HIDE_OVER_BUDGET,
  OPTIONS_STRIP,
  RESULTS_HEADING,
  ROUTE_CO2E,
  ROUTE_OPTIONS,
  ROUTE_QUESTIONS,
  ROUTE_REQUEST,
  SHIPPING_TIP,
  SHIPPING_TIP_LABEL,
} from "../../lib/wording";
import {
  GREENCHEF,
  NO_BUDGET_LINES,
  NO_BUDGET_REPORT,
  THREE_LINES,
  THREE_REPORT,
  WMF,
} from "../lib/report_samples";

/** The words a page shows, without its markup. */
function textOf(markup: string): string {
  return markup
    .replace(/<[^>]+>/g, "")
    .replaceAll("&quot;", '"')
    .replaceAll("&#x27;", "'")
    .replaceAll("&amp;", "&");
}

function words(line: Line): string {
  return line.parts.map((part) => (part.kind === "control" ? "" : part.text)).join("");
}

/** Every line of the report the page shows, each figure as its label and its value. */
function shownLines(lines: ReportLines): string[] {
  const figures = (figure: FigureLine | null) =>
    figure === null ? [] : [words(figure.label), words(figure.value)];
  const optional = (line: Line | null) => (line === null ? [] : [words(line)]);
  return [
    ...optional(lines.evidence_summary),
    ...lines.caveats.map(words),
    ...lines.warnings.map((warning) => words(warning.line)),
    ...lines.stated.map(words),
    ...lines.typical_costs.map(words),
    ...lines.check.groups.flatMap((group) => [words(group.label), ...group.items.map(words)]),
    ...optional(lines.check.confirm_price),
    ...lines.options.flatMap((option) => [
      words(option.name),
      ...figures(option.price),
      ...optional(option.shipping),
      ...optional(option.price_seen),
      ...option.factor_values.flatMap((value) => figures(value.figure)),
      ...figures(option.lifespan),
      ...option.rests_on.flatMap(figures),
      ...option.rests_on_state.map(words),
      ...figures(option.recurring_cost),
      ...figures(option.cost_per_year),
      ...figures(option.cost_per_use),
      ...figures(option.purchases),
      ...figures(option.horizon_cost),
      ...figures(option.co2e),
      ...figures(option.built_from),
      ...figures(option.co2e_less),
      ...option.marks.map(words),
      ...optional(option.over_budget),
    ]),
    ...lines.trail.filter((line) => line.agent !== "second_hand").map(trailWords),
  ];
}

/** The route line's stations in order: each one's name, its state, the id of the part of the
 * trail it opens, and whether that part is open. */
function stationsOf(markup: string) {
  const route = markup.match(/<ol[^>]*data-route[^>]*>[\s\S]*?<\/ol>/)?.[0] ?? "";
  return [...route.matchAll(/<li[^>]*data-state="([^"]+)"[^>]*>[\s\S]*?<\/li>/g)].map(
    ([station, state]) => ({
      name: textOf(station),
      state,
      opens: station.match(/aria-controls="([^"]+)"/)?.[1] ?? "",
      open: station.match(/aria-expanded="([^"]+)"/)?.[1] === "true",
    }),
  );
}

/** The part of the trail with this id: whether it is hidden, and each of its lines' words. */
function partOf(markup: string, id: string) {
  const at = markup.indexOf(`id="${id}"`);
  const part = markup.slice(markup.lastIndexOf("<", at), markup.indexOf("</ol>", at));
  return {
    hidden: /^<[^>]*hidden=""/.test(part),
    lines: [...part.matchAll(/<li[^>]*>([\s\S]*?)<\/li>/g)].map(([, line]) => textOf(line)),
  };
}

/** A trail line's words as the panel shows them: what it says, in the page's words. */
function trailWords({ line }: TrailLine): string {
  return words(plainTrail(line));
}

const page = renderToStaticMarkup(<ResultsView report={THREE_REPORT} lines={THREE_LINES} />);

describe("the results page", () => {
  test("shows every line of a report with every field filled", () => {
    const shown = textOf(page);

    expect(shownLines(THREE_LINES).filter((line) => !shown.includes(line))).toEqual([]);
  });

  test("sets the route line above the options, every station ticked", () => {
    expect(stationsOf(page).map(({ name, state }) => [name, state])).toEqual([
      [ROUTE_REQUEST, "done"],
      [ROUTE_QUESTIONS, "done"],
      [ROUTE_OPTIONS, "done"],
      [ROUTE_CO2E, "done"],
    ]);
    expect(page.indexOf("data-route")).toBeLessThan(page.indexOf(RESULTS_HEADING));
  });

  test("has each station open its agent's part of the trail, every line but second-hand's", () => {
    const [supervisor, category, factor, searched, excluded, estimated, used] = THREE_LINES.trail;
    const parts = stationsOf(page).map(({ name, opens }) => [name, partOf(page, opens).lines]);

    expect(parts).toEqual([
      [ROUTE_REQUEST, [trailWords(supervisor)]],
      [ROUTE_QUESTIONS, [trailWords(category), trailWords(factor)]],
      [ROUTE_OPTIONS, [trailWords(searched), trailWords(excluded)]],
      [ROUTE_CO2E, [trailWords(estimated)]],
    ]);
    expect(textOf(page)).not.toContain(words(used.line));
  });

  test("leads with what the options save, above the sheets, by their letters", () => {
    const [baseline] = THREE_LINES.options;
    const named: ReportLines = {
      ...THREE_LINES,
      options: THREE_LINES.options.map((option) =>
        option.savings === null
          ? option
          : {
              ...option,
              savings: {
                parts: [
                  {
                    kind: "text",
                    text: `Over 10 years: ${words(option.name)} costs €44.92 less than ${words(baseline.name)}.`,
                  },
                ],
              },
            },
      ),
    };
    const markup = renderToStaticMarkup(<ResultsView report={THREE_REPORT} lines={named} />);
    const above = textOf(markup.slice(0, markup.indexOf("data-sheet=")));

    expect(above).toMatch(/Option [BC] costs €44\.92 less than Option A\./);
  });

  test("sets each sheet's letter over its name", () => {
    const [first, second] = page.split("data-sheet=").slice(1);

    expect(textOf(first)).toContain("Option A");
    expect(textOf(second)).toContain("Option B");
  });

  test("names no agent, tier or model in the trail", () => {
    const shown = textOf(page);

    THREE_LINES.trail.forEach(({ by }) => expect(shown).not.toContain(words(by)));
    expect(shown).not.toContain("LCA");
  });

  test("opens with every part of the trail closed", () => {
    const stations = stationsOf(page);

    expect(stations.map(({ open }) => open)).toEqual(Array(4).fill(false));
    expect(stations.map(({ opens }) => partOf(page, opens).hidden)).toEqual(Array(4).fill(true));
  });

  test("lays the options out as sheets and as a deck", () => {
    expect(page.match(/data-sheet=/g)).toHaveLength(3);
    expect(page.match(/data-card=/g)).toHaveLength(1);
  });

  test("marks the option over the budget and offers the switch, off", () => {
    expect(textOf(page)).toContain("Over your budget");
    expect(page).toContain(`role="switch" aria-checked="false"`);
    expect(textOf(page)).toContain(HIDE_OVER_BUDGET);
  });

  test("with no budget has no mark and no switch", () => {
    const unbudgeted = renderToStaticMarkup(
      <ResultsView report={NO_BUDGET_REPORT} lines={NO_BUDGET_LINES} />,
    );

    expect(textOf(unbudgeted)).not.toContain("Over your budget");
    expect(unbudgeted).not.toContain(`role="switch"`);
  });

  test("puts a closed shipping tooltip beside every shipping line", () => {
    const tips = page.match(new RegExp(`aria-label="${SHIPPING_TIP_LABEL}"`, "g"));

    // Three sheets and the deck's one card.
    expect(tips).toHaveLength(4);
    expect(page).not.toContain('aria-expanded="true"');
    expect(textOf(page.match(/<p[^>]*hidden=""[^>]*>([^<]*)</)?.[1] ?? "")).toBe(SHIPPING_TIP);
  });
});

describe("the deck", () => {
  test("pins a strip of each option's name and cost per year, the baseline first", () => {
    const strip = page.match(
      new RegExp(`<ol[^>]*aria-label="${OPTIONS_STRIP}"[^>]*>[\\s\\S]*?</ol>`),
    )?.[0];
    // The wide screen's Cards view shows the cost over the years in place of the cost per year.
    const onAPhone = textOf((strip ?? "").replace(/<span class="hidden[^>]*>.*?<\/span>/g, ""));

    expect(onAPhone).toBe(
      "GreenChef Soft Grip Pro 28 cm€19.50" +
        "WMF Profi Resist 28 cm€13.50" +
        "de Buyer Mineral B Element 28 cm€18.50",
    );
  });

  test("keeps the address on its card, where the sheets leave it to the name", () => {
    const [{ link }] = deckOrder(THREE_LINES.options, THREE_REPORT);
    const sheets = page.slice(page.indexOf("data-sheet="), page.indexOf("data-card="));

    expect(link).not.toBeNull();
    const card = page.slice(page.indexOf("data-card="));
    expect(textOf(card)).toContain("bol.com");
    expect(textOf(card)).not.toContain(words(link!.value));
    expect(textOf(sheets)).not.toContain(words(link!.label));
  });

  test("starts on the baseline's card, its place among the cards beside the steps", () => {
    const card = page.match(/<article[^>]*data-card="([^"]+)"/)?.[1];

    expect(card).toBe("greenchef");
    expect(textOf(page)).toContain("1 of 3");
  });
});

describe("a sheet without a group's figures", () => {
  const bare = { ...GREENCHEF, rests_on: [], rests_on_state: [], factor_values: [] };
  const sheets = textOf(
    renderToStaticMarkup(
      <OptionSheets options={[WMF, bare]} columns={2} letters={new Map()} judgements={new Map()} />,
    ),
  );

  test("leaves its row empty, with no heading over nothing", () => {
    expect(sheets.split(EVIDENCE_HEADING)).toHaveLength(2);
    expect(sheets.split(ANSWERS_HEADING)).toHaveLength(2);
  });
});
