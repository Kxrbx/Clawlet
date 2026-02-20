"use client";

import Link from "next/link";
import { Button } from "@/components/ui/button";

export default function HomePage() {
  return (
    <div className="min-h-screen bg-claw-dark text-white overflow-hidden">
      {/* Noise overlay */}
      <div className="fixed inset-0 pointer-events-none opacity-30 z-50" style={{
        backgroundImage: `url("data:image/svg+xml,%3Csvg viewBox='0 0 256 256' xmlns='http://www.w3.org/2000/svg'%3E%3Cfilter id='noise'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.9' numOctaves='4' stitchTiles='stitch'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23noise)'/%3E%3C/svg%3E")`
      }}></div>

      {/* Navigation */}
      <nav className="fixed top-0 w-full z-40 border-b-4 border-black bg-white">
        <div className="max-w-7xl mx-auto px-4 h-20 flex items-center justify-between">
          <Link href="/" className="flex items-center gap-3 group">
            <div className="w-12 h-12 border-4 border-black bg-claw-lime flex items-center justify-center text-2xl font-mono font-bold text-black shadow-hard">
              C
            </div>
            <div>
              <div className="text-2xl font-bold font-mono tracking-tight text-black">
                CLAWLET
              </div>
              <div className="text-xs font-mono text-gray-600">AI AGENT FRAMEWORK</div>
            </div>
          </Link>
          <div className="flex items-center gap-4">
            <Link href="/docs" className="hidden md:block px-4 py-2 font-mono text-sm font-bold border-2 border-black hover:bg-claw-lime transition-all">
              DOCS
            </Link>
            <a
              href="https://github.com/Kxrbx/Clawlet"
              target="_blank"
              rel="noopener noreferrer"
              className="px-4 py-2 font-mono text-sm font-bold border-2 border-black bg-black text-white hover:bg-claw-lime hover:text-black transition-all"
            >
              GITHUB
            </a>
            <Button size="default" className="btn-hard bg-claw-magenta text-white border-black">
              GET STARTED
            </Button>
          </div>
        </div>
      </nav>

      {/* Hero Section */}
      <section className="pt-32 pb-20 px-4 relative">
        {/* Background accent */}
        <div className="absolute top-0 left-0 w-full h-2 bg-claw-lime"></div>
        <div className="absolute top-40 right-0 w-96 h-96 bg-claw-magenta opacity-20 blur-3xl"></div>
        <div className="absolute bottom-20 left-0 w-96 h-96 bg-claw-cyan opacity-20 blur-3xl"></div>

        <div className="max-w-6xl mx-auto text-center relative z-10">
          {/* Badge */}
          <div className="inline-block mb-6 px-4 py-2 border-4 border-black bg-claw-cyan text-black font-mono text-sm font-bold animate-pulse-hard">
            🚀 Now with Identity System & Dashboard
          </div>

          {/* Main title */}
          <h1 className="text-7xl md:text-9xl font-mono font-bold mb-6 leading-tight">
            <span className="text-claw-lime drop-shadow-[4px_4px_0_#000] block">CLAWLET</span>
            <span className="text-claw-magenta drop-shadow-[4px_4px_0_#000] block md:inline"> AI</span>
            <span className="text-claw-cyan drop-shadow-[4px_4px_0_#000] block md:inline"> THAT</span>
            <span className="text-claw-yellow drop-shadow-[4px_4px_0_#000] block md:inline"> KNOWS</span>
            <span className="text-white drop-shadow-[4px_4px_0_#000] block md:inline"> WHO</span>
            <span className="text-claw-orange drop-shadow-[4px_4px_0_#000] block md:inline"> IT IS</span>
          </h1>

          {/* Subtitle */}
          <p className="text-xl md:text-2xl font-mono mb-4 text-gray-300">
            <span className="text-claw-lime">Local-first</span> • <span className="text-claw-magenta">Identity-aware</span> • <span className="text-claw-cyan">Open source</span>
          </p>

          <p className="text-lg text-gray-400 mb-12 max-w-3xl mx-auto">
            Build self-aware AI agents that read their own <code className="px-2 py-1 bg-claw-gray text-black font-mono border border-black">SOUL.md</code>, <code className="px-2 py-1 bg-claw-gray text-black font-mono border border-black">USER.md</code>, and <code className="px-2 py-1 bg-claw-gray text-black font-mono border border-black">MEMORY.md</code>. Run locally with Ollama, no cloud lock-in, no usage limits.
          </p>

          {/* CTA Buttons */}
          <div className="flex flex-wrap justify-center gap-4 mb-16">
            <Button size="lg" className="btn-hard bg-claw-lime text-black text-lg px-8 py-6">
              GET STARTED →
            </Button>
            <Button size="lg" className="btn-hard bg-claw-magenta text-white text-lg px-8 py-6">
              VIEW DOCS →
            </Button>
            <Button size="lg" className="btn-hard bg-claw-cyan text-black text-lg px-8 py-6">
              STAR ON GITHUB ⭐
            </Button>
          </div>

          {/* Stats */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4 max-w-4xl mx-auto">
            {[
              { label: "Lines of Code", value: "~5,200", color: "text-claw-lime" },
              { label: "License", value: "MIT", color: "text-claw-magenta" },
              { label: "Local & Private", value: "100%", color: "text-claw-cyan" },
              { label: "Free Forever", value: "YES", color: "text-claw-yellow" },
            ].map((stat, i) => (
              <div key={i} className="border-4 border-black bg-claw-gray p-4 shadow-hard">
                <div className={`text-3xl font-mono font-bold mb-1 ${stat.color}`}>
                  {stat.value}
                </div>
                <div className="text-xs font-mono text-gray-600">{stat.label}</div>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Features Marquee */}
      <div className="bg-claw-magenta border-y-4 border-black py-4 overflow-hidden">
        <div className="marquee-container">
          <div className="marquee-content font-mono text-2xl font-bold text-black">
            🚀 LOCAL-FIRST • IDENTITY SYSTEM • REALTIME DASHBOARD • SECURITY HARDENING • INTERACTIVE ONBOARDING • MULTI-LLM SUPPORT • 100% OPEN SOURCE • BUILT WITH ❤️ • LOCAL-FIRST • IDENTITY SYSTEM • REALTIME DASHBOARD • SECURITY HARDENING • INTERACTIVE ONBOARDING • MULTI-LLM SUPPORT • 100% OPEN SOURCE • BUILT WITH ❤️ •
          </div>
        </div>
      </div>

      {/* Features Grid */}
      <section className="py-24 px-4 bg-claw-gray">
        <div className="max-w-7xl mx-auto">
          <div className="text-center mb-16">
            <h2 className="text-5xl font-mono font-bold mb-4 text-black">
              WHY <span className="text-claw-orange">CLAWLET</span>?
            </h2>
            <p className="text-lg text-gray-700 max-w-2xl mx-auto font-mono">
              Built for developers who want full control over their AI assistant. No cloud lock-in, no recurring costs, just pure local intelligence.
            </p>
          </div>

          <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-8">
            {[
              {
                icon: "🏠",
                title: "LOCAL-FIRST ARCHITECTURE",
                desc: "Run entirely on your machine with Ollama or LM Studio. No API fees, no data leaving your network. Your conversations stay private.",
                color: "text-claw-lime",
                border: "border-claw-lime"
              },
              {
                icon: "🎭",
                title: "TRUE IDENTITY SYSTEM",
                desc: "Agents read SOUL.md, USER.md, and MEMORY.md to build personality and memory. Create an assistant that actually knows you.",
                color: "text-claw-magenta",
                border: "border-claw-magenta"
              },
              {
                icon: "🔧",
                title: "DEVELOPER FRIENDLY",
                desc: "~5,200 lines of clean Python. Easy to read, modify, and extend. Add custom tools, change behavior, or integrate with your workflow.",
                color: "text-claw-cyan",
                border: "border-claw-cyan"
              },
              {
                icon: "⚡",
                title: "MULTIPLE PROVIDERS",
                desc: "Switch between OpenRouter, Anthropic, OpenAI, or local models effortlessly. Always have a fallback if one provider goes down.",
                color: "text-claw-yellow",
                border: "border-claw-yellow"
              },
              {
                icon: "🔒",
                title: "SECURITY HARDENING",
                desc: "Blocks 15+ dangerous shell patterns, rate limiting, config validation, and optional confirmation mode. Safety first.",
                color: "text-claw-red",
                border: "border-claw-red"
              },
              {
                icon: "📊",
                title: "BUILT-IN DASHBOARD",
                desc: "React + FastAPI dashboard with real-time logs, health metrics, message history, and a terminal to test commands.",
                color: "text-claw-orange",
                border: "border-claw-orange"
              },
            ].map((feature, idx) => (
              <div key={idx} className="card-hard p-6 bg-white relative group">
                {/* Corner accents */}
                <div className="absolute -top-3 -left-3 w-6 h-6 border-4 border-black bg-claw-lime"></div>
                <div className="absolute -bottom-3 -right-3 w-6 h-6 border-4 border-black bg-claw-magenta"></div>

                <div className="text-6xl mb-6">{feature.icon}</div>
                <h3 className={`font-mono font-bold text-xl mb-3 ${feature.color}`}>
                  {feature.title}
                </h3>
                <p className="text-gray-700 font-mono text-sm leading-relaxed">
                  {feature.desc}
                </p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Comparison Table */}
      <section className="py-24 px-4 bg-claw-dark border-y-4 border-black">
        <div className="max-w-5xl mx-auto">
          <div className="text-center mb-16">
            <h2 className="text-5xl font-mono font-bold mb-4 text-white">
              COMPARE <span className="text-claw-lime">FRAMEWORKS</span>
            </h2>
            <p className="text-lg text-gray-400">See how Clawlet stacks up against other agent frameworks.</p>
          </div>

          <div className="overflow-x-auto border-4 border-black bg-white">
            <table className="w-full font-mono">
              <thead>
                <tr className="border-b-4 border-black bg-claw-lime">
                  <th className="text-left py-4 px-6 font-bold text-black">FEATURE</th>
                  <th className="text-center py-4 px-6 font-bold text-black">CLAWLET</th>
                  <th className="text-center py-4 px-6 font-bold text-gray-700">OPENCLAW</th>
                  <th className="text-center py-4 px-6 font-bold text-gray-700">NANOBOT</th>
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
                  <tr key={feature} className={`border-b-2 border-black hover:bg-claw-lime/20 ${i % 2 === 0 ? "bg-claw-50" : "bg-white"}`}>
                    <td className="py-4 px-6 text-left font-bold text-black">{feature}</td>
                    <td className="py-4 px-6 text-center font-bold text-claw-magenta">{clawlet}</td>
                    <td className="py-4 px-6 text-center text-gray-600">{openclaw}</td>
                    <td className="py-4 px-6 text-center text-gray-600">{nanobot}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </section>

      {/* Quick Start */}
      <section className="py-24 px-4 bg-claw-cyan">
        <div className="max-w-4xl mx-auto">
          <div className="text-center mb-16">
            <h2 className="text-5xl font-mono font-bold mb-4 text-black">
              GET STARTED <span className="text-claw-dark">IN MINUTES</span>
            </h2>
            <p className="text-lg text-gray-800">Install, run the wizard, and you're ready to go.</p>
          </div>

          <div className="grid md:grid-cols-3 gap-8">
            {[
              {
                step: "1",
                title: "INSTALL",
                desc: "Clone the repo and install dependencies with pip install -e .",
                code: "git clone https://github.com/Kxrbx/Clawlet.git\\ncd Clawlet\\npip install -e ."
              },
              {
                step: "2",
                title: "ONBOARD",
                desc: "Run the interactive setup wizard to configure your agent.",
                code: "clawlet onboard"
              },
              {
                step: "3",
                title: "RUN",
                desc: "Start your agent and begin chatting with your AI assistant.",
                code: "clawlet agent"
              },
            ].map((step, i) => (
              <div key={i} className="border-4 border-black bg-white p-6 shadow-hard relative">
                <div className="absolute -top-4 -left-4 w-12 h-12 border-4 border-black bg-claw-orange flex items-center justify-center font-bold text-2xl font-mono text-black">
                  {step.step}
                </div>
                <h3 className="font-mono font-bold text-xl mb-2 text-black mt-4">{step.title}</h3>
                <p className="text-gray-700 mb-4 font-mono text-sm">{step.desc}</p>
                <pre className="bg-claw-dark text-claw-lime p-4 border-2 border-black font-mono text-xs overflow-x-auto">
                  {step.code}
                </pre>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Final CTA */}
      <section className="py-32 px-4 bg-claw-lime border-t-4 border-black text-center">
        <div className="max-w-3xl mx-auto">
          <h2 className="text-5xl font-mono font-bold mb-6 text-black">
            OPEN SOURCE <span className="text-claw-magenta">& FREE</span>
          </h2>
          <p className="text-xl text-gray-900 mb-10 max-w-2xl mx-auto font-mono">
            MIT licensed. No usage limits. No cloud dependency. Clone the repo, run it, own your AI.
          </p>
          <div className="flex flex-wrap justify-center gap-6">
            <Button size="lg" className="btn-hard bg-claw-magenta text-white text-lg px-10 py-6">
              GET STARTED NOW
            </Button>
            <Button size="lg" className="btn-hard bg-claw-dark text-claw-lime text-lg px-10 py-6">
              VIEW ON GITHUB
            </Button>
          </div>
        </div>
      </section>

      {/* Footer */}
      <footer className="bg-claw-dark border-t-4 border-black py-16 px-4">
        <div className="max-w-6xl mx-auto text-center">
          <div className="flex items-center justify-center gap-4 mb-8">
            <div className="w-16 h-16 border-4 border-claw-lime bg-claw-magenta flex items-center justify-center text-4xl font-mono font-bold text-white">
              C
            </div>
            <div className="text-left">
              <div className="text-3xl font-mono font-bold text-claw-lime">CLAWLET</div>
              <div className="text-sm text-gray-400 font-mono">AI AGENT FRAMEWORK</div>
            </div>
          </div>

          <p className="text-claw-gray font-mono mb-8">
            Built with 💕 by the OpenClaw community | MIT License
          </p>

          <div className="flex justify-center gap-8 text-sm font-mono text-gray-500">
            <a href="https://github.com/Kxrbx/Clawlet" className="hover:text-claw-lime transition-colors">GitHub</a>
            <a href="https://github.com/Kxrbx/Clawlet/discussions" className="hover:text-claw-magenta transition-colors">Discussions</a>
            <a href="https://github.com/Kxrbx/Clawlet/issues" className="hover:text-claw-cyan transition-colors">Issues</a>
          </div>
        </div>
      </footer>
    </div>
  );
}
