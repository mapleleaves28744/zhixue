"use client"

import { motion, useAnimationControls, useInView, useReducedMotion } from "framer-motion"
import { useEffect, useRef, type ReactNode } from "react"

import { useScrollDirectionRef } from "@/components/landing/ScrollDirectionProvider"
import { cn } from "@/lib/utils"

const EASE = [0.22, 1, 0.36, 1] as const

function useReplayOnEnter(options: {
  margin?: `${number}${"px" | "%"} ${number}${"px" | "%"} ${number}${"px" | "%"} ${number}${"px" | "%"}`
  delay?: number
  enterY?: number
  replayY?: number
}) {
  const { margin = "-6% 0px -4% 0px", delay = 0, enterY = 36, replayY = 18 } = options
  const scrollDirectionRef = useScrollDirectionRef()
  const ref = useRef<HTMLDivElement>(null)
  const inView = useInView(ref, { margin, amount: 0.12 })
  const controls = useAnimationControls()
  const wasInView = useRef(false)
  const hasEverShown = useRef(false)

  useEffect(() => {
    if (inView && !wasInView.current) {
      const isFirst = !hasEverShown.current
      if (isFirst) {
        hasEverShown.current = true
      }

      const magnitude = isFirst ? enterY : replayY
      const sign = scrollDirectionRef.current === "down" ? 1 : -1
      const startY = magnitude * sign

      void controls.start({
        opacity: 1,
        y: [startY, 0],
        transition: {
          duration: isFirst ? 0.65 : 0.52,
          delay: isFirst ? delay : delay * 0.6,
          ease: EASE
        }
      })
    }
    wasInView.current = inView
  }, [inView, controls, delay, enterY, replayY, scrollDirectionRef])

  return { ref, controls, enterY }
}

type LandingRevealProps = {
  children: ReactNode
  className?: string
  delay?: number
  y?: number
}

export function LandingReveal({ children, className, delay = 0, y = 36 }: LandingRevealProps) {
  const reduceMotion = useReducedMotion()
  const { ref, controls, enterY } = useReplayOnEnter({
    margin: "-8% 0px -6% 0px",
    delay,
    enterY: y,
    replayY: Math.round(y * 0.5)
  })

  if (reduceMotion) {
    return <div className={className}>{children}</div>
  }

  return (
    <motion.div
      ref={ref}
      animate={controls}
      className={className}
      initial={{ opacity: 0, y: enterY }}
    >
      {children}
    </motion.div>
  )
}

type LandingMotionCardProps = {
  children: ReactNode
  className?: string
  index?: number
  float?: boolean
}

export function LandingMotionCard({ children, className, index = 0, float = false }: LandingMotionCardProps) {
  const reduceMotion = useReducedMotion()
  const { ref, controls, enterY } = useReplayOnEnter({
    margin: "-6% 0px -4% 0px",
    delay: index * 0.08,
    enterY: float ? 28 : 40,
    replayY: float ? 14 : 20
  })

  if (reduceMotion) {
    return <div className={className}>{children}</div>
  }

  return (
    <motion.div
      ref={ref}
      animate={controls}
      className={cn("landing-motion-card", className)}
      initial={{ opacity: 0, y: enterY }}
      whileHover={{
        scale: 1.03,
        transition: { type: "spring", stiffness: 320, damping: 22 }
      }}
    >
      <div
        className={cn(float && "landing-float-card h-full")}
        style={float ? { animationDelay: `${index * 0.65}s` } : undefined}
      >
        {children}
      </div>
    </motion.div>
  )
}
