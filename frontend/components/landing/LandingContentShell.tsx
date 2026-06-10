"use client"

import { motion, useReducedMotion, useScroll, useTransform, type MotionValue } from "framer-motion"
import { useRef, type ReactNode } from "react"

type LandingContentShellProps = {
  backdrop: ReactNode
  children: ReactNode
}

export function LandingContentShell({ backdrop, children }: LandingContentShellProps) {
  const reduceMotion = useReducedMotion()
  const ref = useRef<HTMLDivElement>(null)
  const { scrollYProgress } = useScroll({
    target: ref,
    offset: ["start end", "end start"]
  })
  const backdropY = useTransform(scrollYProgress, [0, 1], ["-6%", "10%"])

  return (
    <div ref={ref} className="relative overflow-hidden">
      {reduceMotion ? (
        backdrop
      ) : (
        <ParallaxBackdrop motionY={backdropY}>{backdrop}</ParallaxBackdrop>
      )}
      <div className="relative z-10">{children}</div>
    </div>
  )
}

function ParallaxBackdrop({ children, motionY }: { children: ReactNode; motionY: MotionValue<string> }) {
  return (
    <motion.div className="absolute -inset-y-[12%] inset-x-0 z-0 min-h-[124%] will-change-transform" style={{ y: motionY }}>
      {children}
    </motion.div>
  )
}
