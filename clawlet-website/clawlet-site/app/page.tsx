"use client";

import Link from "next/link";
import { Button } from "@/components/ui/button";

export default function HomePage() {
  return (
    <div className="min-h-screen bg-gradient-to-b from-sakura-50 via-white to-sakura-100">
      {/* Decorative background blobs */}
      <div className="fixed inset-0 overflow-hidden pointer-events-none -z-10">
        <div className="absolute -top-40 -right-40 w-96 h-96 bg-sakura-200 rounded-full mix-blend-multiply filter blur-3xl opacity-40 animate-float"></div>
        <div className="absolute -bottom-40 -left-40 w-96 h-96 bg-sakura-300 rounded-full mix-blend-multiply filter blur-3xl opacity-40 animate-float" style={{ animationDelay: "2s" }}></div>
        <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-96 h-96 bg-sakura-150 rounded-full mix-blend-multiply filter blur-3xl opacity-30 animate-float" style={{ animationDelay: "4s" }}></div>
      </div>

      {/* Navigation */}
      <nav className="fixed top-0 w-full z-50 bg-white/80 backdrop-blur-md border-b border-sakura-200 shadow-glow-sm">
        <div className="max-w-6xl mx-auto px-4 h-16 flex items-center justify-between">
          <Link href="/" className="flex items-center gap-2 group">
            <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-sakura-400 to-sakura-600 flex items-center justify-center text-white font-bold text-lg shadow-glow-sm group-hover:shadow-glow-md transition-shadow">
              C
            </div>
            <div>
              <div className="text-xl font-bold bg-gradient-to-r from-sakura-600 to-sakura-400 bg-clip-text text-transparent">
                Clawlet
              </div>
              <div className="text-[10px] font-mono text-sakura-600 uppercase tracking-wider">AI Agent Framework</div>
            </div>
          </Link>
          <div className="flex items-center gap-3">
            <Link href="/docs" className="hidden md:block px-4 py-2 text-sm font-medium text-sakura-700 hover:text-sakura-500 transition-colors">
              Documentation
            </Link>
            <a
              href="https://github.com/Kxrbx/Clawlet"
              target="_blank"
              rel="noopener noreferrer"
              className="px-4 py-2 text-sm font-medium text-sakura-700 border border-sakura-300 rounded-lg hover:bg-sakura-100 transition-all"
            >
              GitHub
            </a>
            <Button size="sm" className="bg-gradient-to-r from-sakura-500 to-sakura-600 hover:from-sakura-600 hover:to-sakura-500 text-white shadow-glow-sm hover:shadow-glow-md transition-all">
              Get Started
            </Button>
          </div>
        </div>
      </nav>

      {/* Hero Section */}
      <section className="pt-32 pb-20 px-4">
        <div className="max-w-4xl mx-auto text-center">
          {/* Badge */}
          <div className="inline-flex items-center gap-2 px-4 py-2 rounded-full bg-white/60 border border-sakura-300 text-sakura-700 text-sm font-medium mb-8 shadow-glow-sm backdrop-blur-sm animate-float">
            <span className="w-2 h-2 rounded-full bg-sakura-500 animate-pulse"></span>
            Now with Identity System & Realtime Dashboard
          </div>

          {/* Main title */}
          <h1 className="text-5xl md:text-7xl font-bold mb-6 leading-tight">
            <span className="block bg-gradient-to-r from-sakura-400 via-sakura-500 to-sakura-600 bg-clip-text text-transparent">
              Clawlet
            </span>
            <span className="block text-gray-800 md:inline"> AI Agents That</span>
            <span className="block bg-gradient-to-r from-sakura-600 to-sakura-400 bg-clip-text text-transparent md:inline"> Know Who They Are</span>
          </h1>

          {/* Subtitle */}
          <p className="text-xl text-sakura-600 mb-4 font-medium">
            Local-first • Identity-aware • Open Source
          </p>

          <p className="text-lg text-gray-600 mb-12 max-w-2xl mx-auto leading-relaxed">
            Build self-aware AI agents that read their own <code className="px-2 py-1 bg-sakura-100 border border-sakura-200 rounded text-sakura-700 font-mono text-sm">SOUL.md</code>, <code className="px-2 py-1 bg-sakura-100 border border-sakura-200 rounded text-sakura-700 font-mono text-sm">USER.md</code>, and <code className="px-2 py-1 bg-sakura-100 border border-sakura-200 rounded text-sakura-700 font-mono text-sm">MEMORY.md</code>. Run entirely on your machine with Ollama. No cloud lock-in, no usage limits, total privacy.
          </p>

          {/* CTA Buttons */}
          <div className="flex flex-wrap justify-center gap-4 mb-16">
            <Button size="lg" className="bg-gradient-to-r from-sakura-500 to-sakura-600 hover:from-sakura-600 hover:to-sakura-500 text-white shadow-glow-sm hover:shadow-glow-md px-8 py-6 text-lg font-semibold rounded-xl">
              Get Started Free
            </Button>
            <Button size="lg" variant="outline" className="border-sakura-300 text-sakura-700 hover:bg-sakura-100 px-8 py-6 text-lg font-semibold rounded-xl">
              View Documentation
            </Button>
            <Button size="lg" variant="ghost" asChild className="px-8 py-6 text-lg">
              <a href="https://github.com/Kxrbx/Clawlet" target="_blank" rel="noopener noreferrer" className="flex items-center gap-2 text-sakura-600 hover:text-sakura-500">
                <svg className="w-5 h-5" fill="currentColor" viewBox="0 0 24 24"><path d="M12 0c-6.626 0-12 5.373-12 12 0 5.302 3.438 9.8 8.207 11.387.599.111.793-.261.793-.577v-2.234c-3.338.726-4.033-1.416-4.033-1.416-.546-1.387-1.333-1.756-1.333-1.756-1.089-.745.083-.729.083-.729 1.205.084 1.839 1.237 1.839 1.237 1.07 1.834 2.807 1.304 3.492.997.107-.775.418-1.305.762-1.604-2.665-.305-5.467-1.334-5.467-5.931 0-1.311.469-2.381 1.236-3.221-.124-.303-.535-1.524.117-3.176 0 0 1.008-.322 3.301 1.23.957-.266 1.983-.399 3.003-.404 1.02.005 2.047.138 3.006.404 2.291-1.552 3.297-1.23 3.297-1.23.653 1.653.242 2.874.118 3.176.77.84 1.235 1.911 1.235 3.221 0 4.609-2.807 5.624-5.479 5.921.43.372.823 1.102.823 2.222v3.293c0 .319.192.694.801.576 4.765-1.589 8.199-6.086 8.199-11.386 0-6.627-5.373-12-12-12z"/></svg>
                Star on GitHub
              </a>
            </Button>
          </div>

          {/* Stats */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4 max-w-3xl mx-auto">
            {[
              { label: "Lines of Code", value: "~5,200", color: "text-sakura-600" },
              { label: "License", value: "MIT", color: "text-sakura-600" },
              { label: "Local & Private", value: "100%", color: "text-sakura-600" },
              { label: "Free Forever", value: "Yes", color: "text-sakura-600" },
            ].map((stat, i) => (
              <div key={i} className="bg-white/60 backdrop-blur-sm rounded-2xl p-6 border border-sakura-200 shadow-glow-sm hover:shadow-glow-md transition-shadow">
                <div className={`text-3xl font-bold mb-1 ${stat.color}`}>
                  {stat.value}
                </div>
                <div className="text-sm text-sakura-600 font-medium">{stat.label}</div>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Features Section */}
      <section className="py-24 px-4">
        <div className="max-w-6xl mx-auto">
          <div className="text-center mb-16">
            <h2 className="text-4xl font-bold mb-4 text-gray-800">Why Clawlet?</h2>
            <p className="text-lg text-gray-600 max-w-2xl mx-auto">
              Built for developers who want full control over their AI assistant. No cloud lock-in, no recurring costs, just pure local intelligence.
            </p>
          </div>

          <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-8">
            {[
              {
                icon: "🏠",
                title: "Local-First Architecture",
                desc: "Run entirely on your machine with Ollama or LM Studio. No API fees, no data leaving your network. Your conversations stay private."
              },
              {
                icon: "🎭",
                title: "True Identity System",
                desc: "Agents read SOUL.md, USER.md, and MEMORY.md to build personality and memory. Create an assistant that actually knows you."
              },
              {
                icon: "🔧",
                title: "Developer Friendly",
                desc: "~5,200 lines of clean Python. Easy to read, modify, and extend. Add custom tools, change behavior, or integrate with your workflow."
              },
              {
                icon: "⚡",
                title: "Multiple LLM Providers",
                desc: "Switch between OpenRouter, Anthropic, OpenAI, or local models effortlessly. Always have a fallback if one provider goes down."
              },
              {
                icon: "🔒",
                title: "Security Hardened",
                desc: "Blocks 15+ dangerous shell patterns, rate limiting, config validation, and optional confirmation mode. Safety first."
              },
              {
                icon: "📊",
                title: "Built-in Dashboard",
                desc: "React + FastAPI dashboard with real-time logs, health metrics, message history, and a terminal to test commands."
              },
            ].map((feature, idx) => (
              <div key={idx} className="bg-white/70 backdrop-blur-sm rounded-2xl p-8 border border-sakura-200 shadow-glow-sm hover:shadow-glow-md hover:-translate-y-1 transition-all duration-300 animate-fade-in-up" style={{ animationDelay: `${idx * 0.1}s` }}>
                <div className="text-4xl mb-4">{feature.icon}</div>
                <h3 className="font-semibold text-xl mb-3 text-gray-800">
                  {feature.title}
                </h3>
                <p className="text-gray-600 leading-relaxed">
                  {feature.desc}
                </p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Comparison Table */}
      <section className="py-24 px-4 bg-gradient-to-r from-sakura-100 to-sakura-50">
        <div className="max-w-4xl mx-auto">
          <div className="text-center mb-12">
            <h2 className="text-4xl font-bold mb-4 text-gray-800">Compare Frameworks</h2>
            <p className="text-gray-600">See how Clawlet stacks up against other agent frameworks.</p>
          </div>

          <div className="overflow-x-auto bg-white/80 backdrop-blur-sm rounded-2xl border border-sakura-200 shadow-glow-sm">
            <table className="w-full">
              <thead>
                <tr className="border-b border-sakura-200 bg-gradient-to-r from-sakura-100 to-sakura-50">
                  <th className="text-left py-4 px-6 font-semibold text-gray-800">Feature</th>
                  <th className="text-center py-4 px-6 font-semibold text-sakura-600">Clawlet</th>
                  <th className="text-center py-4 px-6 font-semibold text-gray-500">OpenClaw</th>
                  <th className="text-center py-4 px-6 font-semibold text-gray-500">nanobot</th>
                </tr>
              </thead>
              <tbody className="text-sm">
                {[
                  ["Language", "Python", "TypeScript", "Python"],
                  ["Local LLMs", "✅ Ollama, LM Studio", "❌", "❌"],
                  ["Identity System", "✅ SOUL/USER/MEMORY", "✅", "❌"],
                  ["Dashboard", "✅ React + FastAPI", "✅", "❌"],
                  ["Security", "✅ 15+ blocks", "⚠️ Limited", "❌"],
                  ["Onboarding", "✅", "✅", "❌"],
                ].map(([feature, clawlet, openclaw, nanobot], i) => (
                  <tr key={feature} className={`border-b border-sakura-100 hover:bg-sakura-50/50 ${i % 2 === 0 ? "bg-white/50" : "bg-white/30"}`}>
                    <td className="py-4 px-6 text-left font-medium text-gray-800">{feature}</td>
                    <td className="py-4 px-6 text-center font-bold text-sakura-600">{clawlet}</td>
                    <td className="py-4 px-6 text-center text-gray-500">{openclaw}</td>
                    <td className="py-4 px-6 text-center text-gray-500">{nanobot}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </section>

      {/* Quick Start */}
      <section className="py-24 px-4">
        <div className="max-w-4xl mx-auto">
          <div className="text-center mb-12">
            <h2 className="text-4xl font-bold mb-4 text-gray-800">Get Started in Minutes</h2>
            <p className="text-lg text-gray-600">Install, run the wizard, and you're ready to go.</p>
          </div>

          <div className="grid md:grid-cols-3 gap-8">
            {[
              {
                step: "1",
                title: "Install",
                desc: "Clone the repo and install dependencies.",
                code: "git clone https://github.com/Kxrbx/Clawlet.git\ncd Clawlet\npip install -e ."
              },
              {
                step: "2",
                title: "Onboard",
                desc: "Run the interactive setup wizard.",
                code: "clawlet onboard"
              },
              {
                step: "3",
                title: "Run",
                desc: "Start your agent and begin chatting.",
                code: "clawlet agent"
              },
            ].map((step, i) => (
              <div key={i} className="bg-white/80 backdrop-blur-sm rounded-2xl p-8 border border-sakura-200 shadow-glow-sm hover:shadow-glow-md transition-all text-center">
                <div className="w-12 h-12 rounded-full bg-gradient-to-br from-sakura-400 to-sakura-600 flex items-center justify-center font-bold text-xl text-white mx-auto mb-6 shadow-glow-sm">
                  {step.step}
                </div>
                <h3 className="font-semibold text-xl mb-2 text-gray-800">{step.title}</h3>
                <p className="text-gray-600 mb-6">{step.desc}</p>
                <pre className="bg-sakura-50 border border-sakura-200 rounded-lg p-4 text-left text-sm font-mono text-sakura-700 overflow-x-auto">
                  {step.code}
                </pre>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Final CTA */}
      <section className="py-24 px-4 bg-gradient-to-r from-sakura-500 to-sakura-600">
        <div className="max-w-3xl mx-auto text-center text-white">
          <h2 className="text-4xl font-bold mb-6">Open Source & Free</h2>
          <p className="text-xl mb-10 opacity-90 max-w-2xl mx-auto">
            MIT licensed. No usage limits. No cloud dependency. Clone the repo, run it, own your AI.
          </p>
          <div className="flex flex-wrap justify-center gap-4">
            <Button size="lg" className="bg-white text-sakura-600 hover:bg-sakura-50 shadow-glow-sm px-10 py-6 text-lg font-semibold rounded-xl">
              Get Started Now
            </Button>
            <Button size="lg" variant="outline" className="border-white text-white hover:bg-white/10 px-10 py-6 text-lg font-semibold rounded-xl">
              View on GitHub
            </Button>
          </div>
        </div>
      </section>

      {/* Footer */}
      <footer className="bg-white/80 backdrop-blur-sm border-t border-sakura-200 py-16 px-4">
        <div className="max-w-4xl mx-auto text-center">
          <div className="flex items-center justify-center gap-3 mb-6">
            <div className="w-14 h-14 rounded-xl bg-gradient-to-br from-sakura-400 to-sakura-600 flex items-center justify-center text-2xl font-bold text-white shadow-glow-sm">
              C
            </div>
            <div className="text-left">
              <div className="text-2xl font-bold bg-gradient-to-r from-sakura-600 to-sakura-400 bg-clip-text text-transparent">Clawlet</div>
              <div className="text-sm text-sakura-600 font-medium">AI Agent Framework</div>
            </div>
          </div>

          <p className="text-sakura-600 mb-8 font-mono">
            Built with 💕 by the OpenClaw community | MIT License
          </p>

          <div className="flex justify-center gap-8 text-sm text-sakura-500">
            <a href="https://github.com/Kxrbx/Clawlet" target="_blank" rel="noopener noreferrer" className="hover:text-sakura-600 transition-colors">GitHub</a>
            <a href="https://github.com/Kxrbx/Clawlet/discussions" target="_blank" rel="noopener noreferrer" className="hover:text-sakura-600 transition-colors">Discussions</a>
            <a href="https://github.com/Kxrbx/Clawlet/issues" target="_blank" rel="noopener noreferrer" className="hover:text-sakura-600 transition-colors">Issues</a>
          </div>
        </div>
      </footer>
    </div>
  );
}
