export default function HomePage() {
  return (
    <main className="min-h-screen bg-gradient-to-br from-slate-50 via-blue-50 to-indigo-50 px-6 py-12 text-slate-900">
      <section className="mx-auto flex min-h-[calc(100vh-6rem)] max-w-5xl flex-col justify-center">
        <p className="mb-4 text-sm font-medium text-primary-700">中国软件杯 A3 赛题作品</p>
        <h1 className="max-w-3xl text-4xl font-semibold leading-tight sm:text-5xl">
          智学工坊
        </h1>
        <p className="mt-6 max-w-2xl text-lg leading-8 text-slate-600">
          基于自进化学习智能体与 LLM Wiki 的个性化资源生成学习空间。当前为项目基础骨架，后续将逐步接入课程资料、Wiki、问答、资源生成、诊断和自进化策略。
        </p>
        <div className="mt-10 grid gap-4 sm:grid-cols-3">
          {[
            "LLM Wiki 学习空间",
            "轻量多智能体协作",
            "可解释自进化策略"
          ].map((item) => (
            <div key={item} className="rounded-2xl border border-white/70 bg-white/75 p-5 shadow-sm">
              <p className="text-sm font-medium text-slate-800">{item}</p>
            </div>
          ))}
        </div>
      </section>
    </main>
  )
}
