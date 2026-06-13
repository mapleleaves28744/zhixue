/**
 * Luminous Warmth — logged-in student workspace palette.
 * Matches stitch-shared.css and landing.css warm tokens.
 */
export const calmClarityColors = {
  surface: "#fcf9f8",
  "surface-dim": "#dcd9d9",
  "surface-bright": "#fcf9f8",
  "surface-container-lowest": "#ffffff",
  "surface-container-low": "#f6f3f2",
  "surface-container": "#f0eded",
  "surface-container-high": "#eae7e7",
  "surface-container-highest": "#e5e2e1",
  "on-surface": "#1c1b1b",
  "on-surface-variant": "#524434",
  "inverse-surface": "#313030",
  "inverse-on-surface": "#f3f0ef",
  outline: "#857462",
  "outline-variant": "#d7c3ae",
  "surface-tint": "#835400",
  primary: "#835400",
  "on-primary": "#ffffff",
  "primary-container": "#f9a826",
  "on-primary-container": "#674100",
  "inverse-primary": "#ffb957",
  secondary: "#7d5354",
  "on-secondary": "#ffffff",
  "secondary-container": "#fec7c7",
  "on-secondary-container": "#7a5051",
  tertiary: "#585f66",
  "on-tertiary": "#ffffff",
  "tertiary-container": "#b3bac2",
  "on-tertiary-container": "#434a51",
  error: "#ba1a1a",
  "on-error": "#ffffff",
  "error-container": "#ffdad6",
  "on-error-container": "#93000a",
  "primary-fixed": "#ffddb5",
  "primary-fixed-dim": "#ffb957",
  "on-primary-fixed": "#2a1800",
  "on-primary-fixed-variant": "#643f00",
  "secondary-fixed": "#ffdad9",
  "secondary-fixed-dim": "#efb9b9",
  "on-secondary-fixed": "#301214",
  "on-secondary-fixed-variant": "#633c3d",
  "tertiary-fixed": "#dce3eb",
  "tertiary-fixed-dim": "#c0c7cf",
  "on-tertiary-fixed": "#151c22",
  "on-tertiary-fixed-variant": "#40484e",
  background: "#fcf9f8",
  "on-background": "#1c1b1b",
  "surface-variant": "#f0eded",
} as const

export const calmClarityCssVars = `
  --zhixue-surface: ${calmClarityColors.surface};
  --zhixue-primary: ${calmClarityColors.primary};
  --zhixue-primary-container: ${calmClarityColors["primary-container"]};
  --zhixue-on-surface: ${calmClarityColors["on-surface"]};
  --zhixue-on-surface-variant: ${calmClarityColors["on-surface-variant"]};
  --zhixue-error-container: ${calmClarityColors["error-container"]};
  --zhixue-on-error-container: ${calmClarityColors["on-error-container"]};
  --zhixue-tertiary-fixed: ${calmClarityColors["tertiary-fixed"]};
  --glass-shadow: 0 24px 70px rgba(131, 84, 0, 0.08);
`
