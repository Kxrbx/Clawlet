import * as React from "react"
import * as Slot from "@radix-ui/react-slot"
import { cn } from "@/lib/utils"

export interface ButtonProps
  extends React.ComponentProps<"button"> {
  variant?: "default" | "destructive" | "outline" | "secondary" | "ghost" | "link" | "sakura"
  size?: "default" | "sm" | "lg" | "icon"
  asChild?: boolean
}

const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant = "default", size = "default", asChild = false, ...props }, ref) => {
    const Comp = asChild ? Slot.Root : "button"

    return (
      <Comp
        data-slot="button"
        className={cn(
          "inline-flex items-center justify-center gap-2 whitespace-nowrap rounded-lg font-semibold transition-all disabled:pointer-events-none disabled:opacity-50 [&_svg]:pointer-events-none [&_svg:not([class*='size-'])]:size-4 shrink-0 [&_svg]:shrink-0 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-sakura-400 focus-visible:ring-offset-2 active:scale-[0.98]",
          {
            // Default / Sakura primary (gradient)
            "bg-gradient-to-r from-sakura-500 to-sakura-600 text-white shadow-glow-sm hover:shadow-glow-md": variant === "default" || variant === "sakura",
            // Destructive (redish)
            "bg-sakura-700 text-white hover:bg-sakura-800 shadow-glow-sm": variant === "destructive",
            // Outline
            "border border-sakura-300 bg-white text-sakura-600 hover:bg-sakura-50": variant === "outline",
            // Secondary
            "bg-sakura-100 text-sakura-700 hover:bg-sakura-200": variant === "secondary",
            // Ghost
            "text-sakura-600 hover:bg-sakura-100": variant === "ghost",
            // Link
            "text-sakura-600 underline-offset-4 hover:underline": variant === "link",
            // Sizes
            "h-10 px-4 py-2 text-sm": size === "sm",
            "h-12 px-6 py-3 text-base": size === "default",
            "h-14 px-8 py-4 text-lg": size === "lg",
            "h-10 w-10": size === "icon",
          },
          className
        )}
        ref={ref}
        {...props}
      />
    )
  }
)
Button.displayName = "Button"

export { Button }
