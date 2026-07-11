"use client"

import { useState } from "react"
import { toast } from "sonner"
import { saveTutorAnswerToWiki, submitTutorFeedback } from "@/services/tutorService"
import type { TutorChatResponse } from "@/types/tutor"

interface TutorEvidencePanelProps {
  response: TutorChatResponse
  wikiPageId: string | null
  onFollowUp: (question: string) => void
}

const statusCopy = (response: TutorChatResponse): string => {
  if (response.grounding_status === "grounded") {
    return `基于 ${response.citations.length} 条课程资料`
  }
  if (response.grounding_status === "partial") return "部分绑定来源"
  return "课程依据不足"
}

export function TutorEvidencePanel({ response, wikiPageId, onFollowUp }: TutorEvidencePanelProps) {
  const [actionPending, setActionPending] = useState(false)
  const [actionMessage, setActionMessage] = useState<string | null>(null)
  const canAct = Boolean(response.message_id)
  const isMock = `${response.provider || ""} ${response.model || ""}`.toLowerCase().includes("mock")

  const runAction = async (action: () => Promise<unknown>, success: string) => {
    if (actionPending) return
    setActionPending(true)
    setActionMessage(null)
    try {
      await action()
      setActionMessage(success)
    } catch (error) {
      const message = error instanceof Error ? error.message : "操作失败，请稍后重试"
      setActionMessage(message)
      toast.error(message)
    } finally {
      setActionPending(false)
    }
  }

  const feedback = (useful: boolean) => {
    if (!response.message_id) return
    void runAction(
      () =>
        submitTutorFeedback(response.message_id as string, {
          feedback_type: useful ? "useful" : "useless",
          rating: useful ? 5 : 1,
        }),
      useful ? "已记录：这条回答有帮助" : "已记录反馈，我们会继续改进",
    )
  }

  const saveToWiki = () => {
    if (!response.message_id || !wikiPageId) return
    void runAction(
      () => saveTutorAnswerToWiki(response.message_id as string, { wiki_page_id: wikiPageId }),
      "已保存到当前 Wiki 页面",
    )
  }

  return (
    <section className="mt-4 space-y-3 border-t border-outline/10 pt-3 text-xs text-outline">
      <div className="flex flex-wrap items-center gap-2">
        <span
          className={
            response.grounding_status === "grounded"
              ? "rounded-full bg-emerald-500/10 px-2.5 py-1 font-semibold text-emerald-700"
              : response.grounding_status === "partial"
                ? "rounded-full bg-amber-500/10 px-2.5 py-1 font-semibold text-amber-700"
                : "rounded-full bg-rose-500/10 px-2.5 py-1 font-semibold text-rose-700"
          }
        >
          {statusCopy(response)}
        </span>
        {isMock ? (
          <span className="rounded-full border border-sky-400/30 bg-sky-400/10 px-2.5 py-1 font-medium text-sky-700">
            演示模式（Mock Provider）
          </span>
        ) : null}
        {response.fallback_used ? (
          <span className="rounded-full bg-amber-500/10 px-2.5 py-1 text-amber-700">
            主模型不可用，已切换备用模型
          </span>
        ) : null}
      </div>

      <p>{response.grounding_message}</p>

      {response.citations.length ? (
        <details className="rounded-2xl border border-outline/10 bg-white/35 px-3 py-2 open:bg-white/55">
          <summary className="cursor-pointer select-none font-semibold text-ink">
            查看课程依据（{response.citations.length}）
          </summary>
          <div className="mt-2 space-y-2">
            {response.citations.map((citation, index) => (
              <article key={citation.citation_key || `${citation.source_type}-${index}`} className="rounded-xl bg-white/60 p-3">
                <div className="flex flex-wrap items-center gap-2 font-semibold text-ink">
                  <span>{citation.citation_key ? `[${citation.citation_key}] ` : ""}{citation.title}</span>
                  {citation.page_no ? <span className="font-normal text-outline">第 {citation.page_no} 页</span> : null}
                </div>
                {citation.quote ? <p className="mt-1 leading-5">“{citation.quote}”</p> : null}
                <p className="mt-1 text-[11px] text-outline/80">
                  {citation.retrieval_mode ? `检索：${citation.retrieval_mode}` : "检索方式未记录"}
                  {citation.confidence ? ` · 可信度：${citation.confidence}` : ""}
                </p>
              </article>
            ))}
          </div>
        </details>
      ) : null}

      {response.related_knowledge_points.length ? (
        <div className="flex flex-wrap gap-2">
          {response.related_knowledge_points.map((point, index) => (
            <span key={point.knowledge_id || `${point.name}-${index}`} className="rounded-full border border-primary/15 px-2.5 py-1 text-ink">
              {point.name}
            </span>
          ))}
        </div>
      ) : null}

      {response.follow_up_questions.length ? (
        <div className="flex flex-wrap gap-2">
          {response.follow_up_questions.map((question) => (
            <button key={question} type="button" onClick={() => onFollowUp(question)} className="rounded-full bg-primary/8 px-3 py-1.5 text-left font-medium text-primary transition hover:bg-primary/15">
              {question}
            </button>
          ))}
        </div>
      ) : null}

      <div className="flex flex-wrap items-center gap-2">
        <button type="button" disabled={!canAct || actionPending} onClick={() => feedback(true)} className="rounded-full border border-outline/15 px-3 py-1.5 font-medium text-ink disabled:cursor-not-allowed disabled:opacity-40">有用</button>
        <button type="button" disabled={!canAct || actionPending} onClick={() => feedback(false)} className="rounded-full border border-outline/15 px-3 py-1.5 font-medium text-ink disabled:cursor-not-allowed disabled:opacity-40">无用</button>
        <button type="button" disabled={!canAct || !wikiPageId || actionPending} onClick={saveToWiki} className="rounded-full bg-primary px-3 py-1.5 font-semibold text-on-primary disabled:cursor-not-allowed disabled:opacity-40">保存到 Wiki</button>
      </div>
      {!canAct ? <p className="text-amber-700">本次回答未成功保存记录，反馈与 Wiki 操作暂不可用。</p> : null}
      {canAct && !wikiPageId ? <p>选择一个 Wiki 页面后即可保存。</p> : null}
      {response.postprocess_status === "skipped" ? <p className="text-amber-700">深度复核与学习记忆更新未排队。</p> : null}
      {actionMessage ? <p aria-live="polite" className="font-medium text-ink">{actionMessage}</p> : null}
    </section>
  )
}
