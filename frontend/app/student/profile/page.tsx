"use client"

import { useEffect, useState, useCallback } from "react"
import { toast } from "sonner"
import { AppShell } from "@/components/layout/AppShell"
import { studentNavItems } from "@/components/layout/StudentSidebar"
import { ProfileSummaryCard } from "@/components/profile/ProfileSummaryCard"
import { StrategyComparisonTable } from "@/components/evolution/StrategyComparisonTable"
import { Button } from "@/components/ui/button"
import { getProfile, getProfileSummary, getPreferences, rebuildProfile } from "@/services/profileService"
import { analyze, listStrategies, applyStrategy, rollbackStrategy } from "@/services/evolutionService"
import { listMemories } from "@/services/memoryService"
import type { ProfileSummary, StudentProfile, LearningPreference } from "@/types/profile"
import type { EvolutionStrategy } from "@/types/evolution"
import type { StudentMemory } from "@/types/memory"

export default function StudentProfilePage() {
  const [profile, setProfile] = useState<StudentProfile | null>(null)
  const [summary, setSummary] = useState<ProfileSummary | null>(null)
  const [preferences, setPreferences] = useState<LearningPreference[]>([])
  const [strategies, setStrategies] = useState<EvolutionStrategy[]>([])
  const [memories, setMemories] = useState<StudentMemory[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [rebuilding, setRebuilding] = useState(false)
  const [analyzing, setAnalyzing] = useState(false)

  const courseId = "00000000-0000-0000-0000-000000000001"

  useEffect(() => {
    loadData()
  }, [])

  const loadData = async () => {
    try {
      setLoading(true)
      setError(null)
      const [profileData, summaryData, prefsData, strategiesData, memoriesData] = await Promise.all([
        getProfile(),
        getProfileSummary(),
        getPreferences(),
        listStrategies({ courseId, status: "active" }).catch(() => ({ items: [], total: 0 })),
        listMemories().catch(() => []),
      ])
      setProfile(profileData)
      setSummary(summaryData)
      setPreferences(prefsData)
      setStrategies(strategiesData.items)
      setMemories(memoriesData)
    } catch (err) {
      const msg = err instanceof Error ? err.message : "加载画像失败"
      setError(msg)
    } finally {
      setLoading(false)
    }
  }

  const handleRebuild = async () => {
    try {
      setRebuilding(true)
      const updated = await rebuildProfile()
      setProfile(updated)
      const summaryData = await getProfileSummary()
      setSummary(summaryData)
      toast.success("画像重建完成")
    } catch (err) {
      const msg = err instanceof Error ? err.message : "重建失败"
      toast.error(msg)
    } finally {
      setRebuilding(false)
    }
  }

  const handleAnalyze = useCallback(async () => {
    try {
      setAnalyzing(true)
      const result = await analyze(courseId, "学习策略优化")
      setStrategies((prev) => [...result.strategies, ...prev])
      toast.success(`分析完成，生成 ${result.strategies_count} 条策略建议`)
    } catch (err) {
      const msg = err instanceof Error ? err.message : "分析失败"
      toast.error(msg)
    } finally {
      setAnalyzing(false)
    }
  }, [courseId])

  const handleApply = useCallback(async (strategyId: string) => {
    try {
      const updated = await applyStrategy(strategyId)
      setStrategies((prev) =>
        prev.map((s) => {
          if (s.id === strategyId) return updated
          if (s.strategy_type === updated.strategy_type && s.status === "active" && s.id !== strategyId) {
            return { ...s, status: "superseded" }
          }
          return s
        })
      )
      toast.success("策略已生效")
    } catch (err) {
      const msg = err instanceof Error ? err.message : "应用失败"
      toast.error(msg)
    }
  }, [])

  const handleRollback = useCallback(async (strategyId: string) => {
    try {
      const restored = await rollbackStrategy(strategyId)
      setStrategies((prev) =>
        prev.map((s) => {
          if (s.id === strategyId) return { ...s, status: "rolled_back" }
          if (s.id === restored.id) return restored
          return s
        })
      )
      toast.success("已回滚到上一版本")
    } catch (err) {
      const msg = err instanceof Error ? err.message : "回滚失败"
      toast.error(msg)
    }
  }, [])

  return (
    <AppShell title="学习路径与个人模型" navItems={studentNavItems}>
      <div className="grid grid-cols-12 gap-6">
        {/* 左侧：学生画像摘要 */}
        <div className="col-span-12 lg:col-span-4">
          {loading ? (
            <div className="glass-card rounded-xl p-8 flex items-center justify-center h-64">
              <span className="material-symbols-outlined animate-spin text-primary text-3xl">progress_activity</span>
            </div>
          ) : error ? (
            <div className="glass-card rounded-xl p-8 flex flex-col items-center justify-center h-64 text-on-surface-variant">
              <span className="material-symbols-outlined text-4xl mb-3 text-error">error</span>
              <p className="text-body-md mb-4">{error}</p>
              <Button onClick={loadData} variant="outline" size="sm">
                <span className="material-symbols-outlined text-[18px] mr-1">refresh</span>
                重试
              </Button>
            </div>
          ) : summary ? (
            <ProfileSummaryCard
              summary={summary}
              preferences={preferences}
              onRebuild={handleRebuild}
              rebuilding={rebuilding}
            />
          ) : (
            <div className="glass-card rounded-xl p-8 flex flex-col items-center justify-center h-64 text-on-surface-variant">
              <span className="material-symbols-outlined text-4xl mb-3 opacity-40">person</span>
              <p className="text-body-md">暂无画像数据</p>
              <Button onClick={handleRebuild} className="mt-4" disabled={rebuilding}>
                {rebuilding ? "生成中..." : "生成画像"}
              </Button>
            </div>
          )}
        </div>

        {/* 右侧 */}
        <div className="col-span-12 lg:col-span-8 space-y-6">
          {/* 推荐学习路径 */}
          <section className="glass-card rounded-xl p-8 overflow-hidden">
            <div className="flex justify-between items-center mb-6">
              <h3 className="font-headline-md text-headline-md flex items-center">
                <span className="material-symbols-outlined mr-2 text-primary">route</span>
                推荐学习路径
              </h3>
              <span className="bg-primary/10 text-primary px-4 py-1 rounded-full text-label-sm uppercase tracking-wider">AI 定制计划</span>
            </div>
            <div className="relative flex items-center justify-between pb-6 overflow-x-auto">
              <div className="absolute top-5 left-0 w-full h-[2px] bg-outline-variant/40" />
              {["基础概念", "核心原理", "进阶应用", "综合实战"].map((step, i) => (
                <div key={i} className="relative z-10 flex flex-col items-center min-w-[160px]">
                  <div className={`w-10 h-10 rounded-full flex items-center justify-center mb-4 shadow-lg ${
                    i === 0
                      ? "bg-primary text-white shadow-primary/20"
                      : "bg-surface-container-high border border-outline-variant text-outline"
                  }`}>
                    <span className="material-symbols-outlined">{i === 0 ? "check" : i === 1 ? "pending" : "lock"}</span>
                  </div>
                  <div className="text-center px-4">
                    <p className="font-bold text-body-md">{step}</p>
                    <p className="text-label-sm text-on-surface-variant">
                      {i === 0 ? "已完成" : i === 1 ? "进行中" : "待解锁"}
                    </p>
                  </div>
                </div>
              ))}
            </div>
            <div className="mt-6 p-5 rounded-xl bg-primary-fixed/30 border border-primary-container/20">
              <div className="flex items-start space-x-3">
                <span className="material-symbols-outlined text-primary mt-1">lightbulb</span>
                <div>
                  <p className="font-bold text-on-primary-container mb-1">推荐理由</p>
                  <p className="text-label-md text-on-surface-variant leading-relaxed">
                    {profile?.profile_summary || "系统将根据你的学习数据生成个性化推荐。"}
                  </p>
                </div>
              </div>
            </div>
          </section>

          {/* 自进化策略 */}
          <StrategyComparisonTable
            strategies={strategies}
            onApply={handleApply}
            onRollback={handleRollback}
            onAnalyze={handleAnalyze}
            analyzing={analyzing}
          />

          {/* 长期记忆 */}
          <section className="glass-card rounded-xl p-8">
            <div className="flex justify-between items-center mb-6">
              <h3 className="font-headline-md text-headline-md flex items-center">
                <span className="material-symbols-outlined mr-2 text-tertiary">memory</span>
                长期记忆
              </h3>
              <span className="text-label-sm px-3 py-1 rounded-full bg-surface-container-high text-on-surface-variant">
                {memories.length} 条
              </span>
            </div>
            {memories.length === 0 ? (
              <div className="p-5 bg-surface-container-low rounded-xl border border-outline-variant/20">
                <p className="font-bold text-body-md">暂无长期记忆</p>
                <p className="text-label-sm text-on-surface-variant mt-1">
                  使用问答、练习和诊断后，系统会自动生成长期记忆。
                </p>
              </div>
            ) : (
              <div className="space-y-3 max-h-[300px] overflow-y-auto pr-2">
                {memories.slice(0, 6).map((memory) => (
                  <div
                    key={memory.id}
                    className="group p-4 bg-surface-container-low rounded-xl hover:bg-white hover:shadow-sm transition-all flex items-center justify-between border border-transparent hover:border-outline-variant/30"
                  >
                    <div className="flex items-center space-x-4 min-w-0">
                      <div className="w-10 h-10 rounded-lg bg-tertiary-fixed text-on-tertiary-fixed-variant flex items-center justify-center shrink-0">
                        <span className="material-symbols-outlined">
                          {memory.memory_type === "insight" ? "lightbulb" : memory.memory_type === "mistake_pattern" ? "warning" : "psychology"}
                        </span>
                      </div>
                      <div className="min-w-0">
                        <p className="font-bold text-body-md truncate">{memory.content}</p>
                        <p className="text-label-sm text-on-surface-variant">
                          {memory.memory_type} · 置信度 {Math.round(memory.confidence * 100)}%
                        </p>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </section>
        </div>
      </div>
    </AppShell>
  )
}
