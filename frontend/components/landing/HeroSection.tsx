"use client"

import { LiquidGlassButton } from "@/components/landing/LiquidGlassButton"

type HeroSectionProps = {
  onStartClick: () => void
}

export function HeroSection({ onStartClick }: HeroSectionProps) {
  return (
    <div className="relative z-10 flex flex-col items-center px-6 pb-16 pt-4 text-center">
      <h1
        className="animate-fade-rise max-w-7xl text-5xl font-normal leading-[0.95] tracking-[-2.46px] sm:text-7xl md:text-8xl"
        style={{ fontFamily: "var(--font-display)" }}
      >
        在静默中，让
        <em className="landing-accent-text">知识</em>
        缓缓
        <em className="landing-accent-text">升起。</em>
      </h1>

      <p className="animate-fade-rise-delay mt-8 max-w-2xl text-base leading-relaxed text-muted-foreground sm:text-lg">
        深度集成大语言模型，连接碎片化资料、结构化知识与个人成长路径。在纷乱的信息洪流中，我们为深度思考者与安静的学习者，构建专注而有灵感的 AI 原生学习空间。
      </p>

      <div className="animate-fade-rise-delay-2 mt-12">
        <LiquidGlassButton className="landing-primary-btn border-0 shadow-none" onClick={onStartClick} size="lg">
          立即开始体验
        </LiquidGlassButton>
      </div>
    </div>
  )
}
