import type { Metadata } from "next";
import { Nav } from "@/components/nav";
import Link from "next/link";
import { Rocket, Settings, Code, Key, Shield, Bug } from "lucide-react";

export const metadata: Metadata = {
  title: "Documentation - Clawlet",
  description: "Complete documentation for Clawlet AI agent framework",
};

function DocLink({
  href,
  icon,
  children,
}: {
  href: string;
  icon: React.ReactNode;
  children: React.ReactNode;
}) {
  return (
    <Link
      href={href}
      scroll={true}
      className="flex items-center gap-3 px-4 py-2.5 rounded-lg text-sm font-medium text-sakura-600 dark:text-sakura-400 hover:bg-sakura-100 dark:hover:bg-sakura-900/50 transition-all group"
    >
      {icon}
      <span>{children}</span>
    </Link>
  );
}

export default function DocsLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <div className="min-h-screen">
      <Nav />
      <div className="container mx-auto px-4 pt-24 pb-8">
        <div className="grid grid-cols-1 md:grid-cols-[280px_1fr] gap-8">
          {/* Sidebar */}
          <aside className="md:block hidden">
            <div className="sticky top-24 space-y-8">
              <nav className="space-y-2">
                <DocLink href="#getting-started" icon={<Rocket className="size-4" />}>
                  Getting Started
                </DocLink>
                <DocLink href="#installation" icon={<Settings className="size-4" />}>
                  Installation
                </DocLink>
                <DocLink href="#configuration" icon={<Code className="size-4" />}>
                  Configuration
                </DocLink>
                <DocLink href="#identity" icon={<Key className="size-4" />}>
                  Identity System
                </DocLink>
                <DocLink href="#cli" icon={<Code className="size-4" />}>
                  CLI Commands
                </DocLink>
                <DocLink href="#security" icon={<Shield className="size-4" />}>
                  Security
                </DocLink>
                <DocLink href="#troubleshooting" icon={<Bug className="size-4" />}>
                  Troubleshooting
                </DocLink>
              </nav>

              <div className="p-6 bg-gradient-to-br from-sakura-100 to-sakura-50 dark:from-sakura-900/30 dark:to-sakura-950/40 rounded-xl border border-sakura-200 dark:border-sakura-800">
                <h4 className="font-semibold text-sakura-700 dark:text-sakura-300 mb-2">
                  Quick Links
                </h4>
                <div className="space-y-2 text-sm">
                  <Link
                    href="/"
                    className="block text-sakura-600 hover:text-sakura-700 dark:text-sakura-400 dark:hover:text-sakura-300"
                  >
                    ← Back to Home
                  </Link>
                  <a
                    href="https://github.com/Kxrbx/Clawlet/discussions"
                    target="_blank"
                    rel="noopener noreferrer"
                    className="block text-sakura-600 hover:text-sakura-700 dark:text-sakura-400 dark:hover:text-sakura-300"
                  >
                    GitHub Discussions
                  </a>
                  <a
                    href="https://github.com/Kxrbx/Clawlet/issues"
                    target="_blank"
                    rel="noopener noreferrer"
                    className="block text-sakura-600 hover:text-sakura-700 dark:text-sakura-400 dark:hover:text-sakura-300"
                  >
                    Report an Issue
                  </a>
                </div>
              </div>
            </div>
          </aside>

          {/* Main content */}
          <main className="min-w-0 animate-fade-in-up">{children}</main>
        </div>
      </div>
    </div>
  );
}
