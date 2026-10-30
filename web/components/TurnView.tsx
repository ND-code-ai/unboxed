import { useId } from "react";

import type { Round, RoundTurn } from "@/lib/thread";

import { InterviewPanel, type Asking } from "./InterviewPanel";
import { LineView, type Controls } from "./LineView";

interface Props {
  controls: Controls;
  /** What the questions turn shows and does. */
  asking: Asking;
}

/** One round of the thread under its small heading: the shopper's words, then what the app took
 * from them (docs/design/chat_page_brief.md, "The thread"). */
export function RoundView({ round, ...props }: Props & { round: Round }) {
  const heading = useId();
  return (
    <section aria-labelledby={heading} className="grid gap-4">
      <h2 id={heading} className="heading-overline">
        {round.heading}
      </h2>
      <ol className="grid gap-5">
        {round.turns.map(({ key, turn }) => (
          <TurnView key={key} turn={turn} {...props} />
        ))}
      </ol>
    </section>
  );
}

/** One turn of the thread: the user's, or the app's. */
function TurnView(props: Props & { turn: RoundTurn }) {
  return (
    <li className="min-w-0 [overflow-wrap:anywhere]">
      <TurnBody {...props} />
    </li>
  );
}

function TurnBody({ turn, controls, asking }: Props & { turn: RoundTurn }) {
  switch (turn.kind) {
    case "user":
      return (
        <p className="border-l-[3px] border-ink py-1 pl-3.5 whitespace-pre-wrap">{turn.text}</p>
      );
    case "message":
      return <p>{turn.text}</p>;
    case "understood":
      return <LineView line={turn.line} controls={controls} />;
    case "lines":
    case "reply":
      return (
        <div className="grid gap-1">
          {turn.lines.map((line, index) => (
            <LineView key={index} line={line} controls={controls} />
          ))}
        </div>
      );
    case "notes":
      return (
        <div className="grid gap-1 text-sm text-muted">
          {turn.lines.map((line, index) => (
            <LineView key={index} line={line} controls={controls} />
          ))}
        </div>
      );
    case "questions":
      return <InterviewPanel asking={asking} sources={turn.sources} controls={controls} />;
  }
}
