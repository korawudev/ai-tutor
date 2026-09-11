/**
 * 前端类型门面（facade）
 *
 * 契约来源：shared/models 的 Pydantic schema。
 * 再生成链路：
 *   ai-tutor/.venv/bin/python ai-tutor/scripts/export_openapi.py > /tmp/schemas.json
 *   cd web-app && npm run gen:types   # openapi-typescript /tmp/schemas.json -o src/types/generated.ts
 *
 * - 与后端 1:1 的类型直接透传 generated.ts（字段增删由后端驱动）
 * - 后端仅声明 `dict` 的字段（options/mastery_change/queue/stats...）由前端细化结构
 * - ReviewBatch/VerifyItem/BatchStats/DashboardData 等为纯前端组合类型，无后端对应
 */
import type { components } from './generated'

type Schemas = components['schemas']

// ===== 1:1 透传后端 schema =====
export type User = Schemas['UserResponse']
export type Document = Schemas['DocumentResponse']
export type Thread = Schemas['ThreadResponse']
export type WrongQuestion = Schemas['WrongQuestionResponse']
export type ReviewItem = Schemas['ReviewItem']
export type ReviewStats = Schemas['ReviewListResponse']
export type ReviewResult = Schemas['ReviewResult']
export type NormalReviewAnswerType = Schemas['NormalReviewAnswer']
export type NormalReviewSubmit = Schemas['NormalReviewSubmit']
export type FeynmanVerifyResponse = Schemas['FeynmanVerifyResponse']
export type BatchCompletePayload = Schemas['BatchCompleteSubmit']

// ===== 细化后端 dict 字段（后端 dict → 前端结构化） =====
export type Quiz = Omit<Schemas['QuizResponse'], 'questions' | 'topic'> & {
  questions: QuizQuestion[]
  topic?: string
}

export type QuizQuestion = Omit<Schemas['QuizQuestion'], 'type' | 'options' | 'topic'> & {
  type: 'choice' | 'short_answer' | 'concept_analysis'
  options?: Record<string, string>
  topic?: string
}

export interface QuizResultItem {
  question_id: string
  type?: string
  question?: string
  options?: Record<string, string>
  correct: boolean
  score: number
  max_score: number
  feedback: string
  user_answer: string
  correct_answer: string
  explanation?: string
}

export interface QuizResultWrongItem {
  id: string
  question: Record<string, unknown>
  user_answer: string
  correct_answer: string
}

export type QuizResult = Omit<
  Schemas['QuizResult'],
  'results' | 'wrong_questions' | 'suggested_reviews'
> & {
  results: QuizResultItem[]
  wrong_questions: QuizResultWrongItem[]
  suggested_reviews?: SuggestedReview[]
}

export type SuggestedReview = Omit<Schemas['SuggestedReview'], 'question'> & {
  question: {
    id?: string
    question?: string
    type?: string
    options?: Record<string, string>
    answer?: string
    explanation?: string
    topic?: string
    points?: number
  }
}

export type AddToReviewResult = Omit<Schemas['AddToReviewResponse'], 'items'> & {
  items: {
    wrong_id: string
    schedule_id: string
    topic: string
    next_review: string
  }[]
}

export type NormalReviewResponse = Omit<Schemas['NormalReviewResponse'], 'mastery_change'> & {
  mastery_change: {
    old: number
    new: number
    delta: number
  } | null
}

// ===== 纯前端组合类型（无后端 Pydantic 对应） =====
export interface ReviewBatchItem {
  schedule_id: string
  chunk_id: string
  chunk_title: string
  chunk_content: string
  position: number
  retry_reason?: 'vague' | 'forgotten'
  first_answer?: 'mastered' | 'vague' | 'forgotten'
  is_retry: boolean
}

export interface ReviewBatch {
  batch_id: string
  source_type: 'daily' | 'wrong_book' | 'manual'
  main_queue: ReviewBatchItem[]
  retry_queue: ReviewBatchItem[]
  stats: {
    total: number
    completed: number
    retry_count: number
  }
}

export interface VerifyItem {
  item: ReviewItem
  reason: 'vague' | 'forgotten'
  feynman?: boolean
}

export interface BatchStats {
  batch_id: string
  total: number
  mastered_count: number
  retry_count: number
  total_response_ms: number
  started_at: number
  retry_map: Record<string, number>
}

// 后端 /review/session 的 stats/queue 字段为原样 dict，前端细化结构
export type SessionSnapshot = Omit<
  Schemas['SessionSnapshot'],
  'retry_queue' | 'verify_queue' | 'stats'
> & {
  retry_queue: VerifyItem[]
  verify_queue: VerifyItem[]
  stats: BatchStats
}

export interface DashboardData {
  summary: {
    total_documents: number
    total_concepts: number
    mastered_concepts: number
    mastery_rate: number
    average_mastery: number
  }
  today: {
    documents_read: number
    quizzes_taken: number
    quiz_avg_score: number
    feynman_sessions: number
    feynman_avg_score: number
    reviews_completed: number
    time_spent_minutes: number
  }
  trend: { date: string; score: number }[]
}

export interface MasteryRecord {
  id: string
  chunk_id: string
  topic: string
  mastery_score: number
  quiz_accuracy: number
  feynman_score: number
  review_count: number
  updated_at: string
}