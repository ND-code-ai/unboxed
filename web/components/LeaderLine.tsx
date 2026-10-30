import { useEffect, useRef, useState } from "react";

import type { Label } from "@/lib/thread";

// Tailwind's `lg`, where the thread sits beside the box.
const WIDE_AND_MOVING = "(min-width: 64rem) and (prefers-reduced-motion: no-preference)";

interface Ends {
  /** Which answer it joins, and when, so a new one draws afresh. */
  id: string;
  path: string;
}

/** On a wide screen, the line that briefly joins a new label in the thread to the same
 * label on the box (docs/design/chat_page_brief.md, "Labelling"), once the label has dropped onto
 * the box. A drawing only. */
export function LeaderLine({ labels }: { labels: Label[] }) {
  const ids = JSON.stringify(labels.map((label) => label.id));
  const seen = useRef<string[] | null>(null);
  const [ends, setEnds] = useState<Ends | null>(null);

  useEffect(() => {
    const now: string[] = JSON.parse(ids);
    const before = seen.current;
    seen.current = now;
    const added = before === null ? undefined : now.find((id) => !before.includes(id));
    if (added === undefined || !matchMedia(WIDE_AND_MOVING).matches) {
      return;
    }
    let live = true;
    const onBox = boxLabel(added);
    Promise.all((onBox?.getAnimations() ?? []).map((animation) => animation.finished))
      .then(() => {
        const path = live ? leaderPath(added) : null;
        if (path !== null) {
          setEnds({ id: `${added}-${Date.now()}`, path });
        }
      })
      // A drop cut short, by a new render of the box, draws no line.
      .catch(() => undefined);
    return () => {
      live = false;
    };
  }, [ids]);

  if (ends === null) {
    return null;
  }
  return (
    <svg aria-hidden="true" className="pointer-events-none fixed inset-0 z-20 h-full w-full">
      <path key={ends.id} className="leader-line" pathLength={1} d={ends.path} />
    </svg>
  );
}

function boxLabel(id: string): Element | null {
  return document.querySelector(`[data-box] [data-label-for="${CSS.escape(id)}"]`);
}

/** From the label in the thread, out into the field beside the box's face, then into the label on
 * the box from its right, so the line crosses no other label. */
function leaderPath(id: string): string | null {
  const box = document.querySelector("[data-box]");
  const inThread = [...document.querySelectorAll(`[data-label-for="${CSS.escape(id)}"]`)].find(
    (label) => label.closest("[data-box]") === null,
  );
  const onBox = boxLabel(id);
  if (box === null || inThread === undefined || onBox === null) {
    return null;
  }
  const from = inThread.getBoundingClientRect();
  const to = onBox.getBoundingClientRect();
  const field = box.getBoundingClientRect();
  // The face's right edge is at 842 in the drawing, whose viewBox runs 928 wide from 48 (ProductBox.tsx).
  const faceRight = field.left + (field.width * (842 - 48)) / 928;
  const beside = (faceRight + from.left) / 2;
  const fromY = from.top + from.height / 2;
  const toY = to.top + to.height / 2;
  return `M ${from.left} ${fromY} H ${beside} V ${toY} H ${to.right}`;
}
