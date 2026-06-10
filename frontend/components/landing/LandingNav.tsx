"use client"

import { Menu, X } from "lucide-react"
import { useState } from "react"

import { LiquidGlassButton } from "@/components/landing/LiquidGlassButton"
import { cn } from "@/lib/utils"

const NAV_LINKS = [
  { label: "首页", href: "#top" },
  { label: "核心模块", href: "#modules" },
  { label: "品牌愿景", href: "#vision" },
  { label: "社区", href: "#community" }
]

type LandingNavProps = {
  onLoginClick: () => void
  onStartClick: () => void
}

export function LandingNav({ onLoginClick, onStartClick }: LandingNavProps) {
  const [mobileOpen, setMobileOpen] = useState(false)

  function handleNavClick(href: string) {
    setMobileOpen(false)
    const target = document.querySelector(href)
    target?.scrollIntoView({ behavior: "smooth" })
  }

  return (
    <nav className="relative z-10 mx-auto max-w-7xl px-6 py-7 md:px-10 lg:px-12">
      <div className="grid grid-cols-[1fr_auto] items-center gap-4 md:grid-cols-[auto_1fr_auto] md:gap-8 lg:gap-12">
        <a
          className="font-display text-2xl tracking-tight text-foreground md:text-[1.75rem] lg:text-3xl"
          href="#top"
          onClick={(event) => {
            event.preventDefault()
            handleNavClick("#top")
          }}
          style={{ fontFamily: "var(--font-display)" }}
        >
          智学工坊
        </a>

        <div className="hidden justify-center md:flex">
          <div className="flex items-center gap-x-8 lg:gap-x-11">
            {NAV_LINKS.map((link) => (
              <button
                key={link.href}
                className={cn(
                  "whitespace-nowrap text-sm tracking-wide transition-colors lg:text-[15px]",
                  link.href === "#top" ? "font-medium text-primary" : "text-muted-foreground hover:text-primary"
                )}
                onClick={() => handleNavClick(link.href)}
                type="button"
              >
                {link.label}
              </button>
            ))}
          </div>
        </div>

        <div className="hidden items-center justify-end gap-5 md:flex lg:gap-7">
          <button
            className="whitespace-nowrap text-sm tracking-wide text-muted-foreground transition-colors hover:text-primary lg:text-[15px]"
            onClick={onLoginClick}
            type="button"
          >
            登录
          </button>
          <LiquidGlassButton
            className="landing-primary-btn shrink-0 border-0 shadow-none"
            onClick={onStartClick}
            size="sm"
          >
            开启学习之旅
          </LiquidGlassButton>
        </div>

        <button
          aria-label={mobileOpen ? "关闭菜单" : "打开菜单"}
          className="justify-self-end rounded-full p-2 text-foreground md:hidden"
          onClick={() => setMobileOpen((open) => !open)}
          type="button"
        >
          {mobileOpen ? <X className="size-6" /> : <Menu className="size-6" />}
        </button>
      </div>

      {mobileOpen ? (
        <div className="landing-glass-card absolute left-4 right-4 top-full mt-3 rounded-2xl p-5 md:hidden">
          <div className="flex flex-col gap-1">
            {NAV_LINKS.map((link) => (
              <button
                key={link.href}
                className="rounded-xl px-3 py-3 text-left text-sm text-muted-foreground transition-colors hover:bg-white/40 hover:text-foreground"
                onClick={() => handleNavClick(link.href)}
                type="button"
              >
                {link.label}
              </button>
            ))}
            <button
              className="rounded-xl px-3 py-3 text-left text-sm text-muted-foreground transition-colors hover:bg-white/40 hover:text-foreground"
              onClick={() => {
                setMobileOpen(false)
                onLoginClick()
              }}
              type="button"
            >
              登录
            </button>
            <div className="pt-2">
              <LiquidGlassButton
                className="landing-primary-btn w-full border-0 shadow-none"
                onClick={onStartClick}
                size="sm"
              >
                开启学习之旅
              </LiquidGlassButton>
            </div>
          </div>
        </div>
      ) : null}
    </nav>
  )
}
