/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    "./templates/**/*.html",
    "./**/templates/**/*.html",
  ],
  theme: {
    extend: {
      colors: {
        "bicec-yellow": "#FAB50B",
        "bicec-yellow-dark": "#D89A0A",
        "bicec-blue": "#1A3A5C",
        "bicec-blue-light": "#2B5080",
      },
      fontFamily: {
        sans: ["Roboto", "sans-serif"],
        mono: ["JetBrains Mono", "monospace"],
      },
    },
  },
  plugins: [
    require("@tailwindcss/forms"),
  ],
};
