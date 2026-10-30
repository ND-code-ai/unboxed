import { useId, useRef, useState } from "react";

import type { Agent, Station } from "@/lib/thread";
import { CLOSE_NOTE, ROUTE_HINT } from "@/lib/wording";

import { RouteLine, type Opener } from "./RouteLine";

/** The route line from the first send to the results page: each station opens a short note on what
 * its agent does, in plain words, one at a time, laid over the box above the line; its cross, the
 * station pressed again, or Escape closes it. During a wait the hint under the line says so, until
 * a station is pressed or its own cross closes it. The notes describe every run: the trail of this
 * one is on the results page. Its parent places the notes. */
export function RunRoute({ stations, hinted }: { stations: Station[]; hinted: boolean }) {
  const [open, setOpen] = useState<Agent | null>(null);
  const [pressed, setPressed] = useState(false);
  const parts = useId();
  const route = useRef<HTMLDivElement>(null);
  const opener: Opener = {
    open: open === null ? [] : [open],
    partOf: (agent) => `${parts}-${agent}`,
    onToggle: (agent) => {
      setPressed(true);
      setOpen((was) => (was === agent ? null : agent));
    },
  };
  // A cross goes with what it closes, so the focus moves to a station that stays.
  const focusStation = (agent: Agent) =>
    route.current?.querySelector<HTMLElement>(`[aria-controls="${opener.partOf(agent)}"]`)?.focus();
  return (
    <div
      ref={route}
      onKeyDown={(event) => {
        if (event.key === "Escape") {
          setOpen(null);
        }
      }}
    >
      <RouteLine stations={stations} opener={opener} />
      {/* After the stations, so Tab reaches an opened note from its station; placed over the box. */}
      {stations.map(({ agent, detail }) => (
        <div
          key={agent}
          id={opener.partOf(agent)}
          hidden={agent !== open}
          className="paper-note absolute inset-x-0 bottom-full z-10 mb-4 lg:max-w-[34rem]"
        >
          <p className="pr-6">{detail}</p>
          <NoteClose
            onClose={() => {
              setOpen(null);
              focusStation(agent);
            }}
          />
        </div>
      ))}
      {hinted && !pressed && (
        <div className="paper-note relative mt-3 lg:absolute lg:top-14 lg:mt-0 lg:w-max">
          <p className="pr-6">{ROUTE_HINT}</p>
          <NoteClose
            onClose={() => {
              setPressed(true);
              focusStation(stations[0].agent);
            }}
          />
        </div>
      )}
    </div>
  );
}

/** The cross in a note's top right corner. */
function NoteClose({ onClose }: { onClose: () => void }) {
  return (
    <button
      type="button"
      aria-label={CLOSE_NOTE}
      className="absolute top-0 right-0 grid size-8 place-items-center hover:bg-lip"
      onClick={onClose}
    >
      <svg viewBox="0 0 12 12" aria-hidden="true" className="size-3 stroke-current stroke-2">
        <path d="M1 1l10 10M11 1L1 11" />
      </svg>
    </button>
  );
}
