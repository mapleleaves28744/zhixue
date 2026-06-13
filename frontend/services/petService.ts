import { request } from "@/lib/request"
import type { PetFeed, PetNotification, PetPreference } from "@/types/pet"

export function getPetFeed(): Promise<PetFeed> {
  return request<PetFeed>("/api/v1/student/pet/feed", { redirectOnUnauthorized: false })
}

export function markPetNotificationRead(id: string): Promise<PetNotification> {
  return request<PetNotification>(`/api/v1/student/pet/notifications/${id}/read`, {
    method: "PATCH",
    redirectOnUnauthorized: false,
  })
}

export function markAllPetNotificationsRead(): Promise<{ updated_count: number }> {
  return request<{ updated_count: number }>("/api/v1/student/pet/notifications/read-all", {
    method: "POST",
    redirectOnUnauthorized: false,
  })
}

export function getPetPreferences(): Promise<PetPreference> {
  return request<PetPreference>("/api/v1/student/pet/preferences", { redirectOnUnauthorized: false })
}

export function updatePetPreferences(payload: Partial<PetPreference>): Promise<PetPreference> {
  return request<PetPreference>("/api/v1/student/pet/preferences", {
    method: "PUT",
    body: payload,
    redirectOnUnauthorized: false,
  })
}
