import { cn } from "cn";
import { useLayoutEffect, useRef, type CSSProperties, type RefObject } from "react";

import type { Box, Label } from "@/lib/thread";
import { labelled } from "@/lib/wording";

import { WrittenFace } from "./FaceComposer";
import { LabelView } from "./LabelView";
import styles from "./ProductBox.module.css";

interface Props {
  box: Box;
  labels: Label[];
}

/** The plain product box the page is built around: its face the composer before the first send
 * (FaceComposer, laid over it), then carrying the request, faded, under the labels of what was
 * understood and of the answers; sealed while the agents scan, opened at the report. A drawing
 * only: every label and line on it is also in the thread. */
export function ProductBox({ box, labels }: Props) {
  const drawing = useRef<HTMLDivElement>(null);
  useSinkBelowRequest(drawing, box.request, box.cleared);
  const tally = box.tally && labelled(box.tally.answered, box.tally.asked);
  return (
    <div ref={drawing} className={styles.box} data-box data-state={box.state} aria-hidden="true">
      <svg className={styles.layer} viewBox="48 0 928 600">
        <polygon className={styles.inside} points="275,150 749,150 842,242 182,242" />
        <polygon
          className={cn(styles.flap, styles.side, styles.left)}
          points="275,150 162,110 48,180 182,242"
        />
        <polygon
          className={cn(styles.flap, styles.side, styles.right)}
          points="749,150 862,110 976,180 842,242"
        />
        <polygon
          className={cn(styles.flap, styles.backOpen)}
          points="300,62 724,62 749,150 275,150"
        />
        <polygon
          className={cn(styles.flap, styles.backShut)}
          points="275,150 749,150 796,196 228,196"
        />
        <rect className={styles.face} x="182" y="242" width="660" height="356" />
      </svg>
      {box.request !== null && (
        <WrittenFace request={box.request} cleared={box.cleared} tally={tally} />
      )}
      <div className={styles.labels} data-labels>
        <span className={styles.lookingFor}>
          <FirstLabel box={box} />
        </span>
        {labels.map((label, index) => (
          <LabelView
            key={label.id}
            className={styles.drop}
            label={label}
            index={index + 1}
            on="box"
          />
        ))}
      </div>
      <div className={styles.window}>
        {box.scan.map((line) => (
          <span key={`${line.agent}-${line.step}`} className={cn(styles.line, styles.running)}>
            {line.line}
          </span>
        ))}
      </div>
      <svg className={styles.layer} viewBox="48 0 928 600">
        <polygon
          className={cn(styles.flap, styles.lipOpen)}
          points="182,242 842,242 898,298 126,298"
        />
        <polygon
          className={cn(styles.flap, styles.lipShut)}
          points="228,196 796,196 842,242 182,242"
        />
        <rect className={styles.tape} x="494" y="150" width="36" height="130" />
      </svg>
      {/* The marker is held in front of the box, so it rides above the lip: the first label laid
          out again in the same place, unseen but for the marker. */}
      <div className={cn(styles.labels, styles.overLip)}>
        <span className={styles.lookingFor}>
          <FirstLabel box={box} pen />
        </span>
      </div>
    </div>
  );
}

/** Sets how far down the first label sits (`--sink`): just below the request on the face, however
 * many lines it takes, so the request stays in view. Measured again as the box is resized, and as
 * the face is cleared, when the request and the labels rise to their new places. */
function useSinkBelowRequest(
  drawing: RefObject<HTMLDivElement | null>,
  request: string | null,
  cleared: boolean,
) {
  const placed = useRef<{ top: number; sink: number } | null>(null);
  useLayoutEffect(() => {
    const box = drawing.current;
    const words = box?.querySelector<HTMLElement>("[data-request]");
    const labels = box?.querySelector<HTMLElement>("[data-labels]");
    if (!box || !words || !labels) {
      placed.current = null;
      return;
    }
    const place = () => {
      const top = topIn(box, words);
      const gap = box.offsetWidth * 0.012;
      const sink = top + words.offsetHeight + gap - labels.offsetTop;
      box.style.setProperty("--sink", `${sink}px`);
      return { top, sink };
    };
    const was = placed.current;
    const now = place();
    placed.current = now;
    if (cleared && was !== null && !matchMedia("(prefers-reduced-motion: reduce)").matches) {
      const rise = {
        duration: 500,
        easing: getComputedStyle(box).getPropertyValue("--ease-out-expo").trim(),
      };
      const from = (distance: number) => ({ translate: [`0 ${distance}px`, "0 0"] });
      words.parentElement?.animate(from(was.top - now.top), rise);
      for (const layer of box.querySelectorAll(`.${styles.labels}`)) {
        layer.animate(from(was.sink - now.sink), rise);
      }
    }
    const resized = new ResizeObserver(() => {
      placed.current = place();
    });
    resized.observe(box);
    return () => resized.disconnect();
  }, [drawing, request, cleared]);
}

/** How far below the top of the box an element is laid out, its transforms aside. */
function topIn(box: HTMLElement, element: HTMLElement): number {
  let top = 0;
  for (let at: Element | null = element; at instanceof HTMLElement && at !== box;) {
    top += at.offsetTop;
    at = at.offsetParent;
  }
  return top;
}

/** The first label: none before the first send, when the face is the composer (FaceComposer); a
 * blank label, a marker hovering at its start, while the request is read; then what was
 * understood, or "?", written on by the marker. With `pen`, only the marker shows. */
function FirstLabel({ box, pen = false }: { box: Box; pen?: boolean }) {
  if (box.lookingFor !== null) {
    const writing = { "--chars": box.lookingFor.length } as CSSProperties;
    return (
      <LabelView key={box.lookingFor} index={0} on="box">
        <span className={styles.hand} style={writing}>
          <span className={styles.ink}>{box.lookingFor}</span>
          {pen && (
            <span className={styles.track}>
              <Marker className={styles.writing} />
            </span>
          )}
        </span>
      </LabelView>
    );
  }
  if (box.reading) {
    return (
      <LabelView index={0} on="box" className={cn(styles.drop, styles.blank)}>
        <span className={styles.hand}>{pen && <Marker className={styles.hovering} />}</span>
      </LabelView>
    );
  }
  return null;
}

/** A black permanent marker, uncapped, drawn flat; its tip is at the bottom centre. */
function Marker({ className }: { className: string }) {
  return (
    <svg className={cn(styles.marker, className)} viewBox="0 0 40 130">
      <rect x="12" y="2" width="16" height="12" fill="var(--color-ink)" />
      <rect x="9" y="12" width="22" height="84" fill="var(--color-ink)" />
      <rect x="9" y="38" width="22" height="18" fill="var(--color-paper)" />
      <rect x="12" y="96" width="16" height="12" fill="var(--color-muted)" />
      <polygon points="15,108 25,108 22,128 18,128" fill="var(--color-ink)" />
    </svg>
  );
}
