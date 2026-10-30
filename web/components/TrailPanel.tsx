import { useEffect, useId, useRef } from "react";

import type { TrailLine } from "@/lib/api/types";
import { plainTrail, trailPart } from "@/lib/results";
import type { Station } from "@/lib/thread";

import { LineView } from "./LineView";
import type { Opener } from "./RouteLine";

/** The evidence trail (GLOSSARY.md, "Trail") under the route line: one part per station, in the
 * route's order, each its agent's trail lines in the order they were written. A station opens and
 * closes its part, so the panel needs no index of its own; with every part open it shows the whole
 * trail. */
export function TrailPanel({
  stations,
  trail,
  open,
  partOf,
}: {
  stations: Station[];
  trail: TrailLine[];
} & Pick<Opener, "open" | "partOf">) {
  return (
    <div hidden={open.length === 0} className="grid gap-3">
      {stations.map(({ agent, name }) => (
        <TrailPart
          key={agent}
          id={partOf(agent)}
          name={name}
          lines={trailPart(trail, agent)}
          open={open.includes(agent)}
        />
      ))}
    </div>
  );
}

/** One station's part: a sheet under its name, each line saying what was found, decided or left
 * out. The station's name says whose it is, so a line's `by` (agent, tier and model) stays off the
 * page. A long part scrolls inside its sheet, so the options stay near; opened below the fold, it
 * is scrolled into view. */
function TrailPart({
  id,
  name,
  lines,
  open,
}: {
  id: string;
  name: string;
  lines: TrailLine[];
  open: boolean;
}) {
  const heading = useId();
  const part = useRef<HTMLDivElement>(null);
  const wasOpen = useRef(open);
  useEffect(() => {
    if (open && !wasOpen.current) {
      part.current?.scrollIntoView({ block: "nearest" });
    }
    wasOpen.current = open;
  }, [open]);
  return (
    <div
      ref={part}
      id={id}
      hidden={!open}
      className="grid border-2 border-ink bg-paper pt-4 [overflow-wrap:anywhere]"
    >
      <p id={heading} className="heading-overline px-5">
        {name}
      </p>
      <ol
        aria-labelledby={heading}
        // Focusable, so a part longer than its sheet can be scrolled from the keyboard.
        tabIndex={0}
        className="grid max-h-[min(32rem,60dvh)] content-start gap-3 overflow-y-auto px-5 pt-3 pb-4 text-sm"
      >
        {lines.map((line, index) => (
          <li key={index}>
            <LineView line={plainTrail(line.line)} inline />
          </li>
        ))}
      </ol>
    </div>
  );
}
