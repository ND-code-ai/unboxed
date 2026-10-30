import { useEffect, useRef } from "react";

import { SEE_THE_COMPARISON } from "@/lib/wording";

import styles from "./SeeTheComparison.module.css";
import { Button } from "./ui/button";

/** The opened box's one control and the page's primary action: it stands in the opening, as if
 * pulled out of the box, and opens the results page, where every figure lives
 * (docs/design/chat_page_brief.md, "The memorable moment"). Laid over the box, whose drawing is
 * hidden from assistive tech; its parent is the box's container. Paper on the box's dark inside,
 * where an ink fill would not show. Focused when it appears, as the button that sent the answers is
 * gone; the status line says the comparison is ready. The arrow is a drawing, so the button is read
 * by its words. */
export function SeeTheComparison({ onCompare }: { onCompare: () => void }) {
  const button = useRef<HTMLButtonElement>(null);
  useEffect(() => {
    button.current?.focus();
  }, []);
  return (
    <Button ref={button} type="button" size="lg" className={styles.compare} onClick={onCompare}>
      {SEE_THE_COMPARISON}
      <span aria-hidden="true">→</span>
    </Button>
  );
}
