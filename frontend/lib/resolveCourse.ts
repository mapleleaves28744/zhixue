import { listCourses } from "@/services/courseService"
import { listResources } from "@/services/resourceService"
import { listWikiPages } from "@/services/wikiService"
import type { Course } from "@/types/course"

const CURRENT_COURSE_KEY = "zhixue_current_course_id"

async function scoreCourse(course: Course): Promise<number> {
  let score = 0
  if (course.course_code === "STU01-LONGTERM") score += 1000
  try {
    const wiki = await listWikiPages(course.id)
    score += Number(wiki.total ?? wiki.items.length) * 10
  } catch {
    // ignore
  }
  try {
    const resources = await listResources({ courseId: course.id, pageSize: 1, status: "all" })
    score += Number(resources.total ?? resources.items.length) * 20
  } catch {
    // ignore
  }
  return score
}

function pickStoredCourseId(courses: Course[]): string {
  const stored = localStorage.getItem(CURRENT_COURSE_KEY)
  if (stored && courses.some((course) => course.id === stored)) {
    return stored
  }
  return courses[0]?.id || ""
}

export async function resolveCourseIdFromList(
  courses: Course[],
  urlCourseId?: string | null,
): Promise<string> {
  if (!courses.length) {
    throw new Error("请先创建课程")
  }

  if (urlCourseId && courses.some((course) => course.id === urlCourseId)) {
    localStorage.setItem(CURRENT_COURSE_KEY, urlCourseId)
    return urlCourseId
  }

  const stored = localStorage.getItem(CURRENT_COURSE_KEY)
  if (stored && courses.some((course) => course.id === stored)) {
    return stored
  }

  let best = courses[0]
  let bestScore = -1
  for (const course of courses) {
    const score = await scoreCourse(course)
    if (score > bestScore) {
      bestScore = score
      best = course
    }
  }
  localStorage.setItem(CURRENT_COURSE_KEY, best.id)
  return best.id
}

export async function resolveCourseId(urlCourseId?: string | null): Promise<string> {
  const page = await listCourses()
  return resolveCourseIdFromList(page.items, urlCourseId)
}

export function resolveCourseIdSyncFallback(courses: Course[]): string {
  return pickStoredCourseId(courses)
}
