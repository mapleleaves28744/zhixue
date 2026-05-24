import { request } from "@/lib/request"
import type { StudentMemory, MemoryUpdate } from "@/types/memory"

export function listMemories(): Promise<StudentMemory[]> {
  return request<StudentMemory[]>("/api/v1/student/memory")
}

export function reflectMemories(): Promise<StudentMemory[]> {
  return request<StudentMemory[]>("/api/v1/student/memory/reflect", {
    method: "POST",
  })
}

export function deleteMemory(memoryId: string): Promise<void> {
  return request<void>(`/api/v1/student/memory/${memoryId}`, {
    method: "DELETE",
  })
}

export function updateMemory(memoryId: string, payload: MemoryUpdate): Promise<StudentMemory> {
  return request<StudentMemory>(`/api/v1/student/memory/${memoryId}`, {
    method: "PATCH",
    body: payload,
  })
}
