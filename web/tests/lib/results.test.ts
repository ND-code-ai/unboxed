import { describe, expect, test } from "vitest";

import type { Line, OptionLines, TrailLine } from "../../lib/api/types";
import {
  amountIn,
  deckOrder,
  judgementsOf,
  leadOf,
  unconfirmedLine,
  lettersOf,
  offersBudgetSwitch,
  plainTrail,
  rowsOf,
  savingsOf,
  sheetRowsOf,
  shownOptions,
  trailPart,
} from "../../lib/results";
import {
  DE_BUYER,
  GREENCHEF,
  NO_BUDGET_REPORT,
  THREE_LINES,
  THREE_REPORT,
  WMF,
  comparedReport,
  optionLines,
} from "./report_samples";

const ids = (options: { option_id: string }[]) => options.map((option) => option.option_id);

describe("a station's part of the trail", () => {
  test("holds its agent's lines, in the order they were written", () => {
    const [, category, factor] = THREE_LINES.trail;

    expect(trailPart(THREE_LINES.trail, "brief")).toEqual([category, factor]);
  });

  test("is empty for an agent that wrote no line", () => {
    expect(trailPart(THREE_LINES.trail.slice(0, 1), "lca")).toEqual([]);
  });
});

describe("a trail line in the page's words", () => {
  const said = (text: string): Line => ({ parts: [{ kind: "text", text }] });

  test("says CO2e where the API says LCA tier 3", () => {
    expect(plainTrail(said('decided: LCA tier 3 estimated "A pan": 2 materials'))).toEqual(
      said('Estimated the CO2e of "A pan": 2 materials'),
    );
    expect(plainTrail(said('excluded: LCA tier 3 gave no estimate for "A pan"'))).toEqual(
      said('No CO2e estimate for "A pan"'),
    );
  });

  test("drops the kind of entry it opens with, and the API's other terms", () => {
    expect(plainTrail(said("found: Searched pans; 3 results"))).toEqual(
      said("Searched pans; 3 results"),
    );
    expect(plainTrail(said("decided: Understood as: frying pan; scope tuned; budget €50"))).toEqual(
      said("Understood as: frying pan; budget €50"),
    );
    expect(plainTrail(said("excluded: Left out a pan; reason: not_recorded"))).toEqual(
      said("Left out a pan; reason: not recorded"),
    );
    expect(plainTrail(said("found: Judged &quot;Cook&apos;s &amp; Co&apos;s&quot;"))).toEqual(
      said("Judged &quot;Cook's & Co's&quot;"),
    );
  });

  test("cuts a link's words to its site, leaving where it goes", () => {
    const url = "https://www.beslist.nl/p/pan?aff_id=908";

    expect(plainTrail({ parts: [{ kind: "link", text: url, url }] })).toEqual({
      parts: [{ kind: "link", text: "beslist.nl", url }],
    });
  });
});

describe("an option's unconfirmed answers", () => {
  const figure = (label: string, value: string) => ({
    label: { parts: [{ kind: "text" as const, text: label }] },
    value: { parts: [{ kind: "text" as const, text: value }] },
    missing: false,
  });
  const option = (values: ReturnType<typeof figure>[]): OptionLines => ({
    ...THREE_LINES.options[0],
    factor_values: values.map((each, index) => ({ factor_id: `f${index}`, figure: each })),
  });
  const notConfirmed = "could not be confirmed";

  test("fold into one line", () => {
    expect(
      unconfirmedLine(
        option([
          figure("Interior material", notConfirmed),
          figure("Temperature control", notConfirmed),
          figure("Hob", "induction"),
        ]),
      ),
    ).toBe("Interior material, temperature control: not confirmed on the pages read");
  });

  test("leave no line when every answer is confirmed", () => {
    expect(unconfirmedLine(option([figure("Hob", "induction")]))).toBeNull();
  });

  test("take one row for all, a confirmed answer keeping its own", () => {
    const rows = rowsOf([
      option([figure("Interior material", notConfirmed), figure("Hob", "induction")]),
    ]);
    const answers = rows.filter((row) => row.factorId !== undefined || row.field === "unconfirmed");

    expect(answers.map((row) => row.factorId ?? row.field)).toEqual(["f1", "unconfirmed"]);
    expect(answers.map((row) => row.heading)).toEqual(["answers", null]);
  });

  test("head the group when no answer is confirmed", () => {
    const row = rowsOf([option([figure("Interior material", notConfirmed)])]).find(
      ({ field }) => field === "unconfirmed",
    );

    expect(row).toMatchObject({ rule: true, heading: "answers" });
  });
});

describe("what the model read of an option's durability", () => {
  const named = (option_id: string, name: string): OptionLines => ({
    ...THREE_LINES.options[0],
    option_id,
    // Linked to its page, as on a real report.
    name: { parts: [{ kind: "link", text: name, url: "https://www.beslist.nl/p/pan" }] },
  });
  const line = (text: string): TrailLine => ({
    agent: "tco",
    by: { parts: [{ kind: "text", text: "tco" }] },
    line: { parts: [{ kind: "text", text }] },
  });
  const judged = "the model's judgement, not a sourced figure";

  test("is the reason from its product page, over the one from its name", () => {
    const trail = [
      line(`found: Judged "Pan" by its name: long (steel), ${judged}`),
      line(`found: Judged "Pan" by its product page: long (carbon steel, no coating), ${judged}`),
    ];

    expect(judgementsOf(trail, [named("one", "Pan")]).get("one")).toBe("carbon steel, no coating");
  });

  test("falls back to the name, and is missing when no reason was given", () => {
    const trail = [
      line(`found: Judged "Pan" by its name: long (steel (solid)), ${judged}`),
      line(`found: Judged "Kettle" by its name: unknown, ${judged}`),
    ];
    const read = judgementsOf(trail, [named("one", "Pan"), named("two", "Kettle")]);

    expect(read.get("one")).toBe("steel (solid)");
    expect(read.has("two")).toBe(false);
  });
});

describe("the sheets' rows", () => {
  test("go from the price to the cost per year, the address and the savings left out", () => {
    const fields = sheetRowsOf(THREE_LINES.options).map((row) => row.field);

    expect(fields.slice(0, 4)).toEqual(["name", "price", "cost_per_year", "horizon_cost"]);
    expect(fields).not.toContain("link");
    expect(fields).not.toContain("savings");
  });

  test("leave the card's rows in their own order", () => {
    const fields = rowsOf(THREE_LINES.options).map((row) => row.field);

    expect(fields.slice(0, 4)).toEqual(["name", "price", "link", "cost_per_year"]);
    expect(fields).toContain("savings");
  });
});

describe("what the options save", () => {
  test("is each shown option's savings line, in order", () => {
    const saved = THREE_LINES.options.flatMap(({ savings }) => (savings === null ? [] : [savings]));

    expect(savingsOf(THREE_LINES.options)).toEqual(saved);
    expect(saved.length).toBeGreaterThan(0);
  });

  test("finds the amount in a savings sentence, its words untouched", () => {
    expect(amountIn("Over 10 years: A costs €1,205.98 less than B.")).toEqual({
      before: "Over 10 years: A costs ",
      amount: "€1,205.98 less",
      after: " than B.",
    });
  });

  test("finds none in a sentence without one", () => {
    expect(amountIn("Over 10 years: the same.")).toBeNull();
  });
});

describe("the options' letters", () => {
  const named = (option_id: string, name: string, savings: string | null): OptionLines => ({
    ...THREE_LINES.options[0],
    option_id,
    name: { parts: [{ kind: "text", text: name }] },
    savings: savings === null ? null : { parts: [{ kind: "text", text: savings }] },
  });
  const rough = "A lifespan behind this is a rough estimate.";
  const all = [
    named("one", "Tefal", null),
    named("two", "Tefal Pro", `Over 10 years: Tefal Pro costs €5 more than Tefal. ${rough}`),
    named("three", "WMF", `Over 10 years: WMF costs €9 less than Tefal. ${rough}`),
  ];

  test("run in the report's order", () => {
    expect([...lettersOf(all).values()]).toEqual(["Option A", "Option B", "Option C"]);
  });

  test("name the options in the lead, a name inside another left whole", () => {
    expect(leadOf(all, all).sentences).toEqual([
      "Over 10 years: Option B costs €5 more than Option A.",
      "Over 10 years: Option C costs €9 less than Option A.",
    ]);
  });

  test("stay with an option the switch keeps, the baseline it hides named too", () => {
    expect(leadOf(all.slice(2), all).sentences).toEqual([
      "Over 10 years: Option C costs €9 less than Option A.",
    ]);
  });

  test("leave the note on rough estimates once, only when a line has it", () => {
    expect(leadOf(all, all).rough).toBe(rough);
    expect(leadOf(all.slice(0, 1), all)).toEqual({ sentences: [], rough: null });
  });
});

describe("the budget switch", () => {
  test("is offered when one option is over the budget and another within it", () => {
    expect(offersBudgetSwitch(THREE_REPORT)).toBe(true);
  });

  test.each([
    ["no budget", NO_BUDGET_REPORT],
    ["every option within it", comparedReport({ wmf: true, greenchef: true })],
    ["every option over it", comparedReport({ wmf: false, greenchef: false })],
    ["one over, the others unknown", comparedReport({ wmf: false, greenchef: null })],
  ])("is not offered with %s", (_, report) => {
    expect(offersBudgetSwitch(report)).toBe(false);
  });

  test("off, shows every option", () => {
    expect(ids(shownOptions(THREE_LINES.options, THREE_REPORT, false))).toEqual([
      "wmf",
      "greenchef",
      "de-buyer",
    ]);
  });

  test("on, hides the options over the budget", () => {
    expect(ids(shownOptions(THREE_LINES.options, THREE_REPORT, true))).toEqual([
      "wmf",
      "greenchef",
    ]);
  });

  test("never hides an option whose within-budget value is unknown", () => {
    const report = comparedReport({ wmf: true, greenchef: null, "de-buyer": false });

    expect(ids(shownOptions(THREE_LINES.options, report, true))).toEqual(["wmf", "greenchef"]);
  });
});

describe("the deck", () => {
  test("starts with the baseline, then keeps the API's order", () => {
    expect(ids(deckOrder([WMF, DE_BUYER, GREENCHEF], THREE_REPORT))).toEqual([
      "greenchef",
      "wmf",
      "de-buyer",
    ]);
  });

  test("keeps the API's order when the baseline is hidden or there is none", () => {
    expect(ids(deckOrder([WMF, DE_BUYER], THREE_REPORT))).toEqual(["wmf", "de-buyer"]);
  });
});

describe("the rows the sheets line up", () => {
  test("are every figure some option has, in the sheet's order, a factor per row", () => {
    const bare = optionLines("bare", "Bare pan", {
      shipping: null,
      price_seen: null,
      link: null,
      factor_values: [],
      rests_on: [],
      rests_on_state: [],
      recurring_cost: null,
      built_from: null,
      co2e_less: null,
      marks: [],
      savings: null,
    });

    expect(rowsOf([bare]).map((row) => row.key)).toEqual([
      "name",
      "price",
      "cost_per_year",
      "cost_per_use",
      "purchases",
      "horizon_cost",
      "lifespan",
      "co2e",
    ]);
    expect(rowsOf([bare, WMF]).map((row) => row.key)).toEqual([
      "name",
      "price",
      "link",
      "cost_per_year",
      "cost_per_use",
      "recurring_cost",
      "purchases",
      "horizon_cost",
      "savings",
      "lifespan",
      "evidence",
      "factor:hob",
      "co2e",
      "built_from",
      "co2e_less",
    ]);
  });

  test("rule off each group, with a heading only where no figure's label names what follows", () => {
    const marked = rowsOf([WMF]).filter((row) => row.rule || row.heading !== null);

    expect(marked.map(({ key, rule, heading }) => [key, rule, heading])).toEqual([
      ["cost_per_year", true, null],
      ["lifespan", true, null],
      ["evidence", false, "evidence"],
      ["factor:hob", true, "answers"],
      ["co2e", true, null],
    ]);
  });
});
