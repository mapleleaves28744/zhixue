import type { Metadata } from "next"
import "../styles/globals.css"

export const metadata: Metadata = {
  title: "智学工坊",
  description: "基于自进化学习智能体与 LLM Wiki 的个性化资源生成学习空间"
}

interface RootLayoutProps {
  children: React.ReactNode
}

export default function RootLayout({ children }: RootLayoutProps) {
  return (
    <html lang="zh-CN">
      <body>{children}</body>
    </html>
  )
}
