"use client"

import type { Course } from "@/types/course"

interface CourseSelectorProps {
  courses: Course[]
  value: string | null
  onChange: (courseId: string) => void
}

export function CourseSelector({ courses, value, onChange }: CourseSelectorProps) {
  return (
    <label className="block">
      <span className="mb-2 block text-sm font-bold text-[#524434]">当前课程</span>
      <select
        className="w-full rounded-2xl border border-[#d7c3ae]/70 bg-white/60 px-4 py-3 text-base font-semibold text-[#1c1b1b] outline-none transition focus:border-[#835400] focus:bg-white/85"
        onChange={(event) => onChange(event.target.value)}
        value={value ?? ""}
      >
        {courses.length === 0 ? <option value="">暂无课程，请先创建课程</option> : null}
        {courses.map((course) => (
          <option key={course.id} value={course.id}>
            {course.title}
          </option>
        ))}
      </select>
    </label>
  )
}
