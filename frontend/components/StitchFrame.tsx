"use client"

import type { CSSProperties } from "react"
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

export function StitchFrame({ title, src }: StitchFrameProps) {
  return (
    <AnimatePresence mode="wait">
      <motion.main
        animate={{ opacity: 1 }}
        className="stitch-shell"
        exit={{ opacity: 0 }}
        initial={{ opacity: 0 }}
        key={src}
        style={shellStyle}
        transition={{ duration: 0.2, ease: "easeOut" }}
      >
        <iframe className="stitch-frame" key={src} src={src} style={frameStyle} title={title} />
      </motion.main>
    </AnimatePresence>
  )
}
