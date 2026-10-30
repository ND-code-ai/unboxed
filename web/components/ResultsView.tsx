"use client";

import { cn } from "cn";
import { useEffect, useId, useRef, useState } from "react";

import type { Line, ReportLines } from "@/lib/api/types";
import {
  amountIn,
  deckOrder,
  judgementsOf,
  leadOf,
  lettersOf,
  offersBudgetSwitch,
  shownOptions,
} from "@/lib/results";
import { ROUTE_DONE, type Agent, type Results } from "@/lib/thread";
import {
  CHECK_HEADING,
  HIDE_OVER_BUDGET,
  RESULTS_HEADING,
  VIEW_CARDS,
  VIEW_LABEL,
  VIEW_ROWS,
} from "@/lib/wording";

import { LineView } from "./LineView";
import { OptionDeck } from "./OptionDeck";
import { OptionSheets } from "./OptionSheets";
import { RouteLine, type Opener } from "./RouteLine";
import { TrailPanel } from "./TrailPanel";
import { Button } from "./ui/button";

type View = "rows" | "cards";

/** The results page (GLOSSARY.md, "Results page"): a view of the chat page that takes the field's
 * place when "See the comparison" is pressed in the opened box. The route line first, every
 * station ticked, each opening its agent's part of the trail under it; then the evidence summary,
 * caveats and warnings, the options, as sheets on a wide screen and as the deck on a phone, and the
 * report-wide check list. The trail starts closed, the budget switch off and the view on Rows each
 * time; none is remembered. */
export function ResultsView({ report, lines }: Results) {
  const [hideOver, setHideOver] = useState(false);
  const [view, setView] = useState<View>("rows");
  const [open, setOpen] = useState<Agent[]>([]);
  const heading = useId();
  const parts = useId();
  const opener: Opener = {
    open,
    partOf: (agent) => `${parts}-${agent}`,
    onToggle: (agent) =>
      setOpen((was) =>
        was.includes(agent) ? was.filter((each) => each !== agent) : [...was, agent],
      ),
  };
  const options = shownOptions(lines.options, report, hideOver);
  // Opened from the box by "See the comparison", which is gone once it is pressed: the page opens
  // at its top, under the wordmark, with the focus on it.
  const page = useRef<HTMLElement>(null);
  useEffect(() => {
    page.current?.focus({ preventScroll: true });
    window.scrollTo({ top: 0 });
  }, []);
  return (
    <section
      ref={page}
      tabIndex={-1}
      aria-labelledby={heading}
      // Focused to be read from here, not to be pressed: no frame round the whole page.
      className="grid content-start gap-6 outline-none"
    >
      {/* Where the route line stood under the box, as far below the wordmark. */}
      <div className="mt-5 grid min-h-[4.5rem] content-start gap-4 lg:mt-7">
        <RouteLine stations={ROUTE_DONE} opener={opener} />
        <TrailPanel stations={ROUTE_DONE} trail={lines.trail} open={open} partOf={opener.partOf} />
      </div>
      <div className="flex flex-wrap items-end justify-between gap-x-6 gap-y-3">
        <h2 id={heading} className="text-[1.3125rem] leading-snug font-bold">
          {RESULTS_HEADING}
        </h2>
        <div className="flex flex-wrap items-center gap-x-6 gap-y-3">
          {offersBudgetSwitch(report) && (
            <BudgetSwitch on={hideOver} onToggle={() => setHideOver((on) => !on)} />
          )}
          {lines.options.length > 1 && <ViewControl view={view} onView={setView} />}
        </div>
      </div>
      <ReportHead lines={lines} lead={leadOf(options, lines.options)} />
      {options.length > 0 && (
        <>
          <OptionSheets
            options={options}
            columns={lines.options.length}
            letters={lettersOf(lines.options)}
            judgements={judgementsOf(lines.trail, lines.options)}
            className={cn("hidden", view === "rows" && "lg:grid")}
          />
          <OptionDeck
            cards={deckOrder(options, report)}
            letters={lettersOf(lines.options)}
            judgements={judgementsOf(lines.trail, lines.options)}
            className={cn(view === "rows" && "lg:hidden")}
          />
        </>
      )}
      <CheckList lines={lines} />
    </section>
  );
}

/** "Hide options over my budget": a switch whose track inverts when it is on. */
function BudgetSwitch({ on, onToggle }: { on: boolean; onToggle: () => void }) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={on}
      onClick={onToggle}
      className="group inline-flex min-h-11 items-center gap-2.5 font-semibold"
    >
      <span
        aria-hidden="true"
        className="relative h-6 w-11 shrink-0 border-2 border-ink bg-paper transition-colors duration-150 group-hover:not-group-aria-checked:bg-lip group-aria-checked:bg-ink"
      >
        <span className="absolute top-0.5 left-0.5 size-4 bg-ink transition-[translate] duration-150 ease-out-expo group-aria-checked:translate-x-5 group-aria-checked:bg-paper motion-reduce:transition-none" />
      </span>
      {HIDE_OVER_BUDGET}
    </button>
  );
}

/** Rows or Cards, on a wide screen only: a phone always has the deck. */
function ViewControl({ view, onView }: { view: View; onView: (view: View) => void }) {
  return (
    <div role="group" aria-label={VIEW_LABEL} className="hidden gap-2 lg:flex">
      {(
        [
          ["rows", VIEW_ROWS],
          ["cards", VIEW_CARDS],
        ] as const
      ).map(([value, words]) => (
        <Button
          key={value}
          type="button"
          variant="chip"
          size="sm"
          aria-pressed={view === value}
          onClick={() => onView(value)}
        >
          {words}
        </Button>
      ))}
    </div>
  );
}

/** From 1024 px, what the options save, the page's lead: the price is only the start. Then how much
 * of the report rests on sources, and its caveats and warnings: report-wide, so they go on naming
 * an option the switch hides. */
function ReportHead({ lines, lead }: { lines: ReportLines; lead: ReturnType<typeof leadOf> }) {
  const said = [...lines.caveats, ...lines.warnings.map((warning) => warning.line)];
  if (lines.evidence_summary === null && said.length === 0 && lead.sentences.length === 0) {
    return null;
  }
  return (
    <div className="grid gap-1.5 border-2 border-ink bg-paper px-5 py-4">
      {lead.sentences.length > 0 && (
        <div className="mb-2 hidden gap-1 border-b-2 border-ink pb-3.5 lg:grid">
          {lead.sentences.map((sentence, index) => (
            <SavingsSentence key={index} words={sentence} />
          ))}
          {lead.rough !== null && <p className="mt-1 text-muted">{lead.rough}</p>}
        </div>
      )}
      {lines.evidence_summary !== null && (
        <div className="font-semibold lg:font-normal">
          <LineView line={lines.evidence_summary} />
        </div>
      )}
      {said.map((line, index) => (
        <LineView key={index} line={line} />
      ))}
    </div>
  );
}

/** A savings sentence, its amount in bold. */
function SavingsSentence({ words }: { words: string }) {
  const said = amountIn(words);
  return (
    <p className="text-lg leading-snug">
      {said === null ? (
        words
      ) : (
        <>
          {said.before}
          <strong className="font-bold">{said.amount}</strong>
          {said.after}
        </>
      )}
    </p>
  );
}

/** What is still unknown or unconfirmed, report-wide, with what the request stated and the
 * typical yearly costs under it, shown once rather than on each option. */
function CheckList({ lines }: { lines: ReportLines }) {
  const heading = useId();
  const { groups, confirm_price } = lines.check;
  const notes = [...lines.stated, ...lines.typical_costs];
  if (groups.length === 0 && confirm_price === null && notes.length === 0) {
    return null;
  }
  return (
    <section
      aria-labelledby={heading}
      className="grid gap-4 border-2 border-ink bg-paper px-5 pt-4 pb-5"
    >
      <h3 id={heading} className="heading-overline">
        {CHECK_HEADING}
      </h3>
      {groups.map((group, index) => (
        <div key={index}>
          <div className="font-semibold">
            <LineView line={group.label} />
          </div>
          <Items lines={group.items} />
        </div>
      ))}
      {confirm_price !== null && <Items lines={[confirm_price]} />}
      {notes.length > 0 && (
        <div className="grid gap-1 border-t-2 border-ink pt-4 text-muted">
          {notes.map((line, index) => (
            <LineView key={index} line={line} />
          ))}
        </div>
      )}
    </section>
  );
}

function Items({ lines }: { lines: Line[] }) {
  return (
    <ul className="mt-1 grid list-[square] gap-x-8 gap-y-1 pl-5 marker:text-ink lg:grid-cols-2">
      {lines.map((line, index) => (
        <li key={index}>
          <LineView line={line} inline />
        </li>
      ))}
    </ul>
  );
}
