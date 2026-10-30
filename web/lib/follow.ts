/** What the API answered, as the results that change the thread (`thread.ts`). */

import type { Streamed, Viewed } from "./api/client";
import type { ApiResult } from "./thread";

/** Each event as it comes, then the end, however the stream closed: a stream cut mid-read
 * ends like one that closed, so the page picks the session up. */
export async function follow(
  streamed: Streamed,
  heard: (result: ApiResult) => void,
): Promise<void> {
  if (streamed.kind !== "stream") {
    heard(notAnswered(streamed));
    return;
  }
  try {
    for await (const event of streamed.events) {
      heard({ type: "streamed", event });
    }
  } catch {
    // The connection dropped, or an event could not be read: either way the end below has the
    // session read as it is now, which says where it stands.
  }
  heard({ type: "stream_ended" });
}

export function viewResult(viewed: Viewed): ApiResult {
  return viewed.kind === "view" ? { type: "viewed", view: viewed.view } : notAnswered(viewed);
}

function notAnswered(result: Exclude<Viewed | Streamed, { kind: "view" | "stream" }>): ApiResult {
  return result.kind === "refused"
    ? { type: "refused", error: result.error }
    : { type: "unreachable" };
}
