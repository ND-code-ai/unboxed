/**
 * Every call the page makes to the API (docs/service_architecture.md, "API surface"). A start and
 * the answers stream over `POST`; `GET /sessions/{id}` finds a session again. Failure is in the
 * return type: a refusal with the API's error body, or no answer at all.
 */

import { serverSentEvents } from "../sse";
import type { AnswersRequest, ApiError, Health, SessionView, StreamEvent } from "./types";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

type Refused = { kind: "refused"; error: ApiError };
type Unreachable = { kind: "unreachable" };

export type Streamed =
  { kind: "stream"; events: AsyncGenerator<StreamEvent> } | Refused | Unreachable;
export type Viewed = { kind: "view"; view: SessionView } | Refused | Unreachable;

export async function startSession(input: string): Promise<Streamed> {
  return streamedOf(await posted("/sessions", { input }));
}

export async function sendAnswers(sessionId: string, answers: AnswersRequest): Promise<Streamed> {
  return streamedOf(await posted(`${sessionPath(sessionId)}/answers`, answers));
}

export async function readSession(sessionId: string): Promise<Viewed> {
  return viewedOf(await sent(sessionPath(sessionId), { cache: "no-store" }));
}

export async function readTracing(): Promise<boolean> {
  return tracingOf(await sent("/health", { cache: "no-store" }));
}

/** `GET /health`'s response: whether the API traces its runs. Only its saying so counts, so a
 * call that fails shows no notice. */
export async function tracingOf(response: Response | null): Promise<boolean> {
  if (!response?.ok) {
    return false;
  }
  const health = (await bodyOf(response)) as Health | null;
  return health?.tracing === true;
}

/** A stream route's response: its events, or why there are none. */
export async function streamedOf(response: Response | null): Promise<Streamed> {
  if (response?.ok && response.body !== null) {
    return { kind: "stream", events: streamEvents(response.body) };
  }
  return failed(response);
}

/** `GET /sessions/{id}`'s response: the session view, or why there is none. */
export async function viewedOf(response: Response | null): Promise<Viewed> {
  if (!response?.ok) {
    return failed(response);
  }
  const view = await bodyOf(response);
  return view === null ? { kind: "unreachable" } : { kind: "view", view: view as SessionView };
}

/** Each event's data, taken for the `StreamEvent` the schema says it is: the API's contract,
 * checked on the backend's side (`tests/api/test_app.py`), not again here. */
async function* streamEvents(body: ReadableStream<Uint8Array>): AsyncGenerator<StreamEvent> {
  for await (const event of serverSentEvents(body)) {
    const data: StreamEvent = JSON.parse(event.data);
    yield data;
  }
}

/** A refusal when the body is the API's error body; anything else, such as a proxy's error
 * page, is taken for an API that could not be reached. */
async function failed(response: Response | null): Promise<Refused | Unreachable> {
  const body = response === null ? null : await bodyOf(response);
  return isApiError(body) ? { kind: "refused", error: body } : { kind: "unreachable" };
}

function isApiError(body: unknown): body is ApiError {
  return (
    typeof body === "object" &&
    body !== null &&
    "code" in body &&
    typeof body.code === "string" &&
    "message" in body &&
    typeof body.message === "string"
  );
}

async function bodyOf(response: Response): Promise<unknown> {
  try {
    return await response.json();
  } catch {
    return null;
  }
}

function sessionPath(sessionId: string): string {
  return `/sessions/${encodeURIComponent(sessionId)}`;
}

function posted(path: string, body: unknown): Promise<Response | null> {
  return sent(path, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify(body),
  });
}

/** The response, or null when the request got none. */
async function sent(path: string, init: RequestInit): Promise<Response | null> {
  try {
    return await fetch(`${API_URL}${path}`, init);
  } catch {
    return null;
  }
}
