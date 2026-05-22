"use client"

import { FormEvent, useEffect, useState } from "react"

import { createCourse } from "@/services/courseService"
import type { CourseCreatePayload } from "@/types/course"

interface CreateCourseDialogProps {
  open: boolean
  onClose: () => void
  onCreated: () => void
}

const initialForm = {
  title: "",
  course_code: "",
  subject: "",
  description: ""
}

export function CreateCourseDialog({ open, onClose, onCreated }: CreateCourseDialogProps) {
  const [form, setForm] = useState(initialForm)
  const [error, setError] = useState<string | null>(null)
  const [submitting, setSubmitting] = useState(false)

  useEffect(() => {
    if (!open) {
      setForm(initialForm)
      setError(null)
      setSubmitting(false)
    }
  }, [open])

  if (!open) {
    return null
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setError(null)

    const title = form.title.trim()
    if (!title) {
      setError("课程名称不能为空")
      return
    }

    const payload: CourseCreatePayload = {
      title,
      visibility: "private"
    }
    const courseCode = form.course_code.trim()
    const subject = form.subject.trim()
    const description = form.description.trim()
    if (courseCode) {
      payload.course_code = courseCode
    }
    if (subject) {
      payload.subject = subject
    }
    if (description) {
      payload.description = description
    }

    try {
      setSubmitting(true)
      await createCourse(payload)
      onCreated()
      onClose()
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "创建课程失败，请稍后重试")
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center px-4 py-8">
      <button
        aria-label="关闭创建课程弹窗"
        className="absolute inset-0 bg-[#1c1b1b]/25 backdrop-blur-sm"
        onClick={onClose}
        type="button"
      />
      <form
        className="relative z-10 w-full max-w-2xl rounded-[32px] border border-white/75 bg-[#fcf9f8]/90 p-6 shadow-[0_30px_100px_rgba(49,48,48,0.18)] backdrop-blur-3xl md:p-8"
        onSubmit={handleSubmit}
      >
        <div className="mb-7 flex items-start justify-between gap-4">
          <div>
            <p className="mb-2 text-xs font-bold uppercase tracking-[0.16em] text-[#857462]">Course Space</p>
            <h2 className="font-['Plus_Jakarta_Sans'] text-3xl font-bold leading-tight text-[#1c1b1b]">
              创建课程空间
            </h2>
            <p className="mt-3 text-sm leading-7 text-[#524434]">
              课程空间会作为资料、Wiki、答疑、练习和诊断的统一上下文。
            </p>
          </div>
          <button
            className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-white/60 text-[#857462] transition hover:text-[#835400]"
            onClick={onClose}
            type="button"
          >
            <span className="material-symbols-outlined">close</span>
          </button>
        </div>

        <div className="grid gap-5 md:grid-cols-2">
          <label className="md:col-span-2">
            <span className="mb-2 block text-sm font-bold text-[#524434]">课程名称 *</span>
            <input
              className="w-full rounded-2xl border border-[#d7c3ae]/70 bg-white/55 px-4 py-3 text-base text-[#1c1b1b] outline-none transition placeholder:text-[#857462] focus:border-[#835400] focus:bg-white/80"
              maxLength={128}
              onChange={(event) => setForm((current) => ({ ...current, title: event.target.value }))}
              placeholder="例如：数据结构"
              value={form.title}
            />
          </label>
          <label>
            <span className="mb-2 block text-sm font-bold text-[#524434]">课程编号</span>
            <input
              className="w-full rounded-2xl border border-[#d7c3ae]/70 bg-white/55 px-4 py-3 text-base text-[#1c1b1b] outline-none transition placeholder:text-[#857462] focus:border-[#835400] focus:bg-white/80"
              maxLength={64}
              onChange={(event) => setForm((current) => ({ ...current, course_code: event.target.value }))}
              placeholder="CS-DS-001"
              value={form.course_code}
            />
          </label>
          <label>
            <span className="mb-2 block text-sm font-bold text-[#524434]">所属方向</span>
            <input
              className="w-full rounded-2xl border border-[#d7c3ae]/70 bg-white/55 px-4 py-3 text-base text-[#1c1b1b] outline-none transition placeholder:text-[#857462] focus:border-[#835400] focus:bg-white/80"
              maxLength={128}
              onChange={(event) => setForm((current) => ({ ...current, subject: event.target.value }))}
              placeholder="计算机科学与技术"
              value={form.subject}
            />
          </label>
          <label className="md:col-span-2">
            <span className="mb-2 block text-sm font-bold text-[#524434]">课程说明</span>
            <textarea
              className="min-h-28 w-full resize-none rounded-2xl border border-[#d7c3ae]/70 bg-white/55 px-4 py-3 text-base leading-7 text-[#1c1b1b] outline-none transition placeholder:text-[#857462] focus:border-[#835400] focus:bg-white/80"
              onChange={(event) => setForm((current) => ({ ...current, description: event.target.value }))}
              placeholder="说明这门课的学习目标、资料范围或当前复习重点。"
              value={form.description}
            />
          </label>
        </div>

        {error ? (
          <div className="mt-5 rounded-2xl border border-[#ffdad6] bg-[#ffdad6]/45 px-4 py-3 text-sm font-semibold text-[#93000a]">
            {error}
          </div>
        ) : null}

        <div className="mt-7 flex flex-col-reverse gap-3 sm:flex-row sm:justify-end">
          <button
            className="rounded-full border border-[#d7c3ae]/80 bg-white/45 px-6 py-3 text-sm font-bold text-[#524434] transition hover:bg-white/75"
            onClick={onClose}
            type="button"
          >
            取消
          </button>
          <button
            className="inline-flex items-center justify-center gap-2 rounded-full bg-[#f9a826] px-6 py-3 text-sm font-bold text-[#674100] shadow-[0_16px_34px_rgba(249,168,38,0.22)] transition hover:scale-[1.01] disabled:cursor-not-allowed disabled:opacity-60"
            disabled={submitting}
            type="submit"
          >
            <span className="material-symbols-outlined text-lg">{submitting ? "hourglass_top" : "add"}</span>
            {submitting ? "创建中" : "创建课程"}
          </button>
        </div>
      </form>
    </div>
  )
}
