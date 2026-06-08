import { Suspense } from "react"

import { LandingPage } from "@/components/landing/LandingPage"
import { landingFontVariables } from "@/lib/landingFonts"

export default function HomePage() {
  return (
    <div className={`${landingFontVariables} landing-page`}>
      <Suspense fallback={null}>
        <LandingPage />
      </Suspense>
    </div>
  )
}
