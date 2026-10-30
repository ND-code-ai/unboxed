import { cn } from "cn";
import { useId, type CSSProperties, type Ref } from "react";

import type { Composer } from "@/lib/thread";
import { INPUT_HINT, INPUT_LABEL, INPUT_PLACEHOLDER, NEXT, TRACING_NOTICE } from "@/lib/wording";

import { AskBudget, enterSends } from "./AskBudget";
import styles from "./FaceComposer.module.css";
import { Button } from "./ui/button";

interface Props {
  composer: Composer;
  draft: string;
  maxLength: number | undefined;
  /** Whether the deployed app traces, so what is typed is logged. */
  tracing: boolean;
  textarea: Ref<HTMLTextAreaElement>;
  onType: (draft: string) => void;
  onSend: () => void;
}

/** The composer before the first send, set on the box's face (docs/design/chat_page_brief.md,
 * "The opening"): the question as a heading, what goes in the box typed below it on a faint
 * baseline, then that a link works too, and Next. Placed in the box's own units: its parent is
 * the box's container. */
export function FaceComposer(props: Props) {
  const { composer, draft, maxLength, tracing, textarea } = props;
  const id = useId();
  return (
    <form
      className={styles.face}
      onSubmit={(event) => {
        event.preventDefault();
        if (composer.canSend) {
          props.onSend();
        }
      }}
    >
      <label htmlFor={id} className={styles.question}>
        {INPUT_LABEL}
      </label>
      <textarea
        id={id}
        ref={textarea}
        rows={2}
        className={styles.writing}
        style={sized(draft || INPUT_PLACEHOLDER)}
        value={draft}
        placeholder={INPUT_PLACEHOLDER}
        maxLength={maxLength}
        onChange={(event) => props.onType(event.target.value)}
        onKeyDown={enterSends}
      />
      <AskBudget asking={composer.askingBudget} className={styles.ask} />
      <p className={styles.hint}>{INPUT_HINT}</p>
      <Button
        type="submit"
        variant="solid"
        size="sm"
        className={cn(styles.send, "lg:min-h-11 lg:px-6 lg:py-2 lg:text-base")}
        disabled={!composer.canSend}
      >
        {NEXT}
      </Button>
      {tracing && <p className={styles.notice}>{TRACING_NOTICE}</p>}
    </form>
  );
}

/** The face once the request is sent: the question, and the request where it was typed, faded to
 * pencil; the hint and Next are gone, their places kept so nothing moves. Once the face is
 * `cleared` (the questions are asked) the question goes too and the request moves to the face's
 * top, to leave room for the labels, with the count in the corner beside it. A drawing, inside the
 * box, under the labels stuck over it; the thread quotes the request. */
export function WrittenFace({
  request,
  cleared,
  tally,
}: {
  request: string;
  cleared: boolean;
  /** How many questions have an answer, while they are open. */
  tally: string | null;
}) {
  return (
    <div className={cn(styles.face, styles.written, cleared && styles.cleared)}>
      <p className={styles.question}>{INPUT_LABEL}</p>
      <p className={styles.writing} style={sized(request)}>
        {/* The corner stays kept once the count goes, so the request never moves under its labels. */}
        {cleared && <span className={styles.tally}>{tally}</span>}
        {/* Measured by ProductBox, which settles the first label just below it. */}
        <span data-request>{request}</span>
      </p>
      <p className={cn(styles.hint, styles.gone)}>{INPUT_HINT}</p>
      {/* Sized as Next was (Button, size sm). */}
      <span
        className={cn(
          styles.send,
          styles.gone,
          "inline-flex min-h-9 items-center border-2 px-3 py-1 text-sm font-semibold lg:min-h-11 lg:px-6 lg:py-2 lg:text-base",
        )}
      >
        {NEXT}
      </span>
    </div>
  );
}

/** The type of the request shrinks as it grows, so it fits the face without scrolling. */
function sized(words: string): CSSProperties {
  return { "--chars": words.length } as CSSProperties;
}
