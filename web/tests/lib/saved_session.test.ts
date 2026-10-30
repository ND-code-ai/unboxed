import { describe, expect, test } from "vitest";

import { readSaved, writeSaved } from "../../lib/saved_session";
import { FRYING_PAN_INPUT, SESSION_ID } from "./samples";

/** A tab's storage, as a map. */
function storage(held = new Map<string, string>()): Parameters<typeof readSaved>[0] {
  return {
    getItem: (key) => held.get(key) ?? null,
    setItem: (key, value) => void held.set(key, value),
    removeItem: (key) => void held.delete(key),
  };
}

const SAVED = { sessionId: SESSION_ID, input: FRYING_PAN_INPUT };

describe("the session a tab is on", () => {
  test("reads back as it was written", () => {
    const tab = storage();
    writeSaved(tab, SAVED);

    expect(readSaved(tab)).toEqual(SAVED);
  });

  test("is gone once written as none", () => {
    const tab = storage();
    writeSaved(tab, SAVED);
    writeSaved(tab, null);

    expect(readSaved(tab)).toBeNull();
  });

  test("is none when nothing was written, or what was written cannot be read", () => {
    expect(readSaved(storage())).toBeNull();
    expect(readSaved(storage(new Map([["session", "not json"]])))).toBeNull();
    expect(readSaved(storage(new Map([["session", '{"sessionId":1}']])))).toBeNull();
  });

  test("is none, and nothing is thrown, when the browser refuses the storage", () => {
    const refused: Parameters<typeof readSaved>[0] = {
      getItem: () => {
        throw new Error("denied");
      },
      setItem: () => {
        throw new Error("denied");
      },
      removeItem: () => {
        throw new Error("denied");
      },
    };

    expect(readSaved(refused)).toBeNull();
    expect(() => writeSaved(refused, SAVED)).not.toThrow();
    expect(() => writeSaved(refused, null)).not.toThrow();
  });
});
