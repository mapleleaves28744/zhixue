"use client"

import { motion, useReducedMotion, useScroll, useSpring, useTransform } from "framer-motion"

export function LandingScrollProgress() {
  const reduceMotion = useReducedMotion()
  const { scrollYProgress } = useScroll()
  const smoothProgress = useSpring(scrollYProgress, { stiffness: 120, damping: 28, restDelta: 0.001 })
  const width = useTransform(smoothProgress, (value) => `${value * 100}%`)

  if (reduceMotion) {
    return null
  }

  return (
    <div aria-hidden="true" className="pointer-events-none fixed inset-x-0 top-0 z-[60] h-[2px] bg-border/30">
      <motion.div className="h-full bg-primary" style={{ width }} />
    </div>
  )
}
