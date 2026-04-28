/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    "./templates/**/*.html",
    "./**/templates/**/*.html",
  ],
  theme: {
    extend: {
      colors: {
        // Primary Palette (Sentinel Brand)
        "sentinel-orange": "#E87722",
        "sentinel-orange-dark": "#C9631A",
        "sentinel-orange-light": "#FFF3EB",
        "sentinel-brown": "#4A2C2A",
        "sentinel-brown-light": "#6B4A3A",
        "sentinel-brown-dark": "#3A1F1A",

        // Semantic Statuses
        "status-in-progress": "#E87722",
        "status-pending": "#D4A843",
        "status-approved": "#2D8B56",
        "status-rejected": "#C93B3B",
        "status-overdue": "#991B1B",
        "status-closed": "#10B981",

        // Surface & Neutrals
        "surface-base": "#FAF7F4",
        "surface-card": "#FFFFFF",
        "surface-warm": "#F5EDE6",
        "border-subtle": "#E8DFD6",
        "text-primary": "#2D1F1E",
        "text-secondary": "#8B7E74",
        "text-muted": "#B5A99E",
      },
      fontFamily: {
        sans: ["Inter", "system-ui", "sans-serif"],
        mono: ["JetBrains Mono", "monospace"],
      },
    },
  },
  plugins: [
    require("@tailwindcss/forms"),
  ],
};
