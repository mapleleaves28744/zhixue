"use client"

import { LandingMotionCard, LandingReveal } from "@/components/landing/landingMotion"

const VISION_POINTS = [
  "以 AI 为枢纽，加速从信息到认知的转化",
  "打破数据孤岛，实现学习资料的语义化互联"
]

const STEPS = [
  { num: "01", label: "知识驱动", variant: "glass" as const },
  { num: "02", label: "AI 协同", variant: "gold" as const },
  { num: "03", label: "方法论集成", variant: "deep" as const },
  { num: "04", label: "自进化路径", variant: "soft" as const }
]

export function VisionSection() {
  return (
    <div className="relative z-10">
      <div className="landing-section-divider mx-auto max-w-5xl" />
      <div className="mx-auto max-w-7xl px-6 pt-8">
        <LandingReveal>
          <div className="landing-glass-card relative overflow-hidden rounded-[48px] p-8 md:p-20">
            <div className="grid items-center gap-16 md:grid-cols-2">
              <div className="space-y-6">
                <h2
                  className="font-display text-3xl leading-tight md:text-5xl"
                  style={{ fontFamily: "var(--font-display)" }}
                >
                  学习愿景：
                  <br />
                  人机协同的知识进化
                </h2>
                <p className="text-lg leading-relaxed text-muted-foreground">
                  我们相信，未来的学习不应是孤岛。通过将「底层知识」、「人工智能」与「科学方法论」深度融合，智学工坊致力于构建一个会自进化的学习系统。
                </p>
                <div className="space-y-4">
                  {VISION_POINTS.map((point, index) => (
                    <LandingReveal key={point} delay={index * 0.1}>
                      <div className="flex items-start gap-4">
                        <div className="landing-check-chip mt-1 flex h-6 w-6 items-center justify-center rounded-full">
                          <span className="material-symbols-outlined text-sm">check</span>
                        </div>
                        <p className="font-medium text-foreground">{point}</p>
                      </div>
                    </LandingReveal>
                  ))}
                </div>
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div className="mt-0 space-y-4">
                  <VisionCard {...STEPS[0]} aspect="tall" index={0} />
                  <VisionCard {...STEPS[1]} aspect="square" index={1} />
                </div>
                <div className="mt-8 space-y-4">
                  <VisionCard {...STEPS[2]} aspect="square" index={2} />
                  <VisionCard {...STEPS[3]} aspect="tall" index={3} />
                </div>
              </div>
            </div>
          </div>
        </LandingReveal>
      </div>
    </div>
  )
}

function VisionCard({
  num,
  label,
  variant,
  aspect,
  index
}: {
  num: string
  label: string
  variant: "glass" | "gold" | "deep" | "soft"
  aspect: "tall" | "square"
  index: number
}) {
  const aspectClass = aspect === "tall" ? "aspect-[4/5]" : "aspect-square"
  const variantClass =
    variant === "gold"
      ? "landing-vision-gold"
      : variant === "deep"
        ? "landing-vision-deep"
        : variant === "soft"
          ? "landing-vision-soft"
          : "landing-glass-card"

  return (
    <LandingMotionCard float index={index}>
      <div className={`flex h-full flex-col justify-end rounded-3xl p-6 ${aspectClass} ${variantClass}`}>
        <span
          className={`mb-4 text-4xl ${
            variant === "gold" || variant === "deep" ? "opacity-60" : "text-primary/70"
          }`}
        >
          {num}
        </span>
        <p className="font-bold">{label}</p>
      </div>
    </LandingMotionCard>
  )
}
