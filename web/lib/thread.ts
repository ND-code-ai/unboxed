/**
 * The thread: what the page shows of one session, as turns in order (GLOSSARY.md, "Thread"), and
 * how each thing that happens changes it. A pure reducer, so the page only sends requests and
 * dispatches what came back.
 */

import type {
  AnswersRequest,
  ApiError,
  DecisionFactor,
  ErrorEvent,
  GivenAnswer,
  Line,
  ProgressEvent,
  Question,
  Report,
  ReportLines,
  Request,
  SessionLines,
  SessionStart,
  SessionView,
  StreamEvent,
} from "./api/types";
import { lineText } from "./lines";
import {
  ANSWERS_NOT_APPLIED,
  COMPARISON_READY,
  NOT_SURE,
  REPLY_TOO_LONG,
  RESEARCHING_DETAIL,
  ROUND_ANSWERS,
  ROUND_REQUEST,
  RUN_STOPPED,
  STILL_WORKING,
  UNREAD_LABEL,
  UNREACHABLE,
  ROUTE_CO2E,
  ROUTE_CO2E_DETAIL,
  ROUTE_OPTIONS,
  ROUTE_OPTIONS_DETAIL,
  ROUTE_QUESTIONS,
  ROUTE_QUESTIONS_DETAIL,
  ROUTE_REQUEST,
  ROUTE_REQUEST_DETAIL,
  aboutQuestion,
} from "./wording";

type Scope = Request["scope"];

/** One turn of the thread. */
export type Turn =
  | { kind: "user"; text: string }
  /** What was understood, the "Looking for" line, which ends in the `edit` control, and the
   * same words as the box's first label carries them. */
  | { kind: "understood"; line: Line; label: Line | null }
  /** Lines the app says, as the API sent them. */
  | { kind: "lines"; lines: Line[] }
  /** Lines the app adds as asides, shown small and muted: the typical yearly costs, under the
   * request. */
  | { kind: "notes"; lines: Line[] }
  /** What the reply gave once it was read: its lines, and the factors of the user's own the reader
   * kept from it, each of which is labelled. */
  | { kind: "reply"; lines: Line[]; factors: DecisionFactor[] }
  /** The questions, with the source line under each, by question id, and the factors they are
   * drawn from, whose names key the labels; none at a pause with nothing to ask, which still has
   * its closing step. */
  | {
      kind: "questions";
      questions: Question[];
      sources: SessionLines["sources"];
      factors: DecisionFactor[];
    }
  /** The report with its lines, shown on the results page rather than in a round. */
  | { kind: "report"; report: Report; lines: ReportLines }
  /** What did not go to plan, in the words of the API or of `wording.ts`. */
  | { kind: "message"; text: string }
  /** One agent step: its started line while it runs, then its finished line in its place. */
  | {
      kind: "progress";
      agent: ProgressEvent["agent"];
      step: ProgressEvent["step"];
      line: string;
      /** Marked as working: its stream is open and the step has not finished. */
      running: boolean;
      /** The step finished; a step cut off by a lost stream is neither running nor done. */
      done: boolean;
    };

/** The run a stream is for: a new session's start, or the answers to a paused session; or a
 * session read back after a reload, whose stream, if a run was going, is gone. */
export type Run =
  | { kind: "start" }
  | { kind: "answers"; session: SessionStart; given: AnswersRequest }
  | { kind: "reload" };

export type Stage =
  /** The composer takes the input; with the examples when it opened empty. */
  | { name: "editing"; examples: boolean }
  /** A run's stream is open. */
  | { name: "running"; run: Run }
  /** The run's stream was lost, so the session is read as it is now, after `wait` milliseconds;
   * `misses` counts the reads in a row that got no answer. Shows as still working. */
  | { name: "checking"; run: Run; wait: number; misses: number }
  /** The session at the pause, waiting for the answers. */
  | { name: "questions"; session: SessionStart }
  /** The report has landed: the box is opened on it until "See the comparison" (`compared`)
   * opens the results page. */
  | { name: "report"; compared: boolean };

export interface ThreadState {
  /** The current run's token: what the API answers for any other run is dropped. */
  token: number | null;
  /** The text the session was started with. */
  input: string;
  /** What is in the composer. */
  draft: string;
  sessionId: string | null;
  stage: Stage;
  turns: Turn[];
  /** The chips marked at the questions: one choice, or "not sure", per question. */
  picks: GivenAnswer[];
  /** The words in each question's field, under "Something else", by question id; kept when
   * another chip folds the field. */
  ownWords: Record<string, string>;
  /** The questions whose "Something else" is tapped, by id: their field is open, and its words
   * are their answer. */
  inOwnWords: string[];
  /** The words of the closing step, "Anything else we should know?". */
  anythingElse: string;
  /** The id of the question open at the questions, asked one at a time; none once every one has
   * an answer, when the closing step is open. */
  openQuestion: string | null;
  /** Why the answers were not sent, or not applied: shown in the step opened again for it, until
   * another step opens or they are sent. */
  stepError: string | null;
  /** While a session is read again: why the last read got no answer, until one does. */
  notice: string | null;
  /** The request was stopped once to ask for a budget; sent again, it goes as it is. */
  budgetAsked: boolean;
}

/** What the API answered for a run. */
export type ApiResult =
  | { type: "streamed"; event: StreamEvent }
  /** The stream closed, after its last event or before it. */
  | { type: "stream_ended" }
  /** The session as `GET /sessions/{id}` read it. */
  | { type: "viewed"; view: SessionView }
  /** A request answered with an error body, before any stream started. */
  | { type: "refused"; error: ApiError }
  /** A request that got no answer at all. */
  | { type: "unreachable" };

export type Action =
  | { type: "typed"; draft: string }
  /** A request with no number in it sent for the first time: it stays, with the ask for a budget. */
  | { type: "asked_budget" }
  /** A chip tapped: a choice, or "not sure", for one question. */
  | { type: "picked"; pick: GivenAnswer }
  /** "Something else" tapped: the question's field opens, and its words are the answer; tapped
   * again, the field folds. */
  | { type: "own_words"; questionId: string }
  /** Words typed in a question's field, under "Something else". */
  | { type: "wrote"; questionId: string; words: string }
  /** Next, under a question's own words: the next question with no answer opens. */
  | { type: "moved_on"; questionId: string }
  /** Words typed at the closing step. */
  | { type: "added"; words: string }
  /** A label tapped: its question opens again. */
  | { type: "reopened"; questionId: string }
  | { type: "started"; token: number }
  /** The page loaded in a tab that was on a session: it is read back as it is now. */
  | { type: "reloaded"; token: number; sessionId: string; input: string }
  /** The answers sent for the questions. */
  | { type: "answered"; token: number; given: AnswersRequest }
  /** The answers not sent: the reply joined from what was written is longer than the API reads. */
  | { type: "held_back" }
  /** The `edit` control: the input back in the composer, for a new session. */
  | { type: "edited" }
  /** "Start again", after the report. */
  | { type: "started_again" }
  /** "See the comparison", in the opened box: the results page opens. */
  | { type: "compared" }
  | { type: "api"; token: number; result: ApiResult };

export const INITIAL: ThreadState = {
  token: null,
  input: "",
  draft: "",
  sessionId: null,
  stage: { name: "editing", examples: true },
  turns: [],
  picks: [],
  ownWords: {},
  inOwnWords: [],
  anythingElse: "",
  openQuestion: null,
  stepError: null,
  notice: null,
  budgetAsked: false,
};

// How long the page waits before it reads again a session it read as still running, or could
// not read: the first wait, doubled each time up to the longest.
const FIRST_WAIT = 2000;
const LONGEST_WAIT = 30000;
// The reads in a row that got no answer before the page stops reading and says so.
const MOST_MISSES = 5;

// A product link in the request.
const LINK = /https?:\/\/|www\./i;

// The agent the page does not show (`ShownAgent`).
const HIDDEN_AGENT = "second_hand";

// What the id of a factor of the user's own starts with (`USER_FACTOR_ID`, `agents/brief/stated.py`).
const USER_FACTOR_PREFIX = "user-";

export function nextThread(state: ThreadState, action: Action): ThreadState {
  switch (action.type) {
    case "typed":
      return { ...state, draft: action.draft };
    case "asked_budget":
      return { ...state, budgetAsked: true };
    case "picked":
      return state.stage.name === "questions"
        ? picked(state, state.stage.session, action.pick)
        : state;
    case "own_words":
      return askedAt(state, action.questionId, toggledOwnWords);
    case "wrote":
      return askedAt(state, action.questionId, (asked, question) => ({
        ...asked,
        ownWords: { ...asked.ownWords, [question.id]: action.words },
      }));
    case "moved_on":
      return askedAt(state, action.questionId, movedOn);
    case "added":
      return state.stage.name === "questions" ? { ...state, anythingElse: action.words } : state;
    case "reopened":
      return askedAt(state, action.questionId, (asked, question) => ({
        ...asked,
        openQuestion: question.id,
        stepError: null,
      }));
    case "started":
      return {
        ...INITIAL,
        token: action.token,
        input: state.draft,
        stage: { name: "running", run: { kind: "start" } },
        turns: [{ kind: "user", text: state.draft }],
      };
    case "reloaded":
      return {
        ...INITIAL,
        token: action.token,
        sessionId: action.sessionId,
        input: action.input,
        stage: readAtOnce({ kind: "reload" }),
        turns: [{ kind: "user", text: action.input }],
      };
    case "answered":
      return answered(state, action.token, action.given);
    case "held_back":
      return state.stage.name === "questions"
        ? openedAgain(state, state.stage.session, REPLY_TOO_LONG)
        : state;
    case "edited":
      // No run is current, so what the old one still sends is dropped; it finishes on the server.
      return {
        ...INITIAL,
        input: state.input,
        draft: state.input,
        stage: { name: "editing", examples: false },
      };
    case "started_again":
      return INITIAL;
    case "compared":
      return state.stage.name === "report"
        ? { ...state, stage: { name: "report", compared: true } }
        : state;
    case "api":
      return action.token === state.token ? withResult(state, action.result) : state;
  }
}

function withResult(state: ThreadState, result: ApiResult): ThreadState {
  switch (result.type) {
    case "streamed":
      return streamed(state, result.event);
    case "stream_ended":
      return ended(state);
    case "viewed":
      return viewed(state, result.view);
    case "refused":
      return stoppedWith(state, result.error.code, result.error.message);
    case "unreachable":
      return unreachable(state);
  }
}

/** A request that got no answer: answers that may have arrived are picked up from the session,
 * and anything else stops as `internal_error` does, with its words. */
function unreachable(state: ThreadState): ThreadState {
  if (state.stage.name === "running" && state.stage.run.kind === "answers") {
    return { ...state, stage: readAtOnce(state.stage.run) };
  }
  return stoppedWith(state, "internal_error", UNREACHABLE);
}

/** A run's stream is open, or the session is being read after its stream was lost. */
function isWorking(stage: Stage): stage is Extract<Stage, { run: Run }> {
  return stage.name === "running" || stage.name === "checking";
}

/** The run's session, read as it is now with no wait. */
function readAtOnce(run: Run): Stage {
  return { name: "checking", run, wait: 0, misses: 0 };
}

/** A line still running keeps its started words without the working mark. A stream that closed
 * before its last event is picked up from the session it started; one that closed before it
 * named the session cannot be. */
function ended(state: ThreadState): ThreadState {
  const settled = {
    ...state,
    turns: state.turns.map((turn) =>
      turn.kind === "progress" ? { ...turn, running: false } : turn,
    ),
  };
  if (state.stage.name !== "running") {
    return settled;
  }
  if (state.sessionId === null) {
    return stoppedWith(settled, "internal_error", UNREACHABLE);
  }
  return { ...settled, stage: readAtOnce(state.stage.run) };
}

/** The session as it is now, read after its run's stream was lost. */
function viewed(state: ThreadState, view: SessionView): ThreadState {
  if (state.stage.name !== "checking") {
    return state;
  }
  const { run } = state.stage;
  const seen = { ...state, notice: null };
  switch (view.status) {
    case "running":
      return { ...seen, stage: rechecked(state.stage, 0) };
    case "paused":
      return run.kind === "answers"
        ? notApplied(seen, run, ANSWERS_NOT_APPLIED)
        : paused(seen, view.session, view.lines);
    case "finished":
      return run.kind === "reload"
        ? readBack(seen, view.report, view.lines)
        : reported(seen, view.report, view.lines);
    case "interrupted":
      return startAgain(seen, RUN_STOPPED);
  }
}

/** The session read again after a wait: the first wait, or twice the last up to the longest. */
function rechecked(stage: Extract<Stage, { run: Run }>, misses: number): Stage {
  const last = stage.name === "checking" ? stage.wait : 0;
  const wait = last === 0 ? FIRST_WAIT : Math.min(last * 2, LONGEST_WAIT);
  return { name: "checking", run: stage.run, wait, misses };
}

/** A read that got no answer: read again after a wait, saying so, until too many in a row
 * stop it as a request that got no answer does. */
function missedRead(
  state: ThreadState,
  stage: Extract<Stage, { name: "checking" }>,
  message: string,
): ThreadState {
  const misses = stage.misses + 1;
  if (misses < MOST_MISSES) {
    return { ...state, stage: rechecked(stage, misses), notice: message };
  }
  return stage.run.kind === "answers"
    ? notApplied(state, stage.run, message)
    : startAgain(state, message);
}

/** The report a run ends with; for a start, the report of a request that does not run, which
 * shows as its decline. */
function reported(state: ThreadState, report: Report, lines: ReportLines): ThreadState {
  if (lines.declined !== null) {
    return declined(
      { ...state, turns: withoutReading(state.turns) },
      lines.declined,
      report.request.scope,
    );
  }
  return {
    ...state,
    stage: { name: "report", compared: false },
    turns: [...state.turns, { kind: "report", report, lines }],
  };
}

/** The report of a session read back after a reload: its results at once, and the rounds as the
 * report can give them, the answers as their labels. The "Looking for" line and what the reply
 * gave are not in a report's lines, so they do not come back. */
function readBack(state: ThreadState, report: Report, lines: ReportLines): ThreadState {
  if (lines.declined !== null) {
    return reported(state, report, lines);
  }
  const { questions, factors } = report;
  const asked = questions.map((question) => ({
    question,
    answer: report.answers.find((answer) => answer.factor_id === question.factor_id),
  }));
  const inWords = asked.filter(
    ({ answer }) => answer?.status === "stated" && answer.choice_id === null,
  );
  const added = factors.filter((factor) => factor.id.startsWith(USER_FACTOR_PREFIX));
  const turns: Turn[] = [
    ...state.turns,
    ...(lines.stated.length > 0 ? [{ kind: "lines" as const, lines: lines.stated }] : []),
    ...(lines.typical_costs.length > 0
      ? [{ kind: "notes" as const, lines: lines.typical_costs }]
      : []),
    ...(questions.length > 0
      ? [{ kind: "questions" as const, questions, sources: {}, factors }]
      : []),
    ...(added.length > 0 ? [{ kind: "reply" as const, lines: [], factors: added }] : []),
    { kind: "report", report, lines },
  ];
  return {
    ...state,
    stage: { name: "report", compared: true },
    turns,
    picks: asked.flatMap(({ answer }) =>
      answer?.choice_id == null
        ? []
        : [{ factor_id: answer.factor_id, status: "chosen" as const, choice_id: answer.choice_id }],
    ),
    inOwnWords: inWords.map(({ question }) => question.id),
    ownWords: Object.fromEntries(
      inWords.map(({ question, answer }) => [question.id, answer?.stated_value ?? ""]),
    ),
  };
}

/** What the results page shows (GLOSSARY.md, "Results page"): the report and its lines, once it
 * has landed and "See the comparison" was pressed in the opened box. */
export type Results = Pick<Extract<Turn, { kind: "report" }>, "report" | "lines">;

export function resultsOf({ stage, turns }: ThreadState): Results | null {
  const turn = turns.findLast((each) => each.kind === "report");
  return stage.name === "report" && stage.compared && turn !== undefined
    ? { report: turn.report, lines: turn.lines }
    : null;
}

type Code = ApiError["code"] | ErrorEvent["code"];

/** What a code says of the session: it cannot go on, so the page offers to start again; it is
 * still running; or it is as it was, so answers sent were not applied. */
type Outcome = "start_again" | "still_running" | "unchanged";

// Every code the API answers with, so a new one does not typecheck until it is placed here.
const OUTCOMES: Record<Code, Outcome> = {
  session_not_found: "start_again",
  session_not_paused: "start_again",
  invalid_request: "start_again",
  model_call_failed: "start_again",
  run_stopped: "start_again",
  session_running: "still_running",
  invalid_answers: "unchanged",
  input_too_long: "unchanged",
  reply_too_long: "unchanged",
  internal_error: "unchanged",
  reply_unread: "unchanged",
  reply_unanswered: "unchanged",
  too_many_sessions: "unchanged",
  too_many_sessions_today: "unchanged",
  // A recalculation refused changes nothing; the thread sends none yet (task 3.3).
  no_report_yet: "unchanged",
  no_options: "unchanged",
  unknown_option: "unchanged",
  invalid_assumptions: "unchanged",
};

/** A run that stopped, or a request refused, with its code and its words. A session still
 * running is read again, as one that could not be read while picking up a lost stream is; a
 * start that named no session has none to read, so it stops. */
function stoppedWith(state: ThreadState, code: Code, message: string): ThreadState {
  if (!isWorking(state.stage)) {
    return state;
  }
  const { run } = state.stage;
  const outcome = OUTCOMES[code];
  if (outcome === "still_running" && state.sessionId !== null) {
    return { ...state, stage: rechecked(state.stage, 0) };
  }
  if (outcome === "unchanged" && state.stage.name === "checking") {
    return missedRead(state, state.stage, message);
  }
  // Nothing was asked for by the reload, so a session gone, or expired, is simply the opening.
  if (outcome === "start_again" && run.kind === "reload") {
    return INITIAL;
  }
  if (outcome === "start_again" || run.kind !== "answers") {
    return startAgain(state, message);
  }
  return notApplied(state, run, message);
}

/** The session cannot go on: the message, and the composer with the input in it. */
function startAgain(state: ThreadState, message: string): ThreadState {
  return {
    ...state,
    stage: { name: "editing", examples: false },
    draft: state.input,
    turns: [...state.turns, { kind: "message", text: message }],
    notice: null,
  };
}

/** The answers were not applied: the thread goes back to the questions, what the run added gone,
 * with every chip and word as they were sent, and a step opens again with the message. */
function notApplied(
  state: ThreadState,
  run: Extract<Run, { kind: "answers" }>,
  message: string,
): ThreadState {
  const { session, given } = run;
  const asked: ThreadState = {
    ...state,
    stage: { name: "questions", session },
    picks: given.answers,
    turns: untilAsked(state.turns),
    notice: null,
  };
  return openedAgain(asked, session, message);
}

/** The thread as it was when the questions were asked. */
function untilAsked(turns: Turn[]): Turn[] {
  const asked = turns.findLastIndex((turn) => turn.kind === "questions");
  return asked === -1 ? turns : turns.slice(0, asked + 1);
}

/** Answers not sent, or not applied: the step with the most words written opens again with the
 * message, the first on a tie; with nothing written, the first question with no answer, or the
 * closing step. */
function openedAgain(state: ThreadState, session: SessionStart, message: string): ThreadState {
  const written = [
    ...session.questions.map((question) => ({
      step: question.id,
      words: ownAnswerOf(state, question) ?? "",
    })),
    { step: null, words: hasText(state.anythingElse) ? state.anythingElse : "" },
  ].filter(({ words }) => words !== "");
  const step =
    written.length === 0
      ? openAfter(session.questions, state, -1)
      : written.reduce((most, next) => (next.words.length > most.words.length ? next : most)).step;
  return { ...state, openQuestion: step, stepError: message };
}

function streamed(state: ThreadState, event: StreamEvent): ThreadState {
  switch (event.event) {
    case "session_started":
      return { ...state, sessionId: event.session_id };
    case "progress":
      return { ...state, turns: progressed(state.turns, event) };
    case "understood":
      return {
        ...state,
        turns: [
          ...withoutReading(state.turns),
          { kind: "understood", line: event.line, label: event.label },
        ],
      };
    case "session":
      return paused(state, event.session, event.lines);
    case "reply_read": {
      const { lines, factors } = event;
      return lines.length > 0 || factors.length > 0
        ? { ...state, turns: [...state.turns, { kind: "reply", lines, factors }] }
        : state;
    }
    case "report":
      return reported(state, event.report, event.lines);
    case "error":
      return stoppedWith(state, event.code, event.message);
    default:
      return state;
  }
}

/** A turn the thread shows in a round: every turn but progress, which is the status line's, and
 * the report, which is the results page's. */
export type RoundTurn = Exclude<Turn, { kind: "progress" | "report" }>;

/** One round of the thread (docs/design/chat_page_brief.md, "The thread"): what the shopper sent,
 * the request or the answers, under its heading. Their own words come first, then what the app
 * took from them and said of them, each turn with its place in the thread as its key. */
export interface Round {
  heading: string;
  turns: { key: number; turn: RoundTurn }[];
}

/** The thread in rounds: the request, then, once the questions are asked, the answers. */
export function roundsOf(turns: Turn[]): Round[] {
  const keyed = turns.flatMap((turn, key) =>
    turn.kind === "progress" || turn.kind === "report" ? [] : [{ key, turn }],
  );
  const asked = keyed.findIndex(({ turn }) => turn.kind === "questions");
  const parts = asked === -1 ? [keyed] : [keyed.slice(0, asked), keyed.slice(asked)];
  return turns.length === 0
    ? []
    : parts.map((part, index) => ({
        heading: index === 0 ? ROUND_REQUEST : ROUND_ANSWERS,
        turns: [
          ...part.filter(({ turn }) => turn.kind === "user"),
          ...part.filter(({ turn }) => turn.kind !== "user"),
        ],
      }));
}

/** The one status line, the thread's live region for progress: the step at work while a run is
 * open, in its started words, with what category research reads under it; replaced as the next
 * step starts, and gone when the run ends. A step cut off by a lost stream stays while the
 * session is read again. */
export interface Status {
  line: string;
  detail: string | null;
}

export function statusOf({ stage, turns }: ThreadState): Status | null {
  if (stage.name === "report" && !stage.compared) {
    return { line: COMPARISON_READY, detail: null };
  }
  // The session's first read comes back at once; only a run still going needs the line.
  if (stage.name === "checking" && stage.run.kind === "reload" && stage.wait > 0) {
    return { line: STILL_WORKING, detail: null };
  }
  const step = isWorking(stage)
    ? turns.findLast((turn): turn is Progress => turn.kind === "progress" && !turn.done)
    : undefined;
  if (step === undefined) {
    return null;
  }
  const researching = step.agent === "brief" && step.step === "research";
  return { line: step.line, detail: researching ? RESEARCHING_DETAIL : null };
}

/** What the composer shows, or null when it is hidden: it takes the input, from the opening until
 * the first send, and again when a request does not run; the questions have their own steps. */
export interface Composer {
  /** The example buttons, by a composer that opened empty. */
  examples: boolean;
  canSend: boolean;
  /** The request was stopped once to ask for a budget, and still has no number in it. */
  askingBudget: boolean;
}

export function composerOf({ stage, draft, budgetAsked }: ThreadState): Composer | null {
  return stage.name === "editing"
    ? {
        examples: stage.examples,
        canSend: hasText(draft),
        askingBudget: budgetAsked && !hasNumber(draft),
      }
    : null;
}

/** Whether sending the draft stops, this once, to ask for a budget: it has no number in it, and is
 * not a link, whose page states a price. Sent again, it goes as it is. */
export function asksBudget({ draft, budgetAsked }: ThreadState): boolean {
  return !budgetAsked && !hasNumber(draft) && !LINK.test(draft);
}

function hasNumber(text: string): boolean {
  return /\d/.test(text);
}

/** The answers the page sends: the chips marked, and the reply joined from what was written,
 * unless nothing was. */
export function givenOf(state: ThreadState): AnswersRequest {
  const reply = replyOf(state);
  return reply === null ? { answers: state.picks } : { answers: state.picks, reply };
}

/** The one reply the API reads: each answer in the user's own words after the question it
 * answers, then the closing step's words, one to a line. */
function replyOf(state: ThreadState): string | null {
  const questions = state.stage.name === "questions" ? state.stage.session.questions : [];
  const written = [
    ...questions.flatMap((question) => {
      const words = ownAnswerOf(state, question);
      return words === null ? [] : [aboutQuestion(question.text) + words.trim()];
    }),
    ...(hasText(state.anythingElse) ? [state.anythingElse.trim()] : []),
  ];
  return written.length > 0 ? written.join("\n") : null;
}

/** Whether the answers' reply is longer than the API reads (the schema's `maxLength`), counted in
 * characters as the API counts them. */
export function isTooLong({ reply }: AnswersRequest, maxLength: number | undefined): boolean {
  return reply != null && maxLength !== undefined && [...reply].length > maxLength;
}

/** The answers sent: the chips and the words stay as sent, and the closing step's words are the
 * user's turn. */
function answered(state: ThreadState, token: number, given: AnswersRequest): ThreadState {
  if (state.stage.name !== "questions") {
    return state;
  }
  const { session } = state.stage;
  const { anythingElse } = state;
  return {
    ...state,
    token,
    picks: given.answers,
    openQuestion: null,
    stepError: null,
    stage: { name: "running", run: { kind: "answers", session, given } },
    turns: hasText(anythingElse)
      ? [...state.turns, { kind: "user", text: anythingElse }]
      : state.turns,
  };
}

function hasText(text: string): boolean {
  return text.trim() !== "";
}

/** One chip of a question: the answer it marks, and its words. */
export interface Chip {
  pick: GivenAnswer;
  words: string;
}

/** A question's chips: its choices, then "Not sure". */
export function chipsOf(question: Question): Chip[] {
  const { factor_id } = question;
  return [
    ...question.choices.map((choice) => ({
      pick: { factor_id, status: "chosen" as const, choice_id: choice.id },
      words: choice.text,
    })),
    { pick: { factor_id, status: "not_sure" }, words: NOT_SURE },
  ];
}

/** Whether this chip is the one marked for its question. */
export function isPicked(picks: GivenAnswer[], pick: GivenAnswer): boolean {
  return picks.some(
    (marked) =>
      marked.factor_id === pick.factor_id &&
      marked.status === pick.status &&
      (marked.choice_id ?? null) === (pick.choice_id ?? null),
  );
}

/** The marks after a chip is tapped: the question's mark moves to it, or is cleared when it was
 * the one marked. */
function toggled(picks: GivenAnswer[], pick: GivenAnswer): GivenAnswer[] {
  const others = picks.filter((marked) => marked.factor_id !== pick.factor_id);
  return isPicked(picks, pick) ? others : [...others, pick];
}

/** A chip tapped: its mark, in place of the question's own words, whose field folds; then the
 * next question with no answer opens. A mark cleared keeps its question open. */
function picked(state: ThreadState, session: SessionStart, pick: GivenAnswer): ThreadState {
  const at = session.questions.findIndex((question) => question.factor_id === pick.factor_id);
  const picks = toggled(state.picks, pick);
  const marked: ThreadState = {
    ...state,
    picks,
    inOwnWords: state.inOwnWords.filter((id) => id !== session.questions[at]?.id),
    stepError: null,
  };
  if (!isPicked(picks, pick)) {
    return marked;
  }
  return { ...marked, openQuestion: openAfter(session.questions, marked, at) };
}

/** An action on one of the questions asked, by id; anything else leaves the thread as it is. */
function askedAt(
  state: ThreadState,
  questionId: string,
  change: (state: ThreadState, question: Question, session: SessionStart) => ThreadState,
): ThreadState {
  if (state.stage.name !== "questions") {
    return state;
  }
  const { session } = state.stage;
  const question = session.questions.find((asked) => asked.id === questionId);
  return question === undefined ? state : change(state, question, session);
}

/** "Something else" tapped: its field opens and its words become the answer, in place of a
 * chip's mark; tapped again, the field folds, its words kept. */
function toggledOwnWords(state: ThreadState, question: Question): ThreadState {
  const others = state.inOwnWords.filter((id) => id !== question.id);
  if (others.length < state.inOwnWords.length) {
    return { ...state, inOwnWords: others };
  }
  return {
    ...state,
    picks: state.picks.filter((marked) => marked.factor_id !== question.factor_id),
    inOwnWords: [...others, question.id],
  };
}

/** Next, under the question's own words: once they are not blank, the next question with no
 * answer opens. */
function movedOn(state: ThreadState, question: Question, session: SessionStart): ThreadState {
  if (ownAnswerOf(state, question) === null) {
    return state;
  }
  const at = session.questions.indexOf(question);
  return { ...state, openQuestion: openAfter(session.questions, state, at), stepError: null };
}

/** How the questions are answered: the chips marked, and the words written in place of one. */
type Answers = Pick<ThreadState, "picks" | "ownWords" | "inOwnWords">;

/** A question's answer in the user's own words: its field's words while "Something else" is
 * tapped, unless they are blank. */
function ownAnswerOf({ ownWords, inOwnWords }: Answers, question: Question): string | null {
  const words = ownWords[question.id] ?? "";
  return inOwnWords.includes(question.id) && hasText(words) ? words : null;
}

/** The first question after the one at `at` with no answer, from the start again once the end is
 * passed; none when every question has one. */
function openAfter(questions: Question[], answers: Answers, at: number): string | null {
  const order = [...questions.slice(at + 1), ...questions.slice(0, at + 1)];
  return order.find((question) => !isAnswered(answers, question))?.id ?? null;
}

function isAnswered(answers: Answers, question: Question): boolean {
  return (
    answers.picks.some((marked) => marked.factor_id === question.factor_id) ||
    ownAnswerOf(answers, question) !== null
  );
}

/** The question open at the questions: where it is among them, how many others still have no
 * answer, and what is written under its "Something else". */
export interface OpenQuestion {
  question: Question;
  place: number;
  total: number;
  more: number;
  /** The words in its field, kept while a chip is its answer. */
  ownWords: string;
  /** "Something else" is tapped: its field is open, and its words are the answer. */
  inOwnWords: boolean;
  /** Why the answers were not sent, or not applied, when this step opened again for it. */
  error: string | null;
}

/** The open question, or none: before or after the questions, or once every one has an
 * answer. */
export function openQuestionOf(state: ThreadState): OpenQuestion | null {
  const { stage, openQuestion } = state;
  if (stage.name !== "questions") {
    return null;
  }
  const { questions } = stage.session;
  const at = questions.findIndex((question) => question.id === openQuestion);
  if (at === -1) {
    return null;
  }
  const question = questions[at];
  const more = questions.filter((other, index) => index !== at && !isAnswered(state, other)).length;
  return {
    question,
    place: at + 1,
    total: questions.length,
    more,
    ownWords: state.ownWords[question.id] ?? "",
    inOwnWords: state.inOwnWords.includes(question.id),
    error: state.stepError,
  };
}

/** The closing step, open at the questions once every question has an answer, and at a pause
 * with none to ask: "Anything else we should know?", with what is written there. */
export interface ClosingStep {
  words: string;
  /** Why the answers were not sent, or not applied, when this step opened again for it. */
  error: string | null;
}

export function closingStepOf(state: ThreadState): ClosingStep | null {
  return state.stage.name === "questions" && openQuestionOf(state) === null
    ? { words: state.anythingElse, error: state.stepError }
    : null;
}

type Progress = Extract<Turn, { kind: "progress" }>;

/** What the box shows (docs/design/chat_page_brief.md, "The memorable moment"): open for
 * labelling, sealed while the answers run, opened at the report. */
export interface Box {
  state: "labelling" | "sealed" | "open";
  /** The request as it was sent, kept on the face, faded, once the thread has begun. */
  request: string | null;
  /** The questions are asked: the face keeps the request alone, at its top, to leave room for
   * their labels. */
  cleared: boolean;
  /** What its first label says: what was understood, in the words the API sends for it, or "?"
   * for a request that could not be read. */
  lookingFor: string | null;
  /** The request is being read: a blank label waits on the box for the Looking-for words. */
  reading: boolean;
  /** The steps of the answers' run still at work, their lines in its scan window. */
  scan: Progress[];
  /** At the questions: how many of them have an answer. */
  tally: { answered: number; asked: number } | null;
}

export function boxOf(state: ThreadState): Box {
  const { stage, turns } = state;
  const understood = turns.find((turn) => turn.kind === "understood");
  const sent = turns.length > 0;
  // A start that ended with nothing understood: declined, or stopped.
  const unread = sent && understood === undefined && !isWorking(stage);
  const lookingFor =
    understood?.label != null ? lineText(understood.label) : unread ? UNREAD_LABEL : null;
  const tally =
    stage.name === "questions" && stage.session.questions.length > 0
      ? { answered: labelsOf(state).length, asked: stage.session.questions.length }
      : null;
  const reading = lookingFor === null && isWorking(stage) && stage.run.kind === "start";
  const cleared = askedOf(turns) !== undefined;
  const shown = { request: sent ? state.input : null, cleared, lookingFor, reading, tally };
  if (stage.name === "report") {
    return { state: "open", scan: [], ...shown };
  }
  if (isWorking(stage) && stage.run.kind === "answers") {
    const atWork = answersRun(turns).filter((turn) => !turn.done);
    return { state: "sealed", scan: atWork, ...shown };
  }
  return { state: "labelling", scan: [], ...shown };
}

/** The questions turn, once the questions are asked. */
function askedOf(turns: Turn[]): Extract<Turn, { kind: "questions" }> | undefined {
  return turns.findLast((turn) => turn.kind === "questions");
}

/** The progress of the answers' run: the lines after what the user last sent or was told. */
function answersRun(turns: Turn[]): Progress[] {
  const sent = turns.findLastIndex(
    (turn) => turn.kind === "questions" || turn.kind === "user" || turn.kind === "message",
  );
  return turns.slice(sent + 1).filter((turn) => turn.kind === "progress");
}

/** An answered question, as it is labelled in the thread and on the box: the name of the factor
 * it is drawn from, when the session names it, and the answer. Or a factor of the user's own the
 * reply added: its phrase alone. */
export interface Label {
  /** The question's id; for a factor of the user's own, the factor's. */
  id: string;
  key: string | null;
  value: string;
  /** Answered "not sure". */
  unsure: boolean;
  /** A factor of the user's own the reply added, which no question asked: its phrase is shown
   * whole in the thread. */
  added: boolean;
}

/** The answered questions in the order asked, from the questions, the marks and the words
 * written in place of one, then the factors of the user's own the reader kept from the reply; none
 * before the questions. Once the answers are sent, a question sent with none is labelled as not
 * sure, so a skip shows (docs/design/chat_page_brief.md, "The interview panel"). What the user
 * wrote at the closing step is never a label: only what the reader kept from it. */
export function labelsOf(state: ThreadState): Label[] {
  const asked = askedOf(state.turns);
  if (asked === undefined) {
    return [];
  }
  const read = state.turns.findLast((turn) => turn.kind === "reply");
  const added = (read?.factors ?? []).map((factor) => ({
    id: factor.id,
    key: null,
    value: factor.name,
    unsure: false,
    added: true,
  }));
  return [...answeredOf(state, asked), ...added];
}

function answeredOf(state: ThreadState, asked: Extract<Turn, { kind: "questions" }>): Label[] {
  const sent = state.stage.name !== "questions";
  return asked.questions.flatMap((question) => {
    const pick = state.picks.find((marked) => marked.factor_id === question.factor_id);
    const own = ownAnswerOf(state, question);
    if (pick === undefined && own === null && !sent) {
      return [];
    }
    const factor = asked.factors.find((candidate) => candidate.id === question.factor_id);
    const chip =
      pick === undefined
        ? undefined
        : chipsOf(question).find(({ pick: offered }) => isPicked([pick], offered));
    return [
      {
        id: question.id,
        key: factor?.name ?? null,
        value: own?.trim() ?? chip?.words ?? NOT_SURE,
        unsure: own === null && (pick === undefined || pick.status === "not_sure"),
        added: false,
      },
    ];
  });
}

/** The session at the pause: what the app says before the first question, in the terminal
 * app's order (`cli.py`), then the questions; the Looking-for line first when a start lost
 * before its `understood` event did not show it. A request that does not run has its decline. */
function paused(state: ThreadState, session: SessionStart, lines: SessionLines): ThreadState {
  const read = { ...state, turns: withUnderstood(withoutReading(state.turns), lines) };
  if (session.report !== null) {
    return declined(read, lines.declined, session.request.scope);
  }
  const said = [...session.warnings.map((warning) => textLine(warning.message)), ...lines.stated];
  const turns: Turn[] = [
    ...read.turns,
    ...(said.length > 0 ? [{ kind: "lines" as const, lines: said }] : []),
    ...(lines.typical_costs.length > 0
      ? [{ kind: "notes" as const, lines: lines.typical_costs }]
      : []),
    {
      kind: "questions",
      questions: session.questions,
      sources: lines.sources,
      factors: session.factors,
    },
  ];
  return {
    ...read,
    stage: { name: "questions", session },
    openQuestion: openAfter(session.questions, read, -1),
    turns,
  };
}

/** A request that does not run: its decline, then the composer, empty with the examples for
 * something that is not a durable product, and with the input in it for one that could not be
 * understood or named several, so it can be put right. */
function declined(state: ThreadState, line: Line | null, scope: Scope): ThreadState {
  const fresh = scope === "not_a_product";
  return {
    ...state,
    stage: { name: "editing", examples: fresh },
    draft: fresh ? "" : state.input,
    turns: line === null ? state.turns : [...state.turns, { kind: "lines", lines: [line] }],
  };
}

/** A sentence the API sends as a string, such as a warning, as a line of one part. */
function textLine(text: string): Line {
  return { parts: [{ kind: "text", text }] };
}

/** A step's started line is added; its finished line takes the place of the started one. The
 * supervisor's closing line gets none, and the second-hand agent's steps none at all. */
function progressed(turns: Turn[], event: ProgressEvent): Turn[] {
  const { agent, step, message } = event;
  if (agent === HIDDEN_AGENT || (agent === "supervisor" && event.status === "finished")) {
    return turns;
  }
  const line: Turn = { kind: "progress", agent, step, line: message, running: false, done: true };
  if (event.status === "started") {
    return [...turns, { ...line, running: true, done: false }];
  }
  const at = turns.findLastIndex(
    (turn) =>
      turn.kind === "progress" && turn.running && turn.agent === agent && turn.step === step,
  );
  return at === -1 ? [...turns, line] : turns.with(at, line);
}

function withUnderstood(turns: Turn[], { understood, label }: SessionLines): Turn[] {
  const shown = turns.some((turn) => turn.kind === "understood");
  return shown || understood === null
    ? turns
    : [...turns, { kind: "understood", line: understood, label }];
}

/** The thread without the supervisor's line, which goes once what it read is shown. */
function withoutReading(turns: Turn[]): Turn[] {
  return turns.filter((turn) => !(turn.kind === "progress" && turn.agent === "supervisor"));
}

/** Where a station of the route line stands. */
export type StationState = "done" | "current" | "ahead";

export type Agent = ProgressEvent["agent"];

/** One station of the route line (docs/design/chat_page_brief.md, "The route line"): an agent and
 * its state, shown by its dot alone; the agent's line is the status line's. On the results page it
 * opens the agent's part of the trail. */
export interface Station {
  agent: Agent;
  name: string;
  state: StationState;
  /** What the agent does, in any run, in plain words: opened from the route line during a wait. */
  detail: string;
}

// The second-hand agent is a stub in this version, so the page shows none of it: no station, no
// progress and, with no station to open it, no trail.
type ShownAgent = Exclude<Agent, typeof HIDDEN_AGENT>;

// Each shown agent's station, in the order they run. Every one has one, so a new agent does not
// typecheck until it is placed here, and no trail line is left without a station to open it.
const STATION_NAMES: Record<ShownAgent, string> = {
  supervisor: ROUTE_REQUEST,
  brief: ROUTE_QUESTIONS,
  tco: ROUTE_OPTIONS,
  lca: ROUTE_CO2E,
};

const STATION_DETAILS: Record<ShownAgent, string> = {
  supervisor: ROUTE_REQUEST_DETAIL,
  brief: ROUTE_QUESTIONS_DETAIL,
  tco: ROUTE_OPTIONS_DETAIL,
  lca: ROUTE_CO2E_DETAIL,
};

const AGENTS = Object.keys(STATION_NAMES) as ShownAgent[];

// The agents of the answers' run, in the order they run.
const RUN_AGENTS: ShownAgent[] = ["tco", "lca"];

/** The route line once the report has landed, as the results page sets it: every station done. */
export const ROUTE_DONE: Station[] = AGENTS.map((agent) => station(agent, "done"));

/** Whether the stations open their notes: during either wait, the request's or the answers', after
 * a reload that finds a run still going, and between the waits, at the questions and with the box
 * open; but not during a reload's first read, which comes back at once. */
export function explainsRoute({ stage }: ThreadState): boolean {
  if (isWorking(stage)) {
    return !(stage.name === "checking" && stage.run.kind === "reload" && stage.wait === 0);
  }
  return stage.name === "questions" || (stage.name === "report" && !stage.compared);
}

/** Whether the hint under the line says so: during a wait, when there is nothing else to do. */
export function hintsRoute({ stage }: ThreadState): boolean {
  return isWorking(stage);
}

/** The route line: one station per agent, done, current or ahead, from the stage and the
 * progress of the runs; before the first send, and once a session ends without its report,
 * every station is ahead. */
export function routeOf({ stage, turns }: ThreadState): Station[] {
  const starting = isWorking(stage) && stage.run.kind === "start";
  const answering = isWorking(stage) && stage.run.kind === "answers";
  if (stage.name === "report") {
    return ROUTE_DONE;
  }
  if (!starting && !answering && stage.name !== "questions") {
    return AGENTS.map((agent) => station(agent, "ahead"));
  }
  const understood = turns.some((turn) => turn.kind === "understood");
  const run = answering ? answersRun(turns) : [];
  const runStarted = run.some((turn) => turn.agent !== "brief");
  return [
    station("supervisor", understood || !starting ? "done" : "current"),
    station("brief", runStarted ? "done" : !understood && starting ? "ahead" : "current"),
    ...RUN_AGENTS.map((agent) => {
      const step = run.findLast((turn) => turn.agent === agent);
      return station(agent, step?.done ? "done" : step === undefined ? "ahead" : "current");
    }),
  ];
}

function station(agent: ShownAgent, state: StationState): Station {
  return { agent, name: STATION_NAMES[agent], state, detail: STATION_DETAILS[agent] };
}
