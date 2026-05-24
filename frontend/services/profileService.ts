import { request } from "@/lib/request"
import type { LearningPreference, ProfileSummary, StudentProfile, ProfileUpdate } from "@/types/profile"

export function getProfile(): Promise<StudentProfile> {
  return request<StudentProfile>("/api/v1/student/profile")
}

export function updateProfile(payload: ProfileUpdate): Promise<StudentProfile> {
  return request<StudentProfile>("/api/v1/student/profile", {
    method: "PUT",
    body: payload,
  })
}

export function getProfileSummary(): Promise<ProfileSummary> {
  return request<ProfileSummary>("/api/v1/student/profile/summary")
}

export function rebuildProfile(): Promise<StudentProfile> {
  return request<StudentProfile>("/api/v1/student/profile/rebuild", {
    method: "POST",
  })
}

export function getPreferences(): Promise<LearningPreference[]> {
  return request<LearningPreference[]>("/api/v1/student/profile/preferences")
}
