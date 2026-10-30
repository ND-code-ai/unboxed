import { useId, type Ref } from "react";

import type { Composer } from "@/lib/thread";
import { INPUT_HINT, INPUT_LABEL, INPUT_PLACEHOLDER, NEXT, TRACING_NOTICE } from "@/lib/wording";

import { AskBudget, enterSends } from "./AskBudget";
import { Starters } from "./Starters";
import { Button } from "./ui/button";
import { Textarea } from "./ui/textarea";

interface Props {
  composer: Composer;
  draft: string;
  maxLength: number | undefined;
  /** Whether the deployed app traces, so what is typed is logged. */
  tracing: boolean;
  textarea: Ref<HTMLTextAreaElement>;
  onType: (draft: string) => void;
  onSend: () => void;
  /** An example tapped: it fills the composer and is not sent. */
  onExample: (example: string) => void;
}

/** The input box of the thread, in the panel once the thread has begun (before it, the composer
 * is on the box's face: FaceComposer): it takes the input again when a request does not run. */
export function ComposerForm(props: Props) {
  const { composer, draft, maxLength, tracing, textarea } = props;
  const id = useId();
  return (
    <form
      className="grid gap-3"
      onSubmit={(event) => {
        event.preventDefault();
        if (composer.canSend) {
          props.onSend();
        }
      }}
    >
      <label htmlFor={id} className="font-semibold">
        {INPUT_LABEL}
      </label>
      <div>
        <Textarea
          id={id}
          ref={textarea}
          rows={3}
          value={draft}
          placeholder={INPUT_PLACEHOLDER}
          maxLength={maxLength}
          onChange={(event) => props.onType(event.target.value)}
          onKeyDown={enterSends}
        />
        <AskBudget asking={composer.askingBudget} className="has-[p]:mt-3" />
      </div>
      <div className="flex flex-wrap items-center gap-2">
        <Button type="submit" variant="solid" disabled={!composer.canSend}>
          {NEXT}
        </Button>
        <p className="ml-2 text-sm text-muted">{INPUT_HINT}</p>
      </div>
      {composer.examples && <Starters className="mt-4" onPick={props.onExample} />}
      {tracing && <p className="text-sm text-muted">{TRACING_NOTICE}</p>}
    </form>
  );
}
