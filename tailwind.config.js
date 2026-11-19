/** @type {import('tailwindcss').Config} */
export default {
  content: ["./src/templates/**/*.html", "./src/apps/**/templates/**/*.html"],
  theme: {
    extend: {
      colors: {
        primary: "var(--md-sys-color-primary)",
        "on-primary": "var(--md-sys-color-on-primary)",
        secondary: "var(--md-sys-color-secondary)",
        surface: "var(--md-sys-color-surface)",
        "on-surface": "var(--md-sys-color-on-surface)",
        "on-surface-variant": "var(--md-sys-color-on-surface-variant)",
        outline: "var(--md-sys-color-outline)",
        error: "var(--md-sys-color-error)",
        success: "var(--md-sys-color-success)",
      },
      borderRadius: {
        sm: "var(--radius-sm)",
        md: "var(--radius-md)",
        lg: "var(--radius-lg)",
        xl: "var(--radius-xl)",
      },
      boxShadow: {
        glass: "var(--glass-shadow)",
      },
    },
  },
  plugins: [],
};
