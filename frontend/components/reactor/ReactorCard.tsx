"use client"

import type { ReactorCard as ReactorCardType } from "./types"

interface ReactorCardProps {
  card: ReactorCardType
}

const STATUS_ICONS: Record<string, string> = {
  streaming: "⏳",
  complete: "✅",
  error: "❌",
}

export function ReactorCard({ card }: ReactorCardProps) {
  return (
    <div
      style={{
        padding: 16,
        borderRadius: 16,
        background: "#fff",
        border: card.status === "error" ? "1px solid #ba1a1a" : "1px solid #e5e2e1",
        boxShadow: "0 1px 4px rgba(0,0,0,0.04)",
        opacity: card.status === "streaming" ? 0.85 : 1,
        transition: "opacity 0.3s ease",
      }}
    >
      {/* 卡片标题栏 */}
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          marginBottom: 8,
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
          <TypeBadge type={card.type} />
          <span style={{ fontWeight: 600, fontSize: 15 }}>{card.title}</span>
        </div>
        <span style={{ fontSize: 14 }}>{STATUS_ICONS[card.status] || ""}</span>
      </div>

      {/* 卡片内容 */}
      <div
        style={{
          fontSize: 14,
          lineHeight: 1.7,
          color: "#1c1b1b",
          whiteSpace: "pre-wrap",
          wordBreak: "break-word",
        }}
      >
        {card.content || (card.status === "streaming" ? "正在生成…" : "暂无内容")}
      </div>

      {/* 流式中的光标动画 */}
      {card.status === "streaming" && (
        <div
          style={{
            display: "inline-block",
            width: 2,
            height: 16,
            background: "#835400",
            marginLeft: 2,
            animation: "blink 1s step-end infinite",
          }}
        />
      )}
    </div>
  )
}

function TypeBadge({ type }: { type: string }) {
  const colors: Record<string, { bg: string; text: string }> = {
    text: { bg: "#e3f2fd", text: "#1565c0" },
    quiz: { bg: "#fce4ec", text: "#c62828" },
    resource: { bg: "#e8f5e9", text: "#2e7d32" },
    wiki: { bg: "#fff3e0", text: "#e65100" },
  }
  const style = colors[type] || { bg: "#f5f5f5", text: "#616161" }

  return (
    <span
      style={{
        padding: "2px 8px",
        borderRadius: 8,
        fontSize: 11,
        fontWeight: 500,
        background: style.bg,
        color: style.text,
      }}
    >
      {type}
    </span>
  )
}
