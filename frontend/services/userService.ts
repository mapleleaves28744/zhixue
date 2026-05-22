import { request } from "@/lib/request"
import type { User } from "@/types/auth"

export function getCurrentUser(): Promise<User> {
  return request<User>("/api/v1/users/me")
}
