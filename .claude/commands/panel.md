---
description: Have three design critics (product, implementation, data) review the interview summary before you confirm it
argument-hint: "[optional: the task number, or a point to focus on]"
---

Run a review panel on the design summary of this conversation.

Focus, if given: $ARGUMENTS

Use this at the end of a grilling interview, before the shared understanding is confirmed. It
is a review of decisions, not a debate: the critics report, and I decide.

1. **Take the summary.** Use the latest summary of settled decisions in this conversation. If
   there is none, write one now: every settled decision as a numbered item, with the question
   number it came from, and the task number. Show it to me before continuing.
2. **Run the critics in parallel.** Launch three `design-critic` subagents at the same time, one
   per lens: `product`, `implementation` and `data`. The subagents have not seen this
   conversation, so give each one, in its prompt: its lens, the task number, any focus from
   above, and the full text of the summary.
3. **Combine the results** into one table: number, the summary item concerned, lens, objection,
   suggested change, severity. Merge findings that make the same point and note which lenses
   raised them; agreement between lenses is worth knowing. Order by severity.
4. **Add your own view** in one line per finding: agree, disagree or unsure, and why. Keep it
   separate from the critics' text.
5. **Stop and wait.** Do not change any decision, doc or file. I will accept or reject each
   finding. Accepted findings go back into the interview: update the summary, and if one reopens
   a decision, ask that question again before the summary is confirmed.

If all three critics report no objections, say so in one line and remind me that the summary
still needs my confirmation.
