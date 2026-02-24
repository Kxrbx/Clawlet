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
        // Sakura palette
        sakura: {
          50: "#fdf2f8",
          100: "#fce7f3",
          150: "#fbcfe8",
          200: "#f9a8d4",
          300: "#f472b6",
          400: "#ec4899",
          500: "#db2777",
          600: "#be185d",
          700: "#9d174d",
          800: "#831843",
        },
      },
      fontFamily: {
        sans: ["Inter", "system-ui", "sans-serif"],
        mono: ["JetBrains Mono", "monospace"],
      },
      boxShadow: {
        // Custom glow shadows
        "glow-sm": "0 0 12px rgba(236, 72, 153, 0.25), 0 0 4px rgba(236, 72, 153, 0.15)",
        "glow-md": "0 0 20px rgba(236, 72, 153, 0.35), 0 0 8px rgba(236, 72, 153, 0.2)",
        "glow-lg": "0 0 32px rgba(236, 72, 153, 0.5), 0 0 12px rgba(236, 72, 153, 0.25)",
        "glow-xl": "0 0 48px rgba(236, 72, 153, 0.6), 0 0 16px rgba(236, 72, 153, 0.3)",
        "inner-glow": "inset 0 0 12px rgba(236, 72, 153, 0.15)",
      },
      animation: {
        float: "float 6s ease-in-out infinite",
        "fade-in-up": "fadeInUp 0.8s ease-out forwards",
      },
      keyframes: {
        float: {
          "0%, 100%": { transform: "translateY(0)" },
          "50%": { transform: "translateY(-15px)" },
        },
        fadeInUp: {
          "0%": { opacity: "0", transform: "translateY(25px)" },
          "100%": { opacity: "1", transform: "translateY(0)" },
        },
      },
    },
  },
  plugins: [],
} satisfies Config;
