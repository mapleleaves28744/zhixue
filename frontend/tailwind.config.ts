import type { Config } from "tailwindcss"

const config: Config = {
  content: [
    "./app/**/*.{ts,tsx}",
    "./components/**/*.{ts,tsx}",
    "./hooks/**/*.{ts,tsx}",
    "./lib/**/*.{ts,tsx}"
  ],
  theme: {
    extend: {
      colors: {
        primary: {
          50: "#eef7ff",
          100: "#d9ecff",
          500: "#2f80ed",
          600: "#1f6ed4",
          700: "#1a57a8"
        }
      }
    }
  },
  plugins: []
}

export default config
