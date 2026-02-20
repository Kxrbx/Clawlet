import * as React from "react"
import * as Slot from "@radix-ui/react-slot"
import { cn } from "@/lib/utils"

export interface ButtonProps
  extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?:
    | "default"
    | "destructive"
    | "outline"
    | "secondary"
    | "ghost"
    | "link"
    | "lime"
    | "magenta"
    | "cyan"
    | "yellow"
    | "orange"
    | "dark"
  size?: "default" | "sm" | "lg" | "xl" | "icon-sm" | "icon-lg"
  asChild?: boolean
}

const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant = "default", size = "default", asChild = false, ...props }, ref) => {
    const Comp = asChild ? Slot.Root : "button"

    return (
      <Comp
        data-slot="button"
        data-variant={variant}
        data-size={size}
        className={cn(
          "inline-flex items-center justify-center gap-2 whitespace-nowrap font-bold transition-all disabled:pointer-events-none disabled:opacity-50 [&_svg]:pointer-events-none [&_svg:not([class*='size-'])]:size-4 shrink-0 [&_svg]:shrink-0 outline-none focus-visible:outline-none active:translate-x-1 active:translate-y-1",
          {
            "border-4 border-black bg-claw-lime text-black shadow-hard hover:bg-claw-yellow": variant === "default" || variant === "lime",
            "border-4 border-black bg-claw-red text-white shadow-hard hover:bg-claw-orange": variant === "destructive",
            "border-4 border-black bg-transparent text-black shadow-hard-sm hover:bg-claw-gray": variant === "outline",
            "border-4 border-black bg-claw-gray text-black shadow-hard hover:bg-claw-cyan": variant === "secondary",
            "border-2 border-transparent hover:border-black hover:bg-claw-gray/50": variant === "ghost",
            "text-claw-lime underline-offset-4 hover:underline": variant === "link",
            "border-4 border-black bg-claw-magenta text-white shadow-hard hover:bg-claw-orange": variant === "magenta",
            "border-4 border-black bg-claw-cyan text-black shadow-hard hover:bg-claw-lime": variant === "cyan",
            "border-4 border-black bg-claw-yellow text-black shadow-hard hover:bg-claw-lime": variant === "yellow",
            "border-4 border-black bg-claw-orange text-black shadow-hard hover:bg-claw-yellow": variant === "orange",
            "border-4 border-black bg-claw-dark text-white shadow-hard hover:bg-claw-gray": variant === "dark",
            "h-11 px-6 text-base": size === "default",
            "h-8 px-4 text-sm": size === "sm",
            "h-14 px-8 text-lg": size === "lg",
            "h-16 px-10 text-xl": size === "xl",
            "h-8 w-8": size === "icon-sm",
            "h-12 w-12 text-lg": size === "icon-lg",
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
