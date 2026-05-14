import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./src/pages/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/components/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/app/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      fontFamily: {
        mono: ["var(--font-jetbrains)", "monospace"],
      },
      colors: {
        background: "var(--nexus-bg)",
        foreground: "var(--nexus-text)",
        border: "var(--nexus-border)",
        muted: {
          DEFAULT: "var(--nexus-surface)",
          foreground: "var(--nexus-muted)",
        },
        accent: {
          DEFAULT: "var(--nexus-toggle-idle-hover-bg)",
          foreground: "var(--nexus-text)",
        },
        card: {
          DEFAULT: "var(--nexus-panel)",
          foreground: "var(--nexus-text)",
        },
        primary: {
          DEFAULT: "var(--nexus-accent)",
          foreground: "var(--nexus-text)",
        },
      },
    },
  },
  plugins: [],
};
export default config;
