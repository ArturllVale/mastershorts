/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        // MasterShorts Cyber Studio Palette (Cool Slate + Electric Violet & Neon Cyan)
        paper: "oklch(11% 0.015 260 / <alpha-value>)",
        paper2: "oklch(14% 0.018 260 / <alpha-value>)",
        paper3: "oklch(18% 0.022 260 / <alpha-value>)",
        paper4: "oklch(22% 0.025 260 / <alpha-value>)",
        ink: "oklch(98% 0.005 260 / <alpha-value>)",
        ink2: "oklch(90% 0.01 260 / <alpha-value>)",
        muted: "oklch(68% 0.018 260 / <alpha-value>)",
        "muted-dim": "oklch(48% 0.02 260 / <alpha-value>)",
        // Primary brand accent: Electric Violet
        brass: "oklch(65% 0.24 290 / <alpha-value>)",
        brassink: "#ffffff",
        violet: "oklch(65% 0.24 290 / <alpha-value>)",
        cyan: "oklch(75% 0.16 210 / <alpha-value>)",
        coral: "oklch(65% 0.22 25 / <alpha-value>)",
        ok: "oklch(76% 0.16 160 / <alpha-value>)",
        warn: "oklch(80% 0.16 80 / <alpha-value>)",
        danger: "oklch(65% 0.22 25 / <alpha-value>)",
        
        // Semantic aliases
        background: "oklch(11% 0.015 260 / <alpha-value>)",
        surface: "oklch(14% 0.018 260 / <alpha-value>)",
        primary: "oklch(65% 0.24 290 / <alpha-value>)",
        accent: "oklch(65% 0.24 290 / <alpha-value>)",
      },
      fontFamily: {
        display: "var(--font-display)",
        heading: "var(--font-heading)",
        body: "var(--font-body)",
        sans: "var(--font-body)",
        serif: "var(--font-serif)",
        mono: "var(--font-mono)",
      },
      borderColor: {
        rule: "var(--color-rule)",
        rule2: "var(--color-rule-2)",
        "rule-strong": "var(--color-rule-strong)",
      },
      borderRadius: {
        xs: "var(--radius-xs)",
        sm: "var(--radius-sm)",
        input: "var(--radius-input)",
        card: "var(--radius-card)",
        panel: "var(--radius-panel)",
        modal: "var(--radius-modal)",
      },
      boxShadow: {
        card: "var(--shadow-card)",
        elevated: "var(--shadow-elevated)",
        modal: "var(--shadow-modal)",
      },
      fontSize: {
        micro: ["11px", { letterSpacing: "0.06em", lineHeight: "14px" }],
      },
      transitionTimingFunction: {
        out: "var(--ease-out)",
      },
      animation: {
        'pulse-slow': 'pulse 3s cubic-bezier(0.4, 0, 0.6, 1) infinite',
        'fade': 'fadeIn 0.22s var(--ease-out)',
        'slide-in-left': 'slideInLeft 0.22s var(--ease-out)',
        'sheet-up': 'sheetUp 0.24s var(--ease-out)',
      },
      keyframes: {
        fadeIn: {
          from: { opacity: '0' },
          to: { opacity: '1' },
        },
        slideInLeft: {
          from: { transform: 'translateX(-100%)' },
          to: { transform: 'translateX(0)' },
        },
        sheetUp: {
          from: { transform: 'translateY(12px)', opacity: '0' },
          to: { transform: 'translateY(0)', opacity: '1' },
        },
      },
    },
  },
  plugins: [],
}
