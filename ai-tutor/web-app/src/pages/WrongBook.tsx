import { useEffect, useState } from 'react'
import api from '../services/api'
import type { WrongQuestion, AddToReviewResult } from '../types'
import { BookMarked, Check, XCircle, Plus, Clock } from 'lucide-react'
import Toast from '../components/common/Toast'

function QuestionText({ question }: { question: { question?: string; type?: string; options?: Record<string, string> } }) {
  const text = question.question || ''
  const isChoice = question.type === 'choice' && question.options
  return (
    <div className="space-y-2">
      <p className="font-medium text-slate-200">{text}</p>
      {isChoice && (
        <div className="space-y-1.5">
          {Object.entries(question.options!).map(([key, val]) => (
            <div key={key} className="flex items-center gap-2 rounded-lg bg-slate-700/40 px-3 py-1.5 text-sm">
              <span className="text-slate-400">{key}. {val}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

const pad = (n: number) => String(n).padStart(2, '0')

function formatLocalTime(iso: string): string {
  const d = new Date(iso)
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(d.getSeconds())}`
}

export default function WrongBook() {
  const [items, setItems] = useState<WrongQuestion[]>([])
  const [loading, setLoading] = useState(true)
  const [busyId, setBusyId] = useState<string | null>(null)
  const [toast, setToast] = useState<{ key: number; message: string; type?: 'success' | 'error' } | null>(null)
  const [addedIds, setAddedIds] = useState<Set<string>>(new Set())

  const showToast = (message: string, type?: 'success' | 'error') => {
    setToast({ key: Date.now(), message, type })
  }

  const load = () => {
    setLoading(true)
    api.get('/quiz/wrong-book')
      .then((res) => {
        const list = (res.data || []) as WrongQuestion[]
        setItems(list)
        setAddedIds(new Set(list.filter((w) => w.in_review).map((w) => w.id)))
      })
      .finally(() => setLoading(false))
  }

  useEffect(() => { load() }, [])

  const markMastered = async (id: string) => {
    setBusyId(id)
    try {
      await api.post(`/quiz/wrong-book/${id}/mastered`)
      setItems((prev) => prev.filter((w) => w.id !== id))
      showToast('已标记为掌握，从错题本移除')
    } catch {
      showToast('操作失败，请稍后重试', 'error')
    } finally { setBusyId(null) }
  }

  const addToReview = async (w: WrongQuestion) => {
    setBusyId(w.id)
    try {
      const res = await api.post<AddToReviewResult>('/quiz/wrong-book/add-to-review', { wrong_ids: [w.id] })
      const { added, skipped } = res.data
      setAddedIds((prev) => new Set(prev).add(w.id))
      showToast(added > 0 ? '已加入复习计划' : skipped > 0 ? '该知识点已在复习计划中' : '无变化')
    } catch {
      showToast('操作失败，请稍后重试', 'error')
    } finally { setBusyId(null) }
  }

  const q = (w: WrongQuestion) => (w.question || {}) as { question?: string; type?: string; options?: Record<string, string> }

  return (
    <div className="p-6 max-w-2xl mx-auto space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold flex items-center gap-2"><BookMarked size={24} /> 错题本</h1>
        <span className="text-sm text-slate-400">{items.length} 道未掌握</span>
      </div>

      {toast && (
        <Toast key={toast.key} message={toast.message} type={toast.type} onDone={() => setToast(null)} />
      )}

      {loading ? (
        <p className="text-slate-400">加载中...</p>
      ) : items.length === 0 ? (
        <div className="bg-slate-800 rounded-xl p-10 border border-slate-700 text-center text-slate-400">
          <XCircle size={32} className="mx-auto mb-3 text-slate-600" />
          <p>暂无错题</p>
          <p className="text-sm mt-1">去智能测验中做几道题，答错的题目会自动收录到这里。</p>
        </div>
      ) : (
        <div className="space-y-4">
          {items.map((w) => {
            const isAdded = addedIds.has(w.id)
            return (
              <div key={w.id} className="bg-slate-800 rounded-xl p-5 border border-slate-700 space-y-3">
                <QuestionText question={q(w)} />
                <div className="flex flex-col gap-1.5 text-sm">
                  {w.user_answer != null && w.user_answer !== '' && (
                    <p className="text-red-400/90"><span className="font-bold text-red-500 mr-1">×</span>你的答案：{w.user_answer}</p>
                  )}
                  <p className="text-green-400/90"><span className="font-bold text-green-500 mr-1">✔️</span>正确答案：{w.correct_answer}</p>
                </div>
                {w.explanation && (
                  <div className="rounded-lg bg-slate-700/50 border border-slate-600/60 p-3 text-sm text-slate-300">
                    <span className="text-primary-400 font-medium">解析：</span>{w.explanation}
                  </div>
                )}
                <div className="flex items-center justify-between pt-1">
                  <span className="flex items-center gap-1 text-xs text-slate-500">
                    <Clock size={12} /> 错于 {formatLocalTime(w.created_at)} · 复习 {w.review_count} 次
                  </span>
                  <div className="flex gap-2">
                    <button
                      onClick={() => addToReview(w)}
                      disabled={busyId === w.id || isAdded}
                      className={`flex items-center gap-1.5 px-3 py-1.5 text-xs rounded-lg transition-colors ${
                        isAdded
                          ? 'cursor-default bg-green-600/20 text-green-400 border border-green-500/40'
                          : 'bg-slate-700 hover:bg-slate-600 disabled:opacity-50'
                      }`}
                    >
                      {isAdded ? <Check size={14} /> : <Plus size={14} />}
                      {isAdded ? '已加入复习计划' : '加入复习计划'}
                    </button>
                    <button
                      onClick={() => markMastered(w.id)}
                      disabled={busyId === w.id}
                      className="flex items-center gap-1.5 px-3 py-1.5 text-xs bg-primary-600 hover:bg-primary-700 disabled:opacity-50 rounded-lg transition-colors"
                    >
                      <Check size={14} /> 已掌握
                    </button>
                  </div>
                </div>
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}