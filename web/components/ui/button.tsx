import * as React from "react";
import { cva, type VariantProps } from "class-variance-authority";
import { cn } from "cn";

// shadcn/ui's button in the world's vocabulary: square, a 2 px ink border. A button that cannot be
// pressed now keeps its look, faded; dashes are for skipped answers only.
const buttonVariants = cva(
  "inline-flex shrink-0 items-center justify-center gap-2 border-2 font-semibold transition-colors duration-150 disabled:cursor-not-allowed disabled:opacity-40",
  {
    variants: {
      variant: {
        solid: "border-ink bg-ink text-paper enabled:hover:border-inside enabled:hover:bg-inside",
        outline: "border-ink bg-paper text-ink enabled:hover:bg-lip",
        chip: "border-ink bg-paper text-left whitespace-normal text-ink enabled:hover:not-aria-pressed:bg-lip aria-pressed:bg-ink aria-pressed:text-paper",
        link: "border-transparent p-0 text-left text-inherit underline decoration-1 underline-offset-[3px] enabled:hover:decoration-2",
      },
      size: {
        default: "min-h-11 px-5 py-2",
        sm: "min-h-9 px-3 py-1 text-sm",
        lg: "min-h-13 px-6 py-2 text-lg",
        inline: "h-auto",
      },
    },
    defaultVariants: {
      variant: "outline",
      size: "default",
    },
  },
);

function Button({
  className,
  variant = "outline",
  size = "default",
  ...props
}: React.ComponentProps<"button"> & VariantProps<typeof buttonVariants>) {
  return (
    <button
      data-slot="button"
      data-variant={variant}
      data-size={size}
      className={cn(buttonVariants({ variant, size, className }))}
      {...props}
    />
  );
}

export { Button };
