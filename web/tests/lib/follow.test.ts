import { describe, expect, test } from "vitest";

import type { Streamed } from "../../lib/api/client";
import type { StreamEvent } from "../../lib/api/types";
import { follow, viewResult } from "../../lib/follow";
import type { ApiResult } from "../../lib/thread";
import { AT_THE_PAUSE, NOT_FOUND, PAUSE_LINES, PAUSED, READING, STARTED } from "./samples";

async function heard(streamed: Streamed): Promise<ApiResult[]> {
  const results: ApiResult[] = [];
  await follow(streamed, (result) => results.push(result));
  return results;
}

async function* cutAfter(...events: StreamEvent[]): AsyncGenerator<StreamEvent> {
  yield* events;
  throw new TypeError("network error");
}

async function* whole(...events: StreamEvent[]): AsyncGenerator<StreamEvent> {
  yield* events;
}

describe("follow", () => {
  test("passes on each event as it comes, then the end", async () => {
    expect(await heard({ kind: "stream", events: whole(STARTED, PAUSED) })).toEqual([
      { type: "streamed", event: STARTED },
      { type: "streamed", event: PAUSED },
      { type: "stream_ended" },
    ]);
  });

  test("passes on the events of a stream cut mid-read, then the end", async () => {
    expect(await heard({ kind: "stream", events: cutAfter(STARTED, READING) })).toEqual([
      { type: "streamed", event: STARTED },
      { type: "streamed", event: READING },
      { type: "stream_ended" },
    ]);
  });

  test("passes on a refusal with its error body", async () => {
    expect(await heard({ kind: "refused", error: NOT_FOUND })).toEqual([
      { type: "refused", error: NOT_FOUND },
    ]);
  });

  test("passes on a request with no answer as unreachable", async () => {
    expect(await heard({ kind: "unreachable" })).toEqual([{ type: "unreachable" }]);
  });
});

describe("viewResult", () => {
  test("is the view read, the refusal, or no answer", () => {
    const view = { status: "paused", session: AT_THE_PAUSE, lines: PAUSE_LINES } as const;

    expect(viewResult({ kind: "view", view })).toEqual({ type: "viewed", view });
    expect(viewResult({ kind: "refused", error: NOT_FOUND })).toEqual({
      type: "refused",
      error: NOT_FOUND,
    });
    expect(viewResult({ kind: "unreachable" })).toEqual({ type: "unreachable" });
  });
});
