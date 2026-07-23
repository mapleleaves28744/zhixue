"use client"

import { useMemo, useState } from "react"

interface Flashcard {
  front: string
  back: string
  hint?: string
}

function parseFlashcards(content: string): Flashcard[] {
  const source = String(content || "").trim().replace(/^```json\s*/i, "").replace(/```$/, "")
  try {
    const parsed = JSON.parse(source) as { cards?: unknown }
    if (!Array.isArray(parsed.cards)) return []
    return parsed.cards
      .filter((card): card is Record<string, unknown> => Boolean(card) && typeof card === "object")
      .map((card) => ({
        front: String(card.front || "").trim(),
        back: String(card.back || "").trim(),
        hint: String(card.hint || "").trim() || undefined,
      }))
      .filter((card) => card.front && card.back)
  } catch {
    return []
  }
}

export function FlashcardDeck({ content, title }: { content: string; title: string }) {
  const cards = useMemo(() => parseFlashcards(content), [content])
  const [index, setIndex] = useState(0)
  const [flipped, setFlipped] = useState(false)
  const [showHint, setShowHint] = useState(false)
  const card = cards[index]

  if (!card) return null

  const move = (delta: number) => {
    setIndex((value) => (value + delta + cards.length) % cards.length)
    setFlipped(false)
    setShowHint(false)
  }

  return (
    <section className="overflow-hidden rounded-2xl border border-amber-200/70 bg-gradient-to-br from-amber-50 via-white to-orange-50 shadow-sm">
      <header className="flex items-center justify-between gap-3 border-b border-amber-200/60 px-5 py-3">
        <div>
          <p className="text-xs font-bold uppercase tracking-[0.14em] text-amber-700">主动回忆</p>
          <h3 className="mt-0.5 text-sm font-bold text-on-surface">{title}</h3>
        </div>
        <span className="rounded-full bg-white/80 px-3 py-1 text-xs font-bold text-amber-800">
          {index + 1} / {cards.length}
        </span>
      </header>
      <div className="p-5">
        <button
          type="button"
          onClick={() => setFlipped((value) => !value)}
          className="min-h-56 w-full rounded-2xl border border-amber-200 bg-white p-6 text-left shadow-sm transition hover:-translate-y-0.5 hover:shadow-md"
          aria-label="翻转复习卡"
        >
          <p className="text-xs font-bold text-amber-700">{flipped ? "答案 / 解释" : "问题"}</p>
          <p className="mt-4 whitespace-pre-wrap text-lg font-semibold leading-8 text-on-surface">
            {flipped ? card.back : card.front}
          </p>
          <p className="mt-5 text-xs text-outline">点击卡片{flipped ? "返回问题" : "查看答案"}</p>
        </button>
        {card.hint ? (
          <div className="mt-3">
            <button type="button" onClick={() => setShowHint((value) => !value)} className="text-xs font-bold text-primary">
              {showHint ? "收起提示" : "需要一点提示"}
            </button>
            {showHint ? <p className="mt-2 rounded-xl bg-amber-100/70 px-3 py-2 text-sm text-on-surface">{card.hint}</p> : null}
          </div>
        ) : null}
        <div className="mt-5 flex items-center justify-between gap-3">
          <button type="button" onClick={() => move(-1)} className="rounded-xl border border-amber-200 bg-white px-4 py-2 text-sm font-bold text-on-surface">
            上一张
          </button>
          <button type="button" onClick={() => setFlipped((value) => !value)} className="rounded-xl bg-primary px-4 py-2 text-sm font-bold text-on-primary">
            {flipped ? "再想一次" : "翻看答案"}
          </button>
          <button type="button" onClick={() => move(1)} className="rounded-xl border border-amber-200 bg-white px-4 py-2 text-sm font-bold text-on-surface">
            下一张
          </button>
        </div>
      </div>
    </section>
  )
}
