"use client";

import Link from "next/link";
import { Button } from "@/components/ui/button";

export default function HomePage() {
  return (
    <div className="min-h-screen bg-gradient-to-b from-sakura-50 via-white to-sakura-100 relative overflow-hidden">
      {/* Decorative background: floating emoji & blobs */}
      <div className="fixed inset-0 overflow-hidden pointer-events-none -z-10">
        {/* Large gradient blobs with stronger glow */}
        <div className="absolute -top-40 -right-40 w-96 h-96 bg-sakura-200 rounded-full mix-blend-multiply filter blur-3xl opacity-60 glow-lg animate-float"></div>
        <div className="absolute -bottom-40 -left-40 w-96 h-96 bg-sakura-300 rounded-full mix-blend-multiply filter blur-3xl opacity-60 glow-lg animate-float" style={{ animationDelay: "2s" }}></div>
        <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-96 h-96 bg-sakura-150 rounded-full mix-blend-multiply filter blur-3xl opacity-50 glow-lg animate-float" style={{ animationDelay: "4s" }}></div>

        {/* Floating emoji particles */}
        <div className="absolute top-20 left-10 text-4xl opacity-40 animate-float" style={{ animationDelay: "0s" }}>🌸</div>
        <div className="absolute top-1/3 right-10 text-3xl opacity-40 animate-float" style={{ animationDelay: "1s" }}>💖</div>
        <div className="absolute bottom-40 left-20 text-4xl opacity-40 animate-float" style={{ animationDelay: "3s" }}>✨</div>
        <div className="absolute top-1/4 left-1/3 text-2xl opacity-40 animate-float" style={{ animationDelay: "5s" }}>🦾</div>
        <div className="absolute bottom-1/4 right-1/4 text-3xl opacity-40 animate-float" style={{ animationDelay: "2.5s" }}>🤖</div>
        <div className="absolute top-2/3 left-1/2 text-2xl opacity-40 animate-float" style={{ animationDelay: "4.5s" }}>💡</div>
      </div>

      {/* Navigation */}
      <nav className="fixed top-0 w-full z-50 bg-white/80 backdrop-blur-xl border-b border-sakura-200 glow-sm">
        <div className="max-w-6xl mx-auto px-4 h-20 flex items-center justify-between">
          <Link href="/" className="flex items-center gap-2 group">
            <div className="w-12 h-12 rounded-xl bg-gradient-to-br from-sakura-400 to-sakura-600 flex items-center justify-center text-white font-bold text-2xl glow-md group-hover:glow-lg transition-all group-hover:scale-105">
              C
            </div>
            <div>
              <div className="text-xl font-bold bg-gradient-to-r from-sakura-600 to-sakura-400 bg-clip-text text-transparent">
                Clawlet
              </div>
              <div className="text-[10px] font-mono text-sakura-600 uppercase tracking-wider">🤖 AI Agent Framework</div>
            </div>
          </Link>
          <div className="flex items-center gap-3">
            <Link href="/docs" className="hidden md:block px-4 py-2 text-sm font-medium text-sakura-700 hover:text-sakura-500 transition-colors">
              📚 Docs
            </Link>
            <a
              href="https://github.com/Kxrbx/Clawlet"
              target="_blank"
              rel="noopener noreferrer"
              className="px-4 py-2 text-sm font-medium text-sakura-700 border border-sakura-300 rounded-xl hover:bg-sakura-100 transition-all flex items-center gap-2"
            >
              <span>💾</span> GitHub
            </a>
            <Button size="sm" className="bg-gradient-to-r from-sakura-500 to-sakura-600 hover:from-sakura-600 hover:to-sakura-500 text-white glow-sm hover:glow-md transition-all px-5 py-5 rounded-xl">
              🚀 Get Started
            </Button>
          </div>
        </div>
      </nav>

      {/* Hero Section */}
      <section className="pt-32 pb-20 px-4">
        <div className="max-w-4xl mx-auto text-center">
          {/* Badge */}
          <div className="inline-flex items-center gap-2 px-5 py-3 rounded-full bg-white/70 backdrop-blur-md border border-sakura-300 text-sakura-700 text-sm font-semibold mb-10 glow-md animate-float">
            <span className="w-2 h-2 rounded-full bg-sakura-500 animate-pulse"></span>
            ✨ Now with Identity System & Realtime Dashboard
          </div>

          {/* Main title */}
          <h1 className="text-5xl md:text-8xl font-bold mb-8 leading-tight">
            <span className="block bg-gradient-to-r from-sakura-400 via-sakura-500 to-sakura-600 bg-clip-text text-transparent drop-shadow-sm">
              Clawlet
            </span>
            <span className="block text-gray-800 md:inline"> 🤖 AI Agents That</span>
            <span className="block bg-gradient-to-r from-sakura-600 to-sakura-400 bg-clip-text text-transparent md:inline"> Know Who They Are</span>
          </h1>

          {/* Subtitle */}
          <p className="text-xl text-sakura-700 mb-6 font-medium">
            🏠 Local-first • 🎭 Identity-aware • 📖 Open Source
          </p>

          <p className="text-lg text-gray-600 mb-16 max-w-3xl mx-auto leading-relaxed">
            Build self-aware AI agents that read their own <code className="px-3 py-1 bg-sakura-100 border border-sakura-200 rounded-lg text-sakura-700 font-mono text-sm shadow-sm">SOUL.md</code>, <code className="px-3 py-1 bg-sakura-100 border border-sakura-200 rounded-lg text-sakura-700 font-mono text-sm shadow-sm">USER.md</code>, and <code className="px-3 py-1 bg-sakura-100 border border-sakura-200 rounded-lg text-sakura-700 font-mono text-sm shadow-sm">MEMORY.md</code>. Run entirely on your machine with Ollama. No cloud lock-in, no usage limits, total privacy. 🌙
          </p>

          {/* CTA Buttons */}
          <div className="flex flex-wrap justify-center gap-5 mb-20">
            <Button size="lg" className="bg-gradient-to-r from-sakura-500 to-sakura-600 hover:from-sakura-600 hover:to-sakura-500 text-white glow-md hover:glow-lg px-10 py-7 text-xl font-bold rounded-2xl">
              🚀 Get Started Free
            </Button>
            <Button size="lg" variant="outline" className="border-2 border-sakura-300 text-sakura-700 hover:bg-sakura-100 px-10 py-7 text-xl font-bold rounded-2xl glow-sm hover:glow-md">
              📖 View Documentation
            </Button>
            <Button size="lg" variant="ghost" asChild className="px-10 py-7 text-xl rounded-2xl">
              <a href="https://github.com/Kxrbx/Clawlet" target="_blank" rel="noopener noreferrer" className="flex items-center gap-3 text-sakura-600 hover:text-sakura-500 font-bold">
                ⭐ Star on GitHub
              </a>
            </Button>
          </div>

          {/* Stats */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-5 max-w-4xl mx-auto">
            {[
              { label: "Lines of Code", value: "~5,200", color: "text-sakura-600", icon: "💻" },
              { label: "License", value: "MIT", color: "text-sakura-600", icon: "📜" },
              { label: "Local & Private", value: "100%", color: "text-sakura-600", icon: "🔒" },
              { label: "Free Forever", value: "Yes", color: "text-sakura-600", icon: "🎁" },
            ].map((stat, i) => (
              <div key={i} className="bg-white/70 backdrop-blur-lg rounded-2xl p-8 border border-sakura-200 glow-md hover:glow-lg transition-all hover:-translate-y-1 animate-fade-in-up" style={{ animationDelay: `${i * 0.1}s` }}>
                <div className="text-4xl mb-2">{stat.icon}</div>
                <div className={`text-3xl font-bold mb-2 ${stat.color}`}>
                  {stat.value}
                </div>
                <div className="text-sm text-sakura-600 font-semibold">{stat.label}</div>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Features Section */}
      <section className="py-28 px-4 bg-gradient-to-r from-sakura-100/50 to-sakura-50/50">
        <div className="max-w-6xl mx-auto">
          <div className="text-center mb-20">
            <h2 className="text-4xl md:text-5xl font-bold mb-4 text-gray-800">✨ Why Clawlet?</h2>
            <p className="text-lg text-gray-600 max-w-2xl mx-auto">
              Built for developers who want full control over their AI assistant. No cloud lock-in, no recurring costs, just pure local intelligence. 🧠
            </p>
          </div>

          <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-10">
            {[
              {
                icon: "🏠",
                title: "Local-First Architecture",
                desc: "Run entirely on your machine with Ollama or LM Studio. No API fees, no data leaving your network. Your conversations stay private and secure."
              },
              {
                icon: "🎭",
                title: "True Identity System",
                desc: "Agents read SOUL.md, USER.md, and MEMORY.md to build personality and memory. Create an assistant that actually knows you and remembers."
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
              <div key={idx} className="bg-white/80 backdrop-blur-lg rounded-2xl p-8 border border-sakura-200 glow-md hover:glow-lg hover:-translate-y-2 transition-all duration-300 animate-fade-in-up group relative" style={{ animationDelay: `${idx * 0.1}s` }}>
                {/* Decorative corner glow */}
                <div className="absolute -top-2 -right-2 w-8 h-8 bg-gradient-to-br from-sakura-300 to-sakura-500 rounded-full opacity-50 blur-sm"></div>
                <div className="absolute -bottom-2 -left-2 w-8 h-8 bg-gradient-to-br from-sakura-400 to-sakura-600 rounded-full opacity-50 blur-sm"></div>

                <div className="text-5xl mb-6 group-hover:scale-110 transition-transform">{feature.icon}</div>
                <h3 className="font-bold text-xl mb-4 text-gray-800">
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
      <section className="py-28 px-4 bg-gradient-to-br from-sakura-100 to-sakura-50">
        <div className="max-w-4xl mx-auto">
          <div className="text-center mb-12">
            <h2 className="text-4xl font-bold mb-4 text-gray-800">🔍 Compare Frameworks</h2>
            <p className="text-gray-600">See how Clawlet stacks up against other agent frameworks.</p>
          </div>

          <div className="overflow-x-auto bg-white/80 backdrop-blur-lg rounded-2xl border border-sakura-200 glow-md">
            <table className="w-full">
              <thead>
                <tr className="border-b border-sakura-200 bg-gradient-to-r from-sakura-50 to-sakura-100">
                  <th className="text-left py-5 px-6 font-bold text-gray-800">Feature</th>
                  <th className="text-center py-5 px-6 font-bold text-sakura-600">Clawlet</th>
                  <th className="text-center py-5 px-6 font-semibold text-gray-500">OpenClaw</th>
                  <th className="text-center py-5 px-6 font-semibold text-gray-500">nanobot</th>
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
                    <td className="py-4 px-6 text-left font-semibold text-gray-800">{feature}</td>
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
      <section className="py-28 px-4">
        <div className="max-w-4xl mx-auto">
          <div className="text-center mb-12">
            <h2 className="text-4xl font-bold mb-4 text-gray-800">🚀 Get Started in Minutes</h2>
            <p className="text-lg text-gray-600">Install, run the wizard, and you're ready to go.</p>
          </div>

          <div className="grid md:grid-cols-3 gap-10">
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
              <div key={i} className="bg-white/80 backdrop-blur-lg rounded-2xl p-8 border border-sakura-200 glow-md hover:glow-lg transition-all text-center hover:-translate-y-2">
                <div className="w-16 h-16 rounded-full bg-gradient-to-br from-sakura-400 to-sakura-600 flex items-center justify-center font-bold text-2xl text-white mx-auto mb-8 glow-md">
                  {step.step}
                </div>
                <h3 className="font-bold text-xl mb-3 text-gray-800">{step.title}</h3>
                <p className="text-gray-600 mb-6">{step.desc}</p>
                <pre className="bg-sakura-50 border border-sakura-200 rounded-xl p-5 text-left text-sm font-mono text-sakura-700 overflow-x-auto shadow-inner">
                  {step.code}
                </pre>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Final CTA */}
      <section className="py-32 px-4 bg-gradient-to-r from-sakura-500 to-sakura-600 relative overflow-hidden">
        {/* Decorative glow inside CTA */}
        <div className="absolute inset-0 bg-[url('data:image/svg+xml;base64,PHN2Zy4uLgo=')] opacity-10"></div>

        <div className="max-w-3xl mx-auto text-center text-white relative z-10">
          <h2 className="text-4xl md:text-5xl font-bold mb-8 drop-shadow-lg">
            Open Source & Free 🎉
          </h2>
          <p className="text-xl mb-12 opacity-95 max-w-2xl mx-auto">
            MIT licensed. No usage limits. No cloud dependency. Clone the repo, run it, own your AI. 🌟
          </p>
          <div className="flex flex-wrap justify-center gap-6">
            <Button size="lg" className="bg-white text-sakura-600 hover:bg-sakura-50 glow-lg px-10 py-7 text-xl font-bold rounded-2xl">
              🚀 Get Started Now
            </Button>
            <Button size="lg" variant="outline" className="border-2 border-white text-white hover:bg-white/10 px-10 py-7 text-xl font-bold rounded-2xl glow-md">
              💾 View on GitHub
            </Button>
          </div>
        </div>
      </section>

      {/* Footer */}
      <footer className="bg-white/80 backdrop-blur-xl border-t border-sakura-200 py-20 px-4">
        <div className="max-w-4xl mx-auto text-center">
          <div className="flex items-center justify-center gap-4 mb-8">
            <div className="w-16 h-16 rounded-2xl bg-gradient-to-br from-sakura-400 to-sakura-600 flex items-center justify-center text-3xl font-bold text-white glow-md">
              C
            </div>
            <div className="text-left">
              <div className="text-2xl font-bold bg-gradient-to-r from-sakura-600 to-sakura-400 bg-clip-text text-transparent">Clawlet</div>
              <div className="text-sm text-sakura-600 font-semibold">🤖 AI Agent Framework</div>
            </div>
          </div>

          <p className="text-sakura-600 mb-10 font-mono text-sm">
            Built with 💕 by the OpenClaw community | MIT License
          </p>

          <div className="flex justify-center gap-10 text-base text-sakura-500">
            <a href="https://github.com/Kxrbx/Clawlet" target="_blank" rel="noopener noreferrer" className="hover:text-sakura-600 transition-colors font-medium">📚 GitHub</a>
            <a href="https://github.com/Kxrbx/Clawlet/discussions" target="_blank" rel="noopener noreferrer" className="hover:text-sakura-600 transition-colors font-medium">💬 Discussions</a>
            <a href="https://github.com/Kxrbx/Clawlet/issues" target="_blank" rel="noopener noreferrer" className="hover:text-sakura-600 transition-colors font-medium">🐛 Issues</a>
          </div>

          {/* Big goodbye emoji */}
          <div className="mt-12 text-5xl opacity-60">🌸</div>
        </div>
      </footer>
    </div>
  );
}
