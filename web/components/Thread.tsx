"use client";

import { cn } from "cn";
import { useEffect, useReducer, useRef, useState, type ReactNode } from "react";

import { readSession, readTracing, sendAnswers, startSession } from "@/lib/api/client";
import type { MaxLengths } from "@/lib/api/limits";
import { follow, viewResult } from "@/lib/follow";
import { readSaved, writeSaved } from "@/lib/saved_session";
import {
  INITIAL,
  asksBudget,
  boxOf,
  closingStepOf,
  composerOf,
  explainsRoute,
  givenOf,
  hintsRoute,
  isTooLong,
  labelsOf,
  nextThread,
  openQuestionOf,
  resultsOf,
  roundsOf,
  routeOf,
  statusOf,
  type Action,
  type ApiResult,
  type ThreadState,
} from "@/lib/thread";
import { START_AGAIN } from "@/lib/wording";

import { ComposerForm } from "./ComposerForm";
import { FaceComposer } from "./FaceComposer";
import type { Asking } from "./InterviewPanel";
import { LeaderLine } from "./LeaderLine";
import { ProductBox } from "./ProductBox";
import { ResultsView } from "./ResultsView";
import { RouteLine } from "./RouteLine";
import { RunRoute } from "./RunRoute";
import { SeeTheComparison } from "./SeeTheComparison";
import { Starters } from "./Starters";
import { RoundView } from "./TurnView";
import { Button } from "./ui/button";

interface Props {
  /** The page's title, set above the box. */
  masthead: ReactNode;
  /** The schema's caps on the input and on the reply. */
  maxLengths: MaxLengths;
}

/** The chat thread of one session, and its composer (GLOSSARY.md, "Thread"), beside the box that
 * shows it (docs/design/chat_page_brief.md): the box on the coral field, the thread on the panel.
 * At the opening the field fills the page and the box's face is the composer, the starters by it;
 * on Next the request stays on the face, faded, as the panel opens beside the box. When the report
 * lands the box opens on "See the comparison", which puts the results page in its place. */
export function Thread({ masthead, maxLengths }: Props) {
  const [state, dispatch] = useReducer(nextThread, INITIAL);
  // Whether the API traces, so the composer says what is logged; no notice until it has said so.
  const [tracing, setTracing] = useState(false);
  const runs = useRef(0);
  const textarea = useRef<HTMLTextAreaElement>(null);
  // Asked for after a render that opens the composer, which is locked or hidden until then.
  const [focusAsked, askFocus] = useState(0);
  const composer = composerOf(state);
  const opening = state.turns.length === 0;
  const labels = labelsOf(state);
  const box = boxOf(state);
  const status = statusOf(state);
  const results = resultsOf(state);
  useRereading(state, dispatch);

  useEffect(() => {
    void readTracing().then(setTracing);
  }, []);

  // A tab that was on a session goes back to it. Before the effect below, which forgets the kept
  // session while this render has none.
  useEffect(() => {
    const saved = readSaved(window.sessionStorage);
    if (saved !== null) {
      runs.current += 1;
      dispatch({ type: "reloaded", token: runs.current, ...saved });
    }
  }, []);

  const { sessionId, input } = state;
  useEffect(() => {
    writeSaved(window.sessionStorage, sessionId === null ? null : { sessionId, input });
  }, [sessionId, input]);

  useEffect(() => {
    if (focusAsked > 0) {
      textarea.current?.focus();
    }
  }, [focusAsked]);

  /** A new run's token, and where what the API answers for it goes. */
  function newRun(): [number, (result: ApiResult) => void] {
    runs.current += 1;
    const token = runs.current;
    return [token, (result) => dispatch({ type: "api", token, result })];
  }

  async function send() {
    if (asksBudget(state)) {
      thenType({ type: "asked_budget" });
      return;
    }
    const [token, heard] = newRun();
    dispatch({ type: "started", token });
    await follow(await startSession(state.draft), heard);
  }

  /** "Show my options", or "skip the rest": the answers as they are, unless the reply joined from
   * what was written is longer than the API reads. */
  async function answer() {
    const given = givenOf(state);
    if (state.sessionId === null) {
      return;
    }
    if (isTooLong(given, maxLengths.reply)) {
      dispatch({ type: "held_back" });
      return;
    }
    const [token, heard] = newRun();
    dispatch({ type: "answered", token, given });
    await follow(await sendAnswers(state.sessionId, given), heard);
  }

  /** Edit, Start again and an example tapped leave the composer open to type in. */
  function thenType(action: Action) {
    dispatch(action);
    askFocus((asked) => asked + 1);
  }

  const edit = () => thenType({ type: "edited" });
  const asking: Asking = {
    open: openQuestionOf(state),
    closing: closingStepOf(state),
    labels,
    picks: state.picks,
    frozen: state.stage.name !== "questions",
    maxLength: maxLengths.reply,
    tracing,
    onPick: (pick) => dispatch({ type: "picked", pick }),
    onOwnWords: (questionId) => dispatch({ type: "own_words", questionId }),
    onWrite: (questionId, words) => dispatch({ type: "wrote", questionId, words }),
    onMoveOn: (questionId) => dispatch({ type: "moved_on", questionId }),
    onAdd: (words) => dispatch({ type: "added", words }),
    onReopen: (questionId) => dispatch({ type: "reopened", questionId }),
    onSend: answer,
  };

  const typeDraft = (draft: string) => dispatch({ type: "typed", draft });
  const pickExample = (example: string) => thenType({ type: "typed", draft: example });

  // The box's width on a wide screen: the field's, no more than its height leaves room for; at the
  // opening it leaves room either side for the starters by its face.
  const boxWidth = cn(
    "w-full lg:w-[max(40rem,calc((100dvh_-_15.5rem)_*_928_/_600))] lg:max-w-full lg:transition-[max-width] lg:duration-600 lg:ease-out-expo motion-reduce:transition-none",
    opening && "lg:max-w-[calc(100%_-_14rem)]",
  );

  return (
    // On Next the panel's column opens beside the field, and the box slides left with it: a layout
    // change, animated; reduced motion makes it a jump. When the report lands the results take
    // the field's place over the grid's columns 1 to 8, the rounds 9 to 12.
    <div
      className={cn(
        "grid min-h-dvh lg:transition-[grid-template-columns] lg:duration-600 lg:ease-out-expo motion-reduce:transition-none",
        opening
          ? "lg:grid-cols-[1fr_0fr]"
          : results !== null
            ? "lg:grid-cols-[calc(2rem+(100%-4rem)*2/3)_1fr]"
            : "lg:grid-cols-[5fr_3fr]",
      )}
    >
      <LeaderLine labels={labels} />
      <section
        className={cn(
          "flex min-w-0 flex-col bg-field px-4 pt-7 pb-6 lg:px-8 lg:pt-9 lg:pb-10",
          results === null && "lg:sticky lg:top-0 lg:h-dvh lg:self-start",
        )}
      >
        {masthead}
        {results !== null ? (
          <ResultsView report={results.report} lines={results.lines} />
        ) : (
          // The box spans the field from flap tip to flap tip, over the route line.
          <div className="flex flex-1 flex-col items-center justify-center pt-8 lg:pt-4">
            <div className={cn("relative @container", boxWidth)}>
              <ProductBox box={box} labels={labels} />
              {box.state === "open" && (
                <SeeTheComparison onCompare={() => dispatch({ type: "compared" })} />
              )}
              {opening && composer !== null && (
                <FaceComposer
                  composer={composer}
                  draft={state.draft}
                  maxLength={maxLengths.input}
                  tracing={tracing}
                  textarea={textarea}
                  onType={typeDraft}
                  onSend={send}
                />
              )}
              {opening && composer?.examples && (
                <Starters
                  stacked
                  className="mt-6 lg:absolute lg:bottom-[0.5cqi] lg:left-[88cqi] lg:mt-0 lg:w-max"
                  onPick={pickExample}
                />
              )}
            </div>
            <div className={cn("relative mt-5 min-h-[4.5rem] lg:mt-7", boxWidth)}>
              {explainsRoute(state) ? (
                <RunRoute stations={routeOf(state)} hinted={hintsRoute(state)} />
              ) : (
                <RouteLine stations={routeOf(state)} />
              )}
            </div>
          </div>
        )}
      </section>
      <section className={cn("min-w-0 overflow-hidden bg-panel", opening && "max-lg:hidden")}>
        {/* As wide as the column will be, so nothing reflows while it opens; beside the results,
            the column's own width. */}
        <div
          className={cn(
            "grid content-start gap-8 px-4 pt-8 pb-16 lg:px-12 lg:pt-24",
            results === null && "lg:w-[37.5vw]",
          )}
        >
          {!opening && (
            <div className="grid gap-6">
              {/* What each round adds is read out; progress is the status line's alone. */}
              <div role="log" aria-live="polite" className="grid gap-10">
                {roundsOf(state.turns).map((round) => (
                  <RoundView
                    key={round.heading}
                    round={round}
                    // Beside the results the rounds are read back, without their controls.
                    controls={results === null ? { edit } : null}
                    asking={asking}
                  />
                ))}
              </div>
              {/* One line for the step at work, replaced as the next starts: never a log. */}
              <div role="status" className="grid gap-1">
                {status !== null && <p>{status.line}</p>}
                {status?.detail != null && <p className="text-sm text-muted">{status.detail}</p>}
                {state.notice !== null && <p className="text-muted">{state.notice}</p>}
              </div>
            </div>
          )}
          {state.stage.name === "report" ? (
            <Button
              type="button"
              className="justify-self-start"
              onClick={() => thenType({ type: "started_again" })}
            >
              {START_AGAIN}
            </Button>
          ) : (
            !opening &&
            composer !== null && (
              <ComposerForm
                composer={composer}
                draft={state.draft}
                maxLength={maxLengths.input}
                tracing={tracing}
                textarea={textarea}
                onType={typeDraft}
                onSend={send}
                onExample={pickExample}
              />
            )
          )}
        </div>
      </section>
    </div>
  );
}

/** Reads the session again, after the stage's wait, while a lost stream is picked up. */
function useRereading(
  { stage, sessionId, token }: ThreadState,
  dispatch: (action: Extract<Action, { type: "api" }>) => void,
) {
  useEffect(() => {
    if (stage.name !== "checking" || sessionId === null || token === null) {
      return;
    }
    const timer = setTimeout(async () => {
      dispatch({ type: "api", token, result: viewResult(await readSession(sessionId)) });
    }, stage.wait);
    return () => clearTimeout(timer);
  }, [stage, sessionId, token, dispatch]);
}
