"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";

export function Nav() {
  const pathname = usePathname();

  const isDocs = pathname.startsWith("/docs");

  return (
    <nav className="fixed top-0 w-full z-50 border-b border-sakura-200/50 bg-white/80 backdrop-blur-sm dark:bg-slate-950/80 dark:border-sakura-900/50">
      <div className="max-w-6xl mx-auto px-4 h-16 flex items-center justify-between">
        <Link href="/" className="flex items-center gap-2">
          <span className="text-3xl">🌸</span>
          <span className="text-xl font-bold text-sakura-600 dark:text-sakura-400">Clawlet</span>
        </Link>

        <div className="flex items-center gap-6">
          <Link
            href="/"
            className={cn(
              "text-sm transition-colors",
              pathname === "/"
                ? "text-foreground font-medium"
                : "text-muted-foreground hover:text-foreground"
            )}
          >
            Home
          </Link>
          <Link
            href="/docs"
            className={cn(
              "text-sm transition-colors",
              isDocs
                ? "text-foreground font-medium"
                : "text-muted-foreground hover:text-foreground"
            )}
          >
            Documentation
          </Link>
          <Button size="sm" className="bg-sakura-500 hover:bg-sakura-600 text-white">
            Get Started
          </Button>
        </div>
      </div>
    </nav>
  );
}
