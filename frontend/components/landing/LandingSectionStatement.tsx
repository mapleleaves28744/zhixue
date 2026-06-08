"use client"

import { motion, useReducedMotion, useScroll, useTransform } from "framer-motion"
import { useRef } from "react"

type LandingSectionStatementProps = {
  index: string
  title: string
  subtitle?: string
}

export function LandingSectionStatement({ index, title, subtitle }: LandingSectionStatementProps) {
  const reduceMotion = useReducedMotion()
  const ref = useRef<HTMLDivElement>(null)
  const { scrollYProgress } = useScroll({
    target: ref,
    offset: ["start 0.85", "start 0.35"]
  })
  const opacity = useTransform(scrollYProgress, [0, 1], [0.15, 1])
  const y = useTransform(scrollYProgress, [0, 1], [48, 0])
  const clip = useTransform(scrollYProgress, [0, 1], ["inset(100% 0 0 0)", "inset(0% 0 0 0)"])

  if (reduceMotion) {
    return (
      <div className="landing-section-statement mx-auto mb-16 max-w-5xl px-2">
        <p className="text-xs font-bold uppercase tracking-[0.35em] text-primary">{index}</p>
        <h2 className="mt-4 font-display text-3xl leading-tight md:text-5xl lg:text-6xl" style={{ fontFamily: "var(--font-display)" }}>
          {title}
        </h2>
        {subtitle ? <p className="mt-4 max-w-2xl text-lg text-muted-foreground">{subtitle}</p> : null}
      </div>
    )
  }

  return (
    <div ref={ref} className="landing-section-statement mx-auto mb-16 max-w-5xl px-2">
      <motion.p className="text-xs font-bold uppercase tracking-[0.35em] text-primary" style={{ opacity, y }}>
        {index}
      </motion.p>
      <motion.h2
        className="mt-4 font-display text-3xl leading-[1.05] tracking-[-0.02em] md:text-5xl lg:text-6xl"
        style={{ fontFamily: "var(--font-display)", opacity, y, clipPath: clip }}
      >
        {title}
      </motion.h2>
      {subtitle ? (
        <motion.p className="mt-4 max-w-2xl text-lg text-muted-foreground" style={{ opacity, y }}>
          {subtitle}
        </motion.p>
      ) : null}
    </div>
  )
}
