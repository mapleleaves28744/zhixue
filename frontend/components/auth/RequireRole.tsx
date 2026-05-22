"use client"

import { useRouter } from "next/navigation"
import { ReactNode, useEffect } from "react"

import { getDefaultRouteByRole, isAllowedRole } from "@/lib/auth"
import { useAuthStore } from "@/stores/authStore"

interface RequireRoleProps {
  role: "student" | "admin"
  children: ReactNode
}

export function RequireRole({ role, children }: RequireRoleProps) {
  const router = useRouter()
  const auth = useAuthStore()

  useEffect(() => {
    auth.hydrate()
  }, [])

  useEffect(() => {
    if (!auth.hydrated) {
      return
    }
    if (!auth.isAuthenticated) {
      router.replace(`/login?redirect=${encodeURIComponent(window.location.pathname)}`)
      return
    }
    if (!isAllowedRole(auth.user?.role, role)) {
      router.replace(getDefaultRouteByRole(auth.user?.role))
    }
  }, [auth.hydrated, auth.isAuthenticated, auth.user?.role, role, router])

  if (!auth.hydrated || !auth.isAuthenticated || !isAllowedRole(auth.user?.role, role)) {
    return (
      <main className="flex min-h-screen items-center justify-center bg-[#fcf9f8] px-6 text-center text-[#524434]">
        <div className="rounded-[28px] border border-white/70 bg-white/55 p-8 shadow-glass backdrop-blur-3xl">
          <p className="text-sm font-bold">正在校验访问权限</p>
        </div>
      </main>
    )
  }

  return children
}
