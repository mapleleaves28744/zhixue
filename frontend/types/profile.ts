export interface StudentProfile {
  id: string
  user_id: string
  major: string | null
  grade: string | null
  learning_goal: string | null
  profile_summary: string | null
  mastery_snapshot: Record<string, number>
  weak_points: string[]
  error_patterns: string[]
  strategy_summary: Record<string, string>
  version_no: number
  created_at: string
  updated_at: string
}

export interface ProfileSummary {
  profile_summary: string | null
  mastery_snapshot: Record<string, number>
  weak_points: string[]
  error_patterns: string[]
  strategy_summary: Record<string, string>
}

export interface ProfileUpdate {
  major?: string
  grade?: string
  learning_goal?: string
}

export interface LearningPreference {
  id: string
  user_id: string
  course_id: string | null
  answer_length: string | null
  explanation_style: string | null
  resource_preferences: string[]
  confidence: number
  version_no: number
}
