import type { Line } from "@/lib/api/types";
import { webLink } from "@/lib/lines";
import { CONTROLS } from "@/lib/wording";

import { Button } from "./ui/button";

type Part = Line["parts"][number];

/** What each control a line can end in does; none where the thread is read back, as beside the
 * results, so a line keeps its words and drops its control. */
export type Controls = Record<keyof typeof CONTROLS, () => void> | null;

interface Props {
  line: Line;
  /** None by default: the line is read, as on the results page. */
  controls?: Controls;
  /** Set inside another element, such as a figure's key or value: a span, not a paragraph. */
  inline?: boolean;
}

/** A line the API sent, its parts laid out in order (docs/adr/0008-api-sends-finished-lines.md). */
export function LineView({ line, controls = null, inline = false }: Props) {
  const Element = inline ? "span" : "p";
  return (
    <Element>
      {line.parts.map((part, index) => (
        <PartView key={index} part={part} controls={controls} />
      ))}
    </Element>
  );
}

function PartView({ part, controls }: { part: Part; controls: Controls }) {
  switch (part.kind) {
    case "text":
      return part.text;
    case "link": {
      const href = webLink(part.url);
      return href === null ? (
        part.text
      ) : (
        <a href={href} target="_blank" rel="noreferrer">
          {part.text}
        </a>
      );
    }
    case "confidence":
      // Its words only, styled as the line around it: a colour, seal or icon would read as a
      // certification (docs/eu_market.md, "Environmental claims").
      return <span>{part.text}</span>;
    case "control":
      return controls === null ? null : (
        <Button type="button" size="sm" className="ml-3" onClick={controls[part.key]}>
          {CONTROLS[part.key]}
        </Button>
      );
  }
}
