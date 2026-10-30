import { cn } from "cn";
import { useEffect, useId, useRef } from "react";

import type { GivenAnswer, SessionLines } from "@/lib/api/types";
import { chipsOf, isPicked, type ClosingStep, type Label, type OpenQuestion } from "@/lib/thread";
import {
  ANYTHING_ELSE,
  NEXT,
  SHOW_MY_OPTIONS,
  SKIP_THE_REST,
  SOMETHING_ELSE,
  TRACING_NOTICE,
  moreQuestions,
  placeAmong,
} from "@/lib/wording";

import { LabelView } from "./LabelView";
import { LineView, type Controls } from "./LineView";
import { Button } from "./ui/button";
import { Textarea } from "./ui/textarea";

/** Where the questions stand, and what answering them does. */
export interface Asking {
  /** The open question; none once every question has an answer, or once they are sent. */
  open: OpenQuestion | null;
  /** The closing step, once every question has an answer; none once they are sent. */
  closing: ClosingStep | null;
  labels: Label[];
  picks: GivenAnswer[];
  /** Once the answers are sent: the labels stay as sent, and cannot be tapped. */
  frozen: boolean;
  /** The longest a field takes: the reply's cap (the schema's `maxLength`). */
  maxLength: number | undefined;
  /** Whether the deployed app traces, so what is typed is logged. */
  tracing: boolean;
  onPick: (pick: GivenAnswer) => void;
  /** "Something else" tapped: the question's field unfolds, or folds. */
  onOwnWords: (questionId: string) => void;
  onWrite: (questionId: string, words: string) => void;
  /** Next, under a question's own words. */
  onMoveOn: (questionId: string) => void;
  /** Words typed at the closing step. */
  onAdd: (words: string) => void;
  /** A label tapped: its question opens again. */
  onReopen: (questionId: string) => void;
  /** "Show my options", and "skip the rest": sends what was given so far. */
  onSend: () => void;
}

interface Props {
  asking: Asking;
  /** The source line under each question about a researched factor, by question id. */
  sources: SessionLines["sources"];
  controls: Controls;
}

/** The questions, asked one at a time (docs/design/chat_page_brief.md, "The interview panel"):
 * the answered ones as labels, then the open one in a card with its reason, its source line and
 * its choices, "Not sure" and "Something else" as chips, then how many are left; after the last,
 * the closing step. */
export function InterviewPanel({ asking, sources, controls }: Props) {
  const { open, closing, labels, frozen, onReopen, onSend } = asking;
  return (
    <div className="grid gap-4">
      {labels.length > 0 && (
        <ul className="flex flex-wrap items-start gap-2">
          {labels.map((label, index) => (
            <li key={label.id}>
              {frozen ? (
                <LabelView label={label} index={index} on="panel" whole />
              ) : (
                <button
                  type="button"
                  className="block text-left hover:[&>span]:bg-lip"
                  onClick={() => onReopen(label.id)}
                >
                  <LabelView label={label} index={index} on="panel" />
                </button>
              )}
            </li>
          ))}
        </ul>
      )}
      {open !== null && (
        <>
          <QuestionCard open={open} asking={asking} sources={sources} controls={controls} />
          {open.more > 0 && <MoreQuestions more={open.more} onSkipRest={onSend} />}
        </>
      )}
      {closing !== null && (
        // It takes focus when it follows the questions, or opens again with a message; a pause
        // with nothing to ask leaves the reader on the lines above it.
        <ClosingCard
          closing={closing}
          asking={asking}
          focused={labels.length > 0 || closing.error !== null}
        />
      )}
      {!frozen && asking.tracing && <p className="text-sm text-muted">{TRACING_NOTICE}</p>}
    </div>
  );
}

function QuestionCard({ open, asking, sources, controls }: Props & { open: OpenQuestion }) {
  const { question, place, total } = open;
  const textId = useId();
  const elseId = useId();
  const heading = useRef<HTMLParagraphElement>(null);
  const shown = useRef(question.id);
  const source = sources[question.id];

  // When the card moves on to another question, the reader moves with it.
  useEffect(() => {
    if (shown.current !== question.id) {
      shown.current = question.id;
      heading.current?.focus();
    }
  }, [question.id]);

  return (
    <section aria-labelledby={textId} className="border-2 border-ink bg-paper px-5 pt-4 pb-5">
      <div className="flex items-baseline justify-between gap-4">
        <p
          id={textId}
          ref={heading}
          tabIndex={-1}
          className="text-[1.3125rem] leading-snug font-bold text-balance"
        >
          {question.text}
        </p>
        <p className="shrink-0 text-sm font-semibold text-muted tabular-nums">
          {placeAmong(place, total)}
        </p>
      </div>
      <p className="mt-1.5 text-muted">{question.reason}</p>
      {source !== undefined && (
        <div className="mt-1 text-sm text-muted">
          <LineView line={source} controls={controls} />
        </div>
      )}
      <div className="mt-4 flex flex-wrap gap-2" role="group" aria-labelledby={textId}>
        {chipsOf(question).map(({ pick, words }) => (
          <Button
            key={pick.choice_id ?? pick.status}
            type="button"
            variant="chip"
            aria-pressed={isPicked(asking.picks, pick)}
            onClick={() => asking.onPick(pick)}
          >
            {words}
          </Button>
        ))}
        <Button
          id={elseId}
          type="button"
          variant="chip"
          aria-pressed={open.inOwnWords}
          onClick={() => asking.onOwnWords(question.id)}
        >
          <PencilMark />
          {SOMETHING_ELSE}
        </Button>
      </div>
      {open.inOwnWords ? (
        <OwnWords open={open} asking={asking} labelledBy={`${textId} ${elseId}`} />
      ) : (
        open.error !== null && <StepError className="mt-4">{open.error}</StepError>
      )}
    </section>
  );
}

/** The field "Something else" unfolds, focused as it opens, with Next under it. */
function OwnWords({
  open,
  asking,
  labelledBy,
}: {
  open: OpenQuestion;
  asking: Asking;
  /** The question, then "Something else". */
  labelledBy: string;
}) {
  const { question, ownWords, error } = open;
  const field = useRef<HTMLTextAreaElement>(null);
  const errorId = useId();

  useEffect(() => {
    field.current?.focus();
  }, []);

  return (
    <form
      className="mt-3 grid gap-3"
      onSubmit={(event) => {
        event.preventDefault();
        asking.onMoveOn(question.id);
      }}
    >
      <Textarea
        ref={field}
        rows={2}
        className="min-h-20"
        aria-labelledby={labelledBy}
        aria-describedby={error === null ? undefined : errorId}
        value={ownWords}
        maxLength={asking.maxLength}
        onChange={(event) => asking.onWrite(question.id, event.target.value)}
      />
      {error !== null && <StepError id={errorId}>{error}</StepError>}
      <Button
        type="submit"
        variant="solid"
        className="justify-self-start"
        disabled={ownWords.trim() === ""}
      >
        {NEXT}
      </Button>
    </form>
  );
}

/** The closing step: one optional question after the others, not counted among them, and the
 * button that sends the answers. */
function ClosingCard({
  closing,
  asking,
  focused,
}: {
  closing: ClosingStep;
  asking: Asking;
  /** Whether its field takes focus as it opens. */
  focused: boolean;
}) {
  const id = useId();
  const errorId = useId();
  const field = useRef<HTMLTextAreaElement>(null);
  const takesFocus = useRef(focused);

  useEffect(() => {
    if (takesFocus.current) {
      field.current?.focus();
    }
  }, []);

  return (
    <form
      className="grid gap-3 border-2 border-ink bg-paper px-5 pt-4 pb-5"
      onSubmit={(event) => {
        event.preventDefault();
        asking.onSend();
      }}
    >
      <label htmlFor={id} className="text-[1.3125rem] leading-snug font-bold text-balance">
        {ANYTHING_ELSE}
      </label>
      <Textarea
        id={id}
        ref={field}
        rows={2}
        className="min-h-20"
        aria-describedby={closing.error === null ? undefined : errorId}
        value={closing.words}
        maxLength={asking.maxLength}
        onChange={(event) => asking.onAdd(event.target.value)}
      />
      {closing.error !== null && <StepError id={errorId}>{closing.error}</StepError>}
      <Button type="submit" variant="solid" className="justify-self-start">
        {SHOW_MY_OPTIONS}
      </Button>
    </form>
  );
}

/** Why the answers were not sent, or not applied, in the step opened again for it. */
function StepError({
  id,
  className,
  children,
}: {
  id?: string;
  className?: string;
  children: string;
}) {
  return (
    <p id={id} className={cn("font-semibold", className)}>
      {children}
    </p>
  );
}

/** A small pencil: the answer is the user's own words. */
function PencilMark() {
  return (
    <svg
      aria-hidden="true"
      viewBox="0 0 16 16"
      className="size-3.5 shrink-0"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.75"
      strokeLinejoin="round"
    >
      <path d="M2.5 13.5 3 10.5 10.5 3 13 5.5 5.5 13Z M9 4.5 11.5 7" />
    </svg>
  );
}

/** How many questions are left, ending in the button that skips them. */
function MoreQuestions({ more, onSkipRest }: { more: number; onSkipRest: () => void }) {
  const [before, after] = moreQuestions(more);
  return (
    <p className="text-sm text-muted">
      {before}
      <Button variant="link" size="inline" onClick={onSkipRest}>
        {SKIP_THE_REST}
      </Button>
      {after}
    </p>
  );
}
