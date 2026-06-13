export interface QuizQuestion {
  id: string
  quiz_id?: string | null
  course_id: string
  question_type: string
  difficulty?: string | null
  question_text: string
  options: unknown
  standard_answer?: string
  analysis?: string | null
}

export interface QuizDetail {
  id: string
  user_id: string
  course_id: string
  title: string
  quiz_type: string
  difficulty?: string | null
  status: string
  created_at?: string | null
  questions: QuizQuestion[]
}
