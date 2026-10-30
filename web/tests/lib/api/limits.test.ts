import { expect, test } from "vitest";

import { MAX_LENGTHS } from "../../../lib/api/limits";

test("the input and the reply are capped at the schema's 2,000 characters", () => {
  expect(MAX_LENGTHS).toEqual({ input: 2000, reply: 2000 });
});
