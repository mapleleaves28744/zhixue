import type { Course } from "@/types/course"

interface CourseCardProps {
  course: Course
}

function formatDate(value: string): string {
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) {
    return "刚刚更新"
  }
  return new Intl.DateTimeFormat("zh-CN", {
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit"
  }).format(date)
}

export function CourseCard({ course }: CourseCardProps) {
  const subject = course.subject || "个人课程空间"
  const courseCode = course.course_code || "未设置编号"
  const description = course.description || "上传课程资料后，系统会围绕这门课构建资料、Wiki、答疑与练习闭环。"
  const isActive = course.status === "active"

  return (
    <article className="group relative min-h-[280px] overflow-hidden rounded-[28px] border border-white/70 bg-white/55 p-6 shadow-[0_24px_70px_rgba(131,84,0,0.08)] backdrop-blur-3xl transition duration-300 hover:-translate-y-1 hover:bg-white/75">
      {course.cover_url ? (
        <img
          alt=""
          className="absolute -right-10 -top-10 h-40 w-40 rounded-full object-cover opacity-20 blur-sm"
          src={course.cover_url}
        />
      ) : (
        <div className="absolute -right-12 -top-12 h-44 w-44 rounded-full bg-[#f9a826]/20 blur-3xl" />
      )}

      <div className="relative z-10 flex h-full flex-col">
        <div className="mb-7 flex items-start justify-between gap-4">
          <div className="flex h-14 w-14 items-center justify-center rounded-3xl border border-white/70 bg-[#ffddb5]/45 text-[#835400] shadow-inner">
            <span className="material-symbols-outlined text-[30px]" style={{ fontVariationSettings: "'FILL' 1" }}>
              school
            </span>
          </div>
          <span className="rounded-full border border-white/70 bg-white/55 px-3 py-1 text-xs font-bold text-[#857462]">
            {isActive ? "进行中" : "已归档"}
          </span>
        </div>

        <div className="mb-6">
          <div className="mb-3 flex flex-wrap gap-2">
            <span className="rounded-full border border-[#835400]/10 bg-[#ffddb5]/35 px-3 py-1 text-xs font-bold text-[#835400]">
              {subject}
            </span>
            <span className="rounded-full border border-[#d7c3ae]/60 bg-white/45 px-3 py-1 text-xs font-bold text-[#857462]">
              {courseCode}
            </span>
          </div>
          <h2 className="mb-3 font-['Plus_Jakarta_Sans'] text-2xl font-bold leading-tight text-[#1c1b1b]">
            {course.title}
          </h2>
          <p className="line-clamp-3 text-sm leading-7 text-[#524434]">{description}</p>
        </div>

        <div className="mt-auto border-t border-dashed border-[#d7c3ae]/80 pt-5">
          <div className="flex items-center justify-between gap-4 text-sm">
            <div>
              <p className="text-xs font-bold text-[#857462]">最近更新</p>
              <p className="mt-1 font-semibold text-[#524434]">{formatDate(course.updated_at)}</p>
            </div>
            <button
              className="flex items-center gap-1 rounded-full bg-[#835400] px-4 py-2 text-sm font-bold text-white shadow-[0_10px_24px_rgba(131,84,0,0.16)] transition hover:bg-[#674100]"
              type="button"
            >
              进入空间
              <span className="material-symbols-outlined text-base">arrow_forward</span>
            </button>
          </div>
        </div>
      </div>
    </article>
  )
}
