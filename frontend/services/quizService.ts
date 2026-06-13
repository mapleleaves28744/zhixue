import { request } from "@/lib/request"
import type { QuizDetail } from "@/types/quiz"

export function getQuiz(quizId: string): Promise<QuizDetail> {
  return request<QuizDetail>(`/quizzes/${quizId}`)
}
