"use client"

import { useCallback, useEffect, useState, type CSSProperties } from "react"
import {
  applyStrategy,
  listEvents,
  listStrategies,
  rejectStrategy,
  rollbackStrategy,
  type EvolutionEvent,
  type EvolutionStrategy,
} from "@/services/evolutionService"

const RISK_COLORS: Record<string, string> = {
  low: "#4caf50",
  medium: "#f9a826",
  high: "#f44336",
}

const C = {
  primary: "#835400",
  primaryLight: "#ffddb5",
  primaryFixed: "#f9a826",
  surface: "#fcf9f8",
  surfaceContainer: "#f0eded",
  onSurfaceVariant: "#524434",
  onSurface: "#1c1b1b",
  border: "#d7c3ae",
  panelBg: "#f6f3f2",
  link: "#674100",
} as const

const STATUS_LABELS: Record<string, string> = {
  draft: "草稿",
  active: "生效中",
  superseded: "已替代",
  rolled_back: "已回滚",
  rejected: "已拒绝",
}

function formatSnapshotValue(value: unknown): string {
  if (value == null) return "（无）"
  if (typeof value === "string") return value
  if (typeof value === "object") {
    const obj = value as Record<string, unknown>
    if (typeof obj.summary === "string" && obj.summary.trim()) return obj.summary
    if (typeof obj.description === "string" && obj.description.trim()) return obj.description
    if (typeof obj.change_summary === "string" && obj.change_summary.trim()) return obj.change_summary
  }
  try {
    return JSON.stringify(value, null, 2)
  } catch {
    return String(value)
  }
}

const snapshotPreStyle: CSSProperties = {
  padding: 12,
  borderRadius: 8,
  background: "#fff",
  fontSize: 13,
  lineHeight: 1.6,
  overflow: "auto",
  maxHeight: 240,
  whiteSpace: "pre-wrap",
  wordBreak: "break-word",
  overflowWrap: "anywhere",
}

export default function EvolutionPage() {
  const [strategies, setStrategies] = useState<EvolutionStrategy[]>([])
  const [events, setEvents] = useState<EvolutionEvent[]>([])
  const [loading, setLoading] = useState(true)
  const [activeTab, setActiveTab] = useState<"strategies" | "events">("strategies")
  const [filterStatus, setFilterStatus] = useState<string>("")
  const [selectedStrategy, setSelectedStrategy] = useState<EvolutionStrategy | null>(null)
  const [actionLoading, setActionLoading] = useState<string | null>(null)

  const closeDetail = useCallback(() => {
    setSelectedStrategy(null)
  }, [])

  const fetchData = useCallback(async () => {
    setLoading(true)
    try {
      const [stratRes, eventRes] = await Promise.all([
        listStrategies({ status: filterStatus || undefined }),
        listEvents(),
      ])
      setStrategies(stratRes.items)
      setEvents(eventRes.items)
    } catch {
      // 静默处理
    } finally {
      setLoading(false)
    }
  }, [filterStatus])

  useEffect(() => {
    fetchData()
  }, [fetchData])

  useEffect(() => {
    if (!selectedStrategy) return
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") closeDetail()
    }
    window.addEventListener("keydown", onKeyDown)
    return () => window.removeEventListener("keydown", onKeyDown)
  }, [selectedStrategy, closeDetail])

  const handleApply = async (id: string) => {
    setActionLoading(id)
    try {
      await applyStrategy(id)
      await fetchData()
    } finally {
      setActionLoading(null)
    }
  }

  const handleRollback = async (id: string) => {
    setActionLoading(id)
    try {
      await rollbackStrategy(id)
      await fetchData()
      closeDetail()
    } finally {
      setActionLoading(null)
    }
  }

  const handleReject = async (id: string) => {
    setActionLoading(id)
    try {
      await rejectStrategy(id)
      await fetchData()
      closeDetail()
    } finally {
      setActionLoading(null)
    }
  }

  const toggleStrategy = (strategy: EvolutionStrategy) => {
    setSelectedStrategy((prev) => (prev?.id === strategy.id ? null : strategy))
  }

  return (
    <div style={{ maxWidth: 960, margin: "0 auto", padding: "24px 16px" }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: 12, marginBottom: 8, flexWrap: "wrap" }}>
        <h1 style={{ fontSize: 24, fontWeight: 600, margin: 0 }}>自进化策略仪表盘</h1>
        <a
          href="/path-profile"
          style={{
            fontSize: 14,
            fontWeight: 600,
            color: "#4338CA",
            textDecoration: "none",
            padding: "8px 14px",
            borderRadius: 12,
            border: "1px solid rgba(138,90,0,0.2)",
            background: "rgba(255,255,255,0.8)",
          }}
        >
          返回学习路径与画像
        </a>
      </div>
      <p style={{ color: C.onSurfaceVariant, marginBottom: 24 }}>
        查看、管理和回滚学习策略调整记录（与 /path-profile 自进化区块共用同一套 API）
      </p>

      <div style={{ display: "flex", gap: 8, marginBottom: 20 }}>
        {(["strategies", "events"] as const).map((tab) => (
          <button
            key={tab}
            type="button"
            onClick={() => {
              setActiveTab(tab)
              closeDetail()
            }}
            style={{
              padding: "8px 20px",
              borderRadius: 20,
              border: "none",
              cursor: "pointer",
              fontWeight: 500,
              background: activeTab === tab ? C.primary : C.surfaceContainer,
              color: activeTab === tab ? "#fff" : "#1c1b1b",
            }}
          >
            {tab === "strategies" ? "策略列表" : "分析事件"}
          </button>
        ))}
      </div>

      {activeTab === "strategies" && (
        <>
          <div style={{ display: "flex", gap: 8, marginBottom: 16 }}>
            {["", "draft", "active", "superseded", "rolled_back", "rejected"].map((s) => (
              <button
                key={s}
                type="button"
                onClick={() => {
                  setFilterStatus(s)
                  closeDetail()
                }}
                style={{
                  padding: "4px 12px",
                  borderRadius: 12,
                  border: `1px solid ${C.border}`,
                  cursor: "pointer",
                  fontSize: 13,
                  background: filterStatus === s ? C.primaryFixed : "transparent",
                }}
              >
                {s ? STATUS_LABELS[s] : "全部"}
              </button>
            ))}
          </div>

          {loading ? (
            <p style={{ color: C.onSurfaceVariant }}>加载中…</p>
          ) : strategies.length === 0 ? (
            <div style={{ textAlign: "center", padding: 40, color: C.onSurfaceVariant }}>
              暂无策略记录
            </div>
          ) : (
            <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
              {strategies.map((s) => (
                <div
                  key={s.id}
                  role="button"
                  tabIndex={0}
                  onClick={() => toggleStrategy(s)}
                  onKeyDown={(event) => {
                    if (event.key === "Enter" || event.key === " ") {
                      event.preventDefault()
                      toggleStrategy(s)
                    }
                  }}
                  style={{
                    padding: 16,
                    borderRadius: 16,
                    background: "#fff",
                    border: selectedStrategy?.id === s.id ? `2px solid ${C.primary}` : `1px solid ${C.border}`,
                    cursor: "pointer",
                    boxShadow: "0 1px 4px rgba(0,0,0,0.04)",
                  }}
                >
                  <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                    <div>
                      <span style={{ fontWeight: 600 }}>{s.strategy_type}</span>
                      <span
                        style={{
                          marginLeft: 8,
                          padding: "2px 8px",
                          borderRadius: 8,
                          fontSize: 12,
                          background: s.status === "active" ? "#e8f5e9" : s.status === "draft" ? "#fff3e0" : "#f5f5f5",
                        }}
                      >
                        {STATUS_LABELS[s.status] || s.status}
                      </span>
                    </div>
                    <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                      <span
                        style={{
                          display: "inline-block",
                          width: 10,
                          height: 10,
                          borderRadius: "50%",
                          background: RISK_COLORS[s.risk_level] || "#999",
                        }}
                      />
                      <span style={{ fontSize: 13, color: C.onSurface }}>
                        风险: {s.risk_level}
                      </span>
                    </div>
                  </div>
                  <p style={{ marginTop: 8, fontSize: 14, color: C.onSurface, lineHeight: 1.5 }}>
                    {s.description}
                  </p>
                  <div style={{ marginTop: 8, fontSize: 12, color: C.onSurfaceVariant }}>
                    版本 {s.version_no} · {new Date(s.created_at).toLocaleString("zh-CN")}
                  </div>
                </div>
              ))}
            </div>
          )}

          {selectedStrategy && (
            <div
              role="dialog"
              aria-modal="true"
              aria-labelledby="strategy-detail-title"
              onClick={closeDetail}
              style={{
                position: "fixed",
                inset: 0,
                zIndex: 1100,
                background: "rgba(28, 27, 27, 0.45)",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                padding: 16,
              }}
            >
              <div
                onClick={(event) => event.stopPropagation()}
                style={{
                  width: "min(720px, 100%)",
                  maxHeight: "min(88vh, 900px)",
                  overflow: "auto",
                  padding: 20,
                  borderRadius: 16,
                  background: C.panelBg,
                  border: `1px solid ${C.border}`,
                  boxShadow: "0 12px 40px rgba(0,0,0,0.18)",
                }}
              >
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: 8, gap: 12 }}>
                  <div>
                    <h3 id="strategy-detail-title" style={{ fontSize: 18, fontWeight: 600, margin: 0 }}>
                      策略详情
                    </h3>
                    <p style={{ margin: "6px 0 0", fontSize: 12, color: C.onSurfaceVariant }}>
                      当前状态：
                      <strong style={{ color: C.onSurface }}>{STATUS_LABELS[selectedStrategy.status] || selectedStrategy.status}</strong>
                      {" · "}
                      收起面板不会改变策略状态；草稿可拒绝，已生效可回滚。
                    </p>
                  </div>
                  <button
                    type="button"
                    onClick={(event) => {
                      event.preventDefault()
                      event.stopPropagation()
                      closeDetail()
                    }}
                    style={{
                      padding: "6px 14px",
                      borderRadius: 12,
                      border: `1px solid ${C.border}`,
                      background: "#fff",
                      cursor: "pointer",
                      fontSize: 13,
                      fontWeight: 600,
                      color: C.onSurface,
                      flexShrink: 0,
                    }}
                  >
                    收起详情
                  </button>
                </div>
                <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12, marginBottom: 16 }}>
                  <div>
                    <div style={{ fontSize: 12, color: C.onSurfaceVariant, marginBottom: 6 }}>调整前</div>
                    <pre style={snapshotPreStyle}>{formatSnapshotValue(selectedStrategy.before_value)}</pre>
                  </div>
                  <div>
                    <div style={{ fontSize: 12, color: C.onSurfaceVariant, marginBottom: 6 }}>调整后</div>
                    <pre style={snapshotPreStyle}>{formatSnapshotValue(selectedStrategy.after_value)}</pre>
                  </div>
                </div>
                <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
                  {selectedStrategy.status === "draft" && (
                    <>
                      <button
                        type="button"
                        disabled={actionLoading === selectedStrategy.id}
                        onClick={(event) => {
                          event.stopPropagation()
                          void handleApply(selectedStrategy.id)
                        }}
                        style={{
                          padding: "8px 20px",
                          borderRadius: 12,
                          border: "none",
                          background: C.primary,
                          color: "#fff",
                          cursor: "pointer",
                          fontWeight: 500,
                        }}
                      >
                        {actionLoading === selectedStrategy.id ? "处理中…" : "确认并生效"}
                      </button>
                      <button
                        type="button"
                        disabled={actionLoading === selectedStrategy.id}
                        onClick={(event) => {
                          event.stopPropagation()
                          if (window.confirm("确认拒绝这条策略草案？拒绝后状态将变为「已拒绝」。")) {
                            void handleReject(selectedStrategy.id)
                          }
                        }}
                        style={{
                          padding: "8px 20px",
                          borderRadius: 12,
                          border: "1px solid #ba1a1a",
                          background: "transparent",
                          color: "#ba1a1a",
                          cursor: "pointer",
                          fontWeight: 500,
                        }}
                      >
                        {actionLoading === selectedStrategy.id ? "处理中…" : "拒绝草案"}
                      </button>
                    </>
                  )}
                  {selectedStrategy.status === "active" && selectedStrategy.previous_strategy_id && (
                    <button
                      type="button"
                      disabled={actionLoading === selectedStrategy.id}
                      onClick={(event) => {
                        event.stopPropagation()
                        if (window.confirm("确认回滚到上一版本？当前策略将变为「已回滚」。")) {
                          void handleRollback(selectedStrategy.id)
                        }
                      }}
                      style={{
                        padding: "8px 20px",
                        borderRadius: 12,
                        border: "1px solid #ba1a1a",
                        background: "transparent",
                        color: "#ba1a1a",
                        cursor: "pointer",
                        fontWeight: 500,
                      }}
                    >
                      {actionLoading === selectedStrategy.id ? "处理中…" : "回滚到上一版本"}
                    </button>
                  )}
                  {selectedStrategy.status === "active" && !selectedStrategy.previous_strategy_id && (
                    <p style={{ margin: 0, fontSize: 13, color: C.onSurfaceVariant }}>
                      这是首个生效版本，无法回滚。若不想采用新草案，请对草稿使用「拒绝草案」。
                    </p>
                  )}
                </div>
              </div>
            </div>
          )}
        </>
      )}

      {activeTab === "events" && (
        <>
          {loading ? (
            <p style={{ color: C.onSurfaceVariant }}>加载中…</p>
          ) : events.length === 0 ? (
            <div style={{ textAlign: "center", padding: 40, color: C.onSurfaceVariant }}>
              暂无分析事件
            </div>
          ) : (
            <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
              {events.map((e) => (
                <div
                  key={e.id}
                  style={{
                    padding: 16,
                    borderRadius: 16,
                    background: "#fff",
                    border: "1px solid #e5e2e1",
                  }}
                >
                  <div style={{ display: "flex", justifyContent: "space-between" }}>
                    <span style={{ fontWeight: 500 }}>
                      {e.trigger_type === "auto_diagnosis" ? "诊断触发" : "手动触发"}
                    </span>
                    <span style={{ fontSize: 13, color: C.onSurfaceVariant }}>
                      {new Date(e.created_at).toLocaleString("zh-CN")}
                    </span>
                  </div>
                  <p style={{ marginTop: 8, fontSize: 14, color: C.onSurface }}>
                    {e.focus}
                  </p>
                </div>
              ))}
            </div>
          )}
        </>
      )}
    </div>
  )
}
