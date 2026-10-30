import { cn } from "cn";

import type { OptionLines } from "@/lib/api/types";
import { sheetRowsOf } from "@/lib/results";

import { OptionRows } from "./OptionCell";

interface Props {
  options: OptionLines[];
  /** How many sheets the report has, so a sheet the budget switch hides leaves its width to no
   * other. */
  columns: number;
  /** Each option's letter by its id (`lettersOf`). */
  letters: Map<string, string>;
  /** What the model read of each option's durability by its id (`judgementsOf`). */
  judgements: Map<string, string>;
  className?: string;
}

/** Rows, the wide screen's view (DESIGN.md, "Option Sheet"): the options side by side as option
 * sheets, each figure level across them (the sheets share the grid's rows), a row left empty on a
 * sheet without it. */
export function OptionSheets({ options, columns, letters, judgements, className }: Props) {
  const rows = sheetRowsOf(options);
  return (
    <div
      className={cn("gap-x-4 text-pretty", className)}
      style={{
        gridTemplateColumns: `repeat(${columns}, minmax(0, 1fr))`,
        gridTemplateRows: `repeat(${rows.length}, auto)`,
      }}
    >
      {options.map((option) => (
        <article
          key={option.option_id}
          data-sheet={option.option_id}
          className="row-span-full grid grid-rows-subgrid border-2 border-ink bg-paper pb-4"
        >
          <OptionRows
            option={option}
            rows={rows}
            letter={letters.get(option.option_id)}
            judgement={judgements.get(option.option_id)}
          />
        </article>
      ))}
    </div>
  );
}
