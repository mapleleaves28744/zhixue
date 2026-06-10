"use client"

import Image from "next/image"
import type { MouseEvent } from "react"

import { LandingMotionCard } from "@/components/landing/landingMotion"
import { cn } from "@/lib/utils"

type ModuleItem = {
  id: string
  title: string
  description: string
  icon: string
  span: string
  featured?: boolean
  small?: boolean
  image?: string
  imageAlt?: string
}

const MODULES: ModuleItem[] = [
  {
    id: "knowledge-graph",
    title: "知识图谱",
    description:
      "基于先进的语义理解技术，文档自动切片并生成关联 Wiki。将散乱的 PDF 转化为可交互的知识神经网络。",
    icon: "hub",
    span: "md:col-span-8",
    featured: true,
    image: "/brand/stitch-knowledge-graph-original.png",
    imageAlt: "知识图谱视觉图，展示发光节点与语义关联网络"
  },
  {
    id: "tutor",
    title: "智能问答",
    description: "深度连接个人知识库，不仅仅是搜索，更是基于你已有研究的深度对话与洞察提取。",
    icon: "question_answer",
    span: "md:col-span-4"
  },
  {
    id: "courses",
    title: "课程空间",
    description: "资产一站式管理，自动化归类学习论文、笔记与会议录音。",
    icon: "folder_managed",
    span: "md:col-span-4",
    small: true
  },
  {
    id: "practice",
    title: "练习诊断",
    description: "AI 驱动的精准巩固，自动识别知识盲区，生成个性化练习方案。",
    icon: "analytics",
    span: "md:col-span-4",
    small: true
  },
  {
    id: "dashboard",
    title: "仪表盘",
    description: "全景透视学习进度，可视化展示您的学习产出与认知曲线增长。",
    icon: "speed",
    span: "md:col-span-4",
    small: true
  }
]

function handleCardMouseMove(event: MouseEvent<HTMLElement>) {
  const rect = event.currentTarget.getBoundingClientRect()
  const x = event.clientX - rect.left
  const y = event.clientY - rect.top
  event.currentTarget.style.setProperty("--mouse-x", `${x}px`)
  event.currentTarget.style.setProperty("--mouse-y", `${y}px`)
}

export function CoreModulesSection() {
  return (
    <div className="relative z-10 mx-auto max-w-7xl px-6">
      <div className="grid grid-cols-1 gap-6 md:grid-cols-12">
        {MODULES.map((module, index) => (
          <LandingMotionCard
            key={module.id}
            className={cn("landing-motion-card", module.span)}
            index={index}
          >
            <article
              className="landing-glass-card group h-full rounded-3xl p-8 transition-shadow duration-300 hover:shadow-[0_32px_90px_hsl(38_100%_26%/0.14)]"
              onMouseMove={handleCardMouseMove}
            >
              {module.featured ? (
                <div className="flex flex-col items-center gap-8 md:flex-row">
                  <div className="flex-1 space-y-4">
                    <ModuleIcon icon={module.icon} />
                    <h3 className="font-display text-2xl" style={{ fontFamily: "var(--font-display)" }}>
                      {module.title}
                    </h3>
                    <p className="leading-relaxed text-muted-foreground">{module.description}</p>
                  </div>
                  {module.image ? (
                    <div className="aspect-video w-full flex-1 overflow-hidden rounded-2xl border border-border/40">
                      <Image
                        alt={module.imageAlt ?? module.title}
                        className="h-full w-full object-cover transition-transform duration-700 group-hover:scale-105"
                        height={360}
                        src={module.image}
                        width={640}
                      />
                    </div>
                  ) : null}
                </div>
              ) : (
                <div className="space-y-4">
                  <ModuleIcon icon={module.icon} />
                  <h3
                    className={`font-display ${module.small ? "text-xl" : "text-2xl"}`}
                    style={{ fontFamily: "var(--font-display)" }}
                  >
                    {module.title}
                  </h3>
                  <p className={module.small ? "text-sm text-muted-foreground" : "text-muted-foreground"}>
                    {module.description}
                  </p>
                </div>
              )}
            </article>
          </LandingMotionCard>
        ))}
      </div>
    </div>
  )
}

function ModuleIcon({ icon }: { icon: string }) {
  return (
    <div className="landing-icon-chip flex h-14 w-14 items-center justify-center rounded-2xl transition-transform duration-300 group-hover:scale-110">
      <span className="material-symbols-outlined text-3xl">{icon}</span>
    </div>
  )
}
