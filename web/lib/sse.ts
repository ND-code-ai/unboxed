/**
 * Server-Sent Events read from a response body. `EventSource` only does `GET`, and the API's
 * streams answer a `POST`, so the body is read with `fetch` and parsed here.
 */

export interface ServerSentEvent {
  event: string;
  data: string;
}

/** Each event of the stream as it completes; comments are left out, and so is an event the
 * stream ended in the middle of. */
export async function* serverSentEvents(
  body: ReadableStream<Uint8Array>,
): AsyncGenerator<ServerSentEvent> {
  // A reader, not `for await`: Safari cannot iterate a stream.
  const reader = body.getReader();
  const decoder = new TextDecoder();
  let buffered = "";
  for (let read = await reader.read(); !read.done; read = await reader.read()) {
    buffered += decoder.decode(read.value, { stream: true });
    const blocks = buffered.split("\n\n");
    buffered = blocks.pop() ?? "";
    yield* blocks.map(parsedBlock).filter((event) => event !== null);
  }
}

/** One event's lines: its name on `event:`, its data on one or more `data:` lines. */
function parsedBlock(block: string): ServerSentEvent | null {
  let event = "message";
  const data: string[] = [];
  for (const line of block.split("\n")) {
    const [field, value] = fieldOf(line);
    if (field === "event") {
      event = value;
    } else if (field === "data") {
      data.push(value);
    }
  }
  return data.length === 0 ? null : { event, data: data.join("\n") };
}

function fieldOf(line: string): [string, string] {
  const colon = line.indexOf(":");
  if (colon === -1) {
    return [line, ""];
  }
  const value = line.slice(colon + 1);
  return [line.slice(0, colon), value.startsWith(" ") ? value.slice(1) : value];
}
