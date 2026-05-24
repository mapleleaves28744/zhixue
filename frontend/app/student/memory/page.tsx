"use client"

import { useEffect, useState } from "react"
import { toast } from "sonner"
import { AppShell } from "@/components/layout/AppShell"
import { studentNavItems } from "@/components/layout/StudentSidebar"
import { MemoryList } from "@/components/memory/MemoryList"
import { Button } from "@/components/ui/button"
import { listMemories, reflectMemories, deleteMemory } from "@/services/memoryService"
import type { StudentMemory } from "@/types/memory"

export default function StudentMemoryPage() {
  const [memories, setMemories] = useState<StudentMemory[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [reflecting, setReflecting] = useState(false)

  useEffect(() => {
    loadMemories()
  }, [])

  const loadMemories = async () => {
    try {
      setLoading(true)
      setError(null)
      const data = await listMemories()
      setMemories(data)
    } catch (err) {
      const msg = err instanceof Error ? err.message : "加载记忆失败"
      setError(msg)
    } finally {
      setLoading(false)
    }
  }

  const handleReflect = async () => {
    try {
      setReflecting(true)
      const data = await reflectMemories()
      setMemories(data)
      toast.success(`反思完成，共 ${data.length} 条记忆`)
    } catch (err) {
      const msg = err instanceof Error ? err.message : "反思失败"
      toast.error(msg)
    } finally {
      setReflecting(false)
    }
  }

  const handleDelete = async (id: string) => {
    try {
      await deleteMemory(id)
      setMemories((prev) => prev.filter((m) => m.id !== id))
      toast.success("已删除")
    } catch (err) {
      const msg = err instanceof Error ? err.message : "删除失败"
      toast.error(msg)
    }
  }

  return (
    <AppShell title="学习记忆" navItems={studentNavItems}>
      <div className="grid grid-cols-12 gap-6">
        {/* 记忆列表 */}
        <div className="col-span-12 lg:col-span-7">
          {loading ? (
            <div className="glass-card rounded-xl p-8 flex items-center justify-center h-64">
              <span className="material-symbols-outlined animate-spin text-primary text-3xl">progress_activity</span>
            </div>
          ) : error ? (
            <div className="glass-card rounded-xl p-8 flex flex-col items-center justify-center h-64 text-on-surface-variant">
              <span className="material-symbols-outlined text-4xl mb-3 text-error">error</span>
              <p className="text-body-md mb-4">{error}</p>
              <Button onClick={loadMemories} variant="outline" size="sm">
                <span className="material-symbols-outlined text-[18px] mr-1">refresh</span>
                重试
              </Button>
            </div>
          ) : (
            <MemoryList
              memories={memories}
              onDelete={handleDelete}
              onReflect={handleReflect}
              reflecting={reflecting}
            />
          )}
        </div>

        {/* 记忆统计 */}
        <div className="col-span-12 lg:col-span-5 space-y-6">
          <section className="glass-card rounded-xl p-8">
            <h3 className="font-headline-md text-headline-md mb-6 flex items-center">
              <span className="material-symbols-outlined mr-2 text-secondary">analytics</span>
              记忆概览
            </h3>
            <div className="grid grid-cols-2 gap-4">
              <div className="p-4 bg-surface-container-low rounded-xl text-center">
                <p className="text-3xl font-extrabold text-primary">{memories.length}</p>
                <p className="text-label-sm text-on-surface-variant mt-1">总记忆数</p>
              </div>
              <div className="p-4 bg-surface-container-low rounded-xl text-center">
                <p className="text-3xl font-extrabold text-secondary">
                  {memories.filter((m) => m.memory_type === "insight").length}
                </p>
                <p className="text-label-sm text-on-surface-variant mt-1">洞察</p>
              </div>
              <div className="p-4 bg-surface-container-low rounded-xl text-center">
                <p className="text-3xl font-extrabold text-error">
                  {memories.filter((m) => m.memory_type === "mistake_pattern").length}
                </p>
                <p className="text-label-sm text-on-surface-variant mt-1">错误模式</p>
              </div>
              <div className="p-4 bg-surface-container-low rounded-xl text-center">
                <p className="text-3xl font-extrabold text-tertiary">
                  {memories.filter((m) => m.memory_type === "preference").length}
                </p>
                <p className="text-label-sm text-on-surface-variant mt-1">偏好</p>
              </div>
            </div>
          </section>

          <section className="glass-card rounded-xl p-8">
            <h3 className="font-headline-md text-headline-md mb-4 flex items-center">
              <span className="material-symbols-outlined mr-2 text-tertiary">info</span>
              关于长期记忆
            </h3>
            <div className="space-y-3 text-body-md text-on-surface-variant">
              <p>长期记忆是系统通过分析你的学习行为自动提炼的知识洞察。</p>
              <p>点击"反思生成记忆"按钮，系统将从你的学习记录中提取模式和偏好。</p>
              <p>记忆类型包括：</p>
              <ul className="list-disc list-inside space-y-1 ml-2">
                <li><span className="font-bold text-primary">洞察</span> — 学习规律和知识关联</li>
                <li><span className="font-bold text-error">错误模式</span> — 反复出现的错误类型</li>
                <li><span className="font-bold text-secondary">偏好</span> — 学习风格和交互偏好</li>
              </ul>
            </div>
          </section>
        </div>
      </div>
    </AppShell>
  )
}
