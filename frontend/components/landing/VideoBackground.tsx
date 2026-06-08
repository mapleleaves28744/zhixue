"use client"

import { useEffect, useRef } from "react"

import { LANDING_VIDEO_SRC } from "@/components/landing/landingMedia"
import { useReducedMotion } from "@/components/landing/useReducedMotion"

export function VideoBackground() {
  const videoRef = useRef<HTMLVideoElement>(null)
  const reduceMotion = useReducedMotion()

  useEffect(() => {
    const video = videoRef.current
    if (!video || reduceMotion) {
      return
    }
    void video.play().catch(() => {
      // Autoplay may be blocked; static gradient remains visible.
    })
  }, [reduceMotion])

  return (
    <div aria-hidden="true" className="absolute inset-0 z-0 overflow-hidden">
      <div className="landing-video-fallback absolute inset-0" />
      {!reduceMotion ? (
        <>
          <video
            ref={videoRef}
            autoPlay
            className="absolute inset-0 h-full w-full object-cover opacity-[0.55]"
            loop
            muted
            playsInline
            src={LANDING_VIDEO_SRC}
          />
          <div className="landing-video-overlay absolute inset-0" />
        </>
      ) : null}
    </div>
  )
}
