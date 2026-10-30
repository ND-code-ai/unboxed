/** Sample data in the shapes the API sends, typed by the generated schema. */

import type {
  ApiError,
  Line,
  ProgressEvent,
  Report,
  ReportLines,
  Request,
  SessionLines,
  SessionStart,
  StreamEvent,
} from "../../lib/api/types";

export const SESSION_ID = "0b6f7c1e-4a43-4d61-9a39-1f0d6f2b8a10";
export const FRYING_PAN_INPUT = "I need a new frying pan, budget 50 euro";

export const FRYING_PAN: Request = {
  original_text: FRYING_PAN_INPUT,
  product_url: null,
  category: "frying pan",
  budget: "50",
  currency: "EUR",
  scope: "tuned",
};

export const PIZZA: Request = {
  original_text: "a pizza",
  product_url: null,
  category: "pizza",
  budget: null,
  currency: "EUR",
  scope: "not_a_product",
};

export function reportFor(request: Request): Report {
  return {
    request,
    factors: [],
    questions: [],
    answers: [],
    options: [],
    lca_results: [],
    listings: [],
    assumptions: { horizon_years: 10, uses_per_year: null, lifespan_overrides: {} },
    comparison: null,
    evidence_summary: {
      lifespans_sourced: 0,
      lifespans_estimated: 0,
      lifespans_user_set: 0,
      lifespans_missing: 0,
      footprints_published: 0,
      footprints_benchmark: 0,
      footprints_model_estimate: 0,
      footprints_missing: 0,
    },
    caveats: [],
    check_before_you_buy: [],
    trail: [],
    warnings: [],
  };
}

export const AT_THE_PAUSE: SessionStart = {
  session_id: SESSION_ID,
  request: FRYING_PAN,
  warnings: [],
  factors: [],
  questions: [
    {
      id: "question-researched-1",
      factor_id: "researched-1",
      text: "Which hob do you cook on?",
      reason: "Not every pan works on every hob.",
      choices: [
        { id: "choice-1", text: "Gas", uses_per_year: null },
        { id: "choice-2", text: "Induction", uses_per_year: null },
      ],
    },
  ],
  stated_answers: [],
  report: null,
};

/** A session at the pause with two questions, each drawn from a factor the session names. */
export const ASKED_TWO: SessionStart = {
  ...AT_THE_PAUSE,
  factors: [
    {
      id: "researched-1",
      name: "Hob compatibility",
      kind: "compatibility",
      why: "Not every pan works on every hob.",
      source: null,
      typical_yearly_cost: null,
      typical_yearly_cost_source: null,
      typical_yearly_cost_converted_from: null,
    },
  ],
  questions: [
    ...AT_THE_PAUSE.questions,
    {
      id: "question-usage",
      factor_id: "usage",
      text: "How often do you cook with it?",
      reason: "Daily use wears a coating faster.",
      choices: [
        { id: "choice-daily", text: "Every day", uses_per_year: 365 },
        { id: "choice-weekly", text: "A few times a week", uses_per_year: 150 },
      ],
    },
  ],
};

export const DECLINED: SessionStart = {
  session_id: SESSION_ID,
  request: PIZZA,
  warnings: [],
  factors: [],
  questions: [],
  stated_answers: [],
  report: reportFor(PIZZA),
};

export const FRYING_PAN_REPORT = reportFor(FRYING_PAN);

export const BLOCKED_LINK = "https://example.org/shop/blocked";

/** A bare link whose page gave no product. */
export const UNREADABLE: Request = {
  original_text: BLOCKED_LINK,
  product_url: BLOCKED_LINK,
  category: null,
  budget: null,
  currency: "EUR",
  scope: "unclear",
};

export const UNREADABLE_DECLINED: SessionStart = {
  ...DECLINED,
  request: UNREADABLE,
  report: reportFor(UNREADABLE),
};

export const LOOKING_FOR: Line = {
  parts: [
    { kind: "text", text: "Looking for: frying pan · Budget: €50" },
    { kind: "control", key: "edit" },
  ],
};

/** The same words as the box carries them on its first label. */
export const BOX_LABEL: Line = { parts: [{ kind: "text", text: "frying pan · €50" }] };

export const PAUSE_LINES: SessionLines = {
  understood: LOOKING_FOR,
  label: BOX_LABEL,
  declined: null,
  stated: [],
  typical_costs: [],
  sources: {},
};

export const DECLINE: Line = {
  parts: [
    {
      kind: "text",
      text: `This app covers durable products such as cookware, appliances and tools. It can't help with "pizza".`,
    },
  ],
};

export const DECLINED_LINES: SessionLines = {
  understood: null,
  label: null,
  declined: DECLINE,
  stated: [],
  typical_costs: [],
  sources: {},
};

export const LINK_DECLINE: Line = {
  parts: [
    {
      kind: "text",
      text: "We couldn't read the product at your link. Name the product to start, for example 'a frying pan, budget €50'.",
    },
  ],
};

/** The lines of a report with nothing in it: the shape of a declined report, without its decline. */
export const REPORT_LINES: ReportLines = {
  declined: null,
  evidence_summary: null,
  caveats: [],
  warnings: [],
  stated: [],
  typical_costs: [],
  options: [],
  check: { groups: [], confirm_price: null },
  trail: [],
};

export const LINK_UNREADABLE =
  "We couldn't read the product at your link, so it is not among the options below. These are options for frying pan.";

/** The session at the pause of a request with a link that could not be read. */
export const LINKED_AT_THE_PAUSE: SessionStart = {
  ...AT_THE_PAUSE,
  request: { ...FRYING_PAN, product_url: BLOCKED_LINK },
  warnings: [{ code: "link_unreadable", message: LINK_UNREADABLE, option_id: null }],
};

export const STATED: Line = {
  parts: [{ kind: "text", text: `From your request: Usage frequency: Every day ("every day")` }],
};

export const TYPICAL_COST: Line = {
  parts: [
    { kind: "text", text: "Seasoning oil: typically €6 a year (" },
    { kind: "link", text: "stub.invalid", url: "https://stub.invalid/seasoning-oil" },
    { kind: "text", text: ")." },
  ],
};

export const HOB_SOURCE: Line = {
  parts: [
    { kind: "text", text: "Source: " },
    { kind: "link", text: "stub.invalid", url: "https://stub.invalid/hob-compatibility" },
  ],
};

export const LINKED_PAUSE_LINES: SessionLines = {
  ...PAUSE_LINES,
  stated: [STATED],
  typical_costs: [TYPICAL_COST],
  sources: { "question-researched-1": HOB_SOURCE },
};

export function progress(
  agent: ProgressEvent["agent"],
  status: ProgressEvent["status"],
  message: string,
): ProgressEvent {
  return { event: "progress", agent, status, step: "research", message };
}

export const NOT_FOUND: ApiError = {
  code: "session_not_found",
  message: "We couldn't find this session. Start again with your request.",
};

export const STARTED: StreamEvent = { event: "session_started", session_id: SESSION_ID };
export const READING = progress("supervisor", "started", "Reading your request...");
export const RESEARCHING = progress("brief", "started", "Researching what to ask about...");
export const RESEARCHED = progress("brief", "finished", "Finished researching what to ask about.");
export const SUPERVISOR_FINISHED = progress("supervisor", "finished", "Finished.");
export const UNDERSTOOD: StreamEvent = {
  event: "understood",
  request: FRYING_PAN,
  line: LOOKING_FOR,
  label: BOX_LABEL,
};
export const PAUSED: StreamEvent = { event: "session", session: AT_THE_PAUSE, lines: PAUSE_LINES };
/** A session at the pause with no question to ask. */
export const NOTHING_ASKED: StreamEvent = {
  event: "session",
  session: { ...AT_THE_PAUSE, questions: [] },
  lines: PAUSE_LINES,
};
export const LINKED_PAUSED: StreamEvent = {
  event: "session",
  session: LINKED_AT_THE_PAUSE,
  lines: LINKED_PAUSE_LINES,
};
export const DECLINED_SESSION: StreamEvent = {
  event: "session",
  session: DECLINED,
  lines: DECLINED_LINES,
};
export const UNREADABLE_SESSION: StreamEvent = {
  event: "session",
  session: UNREADABLE_DECLINED,
  lines: { ...DECLINED_LINES, declined: LINK_DECLINE },
};
export const REPORTED: StreamEvent = {
  event: "report",
  report: FRYING_PAN_REPORT,
  lines: REPORT_LINES,
};
