/** @type {import('tailwindcss').Config} */
export default {
  darkMode: ["class"],
  content: ["./index.html", "./src/**/*.{js,ts,jsx,tsx}"],
  theme: {
    extend: {
      fontFamily: {
        sans: ['"LXGW WenKai"', "PingFang SC", "Microsoft YaHei", "sans-serif"],
        serif: ['"LXGW WenKai"', '"Noto Serif SC"', "Songti SC", "serif"],
      },
      colors: {
        background: "var(--bg)",
        foreground: "var(--text)",
        muted: {
          DEFAULT: "var(--mut)",
          foreground: "var(--mut-warm)",
        },
        border: "var(--line2)",
        line: "var(--line)",
        line2: "var(--line2)",
        primary: {
          DEFAULT: "var(--pri)",
          foreground: "#ffffff",
        },
        accent: {
          DEFAULT: "var(--acc)",
          foreground: "var(--acc-text)",
        },
        surface: "var(--surf)",
        "nav-on": "var(--nav-on)",
        "acc-bg": "var(--acc-bg)",
        "status-ok": {
          bg: "var(--status-ok-bg)",
          text: "var(--status-ok-text)",
        },
      },
      borderRadius: {
        lg: "var(--r)",
        md: "10px",
        sm: "8px",
      },
      width: {
        sidebar: "220px",
      },
      boxShadow: {
        sm: "var(--shadow-sm)",
        md: "var(--shadow-md)",
      },
    },
  },
  plugins: [],
};
