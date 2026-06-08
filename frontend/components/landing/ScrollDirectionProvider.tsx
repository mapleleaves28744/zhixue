"use client"

import { createContext, useContext, useEffect, useRef, type ReactNode, type RefObject } from "react"

export type ScrollDirection = "up" | "down"

const ScrollDirectionContext = createContext<RefObject<ScrollDirection> | null>(null)

export function ScrollDirectionProvider({ children }: { children: ReactNode }) {
  const directionRef = useRef<ScrollDirection>("down")

  useEffect(() => {
    let lastY = window.scrollY

    function onScroll() {
      const currentY = window.scrollY
      const delta = currentY - lastY

      if (Math.abs(delta) > 4) {
        directionRef.current = delta > 0 ? "down" : "up"
        lastY = currentY
      }
    }

    window.addEventListener("scroll", onScroll, { passive: true })
    return () => window.removeEventListener("scroll", onScroll)
  }, [])

  return <ScrollDirectionContext.Provider value={directionRef}>{children}</ScrollDirectionContext.Provider>
}

export function useScrollDirectionRef(): RefObject<ScrollDirection> {
  const context = useContext(ScrollDirectionContext)
  if (!context) {
    throw new Error("useScrollDirectionRef must be used within ScrollDirectionProvider")
  }
  return context
}
