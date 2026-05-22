import type { User, UserRole } from "@/types/auth"

export const ACCESS_TOKEN_KEY = "access_token"
export const REFRESH_TOKEN_KEY = "refresh_token"
export const AUTH_USER_KEY = "auth_user"
export const AUTH_ROLE_KEY = "auth_role"

function isBrowser(): boolean {
  return typeof window !== "undefined"
}

function setCookie(name: string, value: string, maxAgeSeconds = 60 * 60 * 24 * 7): void {
  if (!isBrowser()) {
    return
  }
  document.cookie = `${name}=${encodeURIComponent(value)}; path=/; max-age=${maxAgeSeconds}; SameSite=Lax`
}

function deleteCookie(name: string): void {
  if (!isBrowser()) {
    return
  }
  document.cookie = `${name}=; path=/; max-age=0; SameSite=Lax`
}

export function getToken(): string | null {
  if (!isBrowser()) {
    return null
  }
  return localStorage.getItem(ACCESS_TOKEN_KEY)
}

export function getRefreshToken(): string | null {
  if (!isBrowser()) {
    return null
  }
  return localStorage.getItem(REFRESH_TOKEN_KEY)
}

export function getStoredUser(): User | null {
  if (!isBrowser()) {
    return null
  }
  const raw = localStorage.getItem(AUTH_USER_KEY)
  if (!raw) {
    return null
  }
  try {
    return JSON.parse(raw) as User
  } catch {
    return null
  }
}

export function setAuthSession(accessToken: string, refreshToken: string, user: User): void {
  if (!isBrowser()) {
    return
  }
  localStorage.setItem(ACCESS_TOKEN_KEY, accessToken)
  localStorage.setItem(REFRESH_TOKEN_KEY, refreshToken)
  localStorage.setItem(AUTH_USER_KEY, JSON.stringify(user))
  setCookie(ACCESS_TOKEN_KEY, accessToken)
  setCookie(AUTH_ROLE_KEY, user.role)
}

export function clearAuthSession(): void {
  if (!isBrowser()) {
    return
  }
  localStorage.removeItem(ACCESS_TOKEN_KEY)
  localStorage.removeItem(REFRESH_TOKEN_KEY)
  localStorage.removeItem(AUTH_USER_KEY)
  deleteCookie(ACCESS_TOKEN_KEY)
  deleteCookie(AUTH_ROLE_KEY)
}

export function getDefaultRouteByRole(role?: UserRole | null): string {
  if (role === "admin") {
    return "/admin/dashboard"
  }
  if (role === "teacher") {
    return "/student/dashboard"
  }
  return "/student/dashboard"
}

export function isAllowedRole(userRole: UserRole | null | undefined, requiredRole: "student" | "admin"): boolean {
  if (!userRole) {
    return false
  }
  return userRole === requiredRole
}
