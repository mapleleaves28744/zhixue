export type MaterialParseStatus = "pending" | "processing" | "success" | "failed"

export interface Material {
  id: string
  course_id: string
  uploaded_by: string
  file_name: string
  file_type: string
  file_size: number
  storage_path: string
  parse_status: MaterialParseStatus | string
  parse_error: string | null
  text_hash: string | null
  extra_meta: Record<string, unknown>
  created_at: string
  updated_at: string
}

export interface MaterialParseResult {
  id: string
  course_id: string
  file_name: string
  file_type: string
  parse_status: MaterialParseStatus | string
  parse_error: string | null
  text_hash: string | null
  text_length: number
  parsed_text_path: string | null
}

export interface UploadMaterialPayload {
  courseId: string
  file: File
}
