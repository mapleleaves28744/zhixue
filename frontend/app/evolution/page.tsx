"use client"

import { useCallback, useEffect, useState } from "react"
import {
  applyStrategy,
  listEvents,
  listStrategies,
  rollbackStrategy,
  type EvolutionEvent,
  type EvolutionStrategy,
} from "@/services/evolutionService"

const RISK_COLORS: Record<string, string> = {
  low: "#4caf50",
  medium: "#ff9800",
  high: "#f44336",
}

const STATUS_LABELS: Record<string, string> = {
  draft: "草稿",
  active: "生效中",
  superseded: "已替代",
  rolled_back: "已回滚",
}

export default function EvolutionPage() {
  const [strategies, setStrategies] = useState<EvolutionStrategy[]>([])
  const [events, setEvents] = useState<EvolutionEvent[]>([])
  const [loading, setLoading] = useState(true)
  const [activeTab, setActiveTab] = useState<"strategies" | "events">("strategies")
  const [filterStatus, setFilterStatus] = useState<string>("")
  const [selectedStrategy, setSelectedStrategy] = useState<EvolutionStrategy | null>(null)
  const [actionLoading, setActionLoading] = useState<string | null>(null)

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
      setSelectedStrategy(null)
    } finally {
      setActionLoading(null)
    }
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
            color: "#8a5a00",
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
      <p style={{ color: "#524434", marginBottom: 24 }}>
        查看、管理和回滚学习策略调整记录（与 /path-profile 自进化区块共用同一套 API）
      </p>

      {/* Tab 切换 */}
      <div style={{ display: "flex", gap: 8, marginBottom: 20 }}>
        {(["strategies", "events"] as const).map((tab) => (
          <button
            key={tab}
            onClick={() => setActiveTab(tab)}
            style={{
              padding: "8px 20px",
              borderRadius: 20,
              border: "none",
              cursor: "pointer",
              fontWeight: 500,
              background: activeTab === tab ? "#835400" : "#f0eded",
              color: activeTab === tab ? "#fff" : "#1c1b1b",
            }}
          >
            {tab === "strategies" ? "策略列表" : "分析事件"}
          </button>
        ))}
      </div>

      {activeTab === "strategies" && (
        <>
          {/* 状态筛选 */}
          <div style={{ display: "flex", gap: 8, marginBottom: 16 }}>
            {["", "draft", "active", "superseded", "rolled_back"].map((s) => (
              <button
                key={s}
                onClick={() => setFilterStatus(s)}
                style={{
                  padding: "4px 12px",
                  borderRadius: 12,
                  border: "1px solid #d7c3ae",
                  cursor: "pointer",
                  fontSize: 13,
                  background: filterStatus === s ? "#ffddb5" : "transparent",
                }}
              >
                {s ? STATUS_LABELS[s] : "全部"}
              </button>
            ))}
          </div>

          {loading ? (
            <p style={{ color: "#857462" }}>加载中…</p>
          ) : strategies.length === 0 ? (
            <div style={{ textAlign: "center", padding: 40, color: "#857462" }}>
              暂无策略记录
            </div>
          ) : (
            <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
              {strategies.map((s) => (
                <div
                  key={s.id}
                  onClick={() => setSelectedStrategy(s)}
                  style={{
                    padding: 16,
                    borderRadius: 16,
                    background: "#fff",
                    border: selectedStrategy?.id === s.id ? "2px solid #835400" : "1px solid #e5e2e1",
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
                      <span style={{ fontSize: 13, color: "#524434" }}>
                        风险: {s.risk_level}
                      </span>
                    </div>
                  </div>
                  <p style={{ marginTop: 8, fontSize: 14, color: "#524434", lineHeight: 1.5 }}>
                    {s.description}
                  </p>
                  <div style={{ marginTop: 8, fontSize: 12, color: "#857462" }}>
                    版本 {s.version_no} · {new Date(s.created_at).toLocaleString("zh-CN")}
                  </div>
                </div>
              ))}
            </div>
          )}

          {/* 策略详情面板 */}
          {selectedStrategy && (
            <div
              style={{
                marginTop: 20,
                padding: 20,
                borderRadius: 16,
                background: "#f6f3f2",
                border: "1px solid #d7c3ae",
              }}
            >
              <h3 style={{ fontSize: 18, fontWeight: 600, marginBottom: 12 }}>
                策略详情
              </h3>
              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12, marginBottom: 16 }}>
                <div>
                  <div style={{ fontSize: 12, color: "#857462" }}>调整前</div>
                  <pre style={{
                    padding: 12,
                    borderRadius: 8,
                    background: "#fff",
                    fontSize: 13,
                    overflow: "auto",
                    maxHeight: 200,
                  }}>
                    {JSON.stringify(selectedStrategy.before_value, null, 2)}
                  </pre>
                </div>
                <div>
                  <div style={{ fontSize: 12, color: "#857462" }}>调整后</div>
                  <pre style={{
                    padding: 12,
                    borderRadius: 8,
                    background: "#fff",
                    fontSize: 13,
                    overflow: "auto",
                    maxHeight: 200,
                  }}>
                    {JSON.stringify(selectedStrategy.after_value, null, 2)}
                  </pre>
                </div>
              </div>
              <div style={{ display: "flex", gap: 8 }}>
                {selectedStrategy.status === "draft" && (
                  <button
                    disabled={actionLoading === selectedStrategy.id}
                    onClick={() => handleApply(selectedStrategy.id)}
                    style={{
                      padding: "8px 20px",
                      borderRadius: 12,
                      border: "none",
                      background: "#835400",
                      color: "#fff",
                      cursor: "pointer",
                      fontWeight: 500,
                    }}
                  >
                    {actionLoading === selectedStrategy.id ? "处理中…" : "应用策略"}
                  </button>
                )}
                {selectedStrategy.status === "active" && selectedStrategy.previous_strategy_id && (
                  <button
                    disabled={actionLoading === selectedStrategy.id}
                    onClick={() => handleRollback(selectedStrategy.id)}
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
                <button
                  onClick={() => setSelectedStrategy(null)}
                  style={{
                    padding: "8px 20px",
                    borderRadius: 12,
                    border: "1px solid #d7c3ae",
                    background: "transparent",
                    cursor: "pointer",
                  }}
                >
                  关闭
                </button>
              </div>
            </div>
          )}
        </>
      )}

      {activeTab === "events" && (
        <>
          {loading ? (
            <p style={{ color: "#857462" }}>加载中…</p>
          ) : events.length === 0 ? (
            <div style={{ textAlign: "center", padding: 40, color: "#857462" }}>
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
                    <span style={{ fontSize: 13, color: "#857462" }}>
                      {new Date(e.created_at).toLocaleString("zh-CN")}
                    </span>
                  </div>
                  <p style={{ marginTop: 8, fontSize: 14, color: "#524434" }}>
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
