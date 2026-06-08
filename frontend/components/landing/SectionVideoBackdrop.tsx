"use client"

import { useEffect, useRef } from "react"

import { LANDING_VIDEO_SRC } from "@/components/landing/landingMedia"
import { useReducedMotion } from "@/components/landing/useReducedMotion"
import { cn } from "@/lib/utils"

type SectionVideoBackdropProps = {
  variant?: "scroll" | "cta"
  className?: string
}

export function SectionVideoBackdrop({ variant = "scroll", className }: SectionVideoBackdropProps) {
  const videoRef = useRef<HTMLVideoElement>(null)
  const reduceMotion = useReducedMotion()

  useEffect(() => {
    const video = videoRef.current
    if (!video || reduceMotion) {
      return
    }
    void video.play().catch(() => {
      // Autoplay may be blocked.
    })
  }, [reduceMotion])

  return (
    <div
      aria-hidden="true"
      className={cn(
        "pointer-events-none overflow-hidden",
        variant === "scroll" && "landing-scroll-video absolute inset-0 z-0 h-full min-h-full",
        variant === "cta" && "landing-cta-video absolute inset-0 z-0 rounded-[40px]",
        className
      )}
    >
      <div className="landing-section-video-fallback absolute inset-0" />
      {!reduceMotion ? (
        <>
          <video
            ref={videoRef}
            autoPlay
            className={cn(
              "absolute inset-0 h-full w-full object-cover",
              variant === "scroll" ? "opacity-[0.42]" : "opacity-[0.38]"
            )}
            loop
            muted
            playsInline
            src={LANDING_VIDEO_SRC}
          />
          <div
            className={cn(
              "absolute inset-0",
              variant === "scroll" ? "landing-section-video-overlay" : "landing-cta-video-overlay"
            )}
          />
        </>
      ) : null}
    </div>
  )
}
