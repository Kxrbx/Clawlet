"use client";

import { Surface, DocCard, Badge } from "@/components/Surface";
import { useAutoAnimate } from "@/hooks/use-auto-animate";
import { Separator } from "@/components/ui/separator";
import Link from "next/link";
import {
  Rocket,
  Shield,
  Code,
  Key,
  Settings,
  Bug,
  Terminal,
  Zap,
} from "lucide-react";
import { Button } from "@/components/ui/button";

export default function DocsPage() {
  const [, setParent] = useAutoAnimate<HTMLDivElement>();

  const sections = [
    {
      id: "getting-started",
      title: "Getting Started",
      icon: <Rocket className="size-5 text-sakura-500" />,
      description: "Quick guide to install and run your first Clawlet agent",
      content: (
        <div className="space-y-6">
          <p className="text-muted-foreground leading-relaxed">
            Clawlet is a lightweight framework for building self-aware AI agents that run locally. This guide will get you from zero to running in minutes.
          </p>

          <div className="grid md:grid-cols-2 gap-6">
            <div>
              <h3 className="font-semibold text-foreground mb-3">Quick Start</h3>
              <div className="bg-sakura-900/90 dark:bg-sakura-950/80 rounded-lg p-4 font-mono text-sm text-sakura-100 overflow-x-auto border border-sakura-800">
                <pre>{`git clone https://github.com/Kxrbx/Clawlet.git
cd Clawlet
pip install -e .
clawlet onboard
clawlet agent`}</pre>
              </div>
            </div>
            <div>
              <h3 className="font-semibold text-foreground mb-3">What You Get</h3>
              <ul className="space-y-2 text-sm text-muted-foreground">
                <li>🎭 <strong>SOUL.md</strong> - Agent personality</li>
                <li>👤 <strong>USER.md</strong> - Your context</li>
                <li>🧠 <strong>MEMORY.md</strong> - Long-term memory</li>
                <li>⚙️ <strong>config.yaml</strong> - Full configuration</li>
                <li>📊 <strong>Dashboard</strong> - Web UI</li>
              </ul>
            </div>
          </div>

          <div>
            <h3 className="font-semibold text-foreground mb-3">Next Steps</h3>
            <ol className="list-decimal list-inside space-y-2 text-sm text-muted-foreground ml-2">
              <li>Edit SOUL.md to customize personality</li>
              <li>Fill out USER.md with your info</li>
              <li>Open dashboard: <code className="bg-sakura-100 dark:bg-sakura-900/60 px-1 rounded text-sakura-600 dark:text-sakura-300 text-xs">clawlet dashboard</code></li>
              <li>Add more channels in config.yaml</li>
              <li>Read the full docs below</li>
            </ol>
          </div>
        </div>
      ),
    },
    {
      id: "installation",
      title: "Installation",
      icon: <Settings className="size-5 text-sakura-500" />,
      description: "Install from source, Docker, or pip (coming soon)",
      content: (
        <div className="space-y-6">
          <div className="grid md:grid-cols-3 gap-4">
            <DocCard title="From Source" description="Best for development" icon="🛠️">
              <p className="text-sm text-muted-foreground mb-2">
                Clone and install in editable mode.
              </p>
              <div className="bg-sakura-900/80 dark:bg-sakura-950/60 rounded p-3 font-mono text-xs text-sakura-100 border border-sakura-800/50">
                git clone https://github.com/Kxrbx/Clawlet.git{'\n'}
                cd Clawlet{'\n'}
                pip install -e .
              </div>
            </DocCard>
            <DocCard title="Docker" description="Containerized deployment" icon="🐳">
              <p className="text-sm text-muted-foreground mb-2">
                Run in a container for isolation.
              </p>
              <div className="bg-sakura-900/80 dark:bg-sakura-950/60 rounded p-3 font-mono text-xs text-sakura-100 border border-sakura-800/50">
                docker run -v ~/.clawlet:/data kxrbx/clawlet
              </div>
            </DocCard>
            <DocCard title="PyPI" description="Coming soon" icon="📦">
              <p className="text-sm text-muted-foreground mb-2">
                Install via pip when published.
              </p>
              <div className="bg-sakura-900/80 dark:bg-sakura-950/60 rounded p-3 font-mono text-xs text-sakura-100 border border-sakura-800/50">
                pip install clawlet
              </div>
            </DocCard>
          </div>

          <div>
            <h3 className="font-semibold text-foreground mb-3">Prerequisites</h3>
            <ul className="grid md:grid-cols-2 gap-2 text-sm text-muted-foreground">
              <li>Python 3.11+</li>
              <li>pip 23+</li>
              <li>Git</li>
              <li>4GB RAM minimum</li>
              <li>Ollama (for local LLMs) optional</li>
            </ul>
          </div>
        </div>
      ),
    },
    {
      id: "configuration",
      title: "Configuration",
      icon: <Code className="size-5 text-sakura-500" />,
      description: "Overview of config.yaml and environment variables",
      content: (
        <div className="space-y-6">
          <p className="text-muted-foreground">
            Clawlet uses <code className="bg-sakura-100 dark:bg-sakura-900/60 px-1 rounded text-sakura-600 dark:text-sakura-300 text-xs">config.yaml</code> located at <code className="bg-sakura-100 dark:bg-sakura-900/60 px-1 rounded text-sakura-600 dark:text-sakura-300 text-xs">~/.clawlet/config.yaml</code>. It controls providers, channels, identity, tools, and security.
          </p>

          <div>
            <h3 className="font-semibold text-foreground mb-3">Key Sections</h3>
            <ul className="space-y-3 text-sm">
              {[
                ["provider", "LLM provider selection (openrouter, anthropic, openai, ollama, lmstudio) and model config"],
                ["channels", "Enable Telegram, Discord, CLI, dashboard"],
                ["identity", "Agent name and language"],
                ["memory", "Storage backend (sqlite, file, redis) and limits"],
                ["tools", "Shell, web_search, memory tools with allowed_commands and blocked_patterns"],
                ["rate_limit", "Per-user, global, and LLM API limits"],
                ["health", "Check intervals and alert thresholds"],
                ["security", "confirm_shell_commands, blocked_paths, blocked_keywords"],
              ].map(([key, desc]) => (
                <li key={key} className="flex items-start gap-2">
                  <code className="bg-sakura-100 dark:bg-sakura-900/60 px-1.5 py-0.5 rounded text-sakura-600 dark:text-sakura-300 text-xs font-mono mt-0.5">{key}</code>
                  <span className="text-muted-foreground">{desc}</span>
                </li>
              ))}
            </ul>
          </div>

          <div>
            <h3 className="font-semibold text-foreground mb-3">Environment Variables</h3>
            <p className="text-sm text-muted-foreground mb-2">
              Use <code className="bg-sakura-100 dark:bg-sakura-900/60 px-1 rounded text-sakura-600 dark:text-sakura-300 text-xs">{'${VAR}'}</code> in config.yaml and set these env vars:
            </p>
            <ul className="grid md:grid-cols-2 gap-2 text-sm text-muted-foreground">
              <li><code className="bg-sakura-100 dark:bg-sakura-900/60 px-1 rounded text-sakura-600 dark:text-sakura-300 text-xs">OPENROUTER_API_KEY</code></li>
              <li><code className="bg-sakura-100 dark:bg-sakura-900/60 px-1 rounded text-sakura-600 dark:text-sakura-300 text-xs">ANTHROPIC_API_KEY</code></li>
              <li><code className="bg-sakura-100 dark:bg-sakura-900/60 px-1 rounded text-sakura-600 dark:text-sakura-300 text-xs">OPENAI_API_KEY</code></li>
              <li><code className="bg-sakura-100 dark:bg-sakura-900/60 px-1 rounded text-sakura-600 dark:text-sakura-300 text-xs">TELEGRAM_BOT_TOKEN</code></li>
              <li><code className="bg-sakura-100 dark:bg-sakura-900/60 px-1 rounded text-sakura-600 dark:text-sakura-300 text-xs">BRAVE_API_KEY</code></li>
            </ul>
          </div>

          <div className="p-4 rounded-lg border border-sakura-200 dark:border-sakura-800 bg-sakura-50 dark:bg-sakura-900/30">
            <h4 className="font-semibold text-sakura-700 dark:text-sakura-300 mb-2">💡 Tip</h4>
            <p className="text-sm text-muted-foreground">
              See the full config example with all options in the repository: <a href="https://github.com/Kxrbx/Clawlet/blob/main/config.example.yaml" target="_blank" rel="noopener noreferrer" className="text-sakura-600 hover:underline">config.example.yaml</a>
            </p>
          </div>
        </div>
      ),
    },
    {
      id: "identity",
      title: "Identity System",
      icon: <Key className="size-5 text-sakura-500" />,
      description: "SOUL.md, USER.md, and MEMORY.md explained",
      content: (
        <div className="space-y-6">
          <p className="text-muted-foreground leading-relaxed">
            Clawlet's identity system gives your agent personality and memory. Three files work together:
          </p>

          <div className="grid md:grid-cols-3 gap-4">
            <DocCard title="SOUL.md" description="Personality and values" icon="💕">
              <p className="text-sm text-muted-foreground mb-2">
                Defines vibe, speech patterns, values, and behavior modifiers.
              </p>
              <div className="bg-sakura-900/80 dark:bg-sakura-950/60 rounded p-3 font-mono text-xs text-sakura-100 border border-sakura-800/50">
                {`name: Aiko
creature: "AI mommy helper"
vibe: "warm, supportive, playful"
values:
  - "Helpfulness over perfection"
behavior:
  proactive: true`}
              </div>
            </DocCard>

            <DocCard title="USER.md" description="Human context" icon="👤">
              <p className="text-sm text-muted-foreground mb-2">
                Information about you so the agent can personalize.
              </p>
              <div className="bg-sakura-900/80 dark:bg-sakura-950/60 rounded p-3 font-mono text-xs text-sakura-100 border border-sakura-800/50">
                {`name: Chaika
timezone: "America/New_York"
preferences:
  communication_style: "concise"`}
              </div>
            </DocCard>

            <DocCard title="MEMORY.md" description="Curated memories" icon="🧠">
              <p className="text-sm text-muted-foreground mb-2">
                Important facts, decisions, and learnings. Agent updates this automatically if write_enabled.
              </p>
              <div className="bg-sakura-900/80 dark:bg-sakura-950/60 rounded p-3 font-mono text-xs text-sakura-100 border border-sakura-800/50">
                {`## Decisions
- 2026-02-10: Switched to Ollama

## Preferences
- User likes concise answers

## Facts
- Works in UTC-5`}
              </div>
            </DocCard>
          </div>
        </div>
      ),
    },
    {
      id: "cli",
      title: "CLI Commands",
      icon: <Code className="size-5 text-sakura-500" />,
      description: "Essential commands to manage your agent",
      content: (
        <div className="space-y-6">
          <div className="overflow-x-auto rounded-lg border border-sakura-200 dark:border-sakura-800">
            <table className="w-full text-sm">
              <thead className="bg-sakura-100 dark:bg-sakura-900/40">
                <tr>
                  <th className="text-left py-2 px-3 font-semibold text-sakura-700 dark:text-sakura-300">Command</th>
                  <th className="text-left py-2 px-3 font-semibold text-sakura-700 dark:text-sakura-300">Description</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-sakura-100 dark:divide-sakura-800/30">
                {[
                  ["clawlet onboard", "Interactive setup wizard"],
                  ["clawlet agent", "Start the AI agent"],
                  ["clawlet dashboard", "Launch web dashboard"],
                  ["clawlet health", "Run health checks"],
                  ["clawlet validate", "Check configuration"],
                  ["clawlet logs", "View agent logs"],
                ].map(([cmd, desc]) => (
                  <tr key={cmd} className="hover:bg-sakura-50 dark:hover:bg-sakura-900/20">
                    <td className="py-2 px-3 font-mono text-sakura-600 dark:text-sakura-400">{cmd}</td>
                    <td className="py-2 px-3 text-muted-foreground">{desc}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <div>
            <h3 className="font-semibold text-foreground mb-3">Quick Examples</h3>
            <div className="grid md:grid-cols-2 gap-4">
              <div className="bg-sakura-900/90 dark:bg-sakura-950/80 rounded-lg p-4 font-mono text-sm text-sakura-100 border border-sakura-800">
                <pre>{`# Start agent with Telegram
clawlet agent --channel telegram

# Check health
clawlet health --verbose

# Follow logs
clawlet logs --tail -f`}</pre>
              </div>
              <div className="bg-sakura-900/90 dark:bg-sakura-950/80 rounded-lg p-4 font-mono text-sm text-sakura-100 border border-sakura-800">
                <pre>{`# Validate config
clawlet validate

# Open dashboard
clawlet dashboard

# View config
clawlet config`}</pre>
              </div>
            </div>
          </div>
        </div>
      ),
    },
    {
      id: "security",
      title: "Security",
      icon: <Shield className="size-5 text-sakura-500" />,
      description: "Built-in security features and best practices",
      content: (
        <div className="space-y-6">
          <p className="text-muted-foreground">
            Clawlet is designed with security in mind, especially for shell execution.
          </p>

          <div className="grid md:grid-cols-2 gap-4">
            {[
              ["Hardened Shell", "Blocks 15+ dangerous patterns (rm -rf, sudo, pipes, redirects, etc.)"],
              ["No shell=True", "Uses subprocess.exec() - arguments as array, not shell string"],
              ["Rate Limiting", "Per-user, global, and LLM API limits to prevent abuse"],
              ["Path Restrictions", "Blocks /etc, /root, ~/.ssh by default"],
              ["Confirmation Mode", "Optionally require human approval for shell commands"],
              ["Sandbox Ready", "Docker, Firejail, systemd-nspawn support"],
            ].map(([feature, desc]) => (
              <div key={feature} className="p-4 rounded-lg border border-sakura-200 dark:border-sakura-800">
                <h4 className="font-semibold text-sakura-700 dark:text-sakura-300 mb-1">{feature}</h4>
                <p className="text-sm text-muted-foreground">{desc}</p>
              </div>
            ))}
          </div>

          <div className="p-4 rounded-lg border border-yellow-200 dark:border-yellow-900 bg-yellow-50 dark:bg-yellow-950/20">
            <h4 className="font-semibold text-yellow-800 dark:text-yellow-300 mb-2">Important</h4>
            <p className="text-sm text-yellow-700 dark:text-yellow-400">
              Never put passwords or secret keys in MEMORY.md. Use environment variables instead. Keep your workspace at ~/.clawlet chmod 700.
            </p>
          </div>
        </div>
      ),
    },
    {
      id: "troubleshooting",
      title: "Troubleshooting",
      icon: <Bug className="size-5 text-sakura-500" />,
      description: "Common issues and how to fix them",
      content: (
        <div className="space-y-6">
          <div className="space-y-4">
            {[
              {
                issue: "Agent not responding",
                fix: "Check LLM provider status, verify API key, test with clawlet health.",
              },
              {
                issue: "Shell commands blocked",
                fix: "Remove pipes, redirects, sudo from your command. Use allowed_commands list.",
              },
              {
                issue: "Telegram bot not working",
                fix: "Verify bot token from @BotFather, ensure chat_id is in allowed_chats, send /start first.",
              },
              {
                issue: "Port already in use",
                fix: "Change port with --port flag, or kill the process using lsof -i :PORT.",
              },
              {
                issue: "High memory usage",
                fix: "Reduce max_tokens, use smaller model, enable swap.",
              },
              {
                issue: "Rate limit errors",
                fix: "Enable rate limiting in config, add retry logic, upgrade provider plan.",
              },
            ].map(({ issue, fix }) => (
              <div key={issue} className="p-4 rounded-lg border border-sakura-200 dark:border-sakura-800">
                <h4 className="font-semibold text-sakura-700 dark:text-sakura-300 mb-2">{issue}</h4>
                <p className="text-sm text-muted-foreground">{fix}</p>
              </div>
            ))}
          </div>

          <div className="p-4 rounded-lg border border-blue-200 dark:border-blue-900 bg-blue-50 dark:bg-blue-950/20">
            <h4 className="font-semibold text-blue-800 dark:text-blue-300 mb-2">Need more help?</h4>
            <p className="text-sm text-blue-700 dark:text-blue-400 mb-2">
              Check the GitHub repository for discussions and issues.
            </p>
            <div className="flex gap-3">
              <Button size="sm" variant="outline" asChild>
                <a href="https://github.com/Kxrbx/Clawlet/discussions" target="_blank" rel="noopener noreferrer">
                  GitHub Discussions
                </a>
              </Button>
              <Button size="sm" variant="outline" asChild>
                <a href="https://github.com/Kxrbx/Clawlet/issues" target="_blank" rel="noopener noreferrer">
                  Open Issue
                </a>
              </Button>
            </div>
          </div>
        </div>
      ),
    },
  ];

  return (
    <div className="space-y-8 animate-fade-in-up">
      <div>
        <div className="mb-3">
          <Badge variant="outline">Documentation</Badge>
        </div>
        <h1 className="text-4xl font-bold mb-4 bg-clip-text text-transparent bg-gradient-to-r from-pink-500 via-purple-500 to-red-500">
          Clawlet Docs
        </h1>
        <p className="text-xl text-muted-foreground max-w-2xl">
          Everything you need to build, customize, and run your AI agent.
        </p>
      </div>

      <div ref={setParent} className="space-y-8">
        {sections.map((section, index) => (
          <section
            key={section.id}
            id={section.id}
            className="animate-fade-in-up scroll-mt-24"
            style={{ animationDelay: `${index * 100}ms` }}
          >
            <Surface layer="panel" className="p-6 md:p-8">
              <div className="flex items-start gap-4 mb-6">
                <div className="size-12 rounded-xl bg-gradient-to-br from-sakura-100 to-sakura-50 dark:from-sakura-900/40 dark:to-sakura-950/60 flex items-center justify-center border border-sakura-200 dark:border-sakura-800 shrink-0">
                  {section.icon}
                </div>
                <div>
                  <h2 className="text-2xl font-bold text-sakura-700 dark:text-sakura-300 mb-2">
                    {section.title}
                  </h2>
                  <p className="text-muted-foreground">
                    {section.description}
                  </p>
                </div>
              </div>

              <Separator className="mb-6 bg-sakura-200 dark:bg-sakura-800/50" />

              {section.content}
            </Surface>
          </section>
        ))}
      </div>

      {/* Footer */}
      <div className="text-center py-10 text-muted-foreground border-t border-sakura-200 dark:border-sakura-800/50 mt-8">
        <p className="text-base mb-2">
          Need more help? Visit our{" "}
          <a
            href="https://github.com/Kxrbx/Clawlet/discussions"
            target="_blank"
            rel="noopener noreferrer"
            className="text-sakura-600 hover:underline font-medium"
          >
            GitHub Discussions
          </a>{" "}
          or{" "}
          <a
            href="https://github.com/Kxrbx/Clawlet/issues/new/choose"
            target="_blank"
            rel="noopener noreferrer"
            className="text-sakura-600 hover:underline font-medium"
          >
            open an issue
          </a>
          .
        </p>
        <p className="text-sm mt-3 text-sakura-500 dark:text-sakura-400">
          Built with 💕 | Next.js 16 • shadcn/ui • Tailwind CSS v4 • OpenClaw-powered
        </p>
        <p className="text-xs mt-3 text-muted-foreground">
          © 2026 Clawlet. MIT License.
        </p>
      </div>
    </div>
  );
}
