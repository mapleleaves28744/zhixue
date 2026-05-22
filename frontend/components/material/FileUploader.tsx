"use client"

import { FormEvent, useState } from "react"

import { uploadMaterial } from "@/services/materialService"

interface FileUploaderProps {
  courseId: string | null
  onUploaded: () => void
}

const accept = ".pdf,.docx,.md,.txt"

export function FileUploader({ courseId, onUploaded }: FileUploaderProps) {
  const [file, setFile] = useState<File | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [submitting, setSubmitting] = useState(false)

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setError(null)
    if (!courseId) {
      setError("请先选择课程")
      return
    }
    if (!file) {
      setError("请选择要上传的课程资料")
      return
    }

    try {
      setSubmitting(true)
      await uploadMaterial({ courseId, file })
      setFile(null)
      onUploaded()
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "资料上传失败")
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <form
      className="rounded-[28px] border border-white/70 bg-white/55 p-6 shadow-[0_24px_70px_rgba(131,84,0,0.08)] backdrop-blur-3xl"
      onSubmit={handleSubmit}
    >
      <div className="mb-5 flex items-start gap-4">
        <div className="flex h-12 w-12 shrink-0 items-center justify-center rounded-3xl border border-white/70 bg-[#ffddb5]/45 text-[#835400]">
          <span className="material-symbols-outlined text-[28px]" style={{ fontVariationSettings: "'FILL' 1" }}>
            upload_file
          </span>
        </div>
        <div>
          <p className="text-xs font-bold uppercase tracking-[0.14em] text-[#857462]">Course Material</p>
          <h2 className="mt-1 font-['Plus_Jakarta_Sans'] text-2xl font-bold text-[#1c1b1b]">上传课程资料</h2>
          <p className="mt-2 text-sm leading-7 text-[#524434]">支持 PDF、DOCX、Markdown 和 TXT，上传后可手动解析为后续切片做准备。</p>
        </div>
      </div>

      <label className="block rounded-[24px] border border-dashed border-[#d7c3ae] bg-white/45 p-5 transition hover:bg-white/70">
        <span className="mb-2 block text-sm font-bold text-[#524434]">选择文件</span>
        <input
          accept={accept}
          className="block w-full cursor-pointer text-sm text-[#524434] file:mr-4 file:rounded-full file:border-0 file:bg-[#f9a826] file:px-4 file:py-2 file:text-sm file:font-bold file:text-[#674100]"
          disabled={!courseId || submitting}
          onChange={(event) => setFile(event.target.files?.[0] ?? null)}
          type="file"
        />
        <span className="mt-3 block text-xs font-semibold text-[#857462]">
          {file ? `${file.name} · ${(file.size / 1024 / 1024).toFixed(2)}MB` : "单个文件最大 50MB"}
        </span>
      </label>

      {error ? (
        <div className="mt-4 rounded-2xl border border-[#ffdad6] bg-[#ffdad6]/45 px-4 py-3 text-sm font-semibold text-[#93000a]">
          {error}
        </div>
      ) : null}

      <button
        className="mt-5 inline-flex w-full items-center justify-center gap-2 rounded-full bg-[#f9a826] px-6 py-3 text-sm font-bold text-[#674100] shadow-[0_16px_34px_rgba(249,168,38,0.22)] transition hover:scale-[1.01] disabled:cursor-not-allowed disabled:opacity-60"
        disabled={!courseId || submitting}
        type="submit"
      >
        <span className="material-symbols-outlined text-lg">{submitting ? "hourglass_top" : "upload"}</span>
        {submitting ? "上传中" : "上传资料"}
      </button>
    </form>
  )
}
