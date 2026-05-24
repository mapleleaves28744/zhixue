"use client"

import { useState } from "react"
import { Button } from "@/components/ui/button"
import type { EvolutionStrategy } from "@/types/evolution"

interface StrategyComparisonTableProps {
  strategies: EvolutionStrategy[]
  onApply: (strategyId: string) => Promise<void>
  onRollback: (strategyId: string) => Promise<void>
  onAnalyze: () => void
  analyzing: boolean
}

const RISK_STYLES: Record<string, string> = {
  low: "bg-green-100 text-green-700",
  medium: "bg-primary-fixed text-on-primary-fixed-variant",
  high: "bg-error text-white",
}

const RISK_LABELS: Record<string, string> = {
  low: "低风险",
  medium: "中风险",
  high: "高风险",
}

const STATUS_LABELS: Record<string, string> = {
  draft: "待确认",
  active: "已生效",
  superseded: "已替代",
  rolled_back: "已回滚",
}

const STRATEGY_TYPE_LABELS: Record<string, string> = {
  difficulty: "难度调节",
  knowledge_skip: "知识跳跃",
  interaction: "交互偏好",
  recommendation: "推荐策略",
  prompt_style: "提示词风格",
  resource_type: "资源类型",
}

export function StrategyComparisonTable({
  strategies,
  onApply,
  onRollback,
  onAnalyze,
  analyzing,
}: StrategyComparisonTableProps) {
  const [loadingId, setLoadingId] = useState<string | null>(null)

  const draftStrategies = strategies.filter((s) => s.status === "draft")
  const activeStrategies = strategies.filter((s) => s.status === "active")

  const handleApply = async (id: string) => {
    setLoadingId(id)
    try {
      await onApply(id)
    } finally {
      setLoadingId(null)
    }
  }

  const handleRollback = async (id: string) => {
    setLoadingId(id)
    try {
      await onRollback(id)
    } finally {
      setLoadingId(null)
    }
  }

  const displayStrategies = draftStrategies.length > 0 ? draftStrategies : activeStrategies

  return (
    <section className="glass-card rounded-xl p-8 overflow-hidden">
      <div className="flex justify-between items-center mb-6">
        <h3 className="font-headline-md text-headline-md flex items-center">
          <span
            className="material-symbols-outlined mr-2 text-primary"
            style={{ fontVariationSettings: "'FILL' 1" }}
          >
            bolt
          </span>
          自进化策略
        </h3>
        <div className="flex space-x-2">
          <Button
            variant="outline"
            size="sm"
            onClick={onAnalyze}
            disabled={analyzing}
          >
            {analyzing ? "分析中..." : "触发分析"}
          </Button>
        </div>
      </div>

      {displayStrategies.length === 0 ? (
        <div className="flex flex-col items-center justify-center py-12 text-on-surface-variant">
          <span className="material-symbols-outlined text-4xl mb-3 opacity-40">psychology</span>
          <p className="text-body-md mb-2">暂无策略建议</p>
          <p className="text-label-md text-outline">点击"触发分析"，让 EvolutionAgent 基于学习数据生成策略建议</p>
        </div>
      ) : (
        <>
          <div className="overflow-x-auto">
            <table className="w-full text-left border-separate border-spacing-y-2">
              <thead>
                <tr className="text-label-sm text-on-surface-variant uppercase tracking-wider">
                  <th className="px-4 pb-2">策略维度</th>
                  <th className="px-4 pb-2">当前方案</th>
                  <th className="px-4 pb-2">进化预测</th>
                  <th className="px-4 pb-2">风险等级</th>
                  <th className="px-4 pb-2">状态</th>
                  <th className="px-4 pb-2 text-right">操作</th>
                </tr>
              </thead>
              <tbody className="text-body-md">
                {displayStrategies.map((strategy) => (
                  <tr
                    key={strategy.id}
                    className={`hover:bg-white transition-colors rounded-xl overflow-hidden group ${
                      strategy.risk_level === "high"
                        ? "bg-error-container/20 border-l-4 border-error"
                        : "bg-surface-container-low/50"
                    }`}
                  >
                    <td className="p-4 rounded-l-xl font-bold">
                      {STRATEGY_TYPE_LABELS[strategy.strategy_type] || strategy.strategy_type}
                    </td>
                    <td className="p-4 text-on-surface-variant">
                      {formatValue(strategy.before_value)}
                    </td>
                    <td className="p-4 font-bold text-primary">
                      {formatValue(strategy.after_value)}
                    </td>
                    <td className="p-4">
                      <span
                        className={`px-2.5 py-0.5 rounded-full text-label-sm font-bold ${
                          RISK_STYLES[strategy.risk_level] || RISK_STYLES.medium
                        }`}
                      >
                        {RISK_LABELS[strategy.risk_level] || strategy.risk_level}
                      </span>
                    </td>
                    <td className="p-4">
                      <span className="text-label-sm text-on-surface-variant">
                        {STATUS_LABELS[strategy.status] || strategy.status}
                      </span>
                    </td>
                    <td className="p-4 rounded-r-xl text-right space-x-2">
                      {strategy.status === "draft" && (
                        <Button
                          size="sm"
                          onClick={() => handleApply(strategy.id)}
                          disabled={loadingId === strategy.id}
                        >
                          {loadingId === strategy.id ? "处理中..." : "确认"}
                        </Button>
                      )}
                      {strategy.status === "active" && strategy.previous_strategy_id && (
                        <Button
                          variant="outline"
                          size="sm"
                          onClick={() => handleRollback(strategy.id)}
                          disabled={loadingId === strategy.id}
                        >
                          {loadingId === strategy.id ? "处理中..." : "回滚"}
                        </Button>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {draftStrategies.length > 0 && (
            <div className="mt-6 flex items-center justify-between text-label-sm text-on-surface-variant">
              <div className="flex items-center">
                <span className="material-symbols-outlined text-base mr-1">info</span>
                高风险策略可能显著改变学习节奏，建议查看证据后操作。
              </div>
              <p>{draftStrategies.length} 条待确认</p>
            </div>
          )}
        </>
      )}
    </section>
  )
}

function formatValue(value: Record<string, unknown>): string {
  if (!value || Object.keys(value).length === 0) return "-"
  const entries = Object.entries(value)
  if (entries.length === 1) return String(entries[0][1])
  return entries.map(([k, v]) => `${k}: ${v}`).join(", ")
}
