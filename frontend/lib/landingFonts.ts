import { Instrument_Serif, Inter } from "next/font/google"

export const landingDisplayFont = Instrument_Serif({
  subsets: ["latin"],
  weight: ["400"],
  variable: "--font-instrument-serif"
})

export const landingBodyFont = Inter({
  subsets: ["latin"],
  weight: ["400", "500"],
  variable: "--font-inter"
})

export const landingFontVariables = `${landingDisplayFont.variable} ${landingBodyFont.variable}`
