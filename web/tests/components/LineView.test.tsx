import { renderToStaticMarkup } from "react-dom/server";
import { expect, test } from "vitest";

import { LineView } from "../../components/LineView";
import type { Line } from "../../lib/api/types";

const NO_CONTROLS = { edit: () => {} };

test("a confidence part shows its words in a plain span between the line's words", () => {
  const line: Line = {
    parts: [
      { kind: "text", text: "12 to 25 kg CO2e to make, over 10 years (" },
      { kind: "confidence", text: "AI synthetic estimate", basis: "estimate" },
      { kind: "text", text: ")" },
    ],
  };

  expect(renderToStaticMarkup(<LineView line={line} controls={NO_CONTROLS} />)).toBe(
    "<p>12 to 25 kg CO2e to make, over 10 years (<span>AI synthetic estimate</span>)</p>",
  );
});

test("a line read back with no controls keeps its words and drops its control", () => {
  const line: Line = {
    parts: [
      { kind: "text", text: "Looking for: frying pan · Budget: €50" },
      { kind: "control", key: "edit" },
    ],
  };

  expect(renderToStaticMarkup(<LineView line={line} />)).toBe(
    "<p>Looking for: frying pan · Budget: €50</p>",
  );
});

test("a line set inside another element is a span", () => {
  const line: Line = { parts: [{ kind: "text", text: "Price" }] };

  expect(renderToStaticMarkup(<LineView line={line} inline />)).toBe("<span>Price</span>");
});
