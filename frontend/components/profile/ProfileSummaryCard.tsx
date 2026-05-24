"use client"

import { Button } from "@/components/ui/button"
import { MasteryChart } from "./MasteryChart"
import type { ProfileSummary, LearningPreference } from "@/types/profile"

interface ProfileSummaryCardProps {
  summary: ProfileSummary
  preferences: LearningPreference[]
  onRebuild: () => void
  rebuilding: boolean
}

export function ProfileSummaryCard({ summary, preferences, onRebuild, rebuilding }: ProfileSummaryCardProps) {
  return (
    <div className="glass-card rounded-xl p-8 flex flex-col">
      <h3 className="font-headline-md text-headline-md mb-6 flex items-center">
        <span className="material-symbols-outlined mr-2 text-secondary">face_6</span>
        学生画像摘要
      </h3>

      {summary.profile_summary && (
        <p className="text-body-md text-on-surface-variant mb-6 leading-relaxed">
          {summary.profile_summary}
        </p>
      )}

      <MasteryChart mastery={summary.mastery_snapshot} />

      {preferences.length > 0 && (
        <div className="mt-6 space-y-3">
          <p className="text-label-md font-bold flex items-center text-on-surface">
            <span className="material-symbols-outlined text-lg mr-2 text-outline">psychology_alt</span>
            学习偏好
          </p>
          <div className="flex flex-wrap gap-2">
            {preferences.map((pref) => (
              <span
                key={pref.id}
                className="text-label-sm px-3 py-1.5 rounded-full bg-secondary-fixed text-on-secondary-fixed-variant"
              >
                {pref.explanation_style || pref.answer_length || "默认偏好"}
              </span>
            ))}
          </div>
        </div>
      )}

      {summary.weak_points.length > 0 && (
        <div className="mt-6 space-y-2">
          <p className="text-label-md font-bold flex items-center text-on-surface">
            <span className="material-symbols-outlined text-lg mr-2 text-error">warning</span>
            薄弱知识点
          </p>
          <div className="flex flex-wrap gap-2">
            {summary.weak_points.map((point, i) => (
              <span
                key={i}
                className="text-label-sm px-3 py-1.5 rounded-full bg-error-container text-on-error-container"
              >
                {String(point)}
              </span>
            ))}
          </div>
        </div>
      )}

      {summary.error_patterns.length > 0 && (
        <div className="mt-6 space-y-2">
          <p className="text-label-md font-bold flex items-center text-on-surface">
            <span className="material-symbols-outlined text-lg mr-2 text-outline">bug_report</span>
            错误模式
          </p>
          <div className="space-y-1">
            {summary.error_patterns.map((pattern, i) => (
              <p key={i} className="text-body-md text-on-surface-variant">
                {String(pattern)}
              </p>
            ))}
          </div>
        </div>
      )}

      <div className="mt-8 pt-6 border-t border-outline-variant/30">
        <Button
          onClick={onRebuild}
          disabled={rebuilding}
          className="w-full"
        >
          <span className="material-symbols-outlined text-[18px] mr-1">
            {rebuilding ? "hourglass_top" : "refresh"}
          </span>
          {rebuilding ? "重建中..." : "重建画像"}
        </Button>
      </div>
    </div>
  )
}
