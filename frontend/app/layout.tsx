import type { Metadata } from "next"
import type { ReactNode } from "react"

import { Toaster } from "@/components/ui/sonner"

import "../styles/globals.css"

export const metadata: Metadata = {
  title: "智学工坊",
  description: "基于自进化学习智能体与 LLM Wiki 的个性化学习空间"
}

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="zh-CN">
      <head>
        <link
          href="/fonts/material-symbols.css"
          rel="stylesheet"
        />
      </head>
      <body>
        {children}
        <Toaster />
      </body>
    </html>
  )
}
