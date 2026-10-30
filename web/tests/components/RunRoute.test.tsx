import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, test } from "vitest";

import { RunRoute } from "../../components/RunRoute";
import { ROUTE_DONE } from "../../lib/thread";
import { CLOSE_NOTE, ROUTE_HINT } from "../../lib/wording";

const page = renderToStaticMarkup(<RunRoute stations={ROUTE_DONE} hinted />);

describe("the route line before the results page", () => {
  test("has each station open its own note, every note closed at first", () => {
    const opens = [...page.matchAll(/aria-controls="([^"]+)"/g)].map(([, id]) => id);

    expect(opens).toHaveLength(ROUTE_DONE.length);
    expect(page).not.toContain(`aria-expanded="true"`);
    ROUTE_DONE.forEach(({ detail }, index) => {
      const note = page.slice(page.indexOf(`<div id="${opens[index]}" hidden=""`));
      const words = detail.replaceAll("'", "&#x27;");
      expect(note.slice(note.indexOf("<p"), note.indexOf("</p>"))).toContain(`>${words}`);
    });
  });

  test("gives every note and the hint a cross to close it", () => {
    expect(page.match(new RegExp(`aria-label="${CLOSE_NOTE}"`, "g"))).toHaveLength(
      ROUTE_DONE.length + 1,
    );
  });

  test("says what the stations do until one is pressed", () => {
    expect(page).toContain(ROUTE_HINT.replaceAll("'", "&#x27;"));
  });

  test("keeps its notes but drops the hint between the waits", () => {
    const between = renderToStaticMarkup(<RunRoute stations={ROUTE_DONE} hinted={false} />);

    expect(between.match(/aria-controls=/g)).toHaveLength(ROUTE_DONE.length);
    expect(between).not.toContain(ROUTE_HINT.replaceAll("'", "&#x27;"));
  });
});
