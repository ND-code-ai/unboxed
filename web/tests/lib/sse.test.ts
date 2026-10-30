import { describe, expect, test } from "vitest";

import { serverSentEvents, type ServerSentEvent } from "../../lib/sse";

function streamOf(...chunks: string[]): ReadableStream<Uint8Array> {
  const encoder = new TextEncoder();
  return new ReadableStream({
    start(controller) {
      chunks.forEach((chunk) => controller.enqueue(encoder.encode(chunk)));
      controller.close();
    },
  });
}

async function read(body: ReadableStream<Uint8Array>): Promise<ServerSentEvent[]> {
  const events: ServerSentEvent[] = [];
  for await (const event of serverSentEvents(body)) {
    events.push(event);
  }
  return events;
}

describe("serverSentEvents", () => {
  test("reads each event's name and data, however the chunks split them", async () => {
    const body = streamOf(
      'event: session_started\ndata: {"event":"session_started"',
      ',"session_id":"s-1"}\n\neve',
      'nt: progress\ndata: {"event":"progress"}\n\n',
    );

    expect(await read(body)).toEqual([
      { event: "session_started", data: '{"event":"session_started","session_id":"s-1"}' },
      { event: "progress", data: '{"event":"progress"}' },
    ]);
  });

  test("skips a keep-alive comment", async () => {
    const body = streamOf(": keep-alive\n\n", "event: report\ndata: {}\n\n");

    expect(await read(body)).toEqual([{ event: "report", data: "{}" }]);
  });

  test("keeps a character split between two chunks whole", async () => {
    const bytes = new TextEncoder().encode('event: progress\ndata: "€5"\n\n');
    const euro = bytes.indexOf(0xe2);
    const body = new ReadableStream<Uint8Array>({
      start(controller) {
        controller.enqueue(bytes.slice(0, euro + 1));
        controller.enqueue(bytes.slice(euro + 1));
        controller.close();
      },
    });

    expect(await read(body)).toEqual([{ event: "progress", data: '"€5"' }]);
  });

  test("leaves out an event the stream ended in the middle of", async () => {
    const body = streamOf("event: report\ndata: {}\n\n", 'event: report\ndata: {"cut');

    expect(await read(body)).toEqual([{ event: "report", data: "{}" }]);
  });
});
