"use client"

import Link from "next/link"
import type { QuizDetail } from "@/types/quiz"

function formatOptions(options: unknown): string[] {
  if (Array.isArray(options)) {
    return options.map((item) => String(item))
  }
  if (options && typeof options === "object") {
    return Object.entries(options as Record<string, unknown>).map(
      ([key, value]) => `${key}. ${String(value)}`,
    )
  }
  return []
}

const TYPE_LABELS: Record<string, string> = {
  single_choice: "单选",
  multiple_choice: "多选",
  judge: "判断",
  short_answer: "简答",
  fill_blank: "填空",
  coding: "编程",
}

export function InlineQuizPreview({ quiz }: { quiz: QuizDetail }) {
  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-2 text-xs text-outline">
        <span className="rounded-full bg-primary/10 px-2 py-0.5 font-semibold text-primary">
          {quiz.questions.length} 道题
        </span>
        {quiz.difficulty ? <span>难度：{quiz.difficulty}</span> : null}
      </div>
      {quiz.questions.map((question, index) => {
        const options = formatOptions(question.options)
        return (
          <div key={question.id} className="rounded-2xl border border-white/80 bg-white/60 p-4">
            <p className="text-sm font-bold text-on-surface">
              {index + 1}. {question.question_text}
              <span className="ml-2 text-xs font-normal text-outline">
                {TYPE_LABELS[question.question_type] || question.question_type}
              </span>
            </p>
            {options.length ? (
              <ul className="mt-3 space-y-2 text-sm text-on-surface-variant">
                {options.map((option) => (
                  <li key={option} className="rounded-xl bg-white/70 px-3 py-2">
                    {option}
                  </li>
                ))}
              </ul>
            ) : null}
          </div>
        )
      })}
      <Link
        href={`/practice?course_id=${quiz.course_id}`}
        className="inline-flex items-center gap-1 text-sm font-semibold text-primary hover:underline"
      >
        前往练习页作答
        <span className="material-symbols-outlined text-base">arrow_forward</span>
      </Link>
    </div>
  )
}
