import { useState, useRef } from 'react'
import api from '../services/api'
import type { Quiz, QuizResult, AddToReviewResult } from '../types'
import { Brain, CheckCircle, XCircle, AlertTriangle, BookOpenCheck, Check } from 'lucide-react'

type Phase = 'setup' | 'taking' | 'result'

function QuestionText({ text, maxLen = 50 }: { text: string; maxLen?: number }) {
  const truncated = text.length > maxLen ? text.slice(0, maxLen) + '…' : text
  return (
    <span className="group relative inline-block">
      <span className="cursor-help">{truncated}</span>
      {text.length > maxLen && (
        <span className="pointer-events-none absolute left-0 top-full z-20 hidden max-w-xl whitespace-pre-wrap rounded-lg border border-slate-600 bg-slate-700 p-3 text-xs leading-relaxed text-slate-100 shadow-xl group-hover:block">
          {text}
        </span>
      )}
    </span>
  )
}

export default function Quiz() {
  const [phase, setPhase] = useState<Phase>('setup')
  const [scope, setScope] = useState('topic')
  const [topic, setTopic] = useState('')
  const [timeRangeDays, setTimeRangeDays] = useState(7)
  const [difficulty, setDifficulty] = useState('medium')
  const [questionCount, setQuestionCount] = useState(5)
  const [quiz, setQuiz] = useState<Quiz | null>(null)
  const [answers, setAnswers] = useState<Record<string, string>>({})
  const [result, setResult] = useState<QuizResult | null>(null)
  const [loading, setLoading] = useState(false)

  const [error, setError] = useState<string | null>(null)

  const [showConfirm, setShowConfirm] = useState(false)
  const unansweredRef = useRef<string[]>([])
  const questionRefs = useRef<Record<string, HTMLDivElement | null>>({})
  const [selectedReviews, setSelectedReviews] = useState<Set<string>>(new Set())
  const [addingReview, setAddingReview] = useState(false)
  const [reviewAdded, setReviewAdded] = useState<number | null>(null)
  const [reviewSkipped, setReviewSkipped] = useState(0)

  const startQuiz = async () => {
    setLoading(true)
    setError(null)
    try {
      const res = await api.post('/quiz/generate', {
        scope,
        topic,
        time_range: scope === 'time_range' ? { days: timeRangeDays } : undefined,
        difficulty,
        question_count: questionCount,
      })
      setQuiz(res.data)
      setPhase('taking')
    } catch (err: any) {
      setError(err.response?.data?.detail || '测验生成失败，请稍后重试')
    } finally { setLoading(false) }
  }

  const submitQuiz = async () => {
    if (!quiz) return
    setLoading(true)
    setShowConfirm(false)
    try {
      const res = await api.post('/quiz/submit', { quiz_id: quiz.id, answers })
      setResult(res.data)
      setSelectedReviews(new Set((res.data.suggested_reviews || []).map((sr: { wrong_id: string }) => sr.wrong_id)))
      setPhase('result')
    } catch { /* ignore */ } finally { setLoading(false) }
  }

  const handleSubmitClick = () => {
    if (!quiz) return
    const unanswered = quiz.questions
      .filter((q) => !answers[q.id] || !String(answers[q.id]).trim())
      .map((q) => q.id)
    if (unanswered.length === 0) {
      submitQuiz()
    } else {
      unansweredRef.current = unanswered
      setShowConfirm(true)
    }
  }

  const continueAnswering = () => {
    setShowConfirm(false)
    if (!quiz) return
    const ids = unansweredRef.current
    if (ids.length === 0) return
    const firstId = quiz.questions.find((q) => ids.includes(q.id))!.id
    questionRefs.current[firstId]?.scrollIntoView({ behavior: 'smooth', block: 'center' })
  }

  const setAnswer = (qId: string, val: string) => setAnswers((prev) => ({ ...prev, [qId]: val }))

  const reset = () => {
    setPhase('setup')
    setQuiz(null)
    setResult(null)
    setAnswers({})
    setShowConfirm(false)
    setSelectedReviews(new Set())
    setReviewAdded(null)
    setReviewSkipped(0)
  }

  const toggleReview = (wrongId: string) => {
    setSelectedReviews((prev) => {
      const next = new Set(prev)
      if (next.has(wrongId)) next.delete(wrongId)
      else next.add(wrongId)
      return next
    })
  }

  const confirmAddToReview = async () => {
    if (!result?.suggested_reviews || selectedReviews.size === 0) return
    setAddingReview(true)
    try {
      const res = await api.post<AddToReviewResult>('/quiz/wrong-book/add-to-review', {
        wrong_ids: [...selectedReviews],
      })
      setReviewAdded(res.data.added)
      setReviewSkipped(res.data.skipped)
      setSelectedReviews(new Set())
    } catch {
      setReviewAdded(0)
    } finally { setAddingReview(false) }
  }

  if (phase === 'setup') {
    return (
      <div className="p-6 max-w-lg mx-auto space-y-6">
        <h1 className="text-2xl font-bold flex items-center gap-2"><Brain size={24} /> 智能测验</h1>
        <div className="bg-slate-800 rounded-xl p-5 border border-slate-700 space-y-4">
          <div>
            <label className="block text-sm text-slate-300 mb-1">测验范围</label>
            <select value={scope} onChange={(e) => setScope(e.target.value)} className="w-full px-3 py-2 bg-slate-700 border border-slate-600 rounded-lg text-sm">
              <option value="topic">按主题</option>
              <option value="time_range">按时间范围</option>
              <option value="wrong_review">错题复习</option>
            </select>
          </div>
          {scope === 'topic' && (
            <div>
              <label className="block text-sm text-slate-300 mb-1">主题</label>
              <input value={topic} onChange={(e) => setTopic(e.target.value)} placeholder="如: Python 基础" className="w-full px-3 py-2 bg-slate-700 border border-slate-600 rounded-lg text-sm" />
            </div>
          )}
          {scope === 'time_range' && (
            <div>
              <label className="block text-sm text-slate-300 mb-1">时间范围</label>
              <select value={timeRangeDays} onChange={(e) => setTimeRangeDays(Number(e.target.value))} className="w-full px-3 py-2 bg-slate-700 border border-slate-600 rounded-lg text-sm">
                <option value={1}>最近 1 天</option>
                <option value={3}>最近 3 天</option>
                <option value={7}>最近 7 天</option>
                <option value={30}>最近 30 天</option>
              </select>
            </div>
          )}
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-sm text-slate-300 mb-1">难度</label>
              <select value={difficulty} onChange={(e) => setDifficulty(e.target.value)} className="w-full px-3 py-2 bg-slate-700 border border-slate-600 rounded-lg text-sm">
                <option value="easy">简单</option>
                <option value="medium">中等</option>
                <option value="hard">困难</option>
              </select>
            </div>
            <div>
              <label className="block text-sm text-slate-300 mb-1">题数</label>
              <select value={questionCount} onChange={(e) => setQuestionCount(Number(e.target.value))} className="w-full px-3 py-2 bg-slate-700 border border-slate-600 rounded-lg text-sm">
                {[3, 5, 8, 10].map((n) => <option key={n} value={n}>{n} 题</option>)}
              </select>
            </div>
          </div>
          <button onClick={startQuiz} disabled={loading} className="w-full py-2.5 bg-primary-600 hover:bg-primary-700 disabled:opacity-50 rounded-lg font-medium transition-colors">
            {loading ? '生成中...' : '开始测验'}
          </button>
          {error && <p className="text-red-400 text-sm mt-2">{error}</p>}
        </div>
      </div>
    )
  }

  if (phase === 'taking' && quiz) {
    return (
      <div className="p-6 max-w-2xl mx-auto space-y-6">
        <div className="sticky top-0 z-10 bg-slate-900/95 backdrop-blur py-3 -mx-6 px-6 border-b border-slate-800 flex items-center justify-between">
          <h1 className="text-xl font-bold">答题中</h1>
          <span className="text-sm text-slate-400">已答 {Object.keys(answers).length} / {quiz.questions.length} 题</span>
        </div>
        <div className="space-y-4">
          {quiz.questions.map((q, i) => (
            <div key={q.id} ref={(el) => { questionRefs.current[q.id] = el }} className="bg-slate-800 rounded-xl p-5 border border-slate-700">
              <p className="font-medium mb-3">{i + 1}. {q.question}</p>
              {q.type === 'choice' && q.options ? (
                <div className="space-y-2">
                  {Object.entries(q.options).map(([key, val]) => (
                    <label key={key} className={`flex items-center gap-3 p-3 rounded-lg cursor-pointer transition-colors ${answers[q.id] === key ? 'bg-primary-600/20 border border-primary-500' : 'bg-slate-700/50 border border-transparent hover:border-slate-600'}`}>
                      <input type="radio" name={q.id} checked={answers[q.id] === key} onChange={() => setAnswer(q.id, key)} className="accent-primary-500" />
                      <span className="text-sm">{key}. {val}</span>
                    </label>
                  ))}
                </div>
              ) : (
                <textarea value={answers[q.id] || ''} onChange={(e) => setAnswer(q.id, e.target.value)} rows={3} placeholder="请输入答案..." className="w-full px-3 py-2 bg-slate-700 border border-slate-600 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-primary-500 resize-none" />
              )}
            </div>
          ))}
        </div>
        <button onClick={handleSubmitClick} disabled={loading} className="w-full py-2.5 bg-primary-600 hover:bg-primary-700 disabled:opacity-50 rounded-lg font-medium transition-colors">
          {loading ? '评分中...' : '提交测验'}
        </button>

        {showConfirm && (
          <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4">
            <div className="bg-slate-800 rounded-xl p-6 w-full max-w-md border border-slate-700">
              <div className="flex items-center gap-2 mb-3">
                <AlertTriangle size={20} className="text-amber-400" />
                <h2 className="text-lg font-bold">确认提交测验</h2>
              </div>
              <p className="text-sm text-slate-300 mb-3">以下题目未作答，提交后这些题将不计分：</p>
              <div className="space-y-1.5 max-h-40 overflow-y-auto mb-4">
                {quiz.questions
                  .filter((q) => unansweredRef.current.includes(q.id))
                  .map((q) => (
                    <p key={q.id} className="text-sm text-red-300 bg-slate-700/50 rounded px-3 py-1.5">
                      {quiz.questions.indexOf(q) + 1}. {q.question}
                    </p>
                  ))}
              </div>
              <div className="flex gap-2 justify-end">
                <button onClick={continueAnswering} className="px-4 py-2 text-sm bg-slate-700 hover:bg-slate-600 rounded-lg transition-colors">
                  继续答题
                </button>
                <button onClick={submitQuiz} disabled={loading} className="px-4 py-2 text-sm bg-primary-600 hover:bg-primary-700 disabled:opacity-50 rounded-lg transition-colors">
                  确认提交
                </button>
              </div>
            </div>
          </div>
        )}
      </div>
    )
  }

  if (phase === 'result' && result) {
    return (
      <div className="p-6 max-w-2xl mx-auto space-y-6">
        <h1 className="text-2xl font-bold">测验结果</h1>
        <div className="bg-slate-800 rounded-xl p-5 border border-slate-700 text-center">
          <p className="text-4xl font-bold text-primary-400">{result.score.toFixed(1)}%</p>
          <p className="text-slate-400 mt-1">{result.correct_count} / {result.total_questions} 正确</p>
          <p className={`text-sm mt-2 ${result.mastery_change >= 0 ? 'text-green-400' : 'text-red-400'}`}>
            掌握度 {result.mastery_change >= 0 ? '+' : ''}{result.mastery_change.toFixed(1)}
          </p>
        </div>

        {result.suggested_reviews && result.suggested_reviews.length > 0 && (
          <div className="bg-amber-500/10 border border-amber-500/40 rounded-xl overflow-hidden">
            <div className="flex items-center gap-2 px-5 py-3 border-b border-amber-500/20">
              <BookOpenCheck size={18} className="text-amber-400" />
              <h2 className="font-bold text-amber-300">加入复习计划</h2>
              <span className="text-xs text-amber-400/80 ml-auto">已选 {selectedReviews.size} / {result.suggested_reviews.length} 道错题</span>
            </div>
            <div className="space-y-1.5 p-3 max-h-48 overflow-y-auto">
              {result.suggested_reviews.map((sr) => (
                <label key={sr.wrong_id} className="flex items-start gap-3 px-3 py-2 rounded-lg cursor-pointer transition-colors hover:bg-slate-700/40">
                  <input
                    type="checkbox"
                    checked={selectedReviews.has(sr.wrong_id)}
                    onChange={() => toggleReview(sr.wrong_id)}
                    className="mt-1 accent-amber-500"
                  />
                  <span className="text-sm text-slate-300"><QuestionText text={sr.question?.question || sr.correct_answer || ''} /></span>
                </label>
              ))}
            </div>
            <div className="flex gap-2 px-5 py-3 border-t border-amber-500/20">
              <button
                onClick={confirmAddToReview}
                disabled={addingReview || selectedReviews.size === 0}
                className="flex-1 py-2 bg-amber-600 hover:bg-amber-700 disabled:opacity-50 rounded-lg text-sm font-medium transition-colors"
              >
                {addingReview ? '加入中...' : `加入复习计划（${selectedReviews.size}）`}
              </button>
              {reviewAdded !== null && (
                <span className="flex items-center gap-1 text-sm text-green-400"><Check size={14} /> 已加入 {reviewAdded} 项，{reviewSkipped > 0 ? `${reviewSkipped} 项已存在` : ''}</span>
              )}
            </div>
          </div>
        )}

        <div className="space-y-3">
          {result.results.map((r, i) => (
            <div key={r.question_id} className="bg-slate-800 rounded-lg p-4 border border-slate-700">
              <div className="flex items-start gap-3">
                {r.correct ? <CheckCircle size={18} className="text-green-400 mt-0.5 shrink-0" /> : <XCircle size={18} className="text-red-400 mt-0.5 shrink-0" />}
                <div className="flex-1 min-w-0 text-sm">
                  <p className="font-medium">
                    {i + 1}. <QuestionText text={r.question || r.question_id} />
                  </p>
                  {r.correct ? (
                    <p className="text-slate-400 mt-1">
                      {r.user_answer
                        ? `回答正确： ${r.user_answer}${r.options?.[r.user_answer] ? ` ：${r.options[r.user_answer]}` : ''}`
                        : '回答正确'}
                    </p>
                  ) : (
                    <div className="mt-3 space-y-2">
                      <p className="text-slate-200 leading-relaxed">{r.question}</p>
                      {r.options ? (
                        <div className="space-y-1.5">
                          {Object.entries(r.options).map(([key, val]) => {
                            const isUserWrong = key === r.user_answer
                            const isCorrect = key === r.correct_answer
                            return (
                              <div key={key} className={`flex items-center gap-2 rounded-lg px-3 py-1.5 border ${isCorrect ? 'bg-green-500/10 border-green-500/40' : isUserWrong ? 'bg-red-500/10 border-red-500/40' : 'bg-slate-700/40 border-transparent'}`}>
                                <span className={`w-4 shrink-0 text-center font-bold ${isCorrect ? 'text-green-500' : isUserWrong ? 'text-red-500' : ''}`}>
                                  {isCorrect ? '✔️' : isUserWrong ? '×' : ''}
                                </span>
                                <span className="text-slate-200">{key}. {val}</span>
                                {isUserWrong && <span className="ml-auto text-xs text-red-400 shrink-0">你的选择</span>}
                                {isCorrect && <span className="ml-auto text-xs text-green-400 shrink-0">正确答案</span>}
                              </div>
                            )
                          })}
                        </div>
                      ) : (
                        <div className="space-y-1">
                          {r.user_answer && (
                            <p className="text-red-400/90"><span className="font-bold text-red-500 mr-1">×</span>你的答案：{r.user_answer}</p>
                          )}
                          <p className="text-green-400/90"><span className="font-bold text-green-500 mr-1">✔️</span>正确答案：{r.correct_answer}</p>
                        </div>
                      )}
                      <div className="rounded-lg bg-slate-700/50 border border-slate-600/60 p-3">
                        <p className="text-slate-300 leading-relaxed">
                          <span className="text-primary-400 font-medium">为什么答案是 {r.correct_answer}？</span> {r.explanation || r.feedback}
                        </p>
                      </div>
                    </div>
                  )}
                </div>
                <span className="text-sm font-medium shrink-0">{r.score}/{r.max_score}</span>
              </div>
            </div>
          ))}
        </div>

        <button onClick={reset} className="w-full py-2.5 bg-slate-700 hover:bg-slate-600 rounded-lg font-medium transition-colors">
          重新测验
        </button>
      </div>
    )
  }

  return null
}
