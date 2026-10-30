import { describe, expect, test } from "vitest";

import { streamedOf, tracingOf, viewedOf } from "../../../lib/api/client";
import type { StreamEvent } from "../../../lib/api/types";
import { AT_THE_PAUSE, NOT_FOUND, PAUSED, READING, STARTED } from "../samples";

function eventStream(...events: StreamEvent[]): Response {
  const text = [": keep-alive\n\n"]
    .concat(events.map((event) => `event: ${event.event}\ndata: ${JSON.stringify(event)}\n\n`))
    .join("");
  return new Response(text, { headers: { "content-type": "text/event-stream" } });
}

function json(status: number, body: unknown): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "content-type": "application/json" },
  });
}

describe("streamedOf", () => {
  test("reads a success as its stream's events", async () => {
    const streamed = await streamedOf(eventStream(STARTED, READING, PAUSED));

    expect(streamed.kind).toBe("stream");
    const events: StreamEvent[] = [];
    if (streamed.kind === "stream") {
      for await (const event of streamed.events) {
        events.push(event);
      }
    }
    expect(events).toEqual([STARTED, READING, PAUSED]);
  });

  test("reads an error body as a refusal with its code and message", async () => {
    expect(await streamedOf(json(404, NOT_FOUND))).toEqual({ kind: "refused", error: NOT_FOUND });
  });

  test("takes no response for an API it could not reach", async () => {
    expect(await streamedOf(null)).toEqual({ kind: "unreachable" });
  });

  test("takes an error whose body is not the API's for one it could not reach", async () => {
    const gateway = new Response("<html>Bad Gateway</html>", { status: 502 });

    expect(await streamedOf(gateway)).toEqual({ kind: "unreachable" });
  });
});

describe("tracingOf", () => {
  test("is true when the API says it traces", async () => {
    expect(await tracingOf(json(200, { status: "ok", tracing: true }))).toBe(true);
  });

  test("is false when the API says it does not", async () => {
    expect(await tracingOf(json(200, { status: "ok", tracing: false }))).toBe(false);
  });

  test("is false when the call failed or its body is not the API's", async () => {
    expect(await tracingOf(null)).toBe(false);
    expect(await tracingOf(new Response("<html>Bad Gateway</html>", { status: 502 }))).toBe(false);
    expect(await tracingOf(new Response("<html>A proxy's page</html>"))).toBe(false);
  });
});

describe("viewedOf", () => {
  test("reads a success as the session view", async () => {
    const view = { status: "paused", session: AT_THE_PAUSE };

    expect(await viewedOf(json(200, view))).toEqual({ kind: "view", view });
  });

  test("reads an error body as a refusal", async () => {
    expect(await viewedOf(json(404, NOT_FOUND))).toEqual({ kind: "refused", error: NOT_FOUND });
  });

  test("takes no response for an API it could not reach", async () => {
    expect(await viewedOf(null)).toEqual({ kind: "unreachable" });
  });
});
