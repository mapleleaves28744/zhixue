"use client"

import { useEffect, useState, useCallback, useMemo } from "react"
import { toast } from "sonner"
import { AppShell } from "@/components/layout/AppShell"
import { studentNavItems } from "@/components/layout/StudentSidebar"
import { ProfileSummaryCard } from "@/components/profile/ProfileSummaryCard"
import { StrategyComparisonTable } from "@/components/evolution/StrategyComparisonTable"
import { Button } from "@/components/ui/button"
import { getProfile, getProfileSummary, getPreferences, rebuildProfile } from "@/services/profileService"
import { analyze, listStrategies, applyStrategy, rollbackStrategy } from "@/services/evolutionService"
import { listMemories } from "@/services/memoryService"
import { listLearningPaths, generateLearningPath, updateLearningPathItem } from "@/services/learningPathService"
import { listCourses } from "@/services/courseService"
import type { ProfileSummary, StudentProfile, LearningPreference } from "@/types/profile"
import type { EvolutionStrategy } from "@/types/evolution"
import type { StudentMemory } from "@/types/memory"
import type { LearningPath } from "@/types/learning-path"

export default function StudentProfilePage() {
  const [profile, setProfile] = useState<StudentProfile | null>(null)
  const [summary, setSummary] = useState<ProfileSummary | null>(null)
  const [preferences, setPreferences] = useState<LearningPreference[]>([])
  const [strategies, setStrategies] = useState<EvolutionStrategy[]>([])
  const [memories, setMemories] = useState<StudentMemory[]>([])
  const [learningPaths, setLearningPaths] = useState<LearningPath[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [rebuilding, setRebuilding] = useState(false)
  const [analyzing, setAnalyzing] = useState(false)
  const [generatingPath, setGeneratingPath] = useState(false)
  const [courseId, setCourseId] = useState<string | null>(null)

  useEffect(() => {
    loadData()
  }, [])

  const loadData = async () => {
    try {
      setLoading(true)
      setError(null)
      const [profileData, summaryData, prefsData, coursesData] = await Promise.all([
        getProfile(),
        getProfileSummary(),
        getPreferences(),
        listCourses().catch(() => ({ items: [], total: 0 })),
      ])
      setProfile(profileData)
      setSummary(summaryData)
      setPreferences(prefsData)

      const activeCourseId = coursesData.items[0]?.id ?? null
      setCourseId(activeCourseId)

      if (activeCourseId) {
        const [strategiesData, memoriesData, pathsData] = await Promise.all([
          listStrategies({ courseId: activeCourseId, status: "active" }).catch(() => ({ items: [], total: 0 })),
          listMemories().catch(() => []),
          listLearningPaths({ courseId: activeCourseId }).catch(() => ({ items: [], total: 0 })),
        ])
        setStrategies(strategiesData.items)
        setMemories(memoriesData)
        setLearningPaths(pathsData.items)
      }
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
    if (!courseId) { toast.error("暂无课程"); return }
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

  const handleGeneratePath = useCallback(async () => {
    if (!courseId) { toast.error("暂无课程"); return }
    try {
      setGeneratingPath(true)
      const path = await generateLearningPath({
        course_id: courseId,
        goal: "补强数据结构核心薄弱点",
        path_type: "weakness_repair",
      })
      setLearningPaths((prev) => [path, ...prev])
      toast.success("学习路径已生成")
    } catch (err) {
      const msg = err instanceof Error ? err.message : "生成失败"
      toast.error(msg)
    } finally {
      setGeneratingPath(false)
    }
  }, [courseId])

  const handleTogglePathItem = useCallback(async (itemId: string) => {
    try {
      await updateLearningPathItem(itemId, "completed")
      setLearningPaths((prev) =>
        prev.map((p) => ({
          ...p,
          items: p.items.map((item) =>
            item.id === itemId ? { ...item, status: "completed" as const } : item,
          ),
          progress: p.items.length > 0
            ? Math.round(((p.items.filter((i) => i.id === itemId || i.status === "completed").length) / p.items.length) * 100)
            : p.progress,
        }))
      )
      toast.success("路径节点已完成")
    } catch (err) {
      const msg = err instanceof Error ? err.message : "更新失败"
      toast.error(msg)
    }
  }, [])

  const activePath = useMemo(
    () => learningPaths.find((p) => p.status === "active") ?? learningPaths[0] ?? null,
    [learningPaths],
  )

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
              <div className="flex items-center gap-2">
                {activePath && (
                  <span className="bg-primary/10 text-primary px-4 py-1 rounded-full text-label-sm uppercase tracking-wider">
                    {Math.round(activePath.progress)}% 已完成
                  </span>
                )}
                <Button size="sm" onClick={handleGeneratePath} disabled={generatingPath}>
                  {generatingPath ? "生成中..." : "生成路径"}
                </Button>
              </div>
            </div>
            {!activePath ? (
              <div className="flex flex-col items-center justify-center py-14 text-center text-on-surface-variant">
                <span className="material-symbols-outlined text-5xl mb-4 text-primary/40">route</span>
                <p className="text-body-lg font-bold text-on-surface mb-2">暂无学习路径</p>
                <p className="text-label-md max-w-xl">
                  点击生成路径，PlannerAgent 会基于课程知识点、画像薄弱点和 Wiki 线索生成第一条可执行路径。
                </p>
              </div>
            ) : (
              <>
                <div className="mb-6">
                  <p className="text-label-sm text-on-surface-variant mb-1">当前目标</p>
                  <h4 className="font-headline-sm text-on-surface">{activePath.title}</h4>
                </div>
                <div className="relative flex items-center justify-between pb-6 overflow-x-auto">
                  <div className="absolute top-5 left-0 w-full h-[2px] bg-outline-variant/40" />
                  {[...activePath.items]
                    .sort((a, b) => a.order_index - b.order_index)
                    .map((item, index) => {
                      const isDone = item.status === "completed"
                      const isDoing = item.status === "doing"
                      const icon = isDone ? "check" : isDoing ? "pending" : "flag"
                      const circleClass = isDone
                        ? "bg-primary text-white shadow-lg shadow-primary/20"
                        : isDoing
                          ? "bg-white border-2 border-primary text-primary"
                          : "bg-surface-container-high border border-outline-variant text-outline"
                      return (
                        <div
                          key={item.id}
                          className={`relative z-10 flex flex-col items-center min-w-[160px] ${item.status === "pending" ? "opacity-70" : ""}`}
                        >
                          <button
                            className={`w-11 h-11 rounded-full ${circleClass} flex items-center justify-center mb-4 transition-transform hover:scale-105`}
                            onClick={() => handleTogglePathItem(item.id)}
                            title="标记完成"
                          >
                            <span className="material-symbols-outlined">{icon}</span>
                          </button>
                          <div className="text-center px-4">
                            <p className={`font-bold text-body-md ${isDoing ? "text-primary" : ""}`}>{item.title}</p>
                            <p className="text-label-sm text-on-surface-variant mb-2">
                              {item.item_type} · {item.estimated_minutes || 30} 分钟
                            </p>
                            <span
                              className={`text-[10px] ${isDone ? "bg-primary/10 text-primary" : "bg-surface-container-high text-on-surface-variant"} px-2 py-0.5 rounded-full font-bold`}
                            >
                              第 {index + 1} 步
                            </span>
                          </div>
                        </div>
                      )
                    })}
                </div>
                <div className="mt-6 p-5 rounded-xl bg-primary-fixed/30 border border-primary-container/20">
                  <div className="flex items-start space-x-3">
                    <span className="material-symbols-outlined text-primary mt-1">lightbulb</span>
                    <div>
                      <p className="font-bold text-on-primary-container mb-1">推荐理由</p>
                      <p className="text-label-md text-on-surface-variant leading-relaxed">
                        {activePath.reason || "基于课程知识顺序、学生画像和近期薄弱点生成。"}
                      </p>
                    </div>
                  </div>
                </div>
              </>
            )}
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
