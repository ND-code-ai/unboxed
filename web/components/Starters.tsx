import { cn } from "cn";
import { useId, type CSSProperties } from "react";

import { EXAMPLES, TRY_ONE } from "@/lib/wording";

import { LabelView } from "./LabelView";

// Beside the box the starters stack a little unevenly, as labels laid down by hand.
const NUDGES = ["0rem", "1.25rem", "0.5rem"];

interface Props {
  /** A starter tapped: it is written into the composer, not sent. */
  onPick: (example: string) => void;
  /** Stacked one above another, nudged unevenly; otherwise in a wrapping row. */
  stacked?: boolean;
  className?: string;
}

/** The example requests, as small paper labels to take, each slightly turned, under "Or try one":
 * by the box's face at the opening (in a row below the box on a phone), and under the composer
 * when it opens empty again. */
export function Starters({ onPick, stacked = false, className }: Props) {
  const heading = useId();
  return (
    <div className={className}>
      <p id={heading} className="text-[0.8125rem] font-semibold tracking-[0.08em] uppercase">
        {TRY_ONE}
      </p>
      <ul
        aria-labelledby={heading}
        className={cn("mt-3 flex flex-wrap items-start gap-2.5", stacked && "lg:grid lg:gap-3.5")}
      >
        {EXAMPLES.map((example, index) => (
          <li
            key={example}
            className={cn(stacked && "lg:ml-(--nudge)")}
            style={{ "--nudge": NUDGES[index % NUDGES.length] } as CSSProperties}
          >
            <button
              type="button"
              className="block hover:[&>span]:bg-lip"
              onClick={() => onPick(example)}
            >
              <LabelView index={index} on="panel" className="text-[0.9375rem] whitespace-nowrap">
                {example}
              </LabelView>
            </button>
          </li>
        ))}
      </ul>
    </div>
  );
}
