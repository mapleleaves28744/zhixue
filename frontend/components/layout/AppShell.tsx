import type { ReactNode } from "react"

import { Topbar } from "@/components/layout/Topbar"

interface NavItem {
  href: string
  icon: string
  label: string
}

interface AppShellProps {
  title: string
  navItems: NavItem[]
  children: ReactNode
}

export function AppShell({ title, navItems, children }: AppShellProps) {
  return (
    <div className="min-h-screen bg-[#fcf9f8] text-[#1c1b1b]">
      <aside className="fixed left-4 top-4 z-30 hidden h-[calc(100vh-2rem)] w-20 flex-col items-center rounded-[28px] border border-white/70 bg-white/55 py-5 shadow-glass backdrop-blur-3xl md:flex">
        <a className="mb-8 flex size-11 items-center justify-center rounded-2xl bg-primary text-white" href="/">
          <span className="material-symbols-outlined">auto_stories</span>
        </a>
        <nav className="flex flex-1 flex-col gap-2">
          {navItems.map((item) => (
            <a
              className="group flex size-12 items-center justify-center rounded-2xl text-[#857462] transition hover:bg-white/70 hover:text-primary"
              href={item.href}
              key={item.href}
              title={item.label}
            >
              <span className="material-symbols-outlined group-hover:scale-110">{item.icon}</span>
            </a>
          ))}
        </nav>
      </aside>
      <div className="md:pl-28">
        <Topbar title={title} />
        <main className="px-5 pb-12 pt-24 md:px-10">{children}</main>
      </div>
    </div>
  )
}
