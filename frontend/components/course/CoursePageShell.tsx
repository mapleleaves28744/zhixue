"use client"

import { useCallback, useEffect, useState } from "react"

import { CourseCard } from "@/components/course/CourseCard"
import { CourseEmptyState } from "@/components/course/CourseEmptyState"
import { CreateCourseDialog } from "@/components/course/CreateCourseDialog"
import { listCourses } from "@/services/courseService"
import type { Course } from "@/types/course"

export function CoursePageShell() {
  const [courses, setCourses] = useState<Course[]>([])
  const [total, setTotal] = useState(0)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [dialogOpen, setDialogOpen] = useState(false)

  const loadCourses = useCallback(async () => {
    try {
      setLoading(true)
      setError(null)
      const pageData = await listCourses()
      setCourses(pageData.items)
      setTotal(pageData.total)
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "课程列表加载失败")
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    void loadCourses()
  }, [loadCourses])

  return (
    <main className="relative min-h-screen overflow-hidden bg-[#fcf9f8] px-5 py-8 font-['Manrope'] text-[#1c1b1b] md:px-10 lg:px-16">
      <div className="pointer-events-none absolute left-[-12rem] top-[-10rem] h-[28rem] w-[28rem] rounded-full bg-[#f9a826]/14 blur-3xl" />
      <div className="pointer-events-none absolute right-[-14rem] top-20 h-[30rem] w-[30rem] rounded-full bg-[#fec7c7]/30 blur-3xl" />
      <div className="pointer-events-none absolute bottom-[-18rem] left-1/3 h-[34rem] w-[34rem] rounded-full bg-[#b3bac2]/20 blur-3xl" />

      <div className="relative z-10 mx-auto max-w-7xl">
        <header className="mb-8 flex flex-col justify-between gap-6 rounded-[36px] border border-white/70 bg-white/45 p-6 shadow-[0_24px_80px_rgba(131,84,0,0.08)] backdrop-blur-3xl md:flex-row md:items-end md:p-8">
          <div className="max-w-3xl">
            <div className="mb-5 inline-flex items-center gap-2 rounded-full border border-white/70 bg-white/50 px-4 py-2 text-xs font-bold uppercase tracking-[0.16em] text-[#857462]">
              <span className="material-symbols-outlined text-base text-[#835400]">auto_stories</span>
              My Course Space
            </div>
            <h1 className="font-['Plus_Jakarta_Sans'] text-4xl font-bold leading-tight text-[#1c1b1b] md:text-5xl">
              我的课程空间
            </h1>
            <p className="mt-4 max-w-2xl text-base leading-8 text-[#524434]">
              围绕课程沉淀资料、Wiki、AI 答疑、练习诊断和推荐策略，让学习闭环从一门课开始持续积累。
            </p>
          </div>

          <div className="flex flex-col gap-3 sm:flex-row">
            <button
              className="inline-flex items-center justify-center gap-2 rounded-full border border-[#d7c3ae]/80 bg-white/45 px-5 py-3 text-sm font-bold text-[#524434] transition hover:bg-white/75"
              onClick={() => void loadCourses()}
              type="button"
            >
              <span className="material-symbols-outlined text-lg">refresh</span>
              刷新列表
            </button>
            <button
              className="inline-flex items-center justify-center gap-2 rounded-full bg-[#f9a826] px-6 py-3 text-sm font-bold text-[#674100] shadow-[0_16px_34px_rgba(249,168,38,0.22)] transition hover:scale-[1.02]"
              onClick={() => setDialogOpen(true)}
              type="button"
            >
              <span className="material-symbols-outlined text-lg">add</span>
              创建课程
            </button>
          </div>
        </header>

        <section className="mb-7 grid gap-4 md:grid-cols-3">
          <div className="rounded-[28px] border border-white/70 bg-white/50 p-5 backdrop-blur-3xl">
            <p className="text-xs font-bold uppercase tracking-[0.14em] text-[#857462]">Active Courses</p>
            <p className="mt-2 font-['Plus_Jakarta_Sans'] text-3xl font-bold text-[#835400]">{total}</p>
          </div>
          <div className="rounded-[28px] border border-white/70 bg-white/50 p-5 backdrop-blur-3xl">
            <p className="text-xs font-bold uppercase tracking-[0.14em] text-[#857462]">Next Step</p>
            <p className="mt-2 text-base font-bold text-[#524434]">上传资料并生成 Wiki</p>
          </div>
          <div className="rounded-[28px] border border-white/70 bg-white/50 p-5 backdrop-blur-3xl">
            <p className="text-xs font-bold uppercase tracking-[0.14em] text-[#857462]">Evidence Rule</p>
            <p className="mt-2 text-base font-bold text-[#524434]">AI 内容保留来源与依据</p>
          </div>
        </section>

        {error ? (
          <div className="mb-6 flex items-start gap-3 rounded-[24px] border border-[#ffdad6] bg-[#ffdad6]/45 p-4 text-sm font-semibold leading-7 text-[#93000a] backdrop-blur-2xl">
            <span className="material-symbols-outlined mt-0.5 text-lg">error</span>
            <div>
              <p>{error}</p>
              <p className="mt-1 font-normal text-[#7a5051]">请确认已登录并保存了 access_token。</p>
            </div>
          </div>
        ) : null}

        {loading ? (
          <div className="grid gap-6 md:grid-cols-2 xl:grid-cols-3">
            {Array.from({ length: 3 }).map((_, index) => (
              <div
                className="h-[280px] animate-pulse rounded-[28px] border border-white/70 bg-white/45 backdrop-blur-3xl"
                key={index}
              />
            ))}
          </div>
        ) : courses.length > 0 ? (
          <div className="grid gap-6 md:grid-cols-2 xl:grid-cols-3">
            {courses.map((course) => (
              <CourseCard course={course} key={course.id} />
            ))}
          </div>
        ) : (
          <CourseEmptyState onCreate={() => setDialogOpen(true)} />
        )}
      </div>

      <CreateCourseDialog open={dialogOpen} onClose={() => setDialogOpen(false)} onCreated={loadCourses} />
    </main>
  )
}
