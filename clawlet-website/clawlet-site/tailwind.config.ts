import type { Config } from "tailwindcss";

export default {
  content: [
    "./pages/**/*.{ts,tsx}",
    "./components/**/*.{ts,tsx}",
    "./app/**/*.{ts,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        // Sakura palette – soft, dreamy, with depth
        sakura: {
          // core pastels
          50: "#fdf2f8",      // very light pink
          100: "#fce7f3",     // light pink
          150: "#fbcfe8",     // slightly stronger
          200: "#f9a8d4",     // pink
          300: "#f472b6",     // hot pink
          400: "#ec4899",     // vibrant pink
          500: "#db2777",     // main brand
          600: "#be185d",     // darker
          700: "#9d174d",     // deep
          800: "#831843",     // deeper
          900: "#831843",     // same as 800 for continuity
          // accents
          lavender: "#a78bfa",
          sky: "#60a5fa",
          mint: "#34d399",
          peach: "#fbbf24",
          coral: "#f87171",
        },
      },
      fontFamily: {
        sans: ["Inter", "system-ui", "sans-serif"],
        mono: ["JetBrains Mono", "monospace"],
      },
      boxShadow: {
        // Soft glowing shadows for sakura aesthetic
        "glow-sm": "0 0 12px rgba(236, 72, 153, 0.25)",
        "glow-md": "0 0 20px rgba(236, 72, 153, 0.35)",
        "glow-lg": "0 0 32px rgba(236, 72, 153, 0.45)",
        "glow-primary": "0 0 24px rgba(219, 39, 119, 0.4)",
        "inner-glow": "inset 0 0 12px rgba(236, 72, 153, 0.15)",
      },
      backdropBlur: {
        xs: "2px",
      },
      animation: {
        "float": "float 6s ease-in-out infinite",
        "pulse-glow": "pulseGlow 3s ease-in-out infinite",
        "fade-in-up": "fadeInUp 0.8s ease-out forwards",
        "slide-up": "slideUp 0.6s ease-out forwards",
      },
      keyframes: {
        float: {
          "0%, 100%": { transform: "translateY(0)" },
          "50%": { transform: "translateY(-12px)" },
        },
        pulseGlow: {
          "0%, 100%": { boxShadow: "0 0 10px rgba(236, 72, 153, 0.2)" },
          "50%": { boxShadow: "0 0 24px rgba(236, 72, 153, 0.45)" },
        },
        fadeInUp: {
          "0%": { opacity: "0", transform: "translateY(20px)" },
          "100%": { opacity: "1", transform: "translateY(0)" },
        },
        slideUp: {
          "0%": { opacity: "0", transform: "translateY(30px)" },
          "100%": { opacity: "1", transform: "translateY(0)" },
        },
      },
    },
  },
  plugins: [],
} satisfies Config;
