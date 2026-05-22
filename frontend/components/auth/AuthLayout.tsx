import type { ReactNode } from "react"

interface AuthLayoutProps {
  title: string
  description: string
  children: ReactNode
}

export function AuthLayout({ title, description, children }: AuthLayoutProps) {
  return (
    <main className="relative min-h-screen overflow-hidden bg-[#fcf9f8] px-5 py-8 text-[#1c1b1b] md:px-10">
      <div className="pointer-events-none absolute left-[-12rem] top-[-12rem] h-[28rem] w-[28rem] rounded-full bg-[#f9a826]/18 blur-3xl" />
      <div className="pointer-events-none absolute bottom-[-12rem] right-[-12rem] h-[30rem] w-[30rem] rounded-full bg-[#fec7c7]/35 blur-3xl" />

      <div className="relative z-10 mx-auto grid min-h-[calc(100vh-4rem)] max-w-6xl items-center gap-8 lg:grid-cols-[1.05fr_0.95fr]">
        <section className="hidden rounded-[36px] border border-white/70 bg-white/45 p-10 shadow-glass backdrop-blur-3xl lg:block">
          <div className="mb-8 inline-flex items-center gap-2 rounded-full border border-white/70 bg-white/50 px-4 py-2 text-xs font-bold uppercase tracking-[0.16em] text-[#857462]">
            <span className="material-symbols-outlined text-base text-primary">auto_stories</span>
            Zhixue Workshop
          </div>
          <h1 className="font-['Plus_Jakarta_Sans'] text-5xl font-bold leading-tight">智学工坊</h1>
          <p className="mt-5 max-w-xl text-base leading-8 text-[#524434]">
            把课程资料、LLM Wiki、AI Tutor、练习诊断和自进化策略沉淀到一个可追溯的个性化学习空间。
          </p>
          <div className="mt-10 grid gap-4">
            {["来源可追溯的 Wiki", "多智能体学习闭环", "无 Key 可演示的 Mock 链路"].map((item) => (
              <div className="flex items-center gap-3 rounded-2xl bg-white/45 p-4 text-sm font-bold text-[#524434]" key={item}>
                <span className="material-symbols-outlined text-primary">check_circle</span>
                {item}
              </div>
            ))}
          </div>
        </section>

        <section className="rounded-[36px] border border-white/70 bg-white/55 p-6 shadow-glass backdrop-blur-3xl md:p-8">
          <div className="mb-7">
            <p className="mb-2 text-xs font-bold uppercase tracking-[0.16em] text-[#857462]">Account</p>
            <h2 className="font-['Plus_Jakarta_Sans'] text-3xl font-bold leading-tight">{title}</h2>
            <p className="mt-3 text-sm leading-7 text-[#524434]">{description}</p>
          </div>
          {children}
        </section>
      </div>
    </main>
  )
}
