"use client"

import type { CSSProperties } from "react"
import { useEffect, useState } from "react"
import { AnimatePresence, motion } from "framer-motion"

type StitchFrameProps = {
  title: string
  src: string
}

const shellStyle: CSSProperties = {
  width: "100vw",
  height: "100dvh",
  minHeight: "100vh",
  margin: 0,
  overflow: "hidden",
  background: "#faf9f8"
}

const frameStyle: CSSProperties = {
  display: "block",
  width: "100%",
  height: "100%",
  border: 0,
  background: "#faf9f8"
}

function buildFrameSrc(src: string): string {
  if (typeof window === "undefined") {
    return src
  }
  const apiBase =
    process.env.NEXT_PUBLIC_API_BASE_URL?.replace(/\/$/, "") ||
    `${window.location.origin}/api/v1`
  const separator = src.includes("?") ? "&" : "?"
  return `${src}${separator}api_base=${encodeURIComponent(apiBase)}`
}

export function StitchFrame({ title, src }: StitchFrameProps) {
  const [frameSrc, setFrameSrc] = useState(src)

  useEffect(() => {
    setFrameSrc(buildFrameSrc(src))
  }, [src])

  return (
    <AnimatePresence mode="wait">
      <motion.main
        animate={{ opacity: 1 }}
        className="stitch-shell"
        exit={{ opacity: 0 }}
        initial={{ opacity: 0 }}
        key={frameSrc}
        style={shellStyle}
        transition={{ duration: 0.2, ease: "easeOut" }}
      >
        <iframe className="stitch-frame" key={frameSrc} src={frameSrc} style={frameStyle} title={title} />
      </motion.main>
    </AnimatePresence>
  )
}
