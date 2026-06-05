/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./app/**/*.{js,ts,jsx,tsx,mdx}",
    "./components/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        background: "#0c0c0e",
        surface: "#141418",
        border: "#252528",
        accent: {
          DEFAULT: "#6ea88e",
          dark: "#558a72",
          muted: "#6ea88e18",
        },
        text: {
          primary: "#eceae4",
          secondary: "#9a9890",
          muted: "#5c5a56",
        },
      },
      fontFamily: {
        sans: ["var(--font-sans)", "system-ui", "sans-serif"],
        display: ["var(--font-display)", "Georgia", "serif"],
        mono: ["var(--font-mono)", "ui-monospace", "SFMono-Regular", "monospace"],
      },
    },
  },
  plugins: [],
};
