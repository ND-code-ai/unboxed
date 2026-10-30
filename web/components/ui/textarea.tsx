import * as React from "react";
import { cn } from "cn";

// shadcn/ui's textarea in the world's vocabulary: white paper with a 2 px ink border, faded while
// nothing can be typed.
function Textarea({ className, ...props }: React.ComponentProps<"textarea">) {
  return (
    <textarea
      data-slot="textarea"
      className={cn(
        "block min-h-24 w-full border-2 border-ink bg-paper px-3.5 py-3 text-base text-ink [field-sizing:content] placeholder:text-muted disabled:cursor-not-allowed disabled:opacity-40",
        className,
      )}
      {...props}
    />
  );
}

export { Textarea };
