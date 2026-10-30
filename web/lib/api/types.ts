/** Names for the schemas the page reads, all generated from the API's OpenAPI schema
 * (`schema.d.ts`, written by `npm run generate`); none is written by hand. */

import type { components } from "./schema";

type Schemas = components["schemas"];

export type StreamEvent = Schemas["StreamEvent"];
export type ProgressEvent = Schemas["ProgressEvent"];
export type ReplyReadEvent = Schemas["ReplyReadEvent"];
export type ErrorEvent = Schemas["ErrorEvent"];
export type SessionView = Schemas["SessionView"];
export type SessionStart = Schemas["SessionStart"];
export type SessionLines = Schemas["SessionLines"];
export type ReportLines = Schemas["ReportLines"];
export type OptionLines = Schemas["OptionLines"];
export type FigureLine = Schemas["FigureLine"];
export type FactorFigure = Schemas["FactorFigure"];
export type CheckLines = Schemas["CheckLines"];
export type CheckGroup = Schemas["CheckGroup"];
export type TrailLine = Schemas["TrailLine"];
export type WarningLine = Schemas["WarningLine"];
export type Line = Schemas["Line"];
export type ConfidencePart = Schemas["ConfidencePart"];
export type Request = Schemas["Request"];
export type Report = Schemas["Report"];
export type ComparisonRow = Schemas["ComparisonRow"];
export type AnswersRequest = Schemas["AnswersRequest"];
export type GivenAnswer = Schemas["GivenAnswer"];
export type Question = Schemas["Question"];
export type DecisionFactor = Schemas["DecisionFactor"];
export type ApiError = Schemas["ApiError"];
export type Health = Schemas["Health"];
