import type { CSSProperties } from "react"

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
    <main className="stitch-shell" style={shellStyle}>
      <iframe className="stitch-frame" src={src} style={frameStyle} title={title} />
    </main>
  )
}
