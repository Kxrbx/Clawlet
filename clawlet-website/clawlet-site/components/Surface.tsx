"use client";

import { cva, type VariantProps } from "class-variance-authority";
import { cn } from "@/lib/utils";

const surfaceVariants = cva(
  "rounded-xl backdrop-blur-sm transition-all duration-300 ease-out",
  {
    variants: {
      layer: {
        panel: "bg-gradient-to-br from-sakura-50 to-white dark:from-sakura-950/50 dark:to-sakura-900/30 border border-sakura-200 dark:border-sakura-800 shadow-sm",
        card: "bg-white dark:bg-sakura-950/40 border border-sakura-100 dark:border-sakura-800/50",
        chip: "bg-sakura-100 dark:bg-sakura-900/50 text-sakura-700 dark:text-sakura-300 border border-sakura-200 dark:border-sakura-700 text-sm px-3 py-1 rounded-full",
        metric: "bg-gradient-to-br from-sakura-100 to-sakura-50 dark:from-sakura-900/60 dark:to-sakura-950/40 border border-sakura-200 dark:border-sakura-700",
      },
      interactive: {
        true: "cursor-pointer hover:shadow-lg hover:scale-[1.02] active:scale-[0.98]",
        false: "",
      },
      glow: {
        true: "shadow-glow hover:shadow-glow-lg",
        false: "",
      },
    },
    defaultVariants: {
      layer: "card",
      interactive: false,
      glow: false,
    },
  }
);

interface SurfaceProps
  extends React.HTMLAttributes<HTMLDivElement>,
    VariantProps<typeof surfaceVariants> {}

export function Surface({
  layer,
  interactive,
  glow,
  className,
  children,
  ...props
}: SurfaceProps & { children: React.ReactNode }) {
  return (
    <div
      className={cn(surfaceVariants({ layer, interactive, glow }), className)}
      {...props}
    >
      {children}
    </div>
  );
}

// Card with header for documentation sections
export function DocCard({
  title,
  description,
  icon,
  children,
}: {
  title: string;
  description?: string;
  icon?: React.ReactNode;
  children?: React.ReactNode;
}) {
  return (
    <Surface layer="panel" className="p-6">
      <div className="flex items-start gap-3 mb-4">
        {icon && <div className="text-2xl">{icon}</div>}
        <div>
          <h3 className="font-semibold text-lg text-sakura-700 dark:text-sakura-300">
            {title}
          </h3>
          {description && (
            <p className="text-sm text-muted-foreground mt-1">{description}</p>
          )}
        </div>
      </div>
      {children && <div className="mt-4">{children}</div>}
    </Surface>
  );
}

// Badge for tags
export function Badge({
  children,
  variant = "default",
}: {
  children: React.ReactNode;
  variant?: "default" | "success" | "warning" | "destructive" | "outline";
}) {
  const variants = cva(
    "inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium transition-colors",
    {
      variants: {
        variant: {
          default:
            "bg-sakura-100 dark:bg-sakura-900/50 text-sakura-700 dark:text-sakura-300 border border-sakura-200 dark:border-sakura-700",
          success:
            "bg-green-100 dark:bg-green-900/30 text-green-700 dark:text-green-400 border border-green-200 dark:border-green-700",
          warning:
            "bg-amber-100 dark:bg-amber-900/30 text-amber-700 dark:text-amber-400 border border-amber-200 dark:border-amber-700",
          destructive:
            "bg-red-100 dark:bg-red-900/30 text-red-700 dark:text-red-400 border border-red-200 dark:border-red-700",
          outline:
            "border border-input bg-background hover:bg-accent hover:text-accent-foreground",
        },
      },
      defaultVariants: { variant: "default" },
    }
  );

  return <span className={variants({ variant })}>{children}</span>;
}
