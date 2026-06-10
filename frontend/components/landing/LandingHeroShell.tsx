"use client"

import { motion, useReducedMotion, useScroll, useTransform } from "framer-motion"
import { useRef, type ReactNode } from "react"

type LandingHeroShellProps = {
  children: ReactNode
  video: ReactNode
  nav: ReactNode
}

export function LandingHeroShell({ children, video, nav }: LandingHeroShellProps) {
  const reduceMotion = useReducedMotion()
  const ref = useRef<HTMLDivElement>(null)
  const { scrollYProgress } = useScroll({
    target: ref,
    offset: ["start start", "end start"]
  })

  const videoY = useTransform(scrollYProgress, [0, 1], ["0%", "22%"])
  const videoScale = useTransform(scrollYProgress, [0, 1], [1, 1.08])
  const contentY = useTransform(scrollYProgress, [0, 1], [0, 120])
  const contentOpacity = useTransform(scrollYProgress, [0, 0.55, 1], [1, 0.55, 0])
  const contentScale = useTransform(scrollYProgress, [0, 1], [1, 0.94])

  return (
    <div ref={ref} className="landing-hero-shell relative min-h-[135vh]" id="top">
      <div className="sticky top-0 h-screen overflow-hidden">
        {reduceMotion ? (
          <>
            <div className="absolute inset-0">{video}</div>
            <div className="relative z-10 flex h-full flex-col">
              {nav}
              <div className="flex flex-1 flex-col justify-center">{children}</div>
            </div>
          </>
        ) : (
          <>
            <motion.div className="absolute inset-0 will-change-transform" style={{ y: videoY, scale: videoScale }}>
              {video}
            </motion.div>
            <div className="relative z-10 flex h-full flex-col">
              {nav}
              <motion.div
                className="flex flex-1 flex-col justify-center will-change-transform"
                style={{ y: contentY, opacity: contentOpacity, scale: contentScale }}
              >
                {children}
              </motion.div>
            </div>
          </>
        )}
      </div>
    </div>
  )
}
