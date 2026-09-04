import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        page: "var(--page)",
        surface: "var(--surface)",
        sunken: "var(--surface-sunken)",
        line: "var(--line)",
        ink: {
          DEFAULT: "var(--ink)",
          soft: "var(--ink-soft)",
          muted: "var(--ink-muted)",
          faint: "var(--ink-faint)",
        },
        accent: "var(--accent)",
        level: {
          green: "var(--green)",
          yellow: "var(--yellow)",
          orange: "var(--orange)",
          red: "var(--red)",
          grey: "var(--grey)",
        },
        normal: "#0f7a54",
        watch: "#a56a07",
        alert: "#b31b28",
        insufficient: "#5f6b78",
      },
      borderColor: {
        DEFAULT: "var(--line)",
      },
      fontFamily: {
        sans: ["var(--font-sans)", "ui-sans-serif", "system-ui", "sans-serif"],
        mono: ["var(--font-mono)", "ui-monospace", "monospace"],
      },
      boxShadow: {
        card: "0 1px 2px rgba(13,22,32,0.04)",
        raised: "0 2px 8px rgba(13,22,32,0.07)",
      },
    },
  },
  plugins: [],
};

export default config;
