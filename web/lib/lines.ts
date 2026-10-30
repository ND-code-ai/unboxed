/** How the page lays out the parts of a line the API sent (docs/adr/0008-api-sends-finished-lines.md). */

import type { Line } from "./api/types";

/** A line's words, without the control it may end in: for a place that shows words alone, such as
 * the box's first label or a button. */
export function lineText(line: Line): string {
  return line.parts
    .map((part) => (part.kind === "control" ? "" : part.text))
    .join("")
    .trim();
}

/** A line with each link's words cut to its site, such as "beslist.nl": a whole address is long and
 * can carry a shop's tracking. The link still opens the same page. */
export function shortLinks(line: Line): Line {
  return {
    ...line,
    parts: line.parts.map((part) => {
      const url = part.kind === "link" ? webLink(part.url) : null;
      return part.kind === "link" && url !== null
        ? { ...part, text: new URL(url).hostname.replace(/^www\./, "") }
        : part;
    }),
  };
}

/** The address a link part may open: a web page only, since a source's URL comes from the web;
 * any other part shows as its words. */
export function webLink(url: string): string | null {
  try {
    const { protocol } = new URL(url);
    return protocol === "https:" || protocol === "http:" ? url : null;
  } catch {
    return null;
  }
}
