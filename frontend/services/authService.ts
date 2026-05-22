import { request } from "@/lib/request"
import type { AuthUser, LoginPayload, RegisterPayload, TokenResponse } from "@/types/auth"

export function login(payload: LoginPayload): Promise<TokenResponse> {
  return request<TokenResponse>("/api/v1/auth/login", {
    method: "POST",
    body: payload,
    redirectOnUnauthorized: false
  })
}

export function register(payload: RegisterPayload): Promise<AuthUser> {
  return request<AuthUser>("/api/v1/auth/register", {
    method: "POST",
    body: {
      role: "student",
      ...payload
    },
    redirectOnUnauthorized: false
  })
}
