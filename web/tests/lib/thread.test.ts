import { describe, expect, test } from "vitest";

import type {
  AnswersRequest,
  ApiError,
  DecisionFactor,
  ErrorEvent,
  GivenAnswer,
  Line,
  ReplyReadEvent,
  SessionView,
  StreamEvent,
} from "../../lib/api/types";
import {
  INITIAL,
  asksBudget,
  boxOf,
  chipsOf,
  closingStepOf,
  composerOf,
  explainsRoute,
  givenOf,
  hintsRoute,
  isTooLong,
  openQuestionOf,
  resultsOf,
  roundsOf,
  routeOf,
  statusOf,
  labelsOf,
  nextThread,
  type Action,
  type ApiResult,
  type ThreadState,
} from "../../lib/thread";
import {
  ANSWERS_NOT_APPLIED,
  NOT_SURE,
  REPLY_TOO_LONG,
  RESEARCHING_DETAIL,
  ROUND_ANSWERS,
  ROUND_REQUEST,
  ROUTE_CO2E,
  ROUTE_OPTIONS,
  ROUTE_QUESTIONS,
  ROUTE_REQUEST,
  COMPARISON_READY,
  RUN_STOPPED,
  STILL_WORKING,
  UNREAD_LABEL,
  UNREACHABLE,
} from "../../lib/wording";
import {
  ASKED_TWO,
  AT_THE_PAUSE,
  BOX_LABEL,
  BLOCKED_LINK,
  DECLINE,
  DECLINED,
  DECLINED_LINES,
  DECLINED_SESSION,
  FRYING_PAN_INPUT,
  FRYING_PAN_REPORT,
  HOB_SOURCE,
  LINK_UNREADABLE,
  LINKED_AT_THE_PAUSE,
  LINKED_PAUSED,
  LOOKING_FOR,
  NOT_FOUND,
  NOTHING_ASKED,
  PAUSE_LINES,
  progress,
  PAUSED,
  READING,
  REPORT_LINES,
  REPORTED,
  RESEARCHED,
  RESEARCHING,
  SESSION_ID,
  STARTED,
  STATED,
  SUPERVISOR_FINISHED,
  TYPICAL_COST,
  UNDERSTOOD,
  UNREADABLE_SESSION,
} from "./samples";

function after(...actions: Action[]): ThreadState {
  return actions.reduce(nextThread, INITIAL);
}

/** What the API answered for a run: the first start's unless another token is given. */
function heard(result: ApiResult, token = 1): Action {
  return { type: "api", token, result };
}

function streamed(event: StreamEvent, token = 1): Action {
  return heard({ type: "streamed", event }, token);
}

/** An event of the answers' run, whose token `answered` gives by default. */
function answerEvent(event: StreamEvent): Action {
  return streamed(event, 2);
}

const typed: Action = { type: "typed", draft: FRYING_PAN_INPUT };
const compared: Action = { type: "compared" };
const started: Action = { type: "started", token: 1 };
const sentStart: Action[] = [typed, started, streamed(STARTED)];

describe("a start", () => {
  test("opens the thread with the input as the user typed it, and empties the composer", () => {
    const state = after(typed, started);

    expect(state.turns).toEqual([{ kind: "user", text: FRYING_PAN_INPUT }]);
    expect(state.draft).toBe("");
  });
});

describe("the pause", () => {
  test("shows the warnings and the request's lines, the typical costs as notes, then the questions", () => {
    const state = after(...sentStart, streamed(UNDERSTOOD), streamed(LINKED_PAUSED));

    expect(state.turns.slice(1)).toEqual([
      { kind: "understood", line: LOOKING_FOR, label: BOX_LABEL },
      { kind: "lines", lines: [{ parts: [{ kind: "text", text: LINK_UNREADABLE }] }, STATED] },
      { kind: "notes", lines: [TYPICAL_COST] },
      {
        kind: "questions",
        questions: LINKED_AT_THE_PAUSE.questions,
        sources: { "question-researched-1": HOB_SOURCE },
        factors: [],
      },
    ]);
  });

  test("waits for the answers to the session's questions", () => {
    const state = after(...sentStart, streamed(UNDERSTOOD), streamed(PAUSED));

    expect(state.stage).toEqual({ name: "questions", session: AT_THE_PAUSE });
  });
});

const atThePause: Action[] = [...sentStart, streamed(UNDERSTOOD), streamed(PAUSED)];
const induction: GivenAnswer = {
  factor_id: "researched-1",
  status: "chosen",
  choice_id: "choice-2",
};
const gas: GivenAnswer = { factor_id: "researched-1", status: "chosen", choice_id: "choice-1" };
const hobNotSure: GivenAnswer = { factor_id: "researched-1", status: "not_sure" };

function picked(pick: GivenAnswer): Action {
  return { type: "picked", pick };
}

/** A label tapped, which opens its question again. */
function reopen(questionId: string): Action {
  return { type: "reopened", questionId };
}

const askedTwo: Action[] = [
  ...sentStart,
  streamed(UNDERSTOOD),
  streamed({ event: "session", session: ASKED_TWO, lines: PAUSE_LINES }),
];
const [hobQuestion, usageQuestion] = ASKED_TWO.questions;
const daily: GivenAnswer = { factor_id: "usage", status: "chosen", choice_id: "choice-daily" };

/** "Something else" tapped on a question, and words written in its field. */
function inOwnWords(questionId: string, words: string): Action[] {
  return [
    { type: "own_words", questionId },
    { type: "wrote", questionId, words },
  ];
}

/** Words written at the closing step. */
function added(words: string): Action {
  return { type: "added", words };
}

describe("the chips", () => {
  test("of a question are its choices, then Not sure", () => {
    expect(chipsOf(AT_THE_PAUSE.questions[0])).toEqual([
      { pick: gas, words: "Gas" },
      { pick: induction, words: "Induction" },
      { pick: hobNotSure, words: NOT_SURE },
    ]);
  });

  test("mark the choice tapped, and a second tap clears the mark", () => {
    const marked = after(...atThePause, picked(induction));
    const cleared = after(...atThePause, picked(induction), picked(induction));

    expect(marked.picks).toEqual([induction]);
    expect(cleared.picks).toEqual([]);
  });

  test("hold one mark per question, which moves to another choice or to not sure", () => {
    const moved = after(...atThePause, picked(induction), picked(gas));
    const unsure = after(...atThePause, picked(induction), picked(hobNotSure));

    expect(moved.picks).toEqual([gas]);
    expect(unsure.picks).toEqual([hobNotSure]);
  });
});

const NOTHING_GIVEN: AnswersRequest = { answers: [] };

function answered(given: AnswersRequest, token = 2): Action {
  return { type: "answered", token, given };
}

const heldBack: Action = { type: "held_back" };

describe("the answers", () => {
  test("are the marks, and the reply joined from what was written", () => {
    const state = after(
      ...askedTwo,
      picked(induction),
      ...inOwnWords(usageQuestion.id, " twice a week "),
      added("We cook on gas "),
    );

    expect(givenOf(state)).toEqual({
      answers: [induction],
      reply: `About "${usageQuestion.text}": twice a week\nWe cook on gas`,
    });
  });

  test("leave the reply out when nothing but blanks was written", () => {
    const state = after(
      ...askedTwo,
      picked(induction),
      ...inOwnWords(usageQuestion.id, "  "),
      added(" "),
    );

    expect(givenOf(state)).toEqual({ answers: [induction] });
  });

  test("leave out the words of a field a chip folded", () => {
    const state = after(...askedTwo, ...inOwnWords(hobQuestion.id, "a camping stove"), picked(gas));

    expect(givenOf(state)).toEqual({ answers: [gas] });
  });

  test("sent add the closing step's words as the user's turn", () => {
    const paused = after(...atThePause, picked(induction), added("We cook on gas"));
    const state = nextThread(paused, answered(givenOf(paused)));

    expect(state.turns).toEqual([...paused.turns, { kind: "user", text: "We cook on gas" }]);
  });

  test("sent as chips and own words alone add no user turn, and stay as given", () => {
    const paused = after(
      ...askedTwo,
      picked(induction),
      ...inOwnWords(usageQuestion.id, "twice a week"),
    );
    const state = nextThread(paused, answered(givenOf(paused)));

    expect(state.turns).toEqual(paused.turns);
    expect(state.picks).toEqual([induction]);
    expect(labelsOf(state).map(({ value }) => value)).toEqual(["Induction", "twice a week"]);
  });

  test("run with the session's questions and what was given", () => {
    const state = after(...atThePause, answered(NOTHING_GIVEN));

    expect(state.stage).toEqual({
      name: "running",
      run: { kind: "answers", session: AT_THE_PAUSE, given: NOTHING_GIVEN },
    });
  });

  test.each([
    ["at the cap", "x".repeat(2000), false],
    ["one character over it", "x".repeat(2001), true],
    ["counted in characters, as the API counts them", "🍳".repeat(2000), false],
  ])("with a reply %s are too long: %s", (_reply, reply, tooLong) => {
    expect(isTooLong({ answers: [], reply }, 2000)).toBe(tooLong);
  });

  test("with no reply are never too long", () => {
    expect(isTooLong({ answers: [induction] }, 2000)).toBe(false);
  });

  test("held back open the step with the most words again, saying why", () => {
    const closingMost = after(
      ...askedTwo,
      ...inOwnWords(hobQuestion.id, "gas"),
      picked(daily),
      added("We cook every day"),
      heldBack,
    );
    const questionMost = after(
      ...askedTwo,
      ...inOwnWords(hobQuestion.id, "a camping stove, mostly"),
      picked(daily),
      added("Thanks"),
      heldBack,
    );

    expect(closingStepOf(closingMost)).toEqual({
      words: "We cook every day",
      error: REPLY_TOO_LONG,
    });
    expect(openQuestionOf(questionMost)).toMatchObject({
      question: hobQuestion,
      inOwnWords: true,
      error: REPLY_TOO_LONG,
    });
    expect(questionMost.stage.name).toBe("questions");
  });
});

describe("an answer in the user's own words", () => {
  test("opens the question's field when Something else is tapped, in place of the chip marked", () => {
    const state = after(...askedTwo, picked(induction), reopen(hobQuestion.id), {
      type: "own_words",
      questionId: hobQuestion.id,
    });

    expect(state.picks).toEqual([]);
    expect(openQuestionOf(state)).toMatchObject({ question: hobQuestion, inOwnWords: true });
  });

  test("answers the question once its words are not blank, and Next moves on", () => {
    const moveOn: Action = { type: "moved_on", questionId: hobQuestion.id };
    const blank = after(...askedTwo, ...inOwnWords(hobQuestion.id, "  "), moveOn);
    const written = after(...askedTwo, ...inOwnWords(hobQuestion.id, "a camping stove"), moveOn);

    expect(openQuestionOf(blank)?.question).toEqual(hobQuestion);
    expect(openQuestionOf(written)?.question).toEqual(usageQuestion);
    expect(labelsOf(written)).toEqual([
      {
        id: hobQuestion.id,
        key: "Hob compatibility",
        value: "a camping stove",
        unsure: false,
        added: false,
      },
    ]);
  });

  test("folds when another chip is tapped, its words kept", () => {
    const state = after(
      ...askedTwo,
      ...inOwnWords(hobQuestion.id, "a camping stove"),
      picked(gas),
      reopen(hobQuestion.id),
    );

    expect(state.picks).toEqual([gas]);
    expect(openQuestionOf(state)).toMatchObject({
      ownWords: "a camping stove",
      inOwnWords: false,
    });
  });

  test("folds when Something else is tapped again, leaving the question with no answer", () => {
    const state = after(...askedTwo, ...inOwnWords(hobQuestion.id, "a camping stove"), {
      type: "own_words",
      questionId: hobQuestion.id,
    });

    expect(openQuestionOf(state)).toMatchObject({ ownWords: "a camping stove", inOwnWords: false });
    expect(labelsOf(state)).toEqual([]);
  });
});

describe("the closing step", () => {
  test("opens once every question has an answer", () => {
    const state = after(...askedTwo, picked(induction), picked(daily));

    expect(openQuestionOf(state)).toBeNull();
    expect(closingStepOf(state)).toEqual({ words: "", error: null });
  });

  test("is all a pause with nothing to ask has", () => {
    const state = after(...sentStart, streamed(NOTHING_ASKED));

    expect(state.turns.at(-1)).toMatchObject({ kind: "questions", questions: [] });
    expect(closingStepOf(state)).toEqual({ words: "", error: null });
  });

  test("keeps what is written there", () => {
    const state = after(...askedTwo, picked(induction), picked(daily), added("Dishwasher safe"));

    expect(closingStepOf(state)?.words).toBe("Dishwasher safe");
  });

  test("is closed while a question is open, and once the answers are sent", () => {
    expect(closingStepOf(after(...askedTwo))).toBeNull();
    expect(closingStepOf(after(...askedTwo, answered(NOTHING_GIVEN)))).toBeNull();
  });
});

const replyLine: Line = {
  parts: [{ kind: "text", text: `From your reply: Hob compatibility: Gas ("gas")` }],
};

function replyRead(lines: Line[], factors: DecisionFactor[] = []): ReplyReadEvent {
  return {
    event: "reply_read",
    stated_answers: [],
    factors,
    asks_to_change_request: false,
    answered_already: false,
    lines,
  };
}

/** A factor of the user's own the reader kept from the reply: its name is the reply's phrase. */
const OWN_FACTOR: DecisionFactor = {
  id: "user-1",
  name: "Fits in a 24 cm cupboard",
  kind: "requirement",
  why: "You asked for it.",
  source: { kind: "user", reference: "Fits in a 24 cm cupboard", label: null, stated_by: null },
  typical_yearly_cost: null,
  typical_yearly_cost_source: null,
  typical_yearly_cost_converted_from: null,
};

const answering: Action[] = [...atThePause, answered(NOTHING_GIVEN)];

describe("after the answers", () => {
  test("the reply's lines are the app's turn", () => {
    const state = after(...answering, answerEvent(replyRead([replyLine])));

    expect(state.turns.at(-1)).toEqual({ kind: "reply", lines: [replyLine], factors: [] });
  });

  test("a reply read with no lines adds no turn", () => {
    const before = after(...answering);
    const state = nextThread(before, answerEvent(replyRead([])));

    expect(state.turns).toEqual(before.turns);
  });

  test("the report ends the thread with its lines", () => {
    const state = after(...answering, answerEvent(REPORTED));

    expect(state.turns.at(-1)).toEqual({
      kind: "report",
      report: FRYING_PAN_REPORT,
      lines: REPORT_LINES,
    });
    expect(state.stage).toEqual({ name: "report", compared: false });
  });

  test("the report lands on the opened box: the results page waits for See the comparison", () => {
    expect(resultsOf(after(...answering, answerEvent(REPORTED)))).toBeNull();
  });

  test("the status line says the comparison is ready, until it is opened", () => {
    expect(statusOf(after(...answering, answerEvent(REPORTED)))).toEqual({
      line: COMPARISON_READY,
      detail: null,
    });
    expect(statusOf(after(...answering, answerEvent(REPORTED), compared))).toBeNull();
  });

  test("See the comparison opens the results page", () => {
    const state = after(...answering, answerEvent(REPORTED), compared);

    expect(resultsOf(state)).toEqual({ report: FRYING_PAN_REPORT, lines: REPORT_LINES });
  });

  test("See the comparison before the report changes nothing", () => {
    const before = after(...answering);

    expect(nextThread(before, compared)).toBe(before);
  });

  test("the report is the results page's, so the rounds leave it out", () => {
    const state = after(...answering, answerEvent(REPORTED), compared);

    expect(
      roundsOf(state.turns).flatMap(({ turns }) => turns.map(({ turn }) => turn.kind)),
    ).not.toContain("report");
  });

  test("there are no results before the report", () => {
    expect(resultsOf(after(...answering))).toBeNull();
  });

  test("Start again empties the thread and opens an empty composer with the examples", () => {
    const state = after(...answering, answerEvent(REPORTED), { type: "started_again" });

    expect(state.turns).toEqual([]);
    expect(state.draft).toBe("");
    expect(state.stage).toEqual({ name: "editing", examples: true });
  });
});

function failed(code: ErrorEvent["code"], message: string): Action {
  return answerEvent({ event: "error", code, message });
}

function refused(code: ApiError["code"], message: string, token = 2): Action {
  return heard({ type: "refused", error: { code, message } }, token);
}

const pickedAndWrote: Action[] = [
  ...askedTwo,
  picked(induction),
  ...inOwnWords(usageQuestion.id, "twice a week"),
  added("We cook on gas"),
];
const sentWords = answered(givenOf(after(...pickedAndWrote)));

describe("answers that were not applied", () => {
  test.each([
    ["reply_unread", failed("reply_unread", "Nothing was run.")],
    ["reply_unanswered", failed("reply_unanswered", "Nothing was run.")],
    ["invalid_answers", refused("invalid_answers", "Nothing was run.")],
    ["reply_too_long", refused("reply_too_long", "Nothing was run.")],
    ["internal_error", refused("internal_error", "Nothing was run.")],
  ])("with %s go back to the questions, every chip and word kept", (_code, stopped) => {
    const paused = after(...pickedAndWrote);
    const state = after(...pickedAndWrote, sentWords, stopped);

    expect(state.stage).toEqual({ name: "questions", session: ASKED_TWO });
    expect(state.turns).toEqual(paused.turns);
    expect(givenOf(state)).toEqual(givenOf(paused));
  });

  test("open the step with the most words again, with the message", () => {
    const state = after(...pickedAndWrote, sentWords, failed("reply_unanswered", "No."));

    expect(closingStepOf(state)).toEqual({ words: "We cook on gas", error: "No." });
  });

  test("open a question again when its own words are the most", () => {
    const wrote = [
      ...askedTwo,
      picked(induction),
      ...inOwnWords(usageQuestion.id, "twice a week, sometimes more"),
      added("gas"),
    ];
    const state = after(
      ...wrote,
      answered(givenOf(after(...wrote))),
      failed("reply_unread", "No."),
    );

    expect(openQuestionOf(state)).toMatchObject({
      question: usageQuestion,
      ownWords: "twice a week, sometimes more",
      inOwnWords: true,
      error: "No.",
    });
  });

  test("with nothing written open the first question with no answer", () => {
    const state = after(
      ...askedTwo,
      picked(induction),
      answered({ answers: [induction] }),
      refused("invalid_answers", "No."),
    );

    expect(openQuestionOf(state)).toMatchObject({ question: usageQuestion, error: "No." });
  });

  test("drop what the run added to the thread", () => {
    const paused = after(...pickedAndWrote);
    const state = after(
      ...pickedAndWrote,
      sentWords,
      answerEvent(RESEARCHING),
      failed("reply_unanswered", "No."),
    );

    expect(state.turns).toEqual(paused.turns);
  });

  test("lose the message once another step opens", () => {
    const state = after(
      ...pickedAndWrote,
      sentWords,
      failed("reply_unanswered", "No."),
      reopen(hobQuestion.id),
    );

    expect(openQuestionOf(state)?.error).toBeNull();
  });

  test("can be sent again", () => {
    const state = after(
      ...pickedAndWrote,
      sentWords,
      failed("reply_unanswered", "No."),
      answered({ answers: [induction] }, 4),
    );

    expect(state.stage.name).toBe("running");
    expect(state.token).toBe(4);
  });
});

const ENDED: ApiResult = { type: "stream_ended" };
const ended = heard(ENDED);

describe("the end of a stream", () => {
  test("leaves a line still running with its started words, without the working mark", () => {
    const state = after(
      ...sentStart,
      streamed(READING),
      streamed({ event: "error", code: "model_call_failed", message: "Try again." }),
      ended,
    );

    expect(state.turns[1]).toEqual({
      kind: "progress",
      agent: "supervisor",
      step: "research",
      line: "Reading your request...",
      running: false,
      done: false,
    });
  });

  test("before it named its session says so, with the input back in the composer", () => {
    const state = after(typed, started, ended);

    expect(state.turns.at(-1)).toEqual({ kind: "message", text: UNREACHABLE });
    expect(state.draft).toBe(FRYING_PAN_INPUT);
    expect(state.stage).toEqual({ name: "editing", examples: false });
  });

  test("mid-run has the session it named read at once", () => {
    const state = after(...sentStart, streamed(READING), ended);

    expect(state.stage).toEqual({ name: "checking", run: { kind: "start" }, wait: 0, misses: 0 });
    expect(state.sessionId).toBe(SESSION_ID);
  });
});

function viewed(view: SessionView, token = 1): Action {
  return heard({ type: "viewed", view }, token);
}

const startCut: Action[] = [...sentStart, streamed(READING), ended];
const answersCut: Action[] = [...answering, answerEvent(RESEARCHING), heard(ENDED, 2)];
const pausedView: SessionView = { status: "paused", session: AT_THE_PAUSE, lines: PAUSE_LINES };

describe("a session read after its stream was lost", () => {
  test("at the pause, for a start cut before its Looking-for line, shows that line first", () => {
    const state = after(...startCut, viewed(pausedView));

    expect(state.turns.slice(1)).toEqual([
      { kind: "understood", line: LOOKING_FOR, label: BOX_LABEL },
      { kind: "questions", questions: AT_THE_PAUSE.questions, sources: {}, factors: [] },
    ]);
    expect(state.stage).toEqual({ name: "questions", session: AT_THE_PAUSE });
  });

  test("at the pause, for a start that showed its Looking-for line, does not show it twice", () => {
    const state = after(...sentStart, streamed(UNDERSTOOD), ended, viewed(pausedView));

    expect(state.turns.filter((turn) => turn.kind === "understood")).toHaveLength(1);
  });

  test("still at the pause after the answers says they were not applied", () => {
    const state = after(...answersCut, viewed(pausedView, 2));

    expect(openQuestionOf(state)?.error).toBe(ANSWERS_NOT_APPLIED);
    expect(state.stage).toEqual({ name: "questions", session: AT_THE_PAUSE });
  });

  test("finished opens the box on the report", () => {
    const state = after(
      ...answersCut,
      viewed({ status: "finished", report: FRYING_PAN_REPORT, lines: REPORT_LINES }, 2),
    );

    expect(boxOf(state).state).toBe("open");
    expect(state.stage).toEqual({ name: "report", compared: false });
  });

  test("finished with a decline, for a start, shows the decline", () => {
    const state = after(
      ...startCut,
      viewed({
        status: "finished",
        report: DECLINED.report!,
        lines: { ...REPORT_LINES, declined: DECLINE },
      }),
    );

    expect(state.turns.slice(1)).toEqual([{ kind: "lines", lines: [DECLINE] }]);
    expect(state.stage).toEqual({ name: "editing", examples: true });
  });

  test("interrupted says the run stopped, with the input back in the composer", () => {
    const state = after(...startCut, viewed({ status: "interrupted", code: "run_stopped" }));

    expect(state.turns.at(-1)).toEqual({ kind: "message", text: RUN_STOPPED });
    expect(state.draft).toBe(FRYING_PAN_INPUT);
  });
});

const running = viewed({ status: "running" });
const missed = heard({ type: "unreachable" });

/** The wait before each read, after the reads given. */
function waits(...reads: Action[]): number[] {
  const states = reads.reduce(
    (seen, read) => [...seen, nextThread(seen[seen.length - 1], read)],
    [after(...startCut)],
  );
  return states.map((state) => (state.stage.name === "checking" ? state.stage.wait : -1));
}

describe("reading a session again", () => {
  test("waits 2 s after a read that finds it still running, then twice as long, up to 30 s", () => {
    expect(waits(running, running, running, running, running, running)).toEqual([
      0, 2000, 4000, 8000, 16000, 30000, 30000,
    ]);
  });

  test("after a read that got no answer says so, and waits as long", () => {
    const state = after(...startCut, missed);

    expect(state.notice).toBe(UNREACHABLE);
    expect(waits(missed, missed)).toEqual([0, 2000, 4000]);
  });

  test("drops the line once the session is read", () => {
    const state = after(...startCut, missed, running);

    expect(state.notice).toBeNull();
  });

  test("of a start stops after five reads in a row with no answer, with the input back", () => {
    const state = after(...startCut, missed, missed, missed, missed, missed);

    expect(state.stage).toEqual({ name: "editing", examples: false });
    expect(state.draft).toBe(FRYING_PAN_INPUT);
    expect(state.turns.at(-1)).toEqual({ kind: "message", text: UNREACHABLE });
    expect(state.notice).toBeNull();
  });

  test("of the answers stops after five reads in a row with no answer, as not applied", () => {
    const missedAnswers = heard({ type: "unreachable" }, 2);
    const state = after(
      ...pickedAndWrote,
      sentWords,
      heard(ENDED, 2),
      missedAnswers,
      missedAnswers,
      missedAnswers,
      missedAnswers,
      missedAnswers,
    );

    expect(state.stage).toEqual({ name: "questions", session: ASKED_TWO });
    expect(closingStepOf(state)).toEqual({ words: "We cook on gas", error: UNREACHABLE });
  });

  test("counts only the reads with no answer in a row", () => {
    const state = after(...startCut, missed, missed, missed, missed, running, missed);

    expect(state.stage.name).toBe("checking");
  });
});

const reloaded: Action = {
  type: "reloaded",
  token: 1,
  sessionId: SESSION_ID,
  input: FRYING_PAN_INPUT,
};

describe("a session read back after a reload", () => {
  test("shows the request and reads the session at once", () => {
    const state = after(reloaded);

    expect(state.turns).toEqual([{ kind: "user", text: FRYING_PAN_INPUT }]);
    expect(state.input).toBe(FRYING_PAN_INPUT);
    expect(state.sessionId).toBe(SESSION_ID);
    expect(state.stage).toEqual({ name: "checking", run: { kind: "reload" }, wait: 0, misses: 0 });
  });

  test("at the pause shows its questions, the first one open", () => {
    const state = after(reloaded, viewed(pausedView));

    expect(state.stage).toEqual({ name: "questions", session: AT_THE_PAUSE });
    expect(openQuestionOf(state)?.question.id).toBe("question-researched-1");
    expect(state.turns[1]).toEqual({ kind: "understood", line: LOOKING_FOR, label: BOX_LABEL });
  });

  test("finished opens its results, without the box in between", () => {
    const state = after(
      reloaded,
      viewed({ status: "finished", report: FRYING_PAN_REPORT, lines: REPORT_LINES }),
    );

    expect(resultsOf(state)).toEqual({ report: FRYING_PAN_REPORT, lines: REPORT_LINES });
  });

  test("finished reads its answers back from the report, as labels", () => {
    const report = {
      ...FRYING_PAN_REPORT,
      factors: ASKED_TWO.factors,
      questions: ASKED_TWO.questions,
      answers: [
        {
          factor_id: "researched-1",
          status: "chosen" as const,
          choice_id: "choice-2",
          stated_value: null,
          stated_phrase: null,
          uses_per_year: null,
          stated_in: "request" as const,
        },
        {
          factor_id: "usage",
          status: "stated" as const,
          choice_id: null,
          stated_value: "Twice a day",
          stated_phrase: "twice a day",
          uses_per_year: 730,
          stated_in: "reply" as const,
        },
      ],
    };
    const state = after(
      reloaded,
      viewed({ status: "finished", report, lines: { ...REPORT_LINES, stated: [STATED] } }),
    );

    expect(labelsOf(state).map(({ value }) => value)).toEqual(["Induction", "Twice a day"]);
    expect(roundsOf(state.turns).map(({ heading }) => heading)).toEqual([
      ROUND_REQUEST,
      ROUND_ANSWERS,
    ]);
    expect(state.turns).toContainEqual({ kind: "lines", lines: [STATED] });
  });

  test("finished with a decline shows the decline in the composer's place", () => {
    const state = after(
      reloaded,
      viewed({
        status: "finished",
        report: DECLINED.report!,
        lines: { ...REPORT_LINES, declined: DECLINE },
      }),
    );

    expect(state.turns.at(-1)).toEqual({ kind: "lines", lines: [DECLINE] });
    expect(state.stage).toEqual({ name: "editing", examples: true });
  });

  test("still running says so, and reads again after a wait", () => {
    expect(statusOf(after(reloaded))).toBeNull();

    const state = after(reloaded, viewed({ status: "running" }));

    expect(statusOf(state)).toEqual({ line: STILL_WORKING, detail: null });
    expect(state.stage).toMatchObject({ name: "checking", wait: 2000 });
  });

  test("of an unknown or expired id clears it and shows the opening", () => {
    const state = after(reloaded, heard({ type: "refused", error: NOT_FOUND }));

    expect(state).toEqual(INITIAL);
  });

  test("that got no answer reads again, then stops with the input back", () => {
    const state = after(reloaded, missed, missed, missed, missed, missed);

    expect(state.stage).toEqual({ name: "editing", examples: false });
    expect(state.draft).toBe(FRYING_PAN_INPUT);
    expect(state.turns.at(-1)).toEqual({ kind: "message", text: UNREACHABLE });
  });

  test("interrupted says the run stopped, with the input back in the composer", () => {
    const state = after(reloaded, viewed({ status: "interrupted", code: "run_stopped" }));

    expect(state.turns.at(-1)).toEqual({ kind: "message", text: RUN_STOPPED });
    expect(state.draft).toBe(FRYING_PAN_INPUT);
  });
});

describe("a request the API did not answer", () => {
  test("with the answers, which may have arrived, has the session read at once", () => {
    const state = after(...answering, heard({ type: "unreachable" }, 2));

    expect(state.stage).toEqual({
      name: "checking",
      run: { kind: "answers", session: AT_THE_PAUSE, given: NOTHING_GIVEN },
      wait: 0,
      misses: 0,
    });
  });

  test("to start says so, with the input back in the composer", () => {
    const state = after(typed, started, missed);

    expect(state.turns.at(-1)).toEqual({ kind: "message", text: UNREACHABLE });
    expect(state.draft).toBe(FRYING_PAN_INPUT);
  });

  test("to start, refused as session_running before the session was named, puts the input back", () => {
    const state = after(typed, started, refused("session_running", "Already running.", 1));

    expect(state.stage).toEqual({ name: "editing", examples: false });
    expect(state.draft).toBe(FRYING_PAN_INPUT);
  });

  test("refused as session_running shows as still working, read again after a wait", () => {
    const state = after(...answering, refused("session_running", "Already running."));

    expect(state.stage).toMatchObject({ name: "checking", wait: 2000 });
    expect(state.turns.at(-1)?.kind).toBe("questions");
  });
});

describe("a request refused before its stream", () => {
  test("to start keeps the input in the composer and shows the message", () => {
    const state = after(typed, started, refused("input_too_long", "That is more text.", 1));

    expect(state.turns.at(-1)).toEqual({ kind: "message", text: "That is more text." });
    expect(state.draft).toBe(FRYING_PAN_INPUT);
  });

  test.each(["session_not_found", "session_not_paused", "invalid_request"] as const)(
    "with %s, which says to start again, puts the input back in the composer",
    (code) => {
      const state = after(...answering, refused(code, "Start again."));

      expect(state.stage).toEqual({ name: "editing", examples: false });
      expect(state.draft).toBe(FRYING_PAN_INPUT);
    },
  );
});

describe("a run that stops", () => {
  test.each([
    ["model_call_failed", sentStart, 1],
    ["run_stopped", answering, 2],
  ] as const)("with %s puts the input back in the composer", (code, run, token) => {
    const state = after(
      ...run,
      streamed({ event: "error", code, message: "Start again." }, token),
      heard(ENDED, token),
    );

    expect(state.turns.at(-1)).toEqual({ kind: "message", text: "Start again." });
    expect(state.draft).toBe(FRYING_PAN_INPUT);
    expect(state.stage).toEqual({ name: "editing", examples: false });
  });
});

describe("the composer", () => {
  test("before the first send takes the input, with the examples, and goes on once typed", () => {
    expect(composerOf(INITIAL)).toEqual({ examples: true, canSend: false, askingBudget: false });
    expect(composerOf(after(typed))?.canSend).toBe(true);
  });

  const draftOf = (draft: string): Action => ({ type: "typed", draft });
  const askedBudget: Action = { type: "asked_budget" };

  test("asks for a budget once, for a request with no number in it", () => {
    expect(asksBudget(after(draftOf("A kettle")))).toBe(true);
    expect(asksBudget(after(draftOf("A kettle"), askedBudget))).toBe(false);
  });

  test("does not ask when the request has a number in it, or is a link", () => {
    expect(asksBudget(after(draftOf("A kettle, €60")))).toBe(false);
    expect(asksBudget(after(draftOf("A kettle under 60 euro")))).toBe(false);
    expect(asksBudget(after(draftOf("https://example.org/shop/blocked")))).toBe(false);
    expect(asksBudget(after(draftOf("this one www.example.org/kettle please")))).toBe(false);
  });

  test("shows the ask until a number is typed", () => {
    const asked = after(draftOf("A kettle"), askedBudget);

    expect(composerOf(asked)?.askingBudget).toBe(true);
    expect(composerOf(nextThread(asked, draftOf("A kettle, 60")))?.askingBudget).toBe(false);
  });

  test("does not ask again for the same draft once words are added", () => {
    const asked = after(draftOf("A kettle"), askedBudget, draftOf("A red kettle"));

    expect(asksBudget(asked)).toBe(false);
  });

  test("forgets the ask once the request is sent", () => {
    const sent = after(draftOf("A kettle"), askedBudget, started);

    expect(sent.budgetAsked).toBe(false);
  });

  test("while the request is read and the questions are prepared is not shown", () => {
    expect(composerOf(after(...sentStart, streamed(READING)))).toBeNull();
    expect(composerOf(after(...sentStart, streamed(UNDERSTOOD), streamed(RESEARCHING)))).toBeNull();
  });

  test("at the questions is not shown: they have their own steps", () => {
    expect(composerOf(after(...atThePause))).toBeNull();
    expect(composerOf(after(...sentStart, streamed(NOTHING_ASKED)))).toBeNull();
  });

  test("while the answers run, and after the report, is not shown", () => {
    expect(composerOf(after(...answering))).toBeNull();
    expect(composerOf(after(...answering, answerEvent(REPORTED)))).toBeNull();
  });
});

const edited: Action = { type: "edited" };

describe("Edit", () => {
  test("while the first stream runs empties the thread and puts the input back", () => {
    const state = after(...sentStart, streamed(UNDERSTOOD), streamed(RESEARCHING), edited);

    expect(state.turns).toEqual([]);
    expect(state.draft).toBe(FRYING_PAN_INPUT);
    expect(state.stage).toEqual({ name: "editing", examples: false });
  });

  test("during a run drops what the old run sends after it", () => {
    const editedState = after(...sentStart, streamed(UNDERSTOOD), edited);
    const state = nextThread(editedState, streamed(PAUSED));

    expect(state).toEqual(editedState);
  });

  test("drops what the old run sends after it, once a new run has started too", () => {
    const restarted = after(...sentStart, streamed(UNDERSTOOD), edited, {
      type: "started",
      token: 3,
    });
    const state = nextThread(restarted, streamed(PAUSED));

    expect(state).toEqual(restarted);
  });

  test("after the report puts the input back too", () => {
    const state = after(...answering, answerEvent(REPORTED), edited);

    expect(state.turns).toEqual([]);
    expect(state.draft).toBe(FRYING_PAN_INPUT);
  });
});

describe("a request that does not run", () => {
  test("shows its decline in place of the supervisor's line", () => {
    const state = after(...sentStart, streamed(READING), streamed(DECLINED_SESSION));

    expect(state.turns.slice(1)).toEqual([{ kind: "lines", lines: [DECLINED_LINES.declined] }]);
  });

  test("not about a product opens an empty composer with the examples", () => {
    const state = after(...sentStart, streamed(DECLINED_SESSION));

    expect(state.stage).toEqual({ name: "editing", examples: true });
    expect(state.draft).toBe("");
  });

  test("not understood opens the composer with the input in it, so a name can be added", () => {
    const linked = after(
      { type: "typed", draft: BLOCKED_LINK },
      started,
      streamed(STARTED),
      streamed(UNREADABLE_SESSION),
    );

    expect(linked.stage).toEqual({ name: "editing", examples: false });
    expect(linked.draft).toBe(BLOCKED_LINK);
  });
});

describe("the open question", () => {
  test("opens the first question, with its place among them and how many follow it", () => {
    expect(openQuestionOf(after(...askedTwo))).toEqual({
      question: hobQuestion,
      place: 1,
      total: 2,
      more: 1,
      ownWords: "",
      inOwnWords: false,
      error: null,
    });
  });

  test("moves on to the next question with no answer once a chip is tapped", () => {
    expect(openQuestionOf(after(...askedTwo, picked(induction)))).toMatchObject({
      question: usageQuestion,
      place: 2,
      total: 2,
      more: 0,
    });
  });

  test("closes once every question has an answer", () => {
    expect(openQuestionOf(after(...askedTwo, picked(induction), picked(daily)))).toBeNull();
  });

  test("stays on a question whose chip is tapped again to clear it", () => {
    const reopened = after(...askedTwo, picked(induction), reopen(hobQuestion.id));

    expect(openQuestionOf(nextThread(reopened, picked(induction)))?.question).toEqual(hobQuestion);
  });

  test("reopens an answered question when its label is tapped", () => {
    const state = after(...askedTwo, picked(induction), picked(daily), reopen(hobQuestion.id));

    expect(openQuestionOf(state)).toMatchObject({ question: hobQuestion, place: 1, more: 0 });
  });

  test("is closed while the answers are sent", () => {
    expect(openQuestionOf(after(...askedTwo, answered({ answers: [induction] })))).toBeNull();
  });
});

describe("the labels", () => {
  test("are the answered questions in the order asked, each with its factor's name", () => {
    const state = after(...askedTwo, picked(daily), picked(hobNotSure));

    expect(labelsOf(state)).toEqual([
      { id: hobQuestion.id, key: "Hob compatibility", value: NOT_SURE, unsure: true, added: false },
      { id: usageQuestion.id, key: null, value: "Every day", unsure: false, added: false },
    ]);
  });

  test("stay as they were sent, a question sent with no answer labelled not sure", () => {
    const state = after(...askedTwo, picked(induction), answered({ answers: [induction] }));

    expect(labelsOf(state)).toEqual([
      {
        id: hobQuestion.id,
        key: "Hob compatibility",
        value: "Induction",
        unsure: false,
        added: false,
      },
      { id: usageQuestion.id, key: null, value: NOT_SURE, unsure: true, added: false },
    ]);
  });

  test("leave out a question with no answer yet while the questions are open", () => {
    expect(labelsOf(after(...askedTwo, picked(induction))).map(({ value }) => value)).toEqual([
      "Induction",
    ]);
  });

  test("are none before the questions", () => {
    expect(labelsOf(after(...sentStart))).toEqual([]);
  });

  test("end with each factor of the user's own the reader kept from the reply, its phrase alone", () => {
    const sent = [...askedTwo, picked(induction), answered({ answers: [induction] })];
    const state = after(...sent, answerEvent(replyRead([], [OWN_FACTOR])));

    expect(labelsOf(state).at(-1)).toEqual({
      id: OWN_FACTOR.id,
      key: null,
      value: "Fits in a 24 cm cupboard",
      unsure: false,
      added: true,
    });
  });

  test("leave out the closing step's words, which only the reader's factors label", () => {
    const sent = [
      ...askedTwo,
      picked(induction),
      added("test"),
      answered({ answers: [induction], reply: "test" }),
    ];
    const state = after(...sent, answerEvent(replyRead([])));

    expect(labelsOf(state).map(({ value }) => value)).toEqual(["Induction", NOT_SURE]);
  });

  test("lose the reply's factors when the answers come back not applied", () => {
    const sent = [...askedTwo, picked(induction), answered({ answers: [induction], reply: "x" })];
    const state = after(
      ...sent,
      answerEvent(replyRead([], [OWN_FACTOR])),
      answerEvent({ event: "error", code: "reply_unread", message: "Not read." }),
    );

    expect(labelsOf(state).some((label) => label.added)).toBe(false);
  });
});

const INDUCTION_AND_WORDS: AnswersRequest = { answers: [induction], reply: "Oven safe" };

describe("the rounds", () => {
  test("are none before the first send", () => {
    expect(roundsOf(INITIAL.turns)).toEqual([]);
  });

  test("hold the request, then what was taken from it, and leave progress to the status line", () => {
    const state = after(...sentStart, streamed(UNDERSTOOD), streamed(RESEARCHING));
    const [request, ...others] = roundsOf(state.turns);

    expect(others).toEqual([]);
    expect(request.heading).toBe(ROUND_REQUEST);
    expect(request.turns.map(({ turn }) => turn.kind)).toEqual(["user", "understood"]);
  });

  test("start the answers at the questions, the user's words first", () => {
    const sent = [
      ...askedTwo,
      picked(induction),
      added("Oven safe"),
      answered(INDUCTION_AND_WORDS),
    ];
    const state = after(...sent, answerEvent(replyRead([replyLine])), answerEvent(FINDING));
    const [, answers] = roundsOf(state.turns);

    expect(answers.heading).toBe(ROUND_ANSWERS);
    expect(answers.turns.map(({ turn }) => turn.kind)).toEqual(["user", "questions", "reply"]);
    expect(answers.turns[0].key).toBe(
      state.turns.findIndex((turn) => turn.kind === "user" && turn.text === "Oven safe"),
    );
  });
});

const FINDING = progress("tco", "started", "Finding options and their prices...");
const FOUND = progress("tco", "finished", "Finished looking for options and their prices.");
const ESTIMATING = progress("lca", "started", "Estimating the CO2e of making each option...");

describe("the box", () => {
  test("before the first send is open for labelling, with nothing on it", () => {
    expect(boxOf(INITIAL)).toEqual({
      state: "labelling",
      request: null,
      cleared: false,
      lookingFor: null,
      reading: false,
      scan: [],
      tally: null,
    });
  });

  test("waits for the Looking-for words while the request is read", () => {
    expect(boxOf(after(...sentStart, streamed(READING))).reading).toBe(true);
  });

  test("stops waiting once the Looking-for words are there", () => {
    expect(boxOf(after(...sentStart, streamed(UNDERSTOOD))).reading).toBe(false);
  });

  test("stops waiting for a request that does not run", () => {
    expect(boxOf(after(...sentStart, streamed(DECLINED_SESSION))).reading).toBe(false);
  });

  test("keeps the request on its face once it is sent", () => {
    expect(boxOf(after(...sentStart)).request).toBe(FRYING_PAN_INPUT);
    expect(boxOf(after(...sentStart, streamed(UNDERSTOOD), streamed(PAUSED))).request).toBe(
      FRYING_PAN_INPUT,
    );
  });

  test("clears its face once the questions are asked, and keeps it clear", () => {
    expect(boxOf(after(...sentStart, streamed(UNDERSTOOD))).cleared).toBe(false);
    expect(boxOf(after(...askedTwo)).cleared).toBe(true);
    expect(boxOf(after(...answering, answerEvent(FINDING))).cleared).toBe(true);
  });

  test("gives the request back to the composer on Edit", () => {
    expect(boxOf(after(...sentStart, streamed(UNDERSTOOD), edited)).request).toBeNull();
  });

  test.each([
    ["is declined", [...sentStart, streamed(DECLINED_SESSION)]],
    ["stops before it named its session", [typed, started, ended]],
  ] as const)("writes a question mark when a request %s", (_how, actions) => {
    const box = boxOf(after(...actions));

    expect(box).toMatchObject({ lookingFor: UNREAD_LABEL, reading: false });
    expect(box.request).toBe(FRYING_PAN_INPUT);
  });

  test("at the questions counts how many of them have an answer", () => {
    expect(boxOf(after(...askedTwo, picked(induction))).tally).toEqual({ answered: 1, asked: 2 });
  });

  test("once the answers are sent counts no more", () => {
    const state = after(...askedTwo, picked(induction), answered({ answers: [induction] }));

    expect(boxOf(state).tally).toBeNull();
  });

  test("carries what was understood in the words of its first label", () => {
    expect(boxOf(after(...sentStart, streamed(UNDERSTOOD))).lookingFor).toBe("frying pan · €50");
  });

  test("is sealed while the answers run, scanning the steps still at work only", () => {
    const state = after(
      ...answering,
      answerEvent(FINDING),
      answerEvent(FOUND),
      answerEvent(ESTIMATING),
    );

    expect(boxOf(state)).toMatchObject({
      state: "sealed",
      scan: [
        {
          kind: "progress",
          agent: "lca",
          step: "research",
          line: ESTIMATING.message,
          running: true,
          done: false,
        },
      ],
    });
  });

  test("stays sealed while a lost stream of the answers is picked up", () => {
    expect(boxOf(after(...answersCut)).state).toBe("sealed");
  });

  test("opens when the report lands", () => {
    expect(boxOf(after(...answering, answerEvent(REPORTED)))).toMatchObject({
      state: "open",
    });
  });

  test("is open for labelling again once the answers were not applied", () => {
    const state = after(...answersCut, heard({ type: "viewed", view: pausedView }, 2));

    expect(boxOf(state)).toMatchObject({ state: "labelling", scan: [] });
  });
});

const SECOND_HAND_CHECKING = progress("second_hand", "started", "Checking for used options...");
const ESTIMATED = progress(
  "lca",
  "finished",
  "Finished estimating the CO2e of making each option.",
);

/** Each station's state, and the line under it when it has one. */
function stations(state: ThreadState): string[] {
  return routeOf(state).map(({ state: at }) => at);
}

describe("the route's notes", () => {
  test("open while the request is read and the questions are prepared", () => {
    expect(explainsRoute(after(typed, started))).toBe(true);
    expect(explainsRoute(after(...sentStart, streamed(UNDERSTOOD), streamed(RESEARCHING)))).toBe(
      true,
    );
  });

  test("open while the answers run, and while a lost stream is picked up", () => {
    expect(explainsRoute(after(...answering))).toBe(true);
    expect(explainsRoute(after(...answersCut))).toBe(true);
  });

  test("open between the waits, at the questions and with the box open", () => {
    expect(explainsRoute(after(...atThePause))).toBe(true);
    expect(explainsRoute(after(...answering, answerEvent(REPORTED)))).toBe(true);
  });

  test("are not there before the first send or on the results page", () => {
    expect(explainsRoute(INITIAL)).toBe(false);
    expect(explainsRoute(after(...answering, answerEvent(REPORTED), { type: "compared" }))).toBe(
      false,
    );
  });

  test("are hinted at during a wait only", () => {
    expect(hintsRoute(after(...sentStart))).toBe(true);
    expect(hintsRoute(after(...answering))).toBe(true);
    expect(hintsRoute(after(...atThePause))).toBe(false);
    expect(hintsRoute(after(...answering, answerEvent(REPORTED)))).toBe(false);
  });

  test("after a reload wait for the first read, and open if a run is still going", () => {
    expect(explainsRoute(after(reloaded))).toBe(false);
    expect(explainsRoute(after(reloaded, viewed({ status: "running" })))).toBe(true);
  });
});

describe("the route", () => {
  test("names its stations in the agents' order", () => {
    expect(routeOf(INITIAL).map(({ name }) => name)).toEqual([
      ROUTE_REQUEST,
      ROUTE_QUESTIONS,
      ROUTE_OPTIONS,
      ROUTE_CO2E,
    ]);
  });

  test("before the first send has every station ahead", () => {
    expect(stations(INITIAL)).toEqual(Array(4).fill("ahead"));
  });

  test("while the request is read is at its first station", () => {
    expect(stations(after(...sentStart, streamed(READING)))).toEqual([
      "current",
      ...Array(3).fill("ahead"),
    ]);
  });

  test("once the request is understood is at the questions while they are researched", () => {
    expect(stations(after(...sentStart, streamed(UNDERSTOOD), streamed(RESEARCHING)))).toEqual([
      "done",
      "current",
      ...Array(2).fill("ahead"),
    ]);
  });

  test("stays at the questions while they are answered", () => {
    expect(stations(after(...askedTwo, picked(induction)))).toEqual([
      "done",
      "current",
      ...Array(2).fill("ahead"),
    ]);
  });

  test("while the answers run marks each agent's station from its progress", () => {
    const state = after(
      ...answering,
      answerEvent(FINDING),
      answerEvent(FOUND),
      answerEvent(ESTIMATING),
    );

    expect(stations(state)).toEqual(["done", "done", "done", "current"]);
    expect(stations(nextThread(state, answerEvent(ESTIMATED)))).toEqual(Array(4).fill("done"));
  });

  test("shows nothing of the second-hand agent's steps", () => {
    const state = after(...answering, answerEvent(SECOND_HAND_CHECKING));

    expect(statusOf(state)).toBeNull();
    expect(boxOf(state).scan).toEqual([]);
  });

  test("keeps a step cut off by a lost stream current while its session is read again", () => {
    const cut = after(...answering, answerEvent(FINDING), heard(ENDED, 2));

    expect(stations(cut)).toEqual(["done", "done", "current", "ahead"]);
  });

  test("after the report has every station done", () => {
    expect(stations(after(...answering, answerEvent(REPORTED)))).toEqual(Array(4).fill("done"));
  });

  test("starts again from the first station once the answers were not applied", () => {
    const state = after(...answersCut, heard({ type: "viewed", view: pausedView }, 2));

    expect(stations(state)).toEqual(["done", "current", "ahead", "ahead"]);
  });
});

describe("progress", () => {
  test("shows a step's started line, marked as working, while the step runs", () => {
    const state = after(...sentStart, streamed(RESEARCHING));

    expect(state.turns.at(-1)).toEqual({
      kind: "progress",
      agent: "brief",
      step: "research",
      line: "Researching what to ask about...",
      running: true,
      done: false,
    });
  });

  test("puts the step's finished line in the place of its started line", () => {
    const state = after(...sentStart, streamed(RESEARCHING), streamed(RESEARCHED));

    expect(state.turns.slice(1)).toEqual([
      {
        kind: "progress",
        agent: "brief",
        step: "research",
        line: "Finished researching what to ask about.",
        running: false,
        done: true,
      },
    ]);
  });

  test("shows the supervisor reading the request until the Looking-for line takes its place", () => {
    const reading = after(...sentStart, streamed(READING));
    const read = after(...sentStart, streamed(READING), streamed(UNDERSTOOD));

    expect(reading.turns.at(-1)).toMatchObject({ line: "Reading your request...", running: true });
    expect(read.turns.slice(1)).toEqual([
      { kind: "understood", line: LOOKING_FOR, label: BOX_LABEL },
    ]);
  });

  test("is the status line while it runs, with what category research reads under it", () => {
    expect(statusOf(after(...sentStart, streamed(READING)))).toEqual({
      line: "Reading your request...",
      detail: null,
    });
    expect(statusOf(after(...sentStart, streamed(UNDERSTOOD), streamed(RESEARCHING)))).toEqual({
      line: "Researching what to ask about...",
      detail: RESEARCHING_DETAIL,
    });
  });

  test("leaves the status line once it finished, and it is gone at the pause", () => {
    expect(statusOf(after(...sentStart, streamed(RESEARCHING), streamed(RESEARCHED)))).toBeNull();
    expect(statusOf(after(...atThePause))).toBeNull();
  });

  test("gives the supervisor's closing line none", () => {
    const state = after(...sentStart, streamed(UNDERSTOOD), streamed(SUPERVISOR_FINISHED));

    expect(state.turns.slice(1)).toEqual([
      { kind: "understood", line: LOOKING_FOR, label: BOX_LABEL },
    ]);
  });
});
