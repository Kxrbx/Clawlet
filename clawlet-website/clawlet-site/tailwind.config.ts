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
        // Neo-brutalist palette
        claw: {
          50: "#f0f0f0",
          100: "#e0e0e0",
          200: "#cccccc",
          300: "#a0a0a0",
          400: "#707070",
          500: "#404040",
          600: "#202020",
          700: "#0a0a0a",
          800: "#000000",
          900: "#000000",
          lime: "#ccff00",
          magenta: "#ff00ff",
          cyan: "#00ffff",
          yellow: "#ffff00",
          orange: "#ff7700",
          red: "#ff0000",
        },
      },
      fontFamily: {
        sans: ["Space Grotesk", "system-ui", "sans-serif"],
        mono: ["JetBrains Mono", "monospace"],
      },
      borderWidth: {
        "4": "4px",
      },
      boxShadow: {
        "hard": "4px 4px 0px 0px #000000",
        "hard-sm": "2px 2px 0px 0px #000000",
        "hard-lg": "8px 8px 0px 0px #000000",
        "glow-lime": "0 0 20px rgba(204, 255, 0, 0.5)",
        "glow-magenta": "0 0 20px rgba(255, 0, 255, 0.5)",
        "glow-cyan": "0 0 20px rgba(0, 255, 255, 0.5)",
      },
      animation: {
        "hard-bounce": "hardBounce 0.6s ease-in-out infinite alternate",
        "glitch": "glitch 0.3s ease-in-out infinite",
        "marquee": "marquee 25s linear infinite",
        "pulse-hard": "pulseHard 2s ease-in-out infinite",
      },
      keyframes: {
        hardBounce: {
          "0%": { transform: "translateY(0)" },
          "100%": { transform: "translateY(-10px)" },
        },
        glitch: {
          "0%, 100%": { transform: "translate(0)" },
          "20%": { transform: "translate(-2px, 2px)" },
          "40%": { transform: "translate(-2px, -2px)" },
          "60%": { transform: "translate(2px, 2px)" },
          "80%": { transform: "translate(2px, -2px)" },
        },
        marquee: {
          "0%": { transform: "translateX(0%)" },
          "100%": { transform: "translateX(-100%)" },
        },
        pulseHard: {
          "0%, 100%": { boxShadow: "0 0 0 0 rgba(204, 255, 0, 0.7)" },
          "50%": { boxShadow: "0 0 0 10px rgba(204, 255, 0, 0)" },
        },
      },
    },
  },
  plugins: [],
} satisfies Config;
