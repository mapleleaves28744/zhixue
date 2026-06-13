import type { Config } from "tailwindcss"

import { calmClarityColors } from "./lib/calmClarityColors"

const config: Config = {
  content: ["./public/stitch-pages/**/*.html"],
  theme: {
    extend: {
      colors: calmClarityColors,
      borderRadius: {
        lg: "1.5rem",
        md: "0.75rem",
        sm: "0.25rem",
      },
      fontFamily: {
        "display-lg": ["Plus Jakarta Sans", "sans-serif"],
        "headline-md": ["Plus Jakarta Sans", "sans-serif"],
        "headline-sm": ["Plus Jakarta Sans", "sans-serif"],
        "body-lg": ["Manrope", "sans-serif"],
        "body-md": ["Manrope", "sans-serif"],
        "label-md": ["Manrope", "sans-serif"],
        "label-sm": ["Manrope", "sans-serif"],
      },
      fontSize: {
        "display-lg": ["57px", { lineHeight: "1.12", fontWeight: "700" }],
        "headline-md": ["24px", { lineHeight: "1.3", fontWeight: "600" }],
        "headline-sm": ["20px", { lineHeight: "1.4", fontWeight: "600" }],
        "body-lg": ["18px", { lineHeight: "1.6", fontWeight: "500" }],
        "body-md": ["16px", { lineHeight: "1.6", fontWeight: "400" }],
        "label-md": ["14px", { lineHeight: "1.2", letterSpacing: "0.01em", fontWeight: "600" }],
        "label-sm": ["12px", { lineHeight: "1.2", fontWeight: "700" }],
      },
      boxShadow: {
        glass: "0 24px 70px rgba(131, 84, 0, 0.08)",
        glow: "0 16px 34px rgba(131, 84, 0, 0.18)",
      },
      spacing: {
        unit: "8px",
        gutter: "16px",
        "card-gap": "24px",
        "container-padding-mobile": "20px",
        "container-padding-desktop": "48px",
      },
    },
  },
  plugins: [],
}

export default config
