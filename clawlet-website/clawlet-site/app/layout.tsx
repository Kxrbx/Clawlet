import type { Metadata } from "next";
import { Inter, JetBrains_Mono } from "next/font/google";
import "./globals.css";

const inter = Inter({
  variable: "--font-inter",
  subsets: ["latin"],
  display: "swap",
});

const jetBrainsMono = JetBrains_Mono({
  variable: "--font-jetbrains-mono",
  subsets: ["latin"],
  display: "swap",
});

export const metadata: Metadata = {
  title: "Clawlet - AI Agent Framework that Knows Who It Is",
  description: "Build self-aware AI agents with identity system (SOUL.md, USER.md, MEMORY.md). Local-first, open source, runs with Ollama. ~5,200 lines of Python.",
  keywords: ["ai", "agent", "llm", "ollama", "local", "python", "framework", "openclaw", "identity", "autonomy"],
  authors: [{ name: "Clawlet Team" }],
  openGraph: {
    title: "Clawlet - AI Agent Framework that Knows Who It Is",
    description: "Build self-aware AI agents with identity system. Local-first, open source, runs with Ollama.",
    url: "https://clawlet.ai",
    siteName: "Clawlet",
    type: "website",
  },
  twitter: {
    card: "summary_large_image",
    title: "Clawlet - AI Agent Framework that Knows Who It Is",
    description: "Build self-aware AI agents with identity system. Local-first, open source, runs with Ollama.",
  },
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" suppressHydrationWarning>
      <body
        className={`${inter.variable} ${jetBrainsMono.variable} font-sans antialiased`}
      >
        {children}
      </body>
    </html>
  );
}
