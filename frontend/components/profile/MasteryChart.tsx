"use client"

interface MasteryChartProps {
  mastery: Record<string, number>
}

export function MasteryChart({ mastery }: MasteryChartProps) {
  const entries = Object.entries(mastery)
  if (entries.length === 0) {
    return (
      <div className="flex items-center justify-center h-48 text-on-surface-variant text-body-md">
        暂无掌握度数据
      </div>
    )
  }

  const avgMastery = entries.reduce((sum, [, v]) => sum + v, 0) / entries.length
  const percent = Math.round(avgMastery * 100)
  const circumference = 2 * Math.PI * 42
  const offset = circumference * (1 - avgMastery)

  return (
    <div className="flex flex-col items-center">
      <div className="relative aspect-square w-full max-w-[200px] mx-auto flex items-center justify-center">
        <svg className="w-full h-full -rotate-90" viewBox="0 0 100 100">
          <circle
            className="text-surface-container-high"
            cx="50" cy="50" fill="transparent" r="42"
            stroke="currentColor" strokeWidth="8"
          />
          <circle
            className="text-primary"
            cx="50" cy="50" fill="transparent" r="42"
            stroke="currentColor"
            strokeDasharray={circumference}
            strokeDashoffset={offset}
            strokeLinecap="round"
            strokeWidth="8"
          />
        </svg>
        <div className="absolute text-center">
          <p className="text-4xl font-extrabold text-on-surface">{percent}%</p>
          <p className="text-label-sm text-on-surface-variant uppercase tracking-widest mt-1">知识掌控度</p>
        </div>
      </div>

      <div className="mt-6 w-full space-y-2">
        {entries.slice(0, 5).map(([topic, value]) => (
          <div key={topic} className="flex items-center gap-3">
            <span className="text-label-sm text-on-surface-variant w-24 truncate">{topic}</span>
            <div className="flex-1 h-2 bg-surface-container-high rounded-full overflow-hidden">
              <div
                className="h-full bg-primary rounded-full transition-all"
                style={{ width: `${Math.round(value * 100)}%` }}
              />
            </div>
            <span className="text-label-sm text-on-surface-variant w-10 text-right">
              {Math.round(value * 100)}%
            </span>
          </div>
        ))}
      </div>
    </div>
  )
}
