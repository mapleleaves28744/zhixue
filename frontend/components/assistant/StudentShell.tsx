"use client"

import Link from "next/link"
import { usePathname } from "next/navigation"
import type { ReactNode } from "react"
import { cn } from "@/lib/utils"

const NAV_ITEMS = [
  { href: "/", icon: "home", title: "首页" },
  { href: "/courses", icon: "grid_view", title: "课程空间" },
  { href: "/assistant", icon: "smart_toy", title: "AI 学习助手" },
  { href: "/practice", icon: "inventory_2", title: "练习与诊断" },
  { href: "/dashboard", icon: "dashboard", title: "学习仪表盘" },
  { href: "/knowledge", icon: "menu_book", title: "课程知识库" },
  { href: "/path-profile", icon: "route", title: "学习路径" },
]

export function StudentShell({ title, children }: { title: string; children: ReactNode }) {
  const pathname = usePathname()

  return (
    <div className="min-h-screen text-on-background">
      <div className="pointer-events-none fixed inset-0 -z-10 overflow-hidden">
        <div className="absolute -left-24 top-0 h-72 w-72 rounded-full bg-primary/10 blur-3xl" />
        <div className="absolute bottom-0 right-0 h-80 w-80 rounded-full bg-secondary/10 blur-3xl" />
      </div>

      <nav className="fixed left-0 top-0 z-50 hidden h-screen w-20 flex-col items-center gap-4 border-r border-white/80 bg-white/60 py-6 backdrop-blur-3xl md:flex">
        <div className="mb-6 flex h-12 w-12 items-center justify-center rounded-full border-2 border-white bg-primary text-on-primary shadow-sm">
          <span className="material-symbols-outlined text-[24px]" style={{ fontVariationSettings: "'FILL' 1" }}>
            school
          </span>
        </div>
        {NAV_ITEMS.map((item) => {
          const active = pathname === item.href
          return (
            <Link
              key={item.href}
              href={item.href}
              title={item.title}
              className={cn(
                "relative flex h-12 w-12 items-center justify-center rounded-2xl transition-all",
                active
                  ? "scale-95 border border-white/90 bg-white/80 text-primary shadow-sm"
                  : "text-outline hover:bg-white/60 hover:text-primary",
              )}
            >
              {active && (
                <span className="absolute -left-1 top-1/2 h-6 w-1.5 -translate-y-1/2 rounded-r-full bg-primary" />
              )}
              <span
                className="material-symbols-outlined"
                style={active ? { fontVariationSettings: "'FILL' 1" } : undefined}
              >
                {item.icon}
              </span>
            </Link>
          )
        })}
      </nav>

      <div className="flex min-h-screen flex-col md:ml-20">
        <header className="sticky top-0 z-40 flex h-16 items-center border-b border-white/60 bg-[#fcf9f8]/80 px-4 backdrop-blur-xl md:px-8">
          <h1 className="text-lg font-bold text-on-surface md:text-xl">{title}</h1>
        </header>
        <main className="flex-1 overflow-hidden p-4 md:p-6">{children}</main>
      </div>
    </div>
  )
}
