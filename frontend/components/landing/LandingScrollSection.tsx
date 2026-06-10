"use client"

import { motion, useReducedMotion, useScroll, useTransform } from "framer-motion"
import { useRef, type ReactNode } from "react"

import { LandingSectionStatement } from "@/components/landing/LandingSectionStatement"
import { cn } from "@/lib/utils"

type LandingScrollSectionProps = {
  id: string
  children: ReactNode
  className?: string
  statement?: {
    index: string
    title: string
    subtitle?: string
  }
}

export function LandingScrollSection({ id, children, className, statement }: LandingScrollSectionProps) {
  const reduceMotion = useReducedMotion()
  const ref = useRef<HTMLElement>(null)
  const { scrollYProgress } = useScroll({
    target: ref,
    offset: ["start end", "end start"]
  })
  const panelY = useTransform(scrollYProgress, [0, 0.35, 0.65, 1], [80, 0, 0, -60])
  const panelScale = useTransform(scrollYProgress, [0, 0.35, 0.65, 1], [0.96, 1, 1, 0.98])
  const panelOpacity = useTransform(scrollYProgress, [0, 0.18, 0.82, 1], [0.35, 1, 1, 0.85])

  return (
    <section
      ref={ref}
      className={cn("landing-snap-section relative flex min-h-screen flex-col justify-center py-24 md:py-32", className)}
      id={id}
    >
      {statement ? (
        <LandingSectionStatement index={statement.index} subtitle={statement.subtitle} title={statement.title} />
      ) : null}

      {reduceMotion ? (
        <div>{children}</div>
      ) : (
        <motion.div style={{ y: panelY, scale: panelScale, opacity: panelOpacity }}>{children}</motion.div>
      )}
    </section>
  )
}
