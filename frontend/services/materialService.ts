import { request } from "@/lib/request"
import type { PageData } from "@/types/api"
import type { Material, MaterialParseResult, UploadMaterialPayload } from "@/types/material"

export function listMaterials(courseId: string): Promise<PageData<Material>> {
  const params = new URLSearchParams({
    course_id: courseId,
    page: "1",
    page_size: "50"
  })
  return request<PageData<Material>>(`/api/v1/materials?${params.toString()}`)
}

export function uploadMaterial(payload: UploadMaterialPayload): Promise<Material> {
  const formData = new FormData()
  formData.set("course_id", payload.courseId)
  formData.set("file", payload.file)

  return request<Material>("/api/v1/materials/upload", {
    method: "POST",
    body: formData
  })
}

export function parseMaterial(materialId: string): Promise<MaterialParseResult> {
  return request<MaterialParseResult>(`/api/v1/materials/${materialId}/parse`, {
    method: "POST"
  })
}
