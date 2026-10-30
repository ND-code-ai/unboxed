import type { Agent, Station } from "@/lib/thread";

import styles from "./RouteLine.module.css";

/** What the stations open on the results page: each its agent's part of the trail, by the id of
 * the element that holds it. Each part opens and closes on its own, so any of them, or all, can be
 * open at once. */
export interface Opener {
  open: Agent[];
  partOf: (agent: Agent) => string;
  onToggle: (agent: Agent) => void;
}

/** The route line (docs/design/chat_page_brief.md, "The route line"): one station per agent, in the
 * order they run. A finished station is ticked, the current one ringed, the rest hollow; the
 * agent's line is the status line's. The dots are a drawing; the list is the reading. With an
 * `opener`, on the results page, each station is a button that opens its agent's part of the
 * trail, and pressed again closes it. */
export function RouteLine({ stations, opener }: { stations: Station[]; opener?: Opener }) {
  return (
    <ol className={styles.route} data-route>
      {stations.map(({ agent, name, state }) => {
        const stop = (
          <>
            <span className={styles.dot} aria-hidden="true" />
            <span className={styles.name}>{name}</span>
          </>
        );
        return (
          <li
            key={agent}
            className={styles.station}
            data-state={state}
            aria-current={state === "current" ? "step" : undefined}
          >
            {opener === undefined ? (
              <span className={styles.stop}>{stop}</span>
            ) : (
              <button
                type="button"
                className={styles.stop}
                aria-expanded={opener.open.includes(agent)}
                aria-controls={opener.partOf(agent)}
                onClick={() => opener.onToggle(agent)}
              >
                {stop}
              </button>
            )}
          </li>
        );
      })}
    </ol>
  );
}
