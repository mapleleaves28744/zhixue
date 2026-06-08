"use client"

import { LiquidGlassButton } from "@/components/landing/LiquidGlassButton"
import { LandingReveal } from "@/components/landing/landingMotion"
import { SectionVideoBackdrop } from "@/components/landing/SectionVideoBackdrop"

type CtaSectionProps = {
  onStartClick: () => void
}

export function CtaSection({ onStartClick }: CtaSectionProps) {
  return (
    <div className="relative z-10 mx-auto max-w-5xl px-6">
      <LandingReveal>
        <div className="relative overflow-hidden rounded-[40px] px-6 py-20 text-center sm:px-12">
          <SectionVideoBackdrop variant="cta" />
          <div className="relative z-10 space-y-10">
            <h2
              className="font-display text-4xl md:text-6xl"
              style={{ fontFamily: "var(--font-display)" }}
            >
              开启您的学习进化之旅
            </h2>
            <p className="text-xl text-muted-foreground">立即加入学者与研究者的行列，体验更有温度的智能学习。</p>
            <div className="flex flex-col justify-center gap-4 sm:flex-row">
              <button
                className="landing-primary-btn rounded-full px-12 py-5 text-xl font-medium transition-transform hover:scale-105 active:scale-95"
                onClick={onStartClick}
                type="button"
              >
                免费开始使用
              </button>
              <LiquidGlassButton className="text-xl font-medium text-foreground" onClick={onStartClick} size="lg">
                预约企业演示
              </LiquidGlassButton>
            </div>
          </div>
        </div>
      </LandingReveal>
    </div>
  )
}
