/**
 * The session a tab is on, kept in the tab's `sessionStorage` so a reload, or Back from a shop's
 * page, finds it again through `GET /sessions/{id}`. Never in the URL: that route has no auth, so a
 * shared link would show the session's input to anyone. A browser may refuse the storage; the page
 * then works as before, without coming back.
 */

const KEY = "session";

export interface SavedSession {
  sessionId: string;
  /** The text the session was started with: a session still running is read back without it. */
  input: string;
}

type TabStorage = Pick<Storage, "getItem" | "setItem" | "removeItem">;

export function readSaved(storage: TabStorage): SavedSession | null {
  try {
    const saved: unknown = JSON.parse(storage.getItem(KEY) ?? "null");
    return isSaved(saved) ? saved : null;
  } catch {
    return null;
  }
}

/** Keeps the session, or with none forgets the one kept. */
export function writeSaved(storage: TabStorage, saved: SavedSession | null): void {
  try {
    if (saved === null) {
      storage.removeItem(KEY);
    } else {
      storage.setItem(KEY, JSON.stringify(saved));
    }
  } catch {
    // Nothing to do: the session just does not come back after a reload.
  }
}

function isSaved(value: unknown): value is SavedSession {
  return (
    typeof value === "object" &&
    value !== null &&
    "sessionId" in value &&
    typeof value.sessionId === "string" &&
    "input" in value &&
    typeof value.input === "string"
  );
}
