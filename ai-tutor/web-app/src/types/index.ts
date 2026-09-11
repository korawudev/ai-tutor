export interface User {
  id: string
  email: string
  username: string
}

export interface Document {
  id: string
  title: string
  source_url?: string
  source_type: string
  status: string
  tags: string[]
  chunk_count: number
  error_message?: string
  created_at: string
  processed_at?: string
}

export interface Thread {
  id: string
  agent_type: string
  title?: string
  status: string
  state: Record<string, unknown>
  created_at: string
}

export interface Quiz {
  id: string
  scope: string
  topic?: string
  questions: QuizQuestion[]
  total_questions: number
  status: string
  created_at: string
}

export interface QuizQuestion {
  id: string
  type: 'choice' | 'short_answer' | 'concept_analysis'
  question: string
  options?: Record<string, string>
  topic?: string
}

export interface QuizResult {
  quiz_id: string
  score: number
  total_questions: number
  correct_count: number
  results: {
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
  }[]
  wrong_questions: {
    id: string
    question: Record<string, unknown>
    user_answer: string
    correct_answer: string
  }[]
  suggested_reviews?: SuggestedReview[]
  mastery_change: number
  time_spent_seconds: number
}

export interface SuggestedReview {
  wrong_id: string
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
  user_answer?: string
  correct_answer?: string
  explanation?: string
}

export interface AddToReviewResult {
  added: number
  skipped: number
  items: {
    wrong_id: string
    schedule_id: string
    topic: string
    next_review: string
  }[]
}

export interface WrongQuestion {
  id: string
  question: Record<string, unknown>
  user_answer?: string
  correct_answer?: string
  explanation?: string
  review_count: number
  mastered: boolean
  in_review?: boolean
  created_at: string
}

export interface ReviewItem {
  schedule_id: string
  chunk_id: string
  topic: string
  answer?: string
  mastery_score: number
  next_review: string
  interval_days: number
  review_count: number
  status: string
  source?: string
  reason?: string
  is_mastered?: boolean
  correct_streak?: number
}

export type NormalReviewAnswerType = 'mastered' | 'vague' | 'forgotten'

export interface NormalReviewSubmit {
  schedule_id: string
  answer: 'mastered' | 'vague' | 'forgotten'
  response_time_ms: number
}

export interface NormalReviewResponse {
  schedule_id: string
  chunk_id: string
  next_review_time: string
  ease_factor: number
  correct_streak: number
  is_mastered: boolean
  need_session_retry: boolean
  retry_reason: string | null
  mastery_change: {
    old: number
    new: number
    delta: number
  } | null
}

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

export interface ReviewStats {
  pending_count: number
  overdue_count: number
  items: ReviewItem[]
}

export interface ReviewResult {
  schedule_id: string
  old_interval: number
  new_interval: number
  ease_factor: number
  mastery_score: number
  next_review: string
  status: string
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

export interface FeynmanVerifyResponse {
  schedule_id: string
  score: number
  passed: boolean
  strengths: string[]
  weaknesses: string[]
  suggestions: string[]
  correct_answer: string
}

export interface SessionSnapshot {
  batch_id: string
  batch_index: number
  main_queue: ReviewItem[]
  retry_queue: VerifyItem[]
  verify_queue: VerifyItem[]
  current_card: ReviewItem | null
  stats: BatchStats
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

export interface BatchCompletePayload {
  batch_id: string
  total_count: number
  mastered_count: number
  retry_count: number
  duration_sec: number
  avg_response_ms: number
}
