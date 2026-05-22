"use client"

import { LogOut } from "lucide-react"
import { useRouter } from "next/navigation"
import { useEffect } from "react"

import { Button } from "@/components/ui/button"
import { useAuthStore } from "@/stores/authStore"

export function Topbar({ title }: { title: string }) {
  const router = useRouter()
  const auth = useAuthStore()

  useEffect(() => {
    auth.hydrate()
  }, [])

  function handleLogout() {
    auth.logout()
    router.replace("/login")
  }

  return (
    <header className="fixed left-0 right-0 top-0 z-20 border-b border-white/70 bg-[#fcf9f8]/75 px-5 py-4 backdrop-blur-2xl md:left-28 md:px-10">
      <div className="flex items-center justify-between gap-4">
        <div>
          <p className="text-xs font-bold uppercase tracking-[0.16em] text-[#857462]">智学工坊</p>
          <h1 className="font-['Plus_Jakarta_Sans'] text-xl font-bold text-[#1c1b1b]">{title}</h1>
        </div>
        <div className="flex items-center gap-3">
          <span className="hidden text-sm font-semibold text-[#524434] sm:inline">{auth.user?.username ?? "学习者"}</span>
          <Button onClick={handleLogout} size="sm" type="button" variant="outline">
            <LogOut className="size-4" />
            退出
          </Button>
        </div>
      </div>
    </header>
  )
}
