/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,jsx}"],
  theme: {
    extend: {
      colors: {
        orange: {
          DEFAULT: "#FF6B35",
          light: "#FF8A4C",
          50: "#FFF1EA",
        },
        ink: {
          DEFAULT: "#172033",
          secondary: "#687386",
          muted: "#98A2B3",
        },
        surface: {
          page: "#F7F8FA",
          card: "#FFFFFF",
          border: "#E7E9ED",
        },
        state: {
          success: "#22A06B",
          warning: "#F59E0B",
          error: "#E5484D",
          info: "#3B82F6",
        },
      },
      fontFamily: {
        sans: [
          "Inter",
          "ui-sans-serif",
          "system-ui",
          "-apple-system",
          "Segoe UI",
          "Roboto",
          "Helvetica Neue",
          "Arial",
          "sans-serif",
        ],
      },
      borderRadius: {
        card: "12px",
      },
      boxShadow: {
        card: "0 1px 2px rgba(23, 32, 51, 0.04), 0 1px 6px rgba(23, 32, 51, 0.04)",
        elevated: "0 4px 16px rgba(23, 32, 51, 0.08)",
      },
      keyframes: {
        fadeIn: {
          "0%": { opacity: 0, transform: "translateY(4px)" },
          "100%": { opacity: 1, transform: "translateY(0)" },
        },
      },
      animation: {
        fadeIn: "fadeIn 0.25s ease-out",
      },
    },
  },
  plugins: [],
};
