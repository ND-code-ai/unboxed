import type { KeyboardEvent } from "react";

import { ASK_BUDGET } from "@/lib/wording";

/** The note by the composer when a request with no number in it is sent for the first time: a
 * budget would help, and sending again goes on without one. Always there, so a screen reader hears
 * it arrive, and empty until it is asked. */
export function AskBudget({ asking, className }: { asking: boolean; className?: string }) {
  return (
    <div role="status" className={className}>
      {asking && <p className="paper-note">{ASK_BUDGET}</p>}
    </div>
  );
}

/** Enter sends, as the form's button does; Shift and Enter start a new line. */
export function enterSends(event: KeyboardEvent<HTMLTextAreaElement>) {
  if (event.key === "Enter" && !event.shiftKey && !event.nativeEvent.isComposing) {
    event.preventDefault();
    event.currentTarget.form?.requestSubmit();
  }
}
