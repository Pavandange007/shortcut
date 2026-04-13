// Project theme — edit colors/fonts to taste
/** eslint-disable */
module.exports = {
  theme: {
    extend: {
      colors: {
        background: "#06070B",
        foreground: "#F5F7FF",
        accent: "#7C5CFF",
        "accent-2": "#3BA7FF",
        "surface-1": "#0F1220",
        "surface-2": "#151A2C",
        "surface-3": "#1D2340",
        success: "#34D399",
        warning: "#F59E0B",
        error: "#FB7185",
        info: "#38BDF8",
      },
      fontFamily: {
        sans: ["var(--font-geist-sans)", "ui-sans-serif", "system-ui"],
        mono: ["var(--font-geist-mono)", "ui-monospace", "SFMono-Regular"],
      },
      borderRadius: {
        xl: "12px",
        "2xl": "18px",
        "3xl": "24px",
      },
      boxShadow: {
        elevated:
          "0 24px 50px rgba(3, 8, 28, 0.45), 0 8px 24px rgba(5, 9, 30, 0.28), inset 0 1px 0 rgba(255, 255, 255, 0.04)",
      },
    },
  },
};
