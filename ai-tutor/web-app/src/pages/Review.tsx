import { useEffect, useRef, useState, useCallback } from 'react'
import { reviewApi } from '../services/api'
import type { NormalReviewAnswerType, NormalReviewResponse, ReviewItem, FeynmanVerifyResponse, BatchStats } from '../types'
import { BookOpen, ArrowRight, PartyPopper, RefreshCcw, Pause, Target } from 'lucide-react'

// 三分支按钮配置（前端 3 级 → 后端 SM-2 三分支）
const FEEDBACK_OPTIONS: { value: NormalReviewAnswerType; label: string; color: string; desc: string }[] = [
  { value: 'forgotten', label: '不认识', color: 'bg-red-600 hover:bg-red-700', desc: '重置间隔' },
  { value: 'vague', label: '模糊', color: 'bg-amber-600 hover:bg-amber-700', desc: '缩短间隔' },
  { value: 'mastered', label: '认识', color: 'bg-emerald-600 hover:bg-emerald-700', desc: '大幅延长' },
]

// D3：费曼评分每组最多 AI 评分 5 题，其余退化为 binary 快速验证
const MAX_FEYNMAN_VERIFY = 5

const SOURCE_OPTIONS = [
  { value: 'daily', label: '日常复习' },
  { value: 'wrong_book', label: '错题回顾' },
  { value: 'manual', label: '手动添加' },
]

type Phase = 'select_source' | 'loading' | 'reviewing' | 'verifying' | 'feynman_verify' | 'done' | 'empty'

interface VerifyItem {
  item: ReviewItem
  reason: 'vague' | 'forgotten'
  feynman?: boolean
}

interface AnswerRecord {
  topic: string
  answer: NormalReviewAnswerType
  next_review_time: string
}

export default function Review() {
  const [phase, setPhase] = useState<Phase>('select_source')
  const [mainQueue, setMainQueue] = useState<ReviewItem[]>([])
  const [retryQueue, setRetryQueue] = useState<VerifyItem[]>([])
  const [verifyQueue, setVerifyQueue] = useState<VerifyItem[]>([])
  const [initialTotal, setInitialTotal] = useState(0)
  const [showAnswer, setShowAnswer] = useState(false)
  const [lastResult, setLastResult] = useState<NormalReviewResponse | null>(null)
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState('')
  const [lastAnswered, setLastAnswered] = useState<ReviewItem | null>(null)
  const [batchStats, setBatchStats] = useState<BatchStats | null>(null)
  const [explanation, setExplanation] = useState('')
  const [feynmanResult, setFeynmanResult] = useState<FeynmanVerifyResponse | null>(null)
  const [isVerifyingFeynman, setIsVerifyingFeynman] = useState(false)
  const [answerRecords, setAnswerRecords] = useState<AnswerRecord[]>([])

  const startTimeRef = useRef<number>(0)
  const lastActivityRef = useRef<number>(Date.now())
  const inactivityTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const feynmanCountRef = useRef<number>(0)
  const lastSourceRef = useRef<'daily' | 'wrong_book' | 'manual'>('daily')

  const isVerifying = phase === 'verifying'
  const isFeynmanVerify = phase === 'feynman_verify'
  const inVerification = isVerifying || isFeynmanVerify
  // 重试轮：主队列已空但重试队列未空（纯前端循环，直到选"认识"才放行）
  const retryRound = phase === 'reviewing' && mainQueue.length === 0 && retryQueue.length > 0
  const queueHead = inVerification
    ? verifyQueue[0]?.item ?? null
    : retryRound
      ? retryQueue[0]?.item ?? null
      : mainQueue[0] ?? null
  const current = showAnswer && !inVerification && lastAnswered ? lastAnswered : queueHead
  const retryReason = inVerification
    ? verifyQueue[0]?.reason ?? null
    : retryRound
      ? retryQueue[0]?.reason ?? null
      : null
  const totalDone = initialTotal - mainQueue.length - retryQueue.length - verifyQueue.length
  const progressPct = initialTotal > 0 ? Math.round((totalDone / initialTotal) * 100) : 0

  const resetInactivityTimer = useCallback(() => {
    lastActivityRef.current = Date.now()
    if (inactivityTimerRef.current) clearTimeout(inactivityTimerRef.current)
    inactivityTimerRef.current = setTimeout(() => {
      // 5 minutes of inactivity
      setPhase('done')
      setError('会话已暂停，请重新开始')
    }, 5 * 60 * 1000)
  }, [])

  useEffect(() => {
    if (phase === 'loading' || phase === 'reviewing' || phase === 'verifying' || phase === 'feynman_verify') {
      resetInactivityTimer()
      window.addEventListener('mousemove', resetInactivityTimer)
      window.addEventListener('keydown', resetInactivityTimer)
      return () => {
        window.removeEventListener('mousemove', resetInactivityTimer)
        window.removeEventListener('keydown', resetInactivityTimer)
        if (inactivityTimerRef.current) clearTimeout(inactivityTimerRef.current)
      }
    }
  }, [phase, resetInactivityTimer])

  // 复习会话自动保存：reviewing/verifying 期间每 20s 快照一次
  useEffect(() => {
    if (phase !== 'reviewing' && phase !== 'verifying') return
    const persist = () => {
      if (!batchStats) return
      reviewApi
        .saveSession({
          batch_id: batchStats.batch_id,
          batch_index: 0,
          main_queue: mainQueue,
          retry_queue: retryQueue,
          verify_queue: verifyQueue,
          current_card: current ?? null,
          stats: batchStats,
        })
        .catch((e) => console.error('save session failed:', e))
    }
    persist()
    const timer = setInterval(persist, 20000)
    return () => clearInterval(timer)
  }, [phase, batchStats, mainQueue, retryQueue, verifyQueue, current])

  // 挂载时尝试恢复上次未完成会话
  useEffect(() => {
    reviewApi
      .loadSession()
      .then((res) => {
        const snap = res.data
        setBatchStats(snap.stats)
        setMainQueue(snap.main_queue)
        setRetryQueue(snap.retry_queue ?? [])
        setVerifyQueue(snap.verify_queue)
        setInitialTotal(snap.stats.total > 0 ? snap.stats.total : snap.main_queue.length)
        const hasContent = snap.main_queue.length || snap.retry_queue.length || snap.verify_queue.length
        setPhase(hasContent ? 'reviewing' : 'select_source')
        if (hasContent) {
          startTimeRef.current = Date.now()
          setError('已恢复上次未完成的复习会话')
        }
      })
      .catch(() => {})
  }, [])

  // 正常完成 / 主动退出时上报 batch stats 并清理会话
  const finishBatch = useCallback(async (): Promise<void> => {
    const stats = batchStats
    if (stats && initialTotal > 0) {
      reviewApi
        .batchComplete({
          batch_id: stats.batch_id,
          total_count: stats.total,
          mastered_count: stats.mastered_count,
          retry_count: stats.retry_count,
          duration_sec: Math.round((Date.now() - stats.started_at) / 1000),
          avg_response_ms: stats.total > 0 ? Math.round(stats.total_response_ms / stats.total) : 0,
        })
        .catch((e) => console.error('batch complete failed:', e))
    }
    reviewApi.clearSession().catch(() => {})
  }, [batchStats, initialTotal])

  const completedRef = useRef(false)
  useEffect(() => {
    if (
      initialTotal > 0 &&
      mainQueue.length === 0 &&
      retryQueue.length === 0 &&
      verifyQueue.length === 0 &&
      phase === 'done' &&
      !completedRef.current
    ) {
      completedRef.current = true
      finishBatch()
    }
  }, [phase, mainQueue, retryQueue, verifyQueue, initialTotal, finishBatch])

  const startSession = async (source: 'daily' | 'wrong_book' | 'manual') => {
    setPhase('loading')
    setError('')
    lastSourceRef.current = source
    completedRef.current = false
    try {
      const res = await reviewApi.getPending(20, source)
      const items = res.data.items ?? []
      setMainQueue(items)
      setRetryQueue([])
      setVerifyQueue([])
      setInitialTotal(items.length)
      setShowAnswer(false)
      setLastResult(null)
      setLastAnswered(null)
      setFeynmanResult(null)
      setExplanation('')
      feynmanCountRef.current = 0
      startTimeRef.current = Date.now()

      const initialStats: BatchStats = {
        batch_id: `batch-${Date.now()}`,
        total: items.length,
        mastered_count: 0,
        retry_count: 0,
        total_response_ms: 0,
        started_at: Date.now(),
        retry_map: {}
      }
      setBatchStats(initialStats)

      if (items.length > 0) {
        setAnswerRecords([])
        setPhase('reviewing')
      } else {
        setBatchStats(null)
        setPhase('empty')
      }
    } catch (e) {
      console.error('load pending failed:', e)
      setError('加载待复习内容失败，请检查网络后重试')
      setPhase('select_source')
    }
  }

  const answerCurrent = async (answer: NormalReviewAnswerType): Promise<void> => {
    if (!current || submitting) return
    setSubmitting(true)
    const t0 = Date.now()
    try {
      const responseTime = t0 - startTimeRef.current
      const res = await reviewApi.submitNormal({
        schedule_id: current.schedule_id,
        answer,
        response_time_ms: responseTime,
      })
      const data = res.data
      const answered = current
      setLastAnswered(current)

      setMainQueue((q) => q.slice(1))
      setBatchStats((s) => {
        if (!s) return s
        const next = { ...s, total_response_ms: s.total_response_ms + responseTime }
        if (data.need_session_retry) {
          next.retry_count += 1
        } else if (answer === 'mastered') {
          next.mastered_count += 1
        }
        return next
      })
      // 记录最后一次有效作答（认识/模糊/不认识）及其下次复习时间，用于完成页展示
      setAnswerRecords((recs) => [
        ...recs.filter((r) => r.topic !== answered.topic),
        { topic: answered.topic, answer, next_review_time: data.next_review_time },
      ])
      if (data.need_session_retry) {
        setRetryQueue((v) => [
          ...v,
          { item: answered, reason: (data.retry_reason ?? 'vague') as 'vague' | 'forgotten' },
        ])
      }
      setLastResult(data)
      setShowAnswer(true)
    } catch (e) {
      console.error('submit normal failed:', e)
      setError('提交失败，请重试')
    } finally {
      setSubmitting(false)
      resetInactivityTimer()
    }
  }

  // 重试队列作答：纯前端逻辑，无后端交互；认识→放行出组进组后验证，模糊/不认识→压回队尾循环
  const handleRetryAnswer = (answer: NormalReviewAnswerType): void => {
    if (!current || submitting || retryQueue.length === 0) return
    const head = retryQueue[0]
    setLastAnswered(current)
    if (answer === 'mastered') {
      const feynman = feynmanCountRef.current < MAX_FEYNMAN_VERIFY && Math.random() < 0.5
      if (feynman) feynmanCountRef.current += 1
      setRetryQueue((q) => q.slice(1))
      setVerifyQueue((v) => [...v, { item: head.item, reason: head.reason, feynman }])
    } else {
      setRetryQueue((q) => [...q.slice(1), head])
    }
    setShowAnswer(true)
    setLastResult(null)
    resetInactivityTimer()
  }

  const handleNext = (): void => {
    setShowAnswer(false)
    setLastResult(null)
    setLastAnswered(null)
    startTimeRef.current = Date.now()
    if (mainQueue.length === 0 && retryQueue.length === 0) {
      setPhase(verifyQueue.length === 0 ? 'done' : 'verifying')
    }
  }

  const handleVerifyPass = (): void => {
    const remaining = verifyQueue.length - 1
    setVerifyQueue((v) => v.slice(1))
    setShowAnswer(false)
    setLastResult(null)
    setFeynmanResult(null)
    setExplanation('')
    startTimeRef.current = Date.now()
    if (remaining <= 0) {
      setPhase('done')
    } else {
      setPhase('verifying')
    }
  }

  const handleVerifyFail = async (): Promise<void> => {
    if (!current || submitting) return
    setSubmitting(true)
    const t0 = Date.now()
    try {
      await reviewApi.submitVerificationFailed({
        chunk_id: current.chunk_id ?? null,
        schedule_id: current.schedule_id,
        response_time_ms: Date.now() - t0,
      })
      const remaining = verifyQueue.length - 1
      setVerifyQueue((v) => v.slice(1))
      setShowAnswer(false)
      setLastResult(null)
      startTimeRef.current = Date.now()
      if (remaining <= 0) {
        setPhase('done')
      }
    } catch (e) {
      console.error('verification failed submit error:', e)
      setError('提交失败，请重试')
    } finally {
      setSubmitting(false)
    }
  }

  const handleFeynmanVerify = async (): Promise<void> => {
    if (!current || submitting || !explanation.trim()) return
    setSubmitting(true)
    setIsVerifyingFeynman(true)
    try {
      const res = await reviewApi.feynmanVerify({
        schedule_id: current.schedule_id,
        explanation,
      })
      setFeynmanResult(res.data)
      if (!res.data.passed) {
        await reviewApi.submitVerificationFailed({
          chunk_id: current.chunk_id ?? null,
          schedule_id: current.schedule_id,
          response_time_ms: Date.now() - startTimeRef.current,
        })
      } else {
        if (batchStats) setBatchStats({ ...batchStats, mastered_count: batchStats.mastered_count + 1 })
      }
    } catch (e) {
      console.error('feynman verify failed:', e)
      setError('AI评分失败，请重试')
    } finally {
      setSubmitting(false)
      setIsVerifyingFeynman(false)
      resetInactivityTimer()
    }
  }

  const handleMarkMastered = async (): Promise<void> => {
    if (!current || submitting) return
    setSubmitting(true)
    try {
      await reviewApi.markMastered(current.schedule_id)
      const remainingMain = mainQueue.length - 1
      setMainQueue((q) => q.slice(1))
      if (batchStats) setBatchStats({ ...batchStats, mastered_count: batchStats.mastered_count + 1 })
      startTimeRef.current = Date.now()
      if (remainingMain === 0 && retryQueue.length === 0) {
        setPhase(verifyQueue.length === 0 ? 'done' : 'verifying')
        setShowAnswer(false)
        setLastResult(null)
      }
    } catch (e) {
      console.error('mark mastered failed:', e)
      setError('操作失败，请重试')
    } finally {
      setSubmitting(false)
    }
  }

  if (phase === 'select_source') {
    return (
      <div className="p-6 max-w-lg mx-auto text-center space-y-6">
        <Target size={48} className="mx-auto text-emerald-400" />
        <h1 className="text-2xl font-bold">选择复习内容</h1>
        <div className="grid gap-4 pt-4">
          {SOURCE_OPTIONS.map(opt => (
            <button
              key={opt.value}
              onClick={() => startSession(opt.value as any)}
              className="p-4 bg-slate-800 hover:bg-slate-700 border border-slate-700 rounded-xl transition-colors text-left"
            >
              <p className="font-medium">{opt.label}</p>
              <p className="text-sm text-slate-400 mt-1">
                {opt.value === 'daily' && '根据艾宾浩斯曲线安排的每日复习'}
                {opt.value === 'wrong_book' && '测验中答错的题目'}
                {opt.value === 'manual' && '手动标记需要复习的知识点'}
              </p>
            </button>
          ))}
        </div>
      </div>
    )
  }

  if (phase === 'loading') {
    return <div className="p-6 text-center text-slate-400">加载中...</div>
  }

  if (phase === 'empty') {
    return (
      <div className="p-6 max-w-lg mx-auto text-center space-y-6">
        <BookOpen size={48} className="mx-auto text-slate-400" />
        <h1 className="text-2xl font-bold">暂无待复习内容</h1>
        <p className="text-sm text-slate-400">当前来源没有待复习的知识点，换一个来源或稍后再来</p>
        <button
          onClick={() => {
            setPhase('select_source')
            setBatchStats(null)
          }}
          className="px-6 py-3 bg-slate-700 hover:bg-slate-600 text-white rounded-xl transition-colors flex items-center gap-2 mx-auto"
        >
          <Target size={16} /> 返回选择
        </button>
      </div>
    )
  }

  if (phase === 'done' || !current) {
    return (
      <div className="p-6 max-w-lg mx-auto text-center space-y-6">
        <PartyPopper size={48} className="mx-auto text-yellow-400" />
        <h1 className="text-2xl font-bold">🎉 复习完成！</h1>
        
        {batchStats && (
          <div className="grid grid-cols-3 gap-4 text-center">
            <div className="bg-emerald-500/10 p-4 rounded-xl border border-emerald-500/30">
              <p className="text-2xl font-bold text-emerald-400">{batchStats.mastered_count}</p>
              <p className="text-xs text-slate-400">已掌握</p>
            </div>
            <div className="bg-amber-500/10 p-4 rounded-xl border border-amber-500/30">
              <p className="text-2xl font-bold text-amber-400">{batchStats.retry_count}</p>
              <p className="text-xs text-slate-400">需巩固</p>
            </div>
            <div className="bg-slate-500/10 p-4 rounded-xl border border-slate-500/30">
              <p className="text-2xl font-bold text-slate-300">{batchStats.total}</p>
              <p className="text-xs text-slate-400">总计</p>
            </div>
          </div>
        )}

        {answerRecords.length > 0 && (
          <div className="w-full text-left space-y-2">
            <p className="text-sm font-medium text-slate-300">本次复习明细</p>
            <div className="max-h-64 overflow-y-auto space-y-2 pr-1">
              {answerRecords.map((rec, idx) => (
                <div key={idx} className="flex items-center justify-between gap-3 bg-slate-800/60 rounded-lg px-3 py-2 text-sm">
                  <span className="flex-1 min-w-0 truncate text-slate-200">{rec.topic}</span>
                  <span
                    className={`shrink-0 px-2 py-0.5 rounded-full text-xs ${
                      rec.answer === 'mastered'
                        ? 'bg-emerald-500/10 text-emerald-300'
                        : rec.answer === 'vague'
                          ? 'bg-amber-500/10 text-amber-300'
                          : 'bg-red-500/10 text-red-300'
                    }`}
                  >
                    {rec.answer === 'mastered' ? '认识' : rec.answer === 'vague' ? '模糊' : '不认识'}
                  </span>
                  <span className="shrink-0 text-xs text-slate-400">
                    {new Date(rec.next_review_time).toLocaleString('zh-CN', {
                      month: 'numeric',
                      day: 'numeric',
                      hour: '2-digit',
                      minute: '2-digit',
                    })}
                  </span>
                </div>
              ))}
            </div>
          </div>
        )}

        <p className="text-sm text-slate-400">
          平均反应时间: {batchStats ? (batchStats.total_response_ms / batchStats.total / 1000).toFixed(1) : '0.0'}s
        </p>

        <div className="flex justify-center gap-4 pt-4">
          <button
            onClick={() => startSession(lastSourceRef.current)}
            className="px-6 py-3 bg-emerald-600 hover:bg-emerald-700 text-white rounded-xl transition-colors flex items-center gap-2"
          >
            <RefreshCcw size={16} /> 继续下一组
          </button>
          <button
            onClick={() => {
              setPhase('select_source')
              setBatchStats(null)
            }}
            className="px-6 py-3 bg-slate-700 hover:bg-slate-600 text-white rounded-xl transition-colors flex items-center gap-2"
          >
            <Pause size={16} /> 暂停退出
          </button>
        </div>
      </div>
    )
  }

  return (
    <div className="p-6 max-w-lg mx-auto space-y-6">
      {/* 头部：标题 + 进度 */}
      <div className="flex items-center justify-between gap-3">
        <h1 className="text-2xl font-bold flex items-center gap-2">
          <BookOpen size={24} className="text-emerald-400" /> 复习计划
        </h1>
        <div className="flex items-center gap-3">
          <div className="bg-slate-800 rounded-xl px-3 py-2 border border-slate-700 min-w-[150px]">
            <p className="text-xs text-slate-400">本组进度</p>
            <p className="text-lg font-bold leading-tight">
              {totalDone} / {initialTotal}
            </p>
            <div className="w-full h-1.5 bg-slate-700 rounded-full overflow-hidden mt-1">
              <div
                className="h-full bg-gradient-to-r from-emerald-500 to-teal-500 rounded-full transition-all duration-500"
                style={{ width: `${progressPct}%` }}
              />
            </div>
          </div>
          <div className="text-sm text-slate-400">
            重试: <span className="text-amber-400 font-medium">{retryQueue.length}</span>
            {inVerification && (
              <>
                {' · '}验证:{' '}
                <span className="text-blue-400 font-medium">{verifyQueue.length}</span>
              </>
            )}
          </div>
        </div>
      </div>

      {error && (
        <div className="bg-red-500/10 border border-red-500/30 text-red-300 text-sm rounded-lg px-3 py-2">
          {error}
        </div>
      )}

      {/* 卡片 */}
      <div className="bg-slate-800 rounded-xl p-5 border border-slate-700 space-y-4">
        <div className="space-y-3">
          <div className="flex items-center justify-between">
            <p className="text-xs text-slate-400">{inVerification ? '组后验证' : retryRound ? '重试巩固' : '知识点'}</p>
            {(isVerifying || retryRound) && retryReason && (
              <span className="text-xs px-2 py-0.5 bg-amber-500/10 text-amber-300 border border-amber-500/30 rounded-full">
                🔁 {retryReason === 'vague' ? '上次模糊' : '上次遗忘'}
              </span>
            )}
          </div>
          <p className="font-medium text-lg leading-relaxed">{current.topic}</p>

          {!isVerifying && (
            <div className="pt-2">
              <p className="text-xs text-slate-400 mb-1">掌握度</p>
              <div className="w-full bg-slate-700 rounded-full h-2">
                <div
                  className="bg-teal-500 h-2 rounded-full transition-all"
                  style={{ width: `${Math.round(current.mastery_score)}%` }}
                />
              </div>
              <p className="text-xs text-slate-400 mt-1">
                {Math.round(current.mastery_score)}% · 已复习 {current.review_count} 次 · 间隔{' '}
                {current.interval_days} 天
              </p>
            </div>
          )}
        </div>

        {/* 答案解析（作答后展示） */}
        {showAnswer && !isFeynmanVerify && (
          <div className="rounded-lg border border-emerald-500/30 bg-emerald-500/5 p-4 space-y-3">
            <p className="text-sm font-medium text-emerald-300">答案与解析</p>
            <div className="text-sm text-slate-300 whitespace-pre-wrap leading-relaxed">
              <span className="text-emerald-400 font-medium">核心知识：</span>
              {current.answer || '（暂无解析）'}
            </div>
            {lastResult && !isVerifying && (
              <div className="flex flex-wrap items-center gap-2 text-xs text-slate-400">
                <span className="px-2 py-0.5 bg-slate-700 rounded">
                  反应时间: {((Date.now() - startTimeRef.current) / 1000).toFixed(1)}s
                </span>
                <span className="px-2 py-0.5 bg-slate-700 rounded">
                  下次复习: {new Date(lastResult.next_review_time).toLocaleDateString()}
                </span>
                <span className="px-2 py-0.5 bg-slate-700 rounded">
                  掌握度 {lastResult.mastery_change?.old.toFixed(0)} →{' '}
                  {lastResult.mastery_change?.new.toFixed(0)}
                </span>
                {lastResult.need_session_retry && (
                  <span className="px-2 py-0.5 bg-amber-500/10 text-amber-300 rounded-full">
                    将进入重试队列
                  </span>
                )}
              </div>
            )}
          </div>
        )}

        {isFeynmanVerify && !feynmanResult && (
          <div className="space-y-3">
            <p className="text-sm font-medium text-blue-300">费曼验证：请用自己的话解释这个知识点</p>
            <textarea
              value={explanation}
              onChange={(e) => setExplanation(e.target.value)}
              className="w-full h-32 bg-slate-900 border border-slate-600 rounded-lg p-3 text-sm resize-none focus:outline-none focus:border-blue-500"
              placeholder="尝试用简单的语言解释这个概念..."
            />
            <button
              onClick={handleFeynmanVerify}
              disabled={submitting || !/[\p{L}\p{N}]/u.test(explanation.trim())}
              className="w-full py-3 text-sm font-medium text-white bg-blue-600 hover:bg-blue-700 rounded-xl transition-colors disabled:opacity-50"
            >
              {isVerifyingFeynman ? 'AI评分中...' : '提交解释'}
            </button>
          </div>
        )}

        {feynmanResult && (
          <div className={`rounded-lg border p-4 space-y-3 ${
            feynmanResult.passed ? 'border-emerald-500/30 bg-emerald-500/5' : 'border-red-500/30 bg-red-500/5'
          }`}>
            <div className="flex items-center justify-between">
              <p className="text-sm font-medium">
                {feynmanResult.passed ? '✅ 通过验证' : '❌ 未通过验证'}
              </p>
              <span className={`text-lg font-bold ${
                feynmanResult.score >= 80 ? 'text-emerald-400' : 'text-red-400'
              }`}>
                {feynmanResult.score}分
              </span>
            </div>
            
            {feynmanResult.strengths.length > 0 && (
              <div>
                <p className="text-xs text-slate-400 mb-1">优点：</p>
                <ul className="text-sm text-slate-300 list-disc list-inside">
                  {feynmanResult.strengths.map((s, i) => <li key={i}>{s}</li>)}
                </ul>
              </div>
            )}
            
            {feynmanResult.weaknesses.length > 0 && (
              <div>
                <p className="text-xs text-slate-400 mb-1">待改进：</p>
                <ul className="text-sm text-slate-300 list-disc list-inside">
                  {feynmanResult.weaknesses.map((w, i) => <li key={i}>{w}</li>)}
                </ul>
              </div>
            )}
            
            {feynmanResult.correct_answer && (
              <div>
                <p className="text-xs text-slate-400 mb-1">答案：</p>
                <p className="text-sm text-slate-300 whitespace-pre-wrap leading-relaxed">{feynmanResult.correct_answer}</p>
              </div>
            )}
            
            <button
              onClick={() => {
                // 失败上报已在 handleFeynmanVerify 内提交过，此处仅推进队列
                setFeynmanResult(null)
                setExplanation('')
                handleVerifyPass()
              }}
              className="w-full py-2.5 text-sm font-medium text-white bg-slate-600 hover:bg-slate-500 rounded-lg transition-colors"
            >
              继续
            </button>
          </div>
        )}

        {/* 操作区 */}
        {!showAnswer && !isVerifying && !isFeynmanVerify && (
          <div className="grid grid-cols-3 gap-2 pt-2">
            {FEEDBACK_OPTIONS.map((opt) => (
              <button
                key={opt.value}
                onClick={() => (retryRound ? handleRetryAnswer(opt.value) : answerCurrent(opt.value))}
                disabled={submitting}
                className={`py-3 text-sm font-medium text-white rounded-xl transition-all disabled:opacity-50 ${opt.color} hover:scale-[1.02] active:scale-[0.98] flex flex-col items-center gap-1`}
              >
                <span>{opt.label}</span>
                <span className="text-xs opacity-80">{opt.desc}</span>
              </button>
            ))}
          </div>
        )}

        {!showAnswer && isVerifying && (
          <button
            onClick={() => {
              setShowAnswer(true)
              startTimeRef.current = Date.now()
              if (verifyQueue[0]?.feynman) {
                setPhase('feynman_verify')
              }
            }}
            disabled={submitting}
            className="w-full py-3 text-sm font-medium text-white bg-slate-600 hover:bg-slate-500 rounded-xl transition-colors disabled:opacity-50 flex items-center justify-center gap-2"
          >
            回想后查看答案 <ArrowRight size={14} />
          </button>
        )}

        {showAnswer && !isFeynmanVerify && (
          <div className="space-y-2 pt-1">
            {isVerifying ? (
              <div className="grid grid-cols-2 gap-2">
                <button
                  onClick={handleVerifyPass}
                  disabled={submitting}
                  className="py-3 text-sm font-medium text-white bg-emerald-600 hover:bg-emerald-700 rounded-xl transition-colors disabled:opacity-50"
                >
                  记得 ✓ 通过
                </button>
                <button
                  onClick={handleVerifyFail}
                  disabled={submitting}
                  className="py-3 text-sm font-medium text-white bg-red-600 hover:bg-red-700 rounded-xl transition-colors disabled:opacity-50"
                >
                  不记得 ✗ 降级
                </button>
              </div>
            ) : (
              <button
                onClick={handleNext}
                disabled={submitting}
                className="w-full py-3 text-sm font-medium text-white bg-emerald-600 hover:bg-emerald-700 rounded-xl transition-colors disabled:opacity-50 flex items-center justify-center gap-2"
              >
                继续下一题 <ArrowRight size={14} />
              </button>
            )}
          </div>
        )}
      </div>

      {/* 底部操作 */}
      {!isVerifying && !showAnswer && !isFeynmanVerify && !retryRound && (
        <button
          onClick={handleMarkMastered}
          disabled={submitting}
          className="w-full py-2.5 text-sm text-slate-300 bg-slate-700/50 hover:bg-slate-700 rounded-lg transition-colors disabled:opacity-50"
        >
          标记掌握并跳过
        </button>
      )}

      {/* 批次点位图 */}
      <div className="flex items-center gap-1 justify-center">
        {Array.from({ length: Math.max(initialTotal, 1) }, (_, i) => (
          <div
            key={i}
            className={`w-2 h-2 rounded-full transition-colors ${
              i < totalDone
                ? 'bg-emerald-500'
                : i === totalDone && !isVerifying
                  ? 'bg-emerald-400 animate-pulse'
                  : 'bg-slate-700'
            }`}
          />
        ))}
        <span className="ml-2 text-xs text-slate-400">
          {totalDone} / {initialTotal}
        </span>
      </div>

      <p className="text-center text-xs text-slate-500">
        {inVerification
          ? '🔁 组后验证：回想是否还记得，通过后本组完成'
          : retryRound
            ? '🔁 重试巩固：选择「认识」放行出组，模糊/不认识会压回队尾循环'
            : '💡 答题后显示答案解析，模糊/不认识的会进入重试队列'}
      </p>
    </div>
  )
}