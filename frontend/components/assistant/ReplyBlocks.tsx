"use client"

import { MarkdownRenderer } from "@/components/markdown/MarkdownRenderer"
import { normalizeAgentAnswer } from "@/lib/normalizeAgentAnswer"
import { AgentStepTimeline } from "@/components/assistant/AgentStepTimeline"
import { StreamActivityLine } from "@/components/assistant/StreamActivityLine"
import { truncateText } from "@/components/assistant/streamLabels"
import type { ChatArtifactRef, ChatMediaArtifactRef } from "@/components/assistant/extractChatArtifacts"
import type { SpeechAudioPayload } from "@/components/assistant/extractSpeechAudio"
import type { AgentTaskEvent } from "@/types/agent"
import { InlineAudioPlayer } from "@/components/assistant/InlineAudioPlayer"
import { InlineChatResources } from "@/components/assistant/InlineChatResources"
import { InlineMediaArtifacts } from "@/components/assistant/InlineMediaArtifacts"
import { MediaJobProgressCard } from "@/components/assistant/MediaJobProgressCard"
import type { MediaJobProgressRef } from "@/components/assistant/extractChatArtifacts"
import { TutorEvidencePanel } from "@/components/assistant/TutorEvidencePanel"
import type { TutorChatResponse } from "@/types/tutor"

interface TutorReplyBlockProps {
  content: string
  progress?: string
  streaming: boolean
  error?: string | null
  result?: TutorChatResponse | null
  wikiPageId?: string | null
  onFollowUp?: (question: string) => void
  onOpenDetail?: () => void
}

export function TutorReplyBlock({
  content,
  progress,
  streaming,
  error,
  result,
  wikiPageId,
  onFollowUp,
  onOpenDetail,
}: TutorReplyBlockProps) {
  if (streaming) {
    return (
      <div className="flex w-full max-w-[88%] flex-col gap-2">
        <StreamActivityLine
          icon="psychology"
          label={progress || "AI 正在回答…"}
          preview={content ? truncateText(content, 96) : "内容流式生成中…"}
          streaming
          error={error}
          onClick={onOpenDetail}
        />
        {content ? (
          <div className="glass-card rounded-3xl rounded-tl-md p-4">
            <MarkdownRenderer content={content} />
          </div>
        ) : null}
      </div>
    )
  }

  if (!content) {
    return (
      <StreamActivityLine
        icon="psychology"
        label="AI 回答"
        preview="暂无内容"
        onClick={onOpenDetail}
        className="max-w-[88%]"
      />
    )
  }

  return (
    <div className="glass-card max-w-[88%] rounded-3xl rounded-tl-md p-4 shadow-sm">
      <MarkdownRenderer content={content} />
      {error ? <p className="mt-3 text-xs text-destructive">回答中断：{error}</p> : null}
      {result ? (
        <TutorEvidencePanel
          response={result}
          wikiPageId={wikiPageId || null}
          onFollowUp={onFollowUp || (() => undefined)}
        />
      ) : null}
    </div>
  )
}

interface AgentReplyBlockProps {
  statusLabel: string
  finalAnswer: string
  streaming: boolean
  error?: string | null
  toolCount?: number
  events?: AgentTaskEvent[]
  paused?: boolean
  speechAudio?: SpeechAudioPayload | null
  chatArtifacts?: ChatArtifactRef[]
  mediaArtifacts?: ChatMediaArtifactRef[]
  pendingMediaJobs?: MediaJobProgressRef[]
  onResume?: () => void
  onCancel?: () => void
  onOpenDetail?: () => void
}

function shouldShowStandaloneSpeech(
  speechAudio: SpeechAudioPayload | null | undefined,
  chatArtifacts: ChatArtifactRef[],
  mediaArtifacts: ChatMediaArtifactRef[],
): boolean {
  if (!speechAudio) return false
  if (chatArtifacts.length > 0) return false
  if (mediaArtifacts.length > 0) return false
  return true
}

export function AgentReplyBlock({
  statusLabel,
  finalAnswer,
  streaming,
  error,
  toolCount = 0,
  events = [],
  paused = false,
  speechAudio,
  chatArtifacts = [],
  mediaArtifacts = [],
  pendingMediaJobs = [],
  onResume,
  onCancel,
  onOpenDetail,
}: AgentReplyBlockProps) {
  const answer = normalizeAgentAnswer(finalAnswer)
  const showStandaloneSpeech = shouldShowStandaloneSpeech(speechAudio, chatArtifacts, mediaArtifacts)

  if (streaming || paused) {
    return (
      <div className="flex w-full max-w-[88%] flex-col gap-2">
        <StreamActivityLine
          icon="smart_toy"
          label={paused ? "已暂停接收，可恢复查看" : statusLabel}
          preview={
            answer
              ? truncateText(answer, 96)
              : toolCount > 0
                ? `已调用 ${toolCount} 个工具，点击可查看过程`
                : paused
                  ? "后台任务可能仍在继续，恢复后会同步历史事件"
                  : "智能体正在执行…"
          }
          streaming={streaming && !paused}
          error={error}
          onClick={onOpenDetail}
        />
        <div className="flex flex-wrap gap-2">
          {paused && onResume ? (
            <button
              type="button"
              onClick={onResume}
              className="rounded-full bg-primary px-3 py-1 text-[11px] font-bold text-on-primary shadow-sm"
            >
              恢复查看
            </button>
          ) : null}
          {onCancel ? (
            <button
              type="button"
              onClick={onCancel}
              className="rounded-full border border-destructive/30 bg-destructive/10 px-3 py-1 text-[11px] font-semibold text-destructive transition hover:bg-destructive/15"
            >
              取消任务
            </button>
          ) : null}
        </div>
        <AgentStepTimeline events={events} streaming={streaming && !paused} onOpenDetail={onOpenDetail} />
        {pendingMediaJobs.map((job) => (
          <MediaJobProgressCard key={job.jobId} job={job} />
        ))}
        {chatArtifacts.length ? <InlineChatResources refs={chatArtifacts} /> : null}
        {mediaArtifacts.length ? <InlineMediaArtifacts refs={mediaArtifacts} /> : null}
        {showStandaloneSpeech && speechAudio ? (
          <div className="glass-card rounded-3xl rounded-tl-md p-4">
            <InlineAudioPlayer audio={speechAudio} />
          </div>
        ) : null}
        {answer ? (
          <div className="glass-card rounded-3xl rounded-tl-md p-4">
            <MarkdownRenderer content={answer} />
          </div>
        ) : null}
      </div>
    )
  }

  return (
    <div className="flex w-full max-w-[88%] flex-col gap-2">
      {events.length > 0 ? (
        <AgentStepTimeline events={events} streaming={false} onOpenDetail={onOpenDetail} />
      ) : toolCount > 0 && onOpenDetail ? (
          <StreamActivityLine
            icon="smart_toy"
            label={`智能体执行完成 · ${toolCount} 次工具调用`}
            preview="点击查看完整执行过程"
            onClick={onOpenDetail}
            className="max-w-full"
          />
        ) : null}
      {pendingMediaJobs.map((job) => (
        <MediaJobProgressCard key={job.jobId} job={job} />
      ))}
      {chatArtifacts.length ? <InlineChatResources refs={chatArtifacts} /> : null}
      {mediaArtifacts.length ? <InlineMediaArtifacts refs={mediaArtifacts} /> : null}
      {showStandaloneSpeech && speechAudio ? (
        <div className="glass-card rounded-3xl rounded-tl-md p-4 shadow-sm">
          <InlineAudioPlayer audio={speechAudio} />
        </div>
      ) : null}
      {answer ? (
        <div className="glass-card rounded-3xl rounded-tl-md p-4 shadow-sm">
          <MarkdownRenderer content={answer} />
        </div>
      ) : error ? (
        <p className="text-sm text-destructive">{error}</p>
      ) : (
        <StreamActivityLine
          icon="smart_toy"
          label="智能体任务"
          preview="未生成回答"
          onClick={onOpenDetail}
        />
      )}
    </div>
  )
}
