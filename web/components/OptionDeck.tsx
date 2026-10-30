"use client";

import { cn } from "cn";
import { useEffect, useRef, useState, type PointerEvent } from "react";

import type { OptionLines } from "@/lib/api/types";
import { lineText } from "@/lib/lines";
import { rowsOf } from "@/lib/results";
import { NEXT_OPTION, OPTIONS_STRIP, PREVIOUS_OPTION, placeAmong } from "@/lib/wording";

import { OptionRows } from "./OptionCell";
import { Button } from "./ui/button";

interface Props {
  /** The cards in the deck's order (`deckOrder`). */
  cards: OptionLines[];
  /** Each option's letter by its id (`lettersOf`). */
  letters: Map<string, string>;
  /** What the model read of each option's durability by its id (`judgementsOf`). */
  judgements: Map<string, string>;
  className?: string;
}

/** Where the card shown came from: the step before it, the step after it, or neither at first. */
type From = "previous" | "next" | null;

// How far a touch has to travel sideways, in pixels, to step to the next card.
const SWIPE = 48;

// On the field a faded button would let the coral through behind its words, so a step that
// cannot be taken keeps its paper and turns its ink muted.
const ON_THE_FIELD = "disabled:border-muted disabled:text-muted disabled:opacity-100";

/** The deck, the phone's view (DESIGN.md, "Deck"): one option card at a time, the baseline first,
 * under a pinned strip of every option's name and cost per year that steps to it; swiped, or
 * stepped with Previous and Next. */
export function OptionDeck({ cards, letters, judgements, className }: Props) {
  const [shown, setShown] = useState<{ id: string | null; from: From }>({ id: null, from: null });
  const strip = useRef<HTMLOListElement>(null);
  const shownCard = useRef<HTMLElement>(null);
  const touch = useRef<{ x: number; y: number } | null>(null);
  // A card the budget switch hid gives way to the first.
  const at = Math.max(
    0,
    cards.findIndex((card) => card.option_id === shown.id),
  );
  const card = cards[at];

  // Stepped to from the card's foot, the next card is read from its top, just under the strip.
  useEffect(() => {
    const top = shownCard.current?.getBoundingClientRect().top;
    const below = (strip.current?.offsetHeight ?? 0) + 8;
    if (shown.from !== null && top !== undefined && top < below) {
      window.scrollBy({ top: top - below });
    }
  }, [shown]);

  function go(index: number) {
    if (index >= 0 && index < cards.length && index !== at) {
      setShown({ id: cards[index].option_id, from: index > at ? "next" : "previous" });
    }
  }

  function swiped(event: PointerEvent) {
    const start = touch.current;
    touch.current = null;
    if (start === null) {
      return;
    }
    const across = event.clientX - start.x;
    if (Math.abs(across) > SWIPE && Math.abs(across) > 1.5 * Math.abs(event.clientY - start.y)) {
      go(across < 0 ? at + 1 : at - 1);
    }
  }

  return (
    <div className={cn("grid gap-4", className)}>
      <ol
        ref={strip}
        aria-label={OPTIONS_STRIP}
        className="sticky top-0 z-20 -mx-4 grid auto-cols-fr grid-flow-col gap-2 bg-field px-4 py-3 lg:mx-0 lg:px-0"
      >
        {cards.map((each, index) => (
          <li key={each.option_id} className="min-w-0">
            <button
              type="button"
              aria-pressed={index === at}
              onClick={() => go(index)}
              className="grid h-full w-full content-start gap-0.5 border-2 border-ink bg-paper px-2.5 py-2 text-left transition-colors duration-150 hover:not-aria-pressed:bg-lip aria-pressed:bg-ink aria-pressed:text-paper"
            >
              <span className="hidden text-xs font-bold lg:block">
                {letters.get(each.option_id)}
              </span>
              <span className="line-clamp-2 text-sm leading-tight font-semibold">
                {lineText(each.name)}
              </span>
              {/* From 1024 px, in the Cards view, the figure the page leads with. */}
              <span className="tabular-nums lg:hidden">{lineText(each.cost_per_year.value)}</span>
              <span className="hidden text-xs lg:block">{lineText(each.horizon_cost.label)}</span>
              <span className="hidden tabular-nums lg:block">
                {lineText(each.horizon_cost.value)}
              </span>
            </button>
          </li>
        ))}
      </ol>
      <article
        key={card.option_id}
        ref={shownCard}
        data-card={card.option_id}
        className={cn(
          "grid touch-pan-y border-2 border-ink bg-paper pb-4",
          shown.from === "next" && "deck-from-next",
          shown.from === "previous" && "deck-from-previous",
        )}
        onPointerDown={(event) => {
          touch.current =
            event.pointerType === "touch" ? { x: event.clientX, y: event.clientY } : null;
        }}
        onPointerUp={swiped}
        onPointerCancel={() => {
          touch.current = null;
        }}
      >
        <OptionRows
          option={card}
          rows={rowsOf([card])}
          letter={letters.get(card.option_id)}
          judgement={judgements.get(card.option_id)}
        />
      </article>
      <div className="flex items-center justify-between gap-3">
        <Button
          type="button"
          className={ON_THE_FIELD}
          disabled={at === 0}
          onClick={() => go(at - 1)}
        >
          {PREVIOUS_OPTION}
        </Button>
        <p aria-live="polite" className="text-sm font-semibold tabular-nums">
          {placeAmong(at + 1, cards.length)}
        </p>
        <Button
          type="button"
          className={ON_THE_FIELD}
          disabled={at === cards.length - 1}
          onClick={() => go(at + 1)}
        >
          {NEXT_OPTION}
        </Button>
      </div>
    </div>
  );
}
