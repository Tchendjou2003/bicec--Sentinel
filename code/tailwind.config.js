/** @type {import('tailwindcss').Config} */
module.exports = {
  darkMode: ["class"],
  content: [
    "./templates/**/*.html",
    "./apps/**/templates/**/*.html",
    "./static/**/*.js",
  ],
  theme: {
    extend: {
      colors: {
        // Primary Palette (Sentinel Brand)
        "sentinel-orange": "#E87722",
        "sentinel-orange-dark": "#C9631A",
        "sentinel-orange-light": "#FFF3EB",
        "sentinel-orange-soft": "#F5C89A",
        "sentinel-brown": "#4A2C2A",
        "sentinel-brown-light": "#6B4A3A",
        "sentinel-brown-dark": "#3A1F1A",

        // ═══ SENTINEL DESIGN SYSTEM — tokens additifs (handoff Claude Design) ═══
        // Brand — orange-darker (actif) + sarcelle/teal (secondaire calme)
        "sentinel-orange-darker": "#A8500F",
        "sentinel-teal": "#14746F",
        "sentinel-teal-dark": "#0E5B57",
        "sentinel-teal-darker": "#0A4744",
        "sentinel-teal-tint": "#E6F2F1",
        "sentinel-brown-tint": "#F5EDE6",
        // Sidebar graphite (rail institutionnel — orange plat actif, sans gradient)
        "graphite": "#211C1B",
        "graphite-hover": "#322B29",
        "graphite-border": "#3A332F",
        "graphite-fg": "#CFC6BF",
        "graphite-fg-strong": "#F3EDE7",
        "graphite-section": "#8A7F78",
        // Surfaces & hairlines complémentaires
        "surface-sunken": "#F3EFEA",
        "surface-faint": "#F8F8F5",
        "border-strong": "#D8CBBE",
        // Texte atténué chaud (labels/corps) — centralise les hex jadis en dur
        "text-faint": "#968A80",
        "text-body": "#6F635B",
        // Renforts sémantiques succès / danger (texte foncé + fond clair)
        "success-strong": "#1E6B41",
        "danger-surface": "#FEE2E2",
        // Workflow status — FSM complet + tints (Recommendation.Status)
        // status-draft : #6F635B (= text-body) et non #968A80 — contraste
        // WCAG AA ≈ 4,6:1 sur la tint (correctif 2.3 du rapport UI/UX)
        "status-draft": "#6F635B",        "status-draft-tint": "#F0ECE7",
        "status-assigned": "#2B6CB0",     "status-assigned-tint": "#E8F0F8",
        "status-in-progress-strong": "#C9631A", "status-in-progress-tint": "#FFF3EB",
        "status-dm-review": "#C08A2D",    "status-dm-review-tint": "#FBF1DF",
        "status-audit-review": "#14746F", "status-audit-review-tint": "#E6F2F1",
        "status-closed-strong": "#2D8B56", "status-closed-tint": "#E7F2EC",
        "status-overdue-strong": "#991B1B", "status-overdue-tint": "#FBEAE7",
        // Criticité (priorité)
        "prio-critique": "#C0392B", "prio-critique-tint": "#FBEAE7",
        "prio-haute": "#C9631A",    "prio-haute-tint": "#FCEFE4",
        "prio-moyenne": "#C08A2D",  "prio-moyenne-tint": "#FBF1DF",
        "prio-faible": "#2D8B56",   "prio-faible-tint": "#E7F2EC",
        // Sémantique — tints + danger (rouge DS calme, sans toucher l'objet HSL destructive)
        "success-tint": "#E7F2EC",
        "warning-tint": "#FBF1DF",
        "destructive-tint": "#FBEAE7",
        "info-tint": "#E8F0F8",
        "danger": "#C0392B",
        "danger-strong": "#991B1B",
        "danger-tint": "#FBEAE7",
        // ═══ fin tokens DS ═══

        // Semantic Statuses (héritées — conservées pour compat ascendante)
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

        // Tokens Material/Stitch : intégralement purgés (lot 3.6 terminé) —
        // tous les consommateurs ont été migrés vers les tokens Sentinel.

        // Tokens HSL du kit (Sentinel Export)
        "border": "hsl(var(--border))",
        "input": "hsl(var(--input))",
        "ring": "hsl(var(--ring))",
        "foreground": "hsl(var(--foreground))",
        "destructive": { DEFAULT: "hsl(var(--destructive))", foreground: "hsl(var(--destructive-foreground))" },
        "success": { DEFAULT: "hsl(var(--success))", foreground: "hsl(var(--success-foreground))" },
        "warning": { DEFAULT: "hsl(var(--warning))", foreground: "hsl(var(--warning-foreground))" },
        "info": { DEFAULT: "hsl(var(--info))", foreground: "hsl(var(--info-foreground))" },
        "muted": { DEFAULT: "hsl(var(--muted))", foreground: "hsl(var(--muted-foreground))" },
        "accent": { DEFAULT: "hsl(var(--accent))", foreground: "hsl(var(--accent-foreground))" },
        "card": { DEFAULT: "hsl(var(--card))", foreground: "hsl(var(--card-foreground))" },
        "sidebar": {
          DEFAULT: "hsl(var(--sidebar-background))",
          foreground: "hsl(var(--sidebar-foreground))",
          primary: "hsl(var(--sidebar-primary))",
          "primary-foreground": "hsl(var(--sidebar-primary-foreground))",
          accent: "hsl(var(--sidebar-accent))",
          "accent-foreground": "hsl(var(--sidebar-accent-foreground))",
          border: "hsl(var(--sidebar-border))",
        },
      },
      fontFamily: {
        sans: ["Inter", "system-ui", "sans-serif"],
        mono: ["JetBrains Mono", "monospace"],
        display: ["Manrope", "system-ui", "sans-serif"],
        heading: ["Manrope", "sans-serif"],
        body: ["Inter", "sans-serif"],
        label: ["Inter", "sans-serif"],
      },
      borderRadius: { lg: "var(--radius)", md: "calc(var(--radius) - 2px)", sm: "calc(var(--radius) - 4px)" },
      keyframes: {
        "pulse-slow": { "0%, 100%": { opacity: "1" }, "50%": { opacity: "0.5" } },
        "fade-in": { from: { opacity: "0" }, to: { opacity: "1" } },
        "slide-up": { from: { opacity: "0", transform: "translateY(12px)" }, to: { opacity: "1", transform: "translateY(0)" } },
        "float": {
          "0%, 100%": { transform: "translateY(0px)" },
          "50%": { transform: "translateY(-18px)" },
        },
        "card-in": {
          from: { opacity: "0", transform: "translateY(14px) scale(0.98)" },
          to: { opacity: "1", transform: "translateY(0) scale(1)" },
        },
        "shake": {
          "0%, 100%": { transform: "translateX(0)" },
          "15%, 55%": { transform: "translateX(-5px)" },
          "35%, 75%": { transform: "translateX(5px)" },
        },
      },
      animation: {
        "pulse-slow": "pulse-slow 2s ease-in-out infinite",
        "fade-in": "fade-in 0.4s ease-out both",
        "slide-up": "slide-up 0.4s cubic-bezier(0.16, 1, 0.3, 1) both",
        "card-in": "card-in 0.45s cubic-bezier(0.16, 1, 0.3, 1) both",
        "shake": "shake 0.45s ease-in-out",
      },
    },
  },
  plugins: [
    require("tailwindcss-animate"),
    require("@tailwindcss/forms"),
  ],
};
