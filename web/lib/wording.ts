/**
 * The lines the page holds itself, because no answer from the API carries them, and the words of
 * its controls: the only copy of their words (docs/wording.md says how they are written). Every
 * other line the page shows comes from the API.
 */

import type { Line } from "./api/types";

/** The page's title, in the browser's tab. */
export const APP_NAME = "Unboxed";

/** The wordmark, top left of the field, set in lowercase. */
export const WORDMARK = `${APP_NAME}.`;

/** Under the wordmark. */
export const TAGLINE = "The price tag is only the start";

/** When `GET /sessions/{id}` reads `paused` after an answers stream that ended before its report:
 * the answers were not applied, so the page keeps the questions and what was given. */
export const ANSWERS_NOT_APPLIED =
  "The session is still waiting for your answers, so nothing was run. Send them again.";

/** The words of `run_stopped`, beside the offer to start again, for a session read back as
 * `interrupted`: a view that carries its code and no message. */
export const RUN_STOPPED =
  "The run stopped before your report was ready. Start again with your request.";

/** The words of `internal_error`, for a request that got no answer at all; after a lost stream it
 * is shown until the session is read again. */
export const UNREACHABLE = "The app couldn't answer just now. Try again in a moment.";

/** The status line after a reload that finds a run still going: the page reads the session again
 * until it ends, and has none of the run's progress to show. */
export const STILL_WORKING = "Still working on your request...";

/** The words of the `edit` control, which ends the "Looking for" line. */
export const EDIT = "Edit";

type ControlKey = Extract<Line["parts"][number], { kind: "control" }>["key"];

/** The words of each control a line from the API can end in. */
export const CONTROLS: Record<ControlKey, string> = { edit: EDIT };

/** The composer's label. */
export const INPUT_LABEL = "What goes in the box?";

/** What to write on the box's face; the starters carry the examples. */
export const INPUT_PLACEHOLDER = "a product, and your budget (optional)";

/** Beside the button that sends the input: a link works too. */
export const INPUT_HINT = "Or paste a product link.";

/** By the composer, when a request with no number in it is sent for the first time. */
export const ASK_BUDGET =
  "Have a budget in mind? Add it here, for example €50. Or press Next to go on without one.";

/** The button that sends the input, and the one under an answer in the user's own words, which
 * moves on to the next question. */
export const NEXT = "Next";

export const NOT_SURE = "Not sure";

/** The chip after "Not sure": it unfolds a field for an answer in the user's own words. */
export const SOMETHING_ELSE = "Something else";

/** After the last question, the one optional step; not counted among the questions. */
export const ANYTHING_ELSE = "Anything else we should know?";

/** The closing step's button, which sends the answers. */
export const SHOW_MY_OPTIONS = "Show my options";

/** In the reply sent, before each answer in the user's own words: the question it answers. */
export const ABOUT_QUESTION = 'About "{question}": ';

/** The words of `reply_too_long`, for a reply the page holds back: what was written, joined, is
 * longer than the API reads. */
export const REPLY_TOO_LONG =
  "That is more text than the app can read, so nothing was sent. Answer in a sentence or two.";

/** The questions are asked one at a time: the open one's place among them. */
export const PLACE = "{place} of {total}";

/** Under the open question; `{skip}` is the button that ends the line. */
export const MORE_QUESTIONS = "{n} more questions · or {skip}";

export const ONE_MORE_QUESTION = "1 more question · or {skip}";

export const SKIP_THE_REST = "skip the rest";

/** The box's first label, written by the marker, when the request could not be read. */
export const UNREAD_LABEL = "?";

/** On the box, at the questions. */
export const LABELLED = "{answered} of {total} labelled";

/** On the box, the label of a question answered "Not sure", or skipped: the box shows answers
 * alone, so its factor's name says which question it is. */
export const NOT_SURE_LABEL = "{factor}?";

/** The headings of the thread's rounds: what the shopper sent, then what the app took from it. */
export const ROUND_REQUEST = "Your request";

export const ROUND_ANSWERS = "Your answers";

/** The route line's stations, one per agent in the order they run (docs/design/chat_page_brief.md,
 * "The route line"). */
export const ROUTE_REQUEST = "your request";

export const ROUTE_QUESTIONS = "questions";

export const ROUTE_OPTIONS = "options";

export const ROUTE_CO2E = "CO2e";

/** What each station's agent does, in plain words, opened from the route line during a wait. They
 * describe the steps every run takes, not this run: what this one found is on the results page. */
export const ROUTE_REQUEST_DETAIL =
  "We're working out what you typed: which product you want, your budget, and whether this app covers it. Together with preparing the questions, this can take about half a minute.";

export const ROUTE_QUESTIONS_DETAIL =
  "We look up what matters when buying this product, in buying guides and care advice, and turn that into up to five questions for you. If you wrote anything in your answers, we read that here too.";

export const ROUTE_OPTIONS_DETAIL =
  "We look for this product on comparison sites, judge which ones are likely to last, and check their product pages for the price and the fit with your answers. We keep up to three, then look up how long they last, what they cost to keep using, and what testers and owners say. This is the longest step and can take a few minutes.";

export const ROUTE_CO2E_DETAIL =
  "An AI model estimates what each option is made of and the greenhouse gases (CO2e) from making those materials. The app's own code then adds this up into a range, labelled as an estimate.";

/** The trail's own terms and the page's words for them. The terms repeat what the agents write
 * (`agents/lca/trail.py`, the supervisor's trail, a page read from a recording), and a model's words
 * can hold an entity from a product page; only a backend redeploy could change those there. */
export const TRAIL_PLAIN_WORDS: [string, string][] = [
  ["LCA tier 3 estimated", "Estimated the CO2e of"],
  ["LCA tier 3 gave no estimate for", "No CO2e estimate for"],
  ["; scope tuned", ""],
  ["not_recorded", "not recorded"],
  ["&apos;", "'"],
  ["&amp;", "&"],
];

/** What the cross on a station's note or on the hint is read as. */
export const CLOSE_NOTE = "Close";

/** Under the route line during a wait, until a station is tapped. */
export const ROUTE_HINT =
  "Press a station to see what that step does. Once your options are ready, each one shows what it found.";

/** What the category research does, under its line in the thread while it runs. */
export const RESEARCHING_DETAIL =
  "Reading buying guides and care advice, then choosing up to five questions.";

export function placeAmong(place: number, total: number): string {
  return filled(PLACE, { place, total });
}

export function labelled(answered: number, total: number): string {
  return filled(LABELLED, { answered, total });
}

export function notSureLabel(factor: string): string {
  return filled(NOT_SURE_LABEL, { factor });
}

export function aboutQuestion(question: string): string {
  return filled(ABOUT_QUESTION, { question });
}

/** The words of the line under the open question, before and after its button, by how many
 * others have no answer. */
export function moreQuestions(more: number): [string, string] {
  const line = more === 1 ? ONE_MORE_QUESTION : filled(MORE_QUESTIONS, { n: more });
  const [before, after = ""] = line.split("{skip}");
  return [before, after];
}

/** A template with its placeholders filled in. */
function filled(template: string, values: Record<string, number | string>): string {
  return Object.entries(values).reduce(
    (line, [name, value]) => line.replace(`{${name}}`, () => String(value)),
    template,
  );
}

export const START_AGAIN = "Start again";

/** In the opened box, once the report has landed: it opens the results page. */
export const SEE_THE_COMPARISON = "See the comparison";

/** The status line once the box has opened, read out with the button above taking the focus. */
export const COMPARISON_READY = "Your comparison is ready.";

/** An option's letter on a wide screen, over its name and in the lead: the first is "Option A". */
export function optionLetter(index: number): string {
  return `Option ${String.fromCharCode(65 + index)}`;
}

/** Repeats the end of a rough savings line (`ROUGH_SAVINGS` in `wording.py`), which the lead says
 * once. */
export const ROUGH_SAVINGS = "A lifespan behind this is a rough estimate.";

/** Repeats an unconfirmed factor's value (`FACTOR_NOT_CONFIRMED` in `wording.py`). */
export const FACTOR_UNCONFIRMED = "could not be confirmed";

/** After the names of the factors an option could not confirm, in one line. */
export const NOT_CONFIRMED_ON_PAGES = "not confirmed on the pages read";

/** Over what the model read of an option's durability, under "Durability evidence". */
export const MODEL_READING = "The model's reading, not a sourced figure";

/** The results page's heading, over the options. */
export const RESULTS_HEADING = "Your options";

/** On a sheet, over what the lifespan rests on: the durability evidence and the owner and tester
 * reports. The lifespan's own label is above it, so it says what the lines are, not that the
 * figure rests on them. */
export const EVIDENCE_HEADING = "Durability evidence";

/** On a sheet, over the option's value for each factor the user answered. */
export const ANSWERS_HEADING = "Your answers";

/** Over the report-wide list of what is still unknown or unconfirmed. */
export const CHECK_HEADING = "Check before you buy";

/** The switch that filters out the options over the budget, on the API's within-budget value. */
export const HIDE_OVER_BUDGET = "Hide options over my budget";

/** On a wide screen, the control that switches between the sheets and the deck. */
export const VIEW_LABEL = "View";

export const VIEW_ROWS = "Rows";

export const VIEW_CARDS = "Cards";

/** The deck's pinned strip of every option, for assistive tech. */
export const OPTIONS_STRIP = "Options";

/** The deck's steps; between them, the card's place among them (`PLACE`). */
export const PREVIOUS_OPTION = "Previous option";

export const NEXT_OPTION = "Next option";

/** The button beside every shipping line that opens the tooltip below, and what it shows on the
 * button. The tooltip holds for a stated amount, "free shipping" and "shipping not stated". */
export const SHIPPING_TIP_LABEL = "About shipping";

export const SHIPPING_TIP_MARK = "?";

export const SHIPPING_TIP =
  "Shipping comes from the shop's page on the day the price was seen, when the page stated it. What you pay at checkout can differ, for example with your address.";

/** Above the examples, shown in capitals. */
export const TRY_ONE = "Or try one";

/** The requests the examples write into the composer: the recorded queries, shortened. */
export const EXAMPLES = [
  "A frying pan, €50",
  "An electric kettle, €60",
  "A cordless drill, €120",
] as const;

/** Under the composer, while the deployed app traces (task 3.5). */
export const TRACING_NOTICE = "What you type here is logged to improve the app.";
