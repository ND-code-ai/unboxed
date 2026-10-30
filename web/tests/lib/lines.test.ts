import { expect, test } from "vitest";

import { lineText, webLink } from "../../lib/lines";

test.each(["https://stub.invalid/hob-compatibility", "http://example.org/pan"])(
  "a web address, %s, is a link",
  (url) => {
    expect(webLink(url)).toBe(url);
  },
);

test.each(["javascript:alert(1)", "data:text/html,hi", "/sessions", "not a url"])(
  "anything else, %s, is not",
  (url) => {
    expect(webLink(url)).toBeNull();
  },
);

test("a line's words are its parts' words, a link's and a label's included, without its control", () => {
  expect(
    lineText({
      parts: [
        { kind: "link", text: "GreenChef Soft Grip Pro", url: "https://www.bol.com/greenchef" },
        { kind: "text", text: " (" },
        { kind: "confidence", text: "AI synthetic estimate", basis: "estimate" },
        { kind: "text", text: ") " },
        { kind: "control", key: "edit" },
      ],
    }),
  ).toBe("GreenChef Soft Grip Pro (AI synthetic estimate)");
});
