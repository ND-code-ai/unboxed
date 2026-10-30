import { cn } from "cn";
import type { CSSProperties, ReactNode } from "react";

import type { Label } from "@/lib/thread";
import { notSureLabel } from "@/lib/wording";

// Each label sits slightly turned, as if stuck on by hand; the turn follows its place.
const TURNS = [-1.5, 1, -0.75, 1.5, -1.25, 0.5];

type Props = {
  /** Its place among the labels, which sets its turn. */
  index: number;
  /** On the box it is sized with the box; in the panel, at reading size. */
  on: "box" | "panel";
  /** Once the answers are sent, in the panel: the answer whole, wrapping inside the column. */
  whole?: boolean;
  className?: string;
} & (
  | {
      label: Pick<Label, "key" | "value" | "unsure"> & Partial<Pick<Label, "id" | "added">>;
      children?: never;
    }
  /** The box's first label, whose words are written on it by hand (ProductBox). */
  | { label?: never; children: ReactNode }
);

/** An answered question as a label, dashed when it has no answer, by "not sure" or a skip, which
 * reads as the factor's name and "?" on the box and in the panel alike
 * (docs/design/chat_page_brief.md, "The interview panel"). Otherwise in the panel its factor's name
 * over the answer; on the box, to fit five on its face, the answer alone on one line. A factor of
 * the user's own the reply added is its phrase alone: whole in the panel, cut short with an ellipsis
 * on the box. */
export function LabelView({ label, index, on, whole = false, className, children }: Props) {
  return (
    <span
      className={cn(
        // The turn is the `rotate` property, so it adds to any transform a drop-in animates.
        "inline-flex max-w-full rotate-(--turn) flex-col items-start border-ink bg-paper leading-tight font-bold [overflow-wrap:anywhere]",
        on === "box" ? "border-[max(1.5px,0.3cqi)] px-[0.7em] py-[0.3em]" : "border-2 px-3 py-1.5",
        // An answer in the user's own words can run long: two lines of it at most (one on the box,
        // about 30 characters), the width fixed in em so a row of labels sizes to it.
        label !== undefined && !whole && "max-w-[16em]",
        label?.unsure && "border-dashed font-semibold text-muted",
        className,
      )}
      style={{ "--turn": `${TURNS[index % TURNS.length]}deg` } as CSSProperties}
      data-label-for={label?.id}
    >
      {label === undefined ? (
        children
      ) : label.unsure && label.key !== null ? (
        <span className={cn("lowercase", on === "box" && "line-clamp-1")}>
          {notSureLabel(label.key)}
        </span>
      ) : on === "box" ? (
        <span className="line-clamp-1 lowercase">{label.value}</span>
      ) : (
        <>
          {label.key !== null && (
            <span className="text-[max(7px,0.6875em)] font-semibold tracking-[0.06em] text-muted uppercase">
              {label.key}
            </span>
          )}
          <span className={cn("lowercase", !label.added && !whole && "line-clamp-2")}>
            {label.value}
          </span>
        </>
      )}
    </span>
  );
}
