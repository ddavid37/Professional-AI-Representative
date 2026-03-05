/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./app/**/*.{js,ts,jsx,tsx,mdx}",
    "./components/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        background: "#0a0a0f",
        surface: "#13131a",
        border: "#1e1e2e",
        accent: {
          DEFAULT: "#00d4aa",
          dark: "#00a880",
          muted: "#00d4aa20",
        },
        text: {
          primary: "#e8e8f0",
          secondary: "#8888aa",
          muted: "#55556a",
        },
      },
      fontFamily: {
        mono: ["var(--font-mono)", "ui-monospace", "SFMono-Regular", "monospace"],
      },
    },
  },
  plugins: [],
};
