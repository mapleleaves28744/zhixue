"use client"

import { MarkdownRenderer } from "@/components/markdown/MarkdownRenderer"
import { StreamActivityLine } from "@/components/assistant/StreamActivityLine"
import { truncateText } from "@/components/assistant/streamLabels"
import type { SpeechAudioPayload } from "@/components/assistant/extractSpeechAudio"
import { InlineAudioPlayer } from "@/components/assistant/InlineAudioPlayer"

interface TutorReplyBlockProps {
  content: string
  progress?: string
  streaming: boolean
  onOpenDetail?: () => void
}

export function TutorReplyBlock({
  content,
  progress,
  streaming,
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
    </div>
  )
}

interface AgentReplyBlockProps {
  statusLabel: string
  finalAnswer: string
  streaming: boolean
  error?: string | null
  toolCount?: number
  speechAudio?: SpeechAudioPayload | null
  onOpenDetail?: () => void
}

export function AgentReplyBlock({
  statusLabel,
  finalAnswer,
  streaming,
  error,
  toolCount = 0,
  speechAudio,
  onOpenDetail,
}: AgentReplyBlockProps) {
  if (streaming) {
    return (
      <div className="flex w-full max-w-[88%] flex-col gap-2">
        <StreamActivityLine
          icon="smart_toy"
          label={statusLabel}
          preview={
            finalAnswer
              ? truncateText(finalAnswer, 96)
              : toolCount > 0
                ? `已调用 ${toolCount} 个工具，点击可查看过程`
                : "智能体正在执行…"
          }
          streaming
          error={error}
          onClick={onOpenDetail}
        />
        {speechAudio ? (
          <div className="glass-card rounded-3xl rounded-tl-md p-4">
            <InlineAudioPlayer audio={speechAudio} />
          </div>
        ) : null}
        {finalAnswer ? (
          <div className="glass-card rounded-3xl rounded-tl-md p-4">
            <MarkdownRenderer content={finalAnswer} />
          </div>
        ) : null}
      </div>
    )
  }

  return (
    <div className="flex w-full max-w-[88%] flex-col gap-2">
      {toolCount > 0 && onOpenDetail ? (
        <StreamActivityLine
          icon="smart_toy"
          label={`智能体执行完成 · ${toolCount} 次工具调用`}
          preview="点击查看完整执行过程"
          onClick={onOpenDetail}
          className="max-w-full"
        />
      ) : null}
      {speechAudio ? (
        <div className="glass-card rounded-3xl rounded-tl-md p-4 shadow-sm">
          <InlineAudioPlayer audio={speechAudio} />
        </div>
      ) : null}
      {finalAnswer ? (
        <div className="glass-card rounded-3xl rounded-tl-md p-4 shadow-sm">
          <MarkdownRenderer content={finalAnswer} />
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
