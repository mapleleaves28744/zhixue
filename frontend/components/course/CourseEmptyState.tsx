interface CourseEmptyStateProps {
  onCreate: () => void
}

export function CourseEmptyState({ onCreate }: CourseEmptyStateProps) {
  return (
    <section className="rounded-[32px] border border-white/70 bg-white/50 px-6 py-14 text-center shadow-[0_24px_70px_rgba(131,84,0,0.08)] backdrop-blur-3xl">
      <div className="mx-auto mb-6 flex h-20 w-20 items-center justify-center rounded-full bg-[#ffddb5]/55 text-[#835400]">
        <span className="material-symbols-outlined text-4xl" style={{ fontVariationSettings: "'FILL' 1" }}>
          add_notes
        </span>
      </div>
      <h2 className="font-['Plus_Jakarta_Sans'] text-2xl font-bold text-[#1c1b1b]">还没有课程空间</h2>
      <p className="mx-auto mt-3 max-w-xl text-sm leading-7 text-[#524434]">
        先创建一门课程，再上传资料、生成 LLM Wiki、发起 AI 答疑和个性化练习。
      </p>
      <button
        className="mt-7 inline-flex items-center gap-2 rounded-full bg-[#f9a826] px-6 py-3 text-sm font-bold text-[#674100] shadow-[0_16px_34px_rgba(249,168,38,0.2)] transition hover:scale-[1.02]"
        onClick={onCreate}
        type="button"
      >
        <span className="material-symbols-outlined text-lg">add</span>
        创建第一门课程
      </button>
    </section>
  )
}
