"use client"

import { useRouter } from "next/navigation"
import { useCallback, useEffect, useState } from "react"

import { AuthDialogProvider, type AuthMode } from "@/components/landing/AuthDialog"
import { CoreModulesSection } from "@/components/landing/CoreModulesSection"
import { CtaSection } from "@/components/landing/CtaSection"
import { HeroSection } from "@/components/landing/HeroSection"
import { LandingContentShell } from "@/components/landing/LandingContentShell"
import { LandingFooter } from "@/components/landing/LandingFooter"
import { LandingHeroShell } from "@/components/landing/LandingHeroShell"
import { LandingNav } from "@/components/landing/LandingNav"
import { LandingScrollProgress } from "@/components/landing/LandingScrollProgress"
import { LandingScrollSection } from "@/components/landing/LandingScrollSection"
import { ScrollDirectionProvider } from "@/components/landing/ScrollDirectionProvider"
import { SectionVideoBackdrop } from "@/components/landing/SectionVideoBackdrop"
import { VideoBackground } from "@/components/landing/VideoBackground"
import { VisionSection } from "@/components/landing/VisionSection"
import { getToken } from "@/lib/auth"

export function LandingPage() {
  const router = useRouter()
  const [authOpen, setAuthOpen] = useState(false)
  const [authMode, setAuthMode] = useState<AuthMode>("login")

  const openAuth = useCallback((mode: AuthMode = "login") => {
    setAuthMode(mode)
    setAuthOpen(true)
  }, [])

  const handleStart = useCallback(() => {
    if (getToken()) {
      router.push("/home")
      return
    }
    openAuth("login")
  }, [openAuth, router])

  useEffect(() => {
    document.body.style.background = "#fcf9f8"
    document.body.style.color = "#1c1b1b"
    document.documentElement.classList.add("landing-scroll-root")
    return () => {
      document.body.style.background = ""
      document.body.style.color = ""
      document.documentElement.classList.remove("landing-scroll-root")
    }
  }, [])

  return (
    <ScrollDirectionProvider>
      <LandingScrollProgress />

      <LandingHeroShell
        nav={<LandingNav onLoginClick={() => openAuth("login")} onStartClick={handleStart} />}
        video={<VideoBackground />}
      >
        <HeroSection onStartClick={handleStart} />
      </LandingHeroShell>

      <LandingContentShell backdrop={<SectionVideoBackdrop variant="scroll" />}>
        <LandingScrollSection
          id="modules"
          statement={{
            index: "01 — 核心模块",
            title: "把碎片化知识，编织成完整学习闭环",
            subtitle: "集成多重维度智能工具，重塑学习全周期效率。"
          }}
        >
          <CoreModulesSection />
        </LandingScrollSection>

        <LandingScrollSection
          id="vision"
          statement={{
            index: "02 — 品牌愿景",
            title: "没有清晰路径的学习，很难产生真正成长",
            subtitle: "我们以整合式方法，连接资料、智能体、诊断与自进化策略。"
          }}
        >
          <VisionSection />
        </LandingScrollSection>

        <LandingScrollSection id="community">
          <CtaSection onStartClick={handleStart} />
        </LandingScrollSection>

        <LandingFooter />
      </LandingContentShell>

      <AuthDialogProvider
        authMode={authMode}
        authOpen={authOpen}
        setAuthMode={setAuthMode}
        setAuthOpen={setAuthOpen}
      />
    </ScrollDirectionProvider>
  )
}
