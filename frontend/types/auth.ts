export type UserRole = "student" | "admin" | "teacher" | string

export interface User {
  id: string
  username: string
  email: string | null
  role: UserRole
  status: string
  avatar_url?: string | null
  last_login_at?: string | null
}

export type AuthUser = User

export interface LoginPayload {
  username: string
  password: string
}

export interface RegisterPayload {
  username: string
  email?: string
  password: string
  role?: "student"
}

export interface TokenResponse {
  access_token: string
  refresh_token: string
  token_type: string
  expires_in: number
  user: AuthUser
}
