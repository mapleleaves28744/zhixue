"use client"

import { useEffect, useMemo, useState } from "react"
import { InlineLearningPathPreview } from "@/components/assistant/InlineLearningPathPreview"
import { InlineQuizPreview } from "@/components/assistant/InlineQuizPreview"
import {
  ResourcePreviewBody,
  shouldInlineResource,
} from "@/components/assistant/ResourcePreviewBody"
import { getLearningPath } from "@/services/learningPathService"
import { getQuiz } from "@/services/quizService"
import { getResource } from "@/services/resourceService"
import type { ChatArtifactRef } from "@/components/assistant/extractChatArtifacts"
import type { LearningPathDetail } from "@/types/learningPath"
import type { QuizDetail } from "@/types/quiz"
import type { GeneratedResource } from "@/types/resource"

const TYPE_LABELS: Record<string, string> = {
  explanation: "讲解",
  summary: "总结",
  example: "例题",
  flashcard: "复习卡",
  review: "错题解析",
  mindmap: "思维导图",
  diagram: "图解",
  image: "教学插图",
  quiz: "练习题",
  learning_path: "学习路径",
}

function resourceIcon(artifactType: string, resourceType?: string): string {
  if (artifactType === "quiz") return "quiz"
  if (artifactType === "learning_path") return "route"
  if (resourceType === "mindmap") return "account_tree"
  if (resourceType === "diagram") return "schema"
  if (resourceType === "explanation") return "volume_up"
  return "image"
}

interface InlineChatResourcesProps {
  refs: ChatArtifactRef[]
}

export function InlineChatResources({ refs }: InlineChatResourcesProps) {
  const refKey = useMemo(() => refs.map((r) => `${r.type}:${r.id}`).join(","), [refs])
  const [resources, setResources] = useState<GeneratedResource[]>([])
  const [quizzes, setQuizzes] = useState<QuizDetail[]>([])
  const [paths, setPaths] = useState<LearningPathDetail[]>([])
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    if (!refs.length) {
      setResources([])
      setQuizzes([])
      setPaths([])
      return
    }
    let cancelled = false
    setLoading(true)
    Promise.all([
      Promise.all(
        refs
          .filter((ref) => ref.type === "resource")
          .map((ref) => getResource(ref.id).catch(() => null)),
      ),
      Promise.all(
        refs.filter((ref) => ref.type === "quiz").map((ref) => getQuiz(ref.id).catch(() => null)),
      ),
      Promise.all(
        refs
          .filter((ref) => ref.type === "learning_path")
          .map((ref) => getLearningPath(ref.id).catch(() => null)),
      ),
    ])
      .then(([resourceItems, quizItems, pathItems]) => {
        if (cancelled) return
        setResources(resourceItems.filter(Boolean) as GeneratedResource[])
        setQuizzes(quizItems.filter(Boolean) as QuizDetail[])
        setPaths(pathItems.filter(Boolean) as LearningPathDetail[])
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })
    return () => {
      cancelled = true
    }
  }, [refKey, refs])

  if (!refs.length) return null

  const inlineResources = resources.filter(shouldInlineResource)
  const hasContent = inlineResources.length > 0 || quizzes.length > 0 || paths.length > 0

  if (!loading && !hasContent) return null

  return (
    <div className="flex w-full flex-col gap-3">
      {loading && !hasContent ? (
        <div className="glass-card rounded-3xl rounded-tl-md px-4 py-3 text-xs text-outline">
          正在加载生成内容…
        </div>
      ) : null}

      {quizzes.map((quiz) => (
        <div key={quiz.id} className="glass-card rounded-3xl rounded-tl-md p-4 shadow-sm">
          <p className="mb-3 flex flex-wrap items-center gap-2 text-sm font-bold text-primary">
            <span className="material-symbols-outlined text-lg">{resourceIcon("quiz")}</span>
            <span>{quiz.title}</span>
            <span className="text-xs font-normal text-outline">{TYPE_LABELS.quiz}</span>
          </p>
          <InlineQuizPreview quiz={quiz} />
        </div>
      ))}

      {paths.map((path) => (
        <div key={path.id} className="glass-card rounded-3xl rounded-tl-md p-4 shadow-sm">
          <p className="mb-3 flex flex-wrap items-center gap-2 text-sm font-bold text-primary">
            <span className="material-symbols-outlined text-lg">{resourceIcon("learning_path")}</span>
            <span>{path.title}</span>
            <span className="text-xs font-normal text-outline">{TYPE_LABELS.learning_path}</span>
          </p>
          <InlineLearningPathPreview path={path} />
        </div>
      ))}

      {inlineResources.map((resource) => {
        const typeLabel = TYPE_LABELS[resource.resource_type] || resource.resource_type
        return (
          <div key={resource.id} className="glass-card rounded-3xl rounded-tl-md p-4 shadow-sm">
            <p className="mb-3 flex flex-wrap items-center gap-2 text-sm font-bold text-primary">
              <span className="material-symbols-outlined text-lg">
                {resourceIcon("resource", resource.resource_type)}
              </span>
              <span>{resource.title}</span>
              <span className="text-xs font-normal text-outline">{typeLabel}</span>
            </p>
            <ResourcePreviewBody
              resource={resource}
              collapseScript={resource.resource_type === "explanation"}
            />
          </div>
        )
      })}
    </div>
  )
}
