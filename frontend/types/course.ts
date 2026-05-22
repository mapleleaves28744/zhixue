export type CourseVisibility = "private" | "public_template"

export type CourseStatus = "active" | "archived"

export interface Course {
  id: string
  owner_id: string
  title: string
  course_code: string | null
  description: string | null
  subject: string | null
  cover_url: string | null
  visibility: CourseVisibility | string
  status: CourseStatus | string
  created_at: string
  updated_at: string
}

export interface CourseCreatePayload {
  title: string
  course_code?: string
  subject?: string
  description?: string
  visibility: "private"
}
