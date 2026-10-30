/**
 * The longest input and reply the API reads, as its OpenAPI schema publishes them (`maxLength`);
 * the generated types carry no number. Read on the server, so the schema is not sent to the
 * browser.
 */

import schema from "./openapi.json";

export type MaxLengths = Record<"input" | "reply", number | undefined>;

const { StartRequest, AnswersRequest } = schema.components.schemas;

export const MAX_LENGTHS: MaxLengths = {
  input: StartRequest.properties.input.maxLength,
  // The reply may be null, so its cap is on the string among the schema's options.
  reply: AnswersRequest.properties.reply.anyOf.find((option) => "maxLength" in option)?.maxLength,
};
