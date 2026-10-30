/** A frying pan report of three options with every field of its lines filled, in the shapes the
 * API sends: the results page's sample. Words follow `wording.py`; the figures are written here. */

import type {
  ComparisonRow,
  FigureLine,
  Line,
  OptionLines,
  Report,
  ReportLines,
} from "../../lib/api/types";
import { FRYING_PAN, reportFor } from "./samples";

export function text(words: string): Line {
  return { parts: [{ kind: "text", text: words }] };
}

/** A line whose words end in a site, linked to its page. */
export function sited(words: string, site: string): Line {
  return {
    parts: [
      { kind: "text", text: `${words} (` },
      { kind: "link", text: site, url: `https://www.${site}/` },
      { kind: "text", text: ")" },
    ],
  };
}

export function figure(label: string, value: Line | string, missing = false): FigureLine {
  return { label: text(label), value: typeof value === "string" ? text(value) : value, missing };
}

const ROUGH = text("2 years (rough estimate)");

/** One option's lines with every field filled; `name` and `id` tell them apart. */
export function optionLines(
  id: string,
  name: string,
  more: Partial<OptionLines> = {},
): OptionLines {
  return {
    option_id: id,
    name: { parts: [{ kind: "link", text: name, url: `https://www.bol.com/${id}` }] },
    price: figure("Price", `€${id.length}9.99`),
    shipping: text("plus €2.99 shipping"),
    price_seen: text("price seen at bol. via kieskeurig.nl on 1 October 2026"),
    link: figure("Link", {
      parts: [
        { kind: "link", text: `https://www.bol.com/${id}`, url: `https://www.bol.com/${id}` },
      ],
    }),
    factor_values: [
      { factor_id: "hob", figure: figure("Hob compatibility", sited("induction", "bol.com")) },
    ],
    lifespan: figure("Lifespan", ROUGH),
    rests_on: [figure("Warranty", sited("2 years", "tefal.nl"))],
    rests_on_state: [text("Owner and tester reports not looked up")],
    recurring_cost: figure("Recurring cost", text("recurring costs not found"), true),
    cost_per_year: figure("Cost per year", `€1${id.length}.50`),
    cost_per_use: figure("Cost per use", "€0.09"),
    purchases: figure("Purchases over 10 years", "5"),
    horizon_cost: figure("Cost over 10 years", "€134.90"),
    co2e: figure("CO2e", {
      parts: [
        { kind: "text", text: "45 to 100 kg CO2e to make, over 10 years (" },
        { kind: "confidence", text: "AI synthetic estimate", basis: "estimate" },
        { kind: "text", text: ")" },
      ],
    }),
    built_from: figure("Built from (estimated)", "aluminium, typical, 1.1 kg"),
    co2e_less: figure("Against GreenChef", "2 to 8 kg CO2e less to make over 10 years"),
    marks: [text("Out of stock")],
    over_budget: null,
    savings: text("Over 10 years: this pan costs €44.92 less than GreenChef."),
    ...more,
  };
}

export const GREENCHEF = optionLines("greenchef", "GreenChef Soft Grip Pro 28 cm", {
  co2e_less: null,
  savings: null,
});
export const DE_BUYER = optionLines("de-buyer", "de Buyer Mineral B Element 28 cm", {
  over_budget: text("Over your budget"),
});
export const WMF = optionLines("wmf", "WMF Profi Resist 28 cm");

export function row(option_id: string, within_budget: boolean | null): ComparisonRow {
  return {
    option_id,
    cost_per_year: null,
    cost_per_use: null,
    purchases: null,
    horizon_cost: null,
    horizon_co2e_low: null,
    horizon_co2e_high: null,
    horizon_co2e_tier: null,
    savings: null,
    co2e_avoided_low: null,
    co2e_avoided_high: null,
    co2e_avoided_tier: null,
    missing_reasons: {},
    recurring_costs_not_found: false,
    recurring_cost_converted_from: null,
    within_budget,
  };
}

/** The report's data the page acts on: which option is the baseline, and which are within the
 * budget. The API's order is WMF, GreenChef, de Buyer; GreenChef is the baseline. */
export function comparedReport(within: Record<string, boolean | null>): Report {
  return {
    ...reportFor(FRYING_PAN),
    comparison: {
      baseline_option_id: "greenchef",
      rows: Object.entries(within).map(([id, fits]) => row(id, fits)),
    },
  };
}

export const THREE_REPORT = comparedReport({ wmf: true, greenchef: true, "de-buyer": false });

export const THREE_LINES: ReportLines = {
  declined: null,
  evidence_summary: text(
    "Lifespan sourced for 0 of 3 options. CO2e to make: AI synthetic estimate for 3.",
  ),
  caveats: [text("This category is one the app is tuned for; check the sources.")],
  warnings: [
    {
      code: "nothing_within_budget",
      option_id: null,
      line: text("Nothing found within €15; the cheapest option is €22."),
    },
  ],
  stated: [text('From your request: Usage frequency: A few times a week ("a few times a week")')],
  typical_costs: [sited("Seasoning oil: typically €6 a year", "stub.invalid")],
  options: [WMF, GREENCHEF, DE_BUYER],
  check: {
    groups: [
      {
        label: text("Not yet known"),
        items: [text("Hob compatibility: Not every pan works on every hob.")],
      },
    ],
    confirm_price: text("Confirm the current price: Prices change after the day each was seen."),
  },
  trail: [
    {
      agent: "supervisor",
      by: text("supervisor [small, nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B]"),
      line: text("decided: Understood as: frying pan; scope tuned; budget €50"),
    },
    {
      agent: "brief",
      by: text("brief"),
      line: text("found: Category research for frying pan from the cache"),
    },
    {
      agent: "brief",
      by: text("brief [medium, nvidia/nemotron-3-super-120b-a12b]"),
      line: sited('found: Factor "Material" (requirement), stated by a tester', "tasteofhome.com"),
    },
    {
      agent: "tco",
      by: text("tco"),
      line: text('found: Searched "koekenpan kopen": 8 results, from the cache'),
    },
    {
      agent: "tco",
      by: text("tco [medium, nvidia/nemotron-3-super-120b-a12b]"),
      line: text('excluded: Left out "Tefal Trattoria Braadpan"; reason: not a koekenpan'),
    },
    {
      agent: "lca",
      by: text("lca [large, nvidia/Nemotron-3-Ultra-550b-a55b]"),
      line: text('decided: LCA tier 3 estimated "WMF Profi Resist 28 cm": 2 materials'),
    },
    {
      agent: "second_hand",
      by: text("second_hand"),
      line: text("decided: Stub: used listings are not searched yet"),
    },
  ],
};

/** The same report with no budget: nothing is marked, and nothing is within or over. */
export const NO_BUDGET_REPORT = comparedReport({ wmf: null, greenchef: null, "de-buyer": null });
export const NO_BUDGET_LINES: ReportLines = {
  ...THREE_LINES,
  options: [WMF, GREENCHEF, { ...DE_BUYER, over_budget: null }],
};
