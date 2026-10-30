import { expect, test } from "vitest";

import { aboutQuestion, moreQuestions, placeAmong } from "../../lib/wording";

test("the place of the open question is filled in", () => {
  expect(placeAmong(2, 5)).toBe("2 of 5");
});

test("the question an answer in the user's own words is about is filled in", () => {
  expect(aboutQuestion("Which hob do you cook on?")).toBe('About "Which hob do you cook on?": ');
});

test.each([
  [3, ["3 more questions · or ", ""]],
  [1, ["1 more question · or ", ""]],
])("the words around the button, with %i more, are %j", (more, words) => {
  expect(moreQuestions(more)).toEqual(words);
});
