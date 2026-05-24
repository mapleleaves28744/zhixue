"use client"

import { useState } from "react"
import { toast } from "sonner"
import { Button } from "@/components/ui/button"
import { Textarea } from "@/components/ui/textarea"
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogFooter,
} from "@/components/ui/dialog"
import { generateResource, saveResourceToWiki } from "@/services/resourceService"
import type { ResourceGenerateResult, ResourceType } from "@/types/resource"

const RESOURCE_TYPES: { value: ResourceType; label: string; icon: string }[] = [
  { value: "explanation", label: "讲解", icon: "menu_book" },
  { value: "summary", label: "总结", icon: "summarize" },
  { value: "example", label: "例题", icon: "quiz" },
  { value: "flashcard", label: "复习卡", icon: "style" },
  { value: "review", label: "错题解析", icon: "rate_review" },
]

interface Props {
  open: boolean
  onOpenChange: (open: boolean) => void
  courseId: string
  wikiPageId: string
  wikiPageTitle: string
  knowledgeId?: string | null
  onSaved?: () => void
}

export function ResourceGenerateDialog({
  open,
  onOpenChange,
  courseId,
  wikiPageId,
  wikiPageTitle,
  knowledgeId,
  onSaved,
}: Props) {
  const [resourceType, setResourceType] = useState<ResourceType>("explanation")
  const [requirement, setRequirement] = useState("")
  const [generating, setGenerating] = useState(false)
  const [saving, setSaving] = useState(false)
  const [result, setResult] = useState<ResourceGenerateResult | null>(null)

  const handleGenerate = async () => {
    try {
      setGenerating(true)
      setResult(null)
      const data = await generateResource({
        course_id: courseId,
        knowledge_id: knowledgeId ?? null,
        wiki_page_id: wikiPageId,
        resource_type: resourceType,
        requirement: requirement || null,
        use_profile: true,
      })
      setResult(data)
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "生成失败")
    } finally {
      setGenerating(false)
    }
  }

  const handleSaveToWiki = async () => {
    if (!result) return
    try {
      setSaving(true)
      await saveResourceToWiki(result.resource_id, { wiki_page_id: wikiPageId })
      toast.success("已保存到 Wiki")
      onSaved?.()
      onOpenChange(false)
      setResult(null)
      setRequirement("")
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "保存失败")
    } finally {
      setSaving(false)
    }
  }

  const handleClose = () => {
    onOpenChange(false)
    setResult(null)
    setRequirement("")
  }

  return (
    <Dialog open={open} onOpenChange={handleClose}>
      <DialogContent className="max-w-2xl max-h-[85vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle>生成学习资源</DialogTitle>
          <DialogDescription>
            为「{wikiPageTitle}」生成个性化学习资源，可保存回 Wiki 页面。
          </DialogDescription>
        </DialogHeader>

        {/* Resource type selector */}
        <div className="space-y-3">
          <p className="text-label-md font-bold text-on-surface">资源类型</p>
          <div className="grid grid-cols-5 gap-2">
            {RESOURCE_TYPES.map((t) => (
              <button
                key={t.value}
                onClick={() => setResourceType(t.value)}
                className={`flex flex-col items-center gap-1.5 p-3 rounded-xl text-label-sm transition-all ${
                  resourceType === t.value
                    ? "bg-primary/10 text-primary border-2 border-primary/30"
                    : "bg-surface-container-low text-on-surface-variant border border-transparent hover:bg-white"
                }`}
              >
                <span className="material-symbols-outlined text-xl">{t.icon}</span>
                {t.label}
              </button>
            ))}
          </div>
        </div>

        {/* Requirement input */}
        <div className="space-y-2">
          <p className="text-label-md font-bold text-on-surface">补充要求（可选）</p>
          <Textarea
            placeholder="例如：用通俗语言解释、多举生活中的例子、重点讲解应用场景..."
            value={requirement}
            onChange={(e) => setRequirement(e.target.value)}
            className="min-h-20"
          />
        </div>

        {/* Generate button */}
        {!result && (
          <Button onClick={handleGenerate} disabled={generating} className="w-full">
            {generating ? (
              <>
                <span className="material-symbols-outlined text-[18px] mr-1 animate-spin">progress_activity</span>
                正在生成...
              </>
            ) : (
              <>
                <span className="material-symbols-outlined text-[18px] mr-1">auto_awesome</span>
                生成资源
              </>
            )}
          </Button>
        )}

        {/* Result display */}
        {result && (
          <div className="space-y-4">
            <div className="glass-card rounded-xl p-5">
              <h4 className="font-headline-sm text-on-surface mb-3">{result.title}</h4>
              <div className="prose prose-sm max-w-none text-on-surface-variant whitespace-pre-wrap text-body-md leading-relaxed">
                {result.content}
              </div>
            </div>

            {result.personalized_reason && (
              <div className="p-4 rounded-xl bg-primary-fixed/30 border border-primary-container/20">
                <p className="text-label-md font-bold text-on-primary-container mb-1">个性化原因</p>
                <p className="text-label-md text-on-surface-variant">{result.personalized_reason}</p>
              </div>
            )}

            {result.citations.length > 0 && (
              <div className="p-4 rounded-xl bg-surface-container-low">
                <p className="text-label-md font-bold text-on-surface mb-2">引用来源</p>
                <ul className="space-y-1.5">
                  {result.citations.map((c, i) => (
                    <li key={i} className="text-label-md text-on-surface-variant flex items-start gap-2">
                      <span className="material-symbols-outlined text-[14px] mt-0.5 text-primary">link</span>
                      <span>
                        [{c.source_type}] {c.title || "来源"}
                        {c.score != null && <span className="text-outline ml-1">({(c.score * 100).toFixed(0)}%)</span>}
                      </span>
                    </li>
                  ))}
                </ul>
              </div>
            )}

            <DialogFooter>
              <Button variant="outline" onClick={() => { setResult(null) }}>
                重新生成
              </Button>
              <Button onClick={handleSaveToWiki} disabled={saving}>
                {saving ? "保存中..." : "保存到 Wiki"}
              </Button>
            </DialogFooter>
          </div>
        )}
      </DialogContent>
    </Dialog>
  )
}
