import { request } from "@/lib/request"
import type { PageData } from "@/types/api"
import type { Course, CourseCreatePayload } from "@/types/course"

export function listCourses(): Promise<PageData<Course>> {
  return request<PageData<Course>>("/api/v1/courses?page=1&page_size=20&status=active")
}

export function createCourse(payload: CourseCreatePayload): Promise<Course> {
  return request<Course>("/api/v1/courses", {
    method: "POST",
    body: payload
  })
}
