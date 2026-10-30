"use client";

import { cn } from "cn";
import { useId, useState } from "react";

import type { FigureLine, Line, OptionLines } from "@/lib/api/types";
import { shortLinks } from "@/lib/lines";
import { isUnconfirmed, unconfirmedLine, type Heading, type SheetRow } from "@/lib/results";
import {
  ANSWERS_HEADING,
  EVIDENCE_HEADING,
  MODEL_READING,
  SHIPPING_TIP,
  SHIPPING_TIP_LABEL,
  SHIPPING_TIP_MARK,
} from "@/lib/wording";

import { LineView } from "./LineView";

const HEADINGS: Record<Heading, string> = {
  evidence: EVIDENCE_HEADING,
  answers: ANSWERS_HEADING,
};

/** A figure's key, as a label's key is set: small capitals in muted. */
const KEY = "block text-[0.6875rem] font-semibold tracking-[0.06em] text-muted uppercase";

/** One option's rows, each in its cell: a sheet passes every row the sheets line up, leaving a
 * cell empty where the option has nothing; a card passes the option's own rows. From 1024 px its
 * letter stands over its name, as the lead names it. */
export function OptionRows({
  option,
  rows,
  letter,
  judgement,
}: {
  option: OptionLines;
  rows: SheetRow[];
  letter?: string;
  /** What the model read of its durability (`judgementsOf`). */
  judgement?: string;
}) {
  return rows.map((row) => (
    <div
      key={row.key}
      className={cn(
        "min-w-0 px-4 [overflow-wrap:anywhere]",
        row.field === "name" ? "pt-4 pb-1" : "pt-3",
        // A group opens on a thin rule: one sheet, not a stack of boxes.
        row.rule && "mt-3 border-t border-ink/25 pt-4",
        // From 1024 px the savings lead the page, whichever view is on.
        row.field === "savings" && "lg:hidden",
      )}
    >
      {row.field === "name" && letter !== undefined && (
        <p className="heading-overline mb-1.5 hidden lg:block">{letter}</p>
      )}
      <OptionCell option={option} row={row} judgement={judgement} />
    </div>
  ));
}

/** What one option shows in one row; nothing where it has nothing there, its heading included,
 * except that "Your answers" heads the first factor's row of any option with a factor value. */
function OptionCell({
  option,
  row,
  judgement,
}: {
  option: OptionLines;
  row: SheetRow;
  judgement?: string;
}) {
  const body =
    row.factorId === undefined ? fieldOf(option, row, judgement) : factorOf(option, row.factorId);
  const headed =
    row.heading === "answers"
      ? option.factor_values.length > 0
      : row.heading !== null && body !== null;
  return (
    <>
      {headed && row.heading !== null && (
        <p className="heading-overline mb-2">{HEADINGS[row.heading]}</p>
      )}
      {body}
    </>
  );
}

function factorOf(option: OptionLines, factorId: string) {
  const value = option.factor_values.find((each) => each.factor_id === factorId);
  return value === undefined || isUnconfirmed(value) ? null : <Figure figure={value.figure} />;
}

function fieldOf(option: OptionLines, { field }: SheetRow, judgement?: string) {
  switch (field) {
    case "name":
      return (
        <div className="grid gap-1.5">
          <p className="leading-snug font-bold">
            <LineView line={option.name} inline />
          </p>
          {option.over_budget !== null && (
            // A mark, not a second name: a plain paper tag on the label's 2 px ink edge.
            <p>
              <span className="inline-block border-2 border-ink px-2 py-0.5 font-semibold">
                <LineView line={option.over_budget} inline />
              </span>
            </p>
          )}
          {option.marks.map((mark, index) => (
            <LineView key={index} line={mark} />
          ))}
        </div>
      );
    case "price":
      return (
        <div className="grid gap-1">
          <Figure figure={option.price} lead />
          {option.shipping !== null && <ShippingLine line={option.shipping} />}
          {option.price_seen !== null && (
            <p className="text-sm text-muted">
              <LineView line={option.price_seen} inline />
            </p>
          )}
        </div>
      );
    case "evidence":
      return option.rests_on.length === 0 && option.rests_on_state.length === 0 ? null : (
        <div className="grid gap-2">
          {judgement !== undefined && (
            <div className="min-w-0">
              <span className={KEY}>{MODEL_READING}</span>
              <p>{judgement}</p>
            </div>
          )}
          {option.rests_on.map((item, index) => (
            <Figure key={index} figure={item} />
          ))}
          {option.rests_on_state.map((line, index) => (
            <p key={`state-${index}`} className="text-muted">
              <LineView line={line} inline />
            </p>
          ))}
        </div>
      );
    case "savings":
      return option.savings === null ? null : <LineView line={option.savings} />;
    case "link":
      // The site alone: the name above opens the same page.
      return option.link === null ? null : (
        <Figure figure={{ ...option.link, value: shortLinks(option.link.value) }} oneLine />
      );
    case "unconfirmed": {
      const line = unconfirmedLine(option);
      return line === null ? null : <p className="text-muted">{line}</p>;
    }
    case "recurring_cost":
    case "built_from": {
      const figure = option[field];
      return figure === null ? null : <Figure figure={figure} />;
    }
    case "co2e_less":
      return option.co2e_less === null ? null : <Figure figure={option.co2e_less} ownCase />;
    case "cost_per_year":
      return <Figure figure={option.cost_per_year} lead large />;
    case "horizon_cost":
    case "cost_per_use":
    case "purchases":
    case "lifespan":
      return <Figure figure={option[field]} lead />;
    case "co2e":
      return <Figure figure={option.co2e} lead ownCase />;
    case undefined:
      return null;
  }
}

/** A figure as a key over its value; a missing one shows the reason in its place, in muted. A
 * headline figure (`lead`: the price, the cost figures, the lifespan, the CO2e) is semibold, the
 * figures around it regular. From 1024 px the cost per year, the number the app is built around,
 * stands a size larger than the rest, and a key that names CO2e or an option (`ownCase`) keeps its
 * capitals as written. */
function Figure({
  figure,
  lead = false,
  oneLine = false,
  large = false,
  ownCase = false,
}: {
  figure: FigureLine;
  lead?: boolean;
  oneLine?: boolean;
  large?: boolean;
  ownCase?: boolean;
}) {
  return (
    <div className="min-w-0">
      <span className={cn(KEY, ownCase && "lg:normal-case")}>
        <LineView line={figure.label} inline />
      </span>
      <p
        className={cn(
          "tabular-nums",
          figure.missing ? "text-muted" : lead && "font-semibold",
          oneLine && "truncate",
          large && !figure.missing && "lg:text-[1.625rem] lg:leading-tight lg:font-bold",
        )}
      >
        <LineView line={figure.value} inline />
      </p>
    </div>
  );
}

/** The shipping its offer states, with a button that opens, on a tap or from the keyboard, the
 * note that shipping may not be what is paid; Escape closes it. */
function ShippingLine({ line }: { line: Line }) {
  const [open, setOpen] = useState(false);
  const tip = useId();
  return (
    <div>
      <p className="text-muted">
        <LineView line={line} inline />
        <button
          type="button"
          aria-label={SHIPPING_TIP_LABEL}
          aria-expanded={open}
          aria-controls={tip}
          onClick={() => setOpen((shown) => !shown)}
          onKeyDown={(event) => {
            if (event.key === "Escape") {
              setOpen(false);
            }
          }}
          className="ml-2 inline-grid size-6 place-items-center border-2 border-ink bg-paper align-middle text-xs leading-none font-bold text-ink transition-colors duration-150 hover:not-aria-expanded:bg-lip aria-expanded:bg-ink aria-expanded:text-paper"
        >
          {SHIPPING_TIP_MARK}
        </button>
      </p>
      <p id={tip} hidden={!open} className="mt-1.5 text-sm">
        {SHIPPING_TIP}
      </p>
    </div>
  );
}
