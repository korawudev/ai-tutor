import { useEffect, useState, useRef, useCallback } from 'react'
import api from '../services/api'
import type { Thread } from '../types'
import { Send, Plus, Loader2, PanelLeftClose, PanelLeft, Check, X, Edit3 } from 'lucide-react'

interface Message { role: 'user' | 'assistant'; content: string; isStreaming?: boolean }

interface ReviewPoint {
  problem: string
  answer: string
}

interface Evaluation {
  score: number
  understanding: number
  completeness: number
  clarity: number
  strengths: string[]
  weaknesses: string[]
  suggestions: string[]
  review_points?: ReviewPoint[]
}

interface ReviewItem {
  topic: string
  answer?: string
  source?: string
}

export default function Chat() {
  const [threads, setThreads] = useState<Thread[]>([])
  const [activeThread, setActiveThread] = useState<string | null>(null)
  const [messages, setMessages] = useState<Message[]>([])
  const [input, setInput] = useState('')
  const [sending, setSending] = useState(false)
  const [feynmanMode, setFeynmanMode] = useState(true)
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false)
  const messagesEnd = useRef<HTMLDivElement>(null)
  const composingRef = useRef(false)
  const textareaRef = useRef<HTMLTextAreaElement>(null)

  const [showEndDialog, setShowEndDialog] = useState(false)
  const [showEvaluation, setShowEvaluation] = useState(false)
  const [evaluation, setEvaluation] = useState<Evaluation | null>(null)
  const [reviewItems, setReviewItems] = useState<ReviewItem[]>([])
  const [reviewInput, setReviewInput] = useState('')
  const [editingReview, setEditingReview] = useState(false)
  const [evaluating, setEvaluating] = useState(false)

  const [historyOffset, setHistoryOffset] = useState(0)
  const [hasMoreOlder, setHasMoreOlder] = useState(false)
  const [loadingOlder, setLoadingOlder] = useState(false)
  const scrollRef = useRef<HTMLDivElement>(null)
  const historyThreadRef = useRef<string | null>(null)
  const messagesTopRef = useRef(false)

  useEffect(() => {
    api.get('/threads', { params: { agent_type: 'feynman' } }).then((res) => setThreads(res.data))
  }, [])

  useEffect(() => {
    if (messagesTopRef.current) {
      messagesTopRef.current = false
      return
    }
    messagesEnd.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  const autoGrow = useCallback(() => {
    const el = textareaRef.current
    if (!el) return
    el.style.height = 'auto'
    const lineHeight = 24
    const maxHeight = lineHeight * 7
    el.style.height = `${Math.min(el.scrollHeight, maxHeight)}px`
    el.style.overflowY = el.scrollHeight > maxHeight ? 'auto' : 'hidden'
  }, [])

  useEffect(() => { autoGrow() }, [input, autoGrow])

  const newThread = async () => {
    const res = await api.post('/threads', { agent_type: feynmanMode ? 'feynman' : 'rag' })
    setThreads((prev) => [res.data, ...prev])
    setActiveThread(res.data.id)
    setMessages([])
    setShowEvaluation(false)
    setEvaluation(null)
    setReviewItems([])
    historyThreadRef.current = res.data.id
    setHistoryOffset(0)
    setHasMoreOlder(false)
  }

  const PAGE = 10

  const loadHistory = async (threadId: string, offset: number, prepend: boolean) => {
    setLoadingOlder(true)
    try {
      const res = await api.get(`/threads/${threadId}/runs`, { params: { limit: PAGE, offset } })
      const runs = res.data as Array<{ input: any; output: any }>
      if (historyThreadRef.current !== threadId) return

      const pairs: Message[] = []
      for (const r of [...runs].reverse()) {
        const userText = typeof r.input === 'object' ? (r.input?.input ?? '') : String(r.input ?? '')
        if (userText) pairs.push({ role: 'user', content: userText })
        const respText = r.output?.response
        if (respText) pairs.push({ role: 'assistant', content: respText })
      }

      setHasMoreOlder(runs.length === PAGE)

      if (prepend) {
        const el = scrollRef.current
        const prevHeight = el ? el.scrollHeight : 0
        messagesTopRef.current = true
        setMessages((prev) => [...pairs, ...prev])
        setHistoryOffset((o) => o + PAGE)
        requestAnimationFrame(() => {
          if (el) el.scrollTop = el.scrollHeight - prevHeight
        })
      } else {
        messagesTopRef.current = true
        setMessages(pairs)
        setHistoryOffset(PAGE)
      }
    } catch {
      setHasMoreOlder(false)
    } finally {
      setLoadingOlder(false)
    }
  }

  const handleSelectThread = (threadId: string) => {
    historyThreadRef.current = threadId
    setActiveThread(threadId)
    setMessages([])
    setShowEvaluation(false)
    setEvaluation(null)
    setReviewItems([])
    setHistoryOffset(0)
    setHasMoreOlder(false)
    loadHistory(threadId, 0, false)
  }

  const handleScroll = () => {
    const el = scrollRef.current
    if (!el || el.scrollTop > 4) return
    const tid = historyThreadRef.current
    const offset = historyOffset
    if (tid && hasMoreOlder && !loadingOlder) {
      loadHistory(tid, offset, true)
    }
  }

  const send = async () => {
    if (!input.trim() || sending || composingRef.current) return
    const userMsg = input.trim()
    setInput('')
    setMessages((prev) => [...prev, { role: 'user', content: userMsg }])
    setSending(true)

    let threadId = activeThread
    if (!threadId) {
      const threadRes = await api.post('/threads', { agent_type: feynmanMode ? 'feynman' : 'rag' })
      threadId = threadRes.data.id
      setThreads((prev) => [threadRes.data, ...prev])
      setActiveThread(threadId)
    }

    if (!threadId) return

    if (feynmanMode) {
      await sendFeynman(threadId, userMsg)
    } else {
      await sendNormal(threadId, userMsg)
    }
  }

  const sendNormal = async (threadId: string, userMsg: string) => {
    try {
      const res = await api.post(`/threads/${threadId}/runs`, {
        agent_type: 'rag',
        action: 'chat',
        input: userMsg,
      })
      const aiMsg = res.data?.output?.response || '收到您的消息，正在处理中...'
      setMessages((prev) => [...prev, { role: 'assistant', content: aiMsg }])
      setThreads((prev) => prev.map((t) =>
        t.id === threadId ? { ...t, title: t.title || userMsg.slice(0, 30) } : t
      ))
    } catch {
      setMessages((prev) => [...prev, { role: 'assistant', content: '请求失败，请稍后重试。' }])
    } finally {
      setSending(false)
    }
  }

  const sendFeynman = async (threadId: string, userMsg: string) => {
    const streamingIdx = messages.length + 1
    setMessages((prev) => [...prev, { role: 'assistant', content: '', isStreaming: true }])

    try {
      const token = localStorage.getItem('token')
      const resp = await fetch(`/api/threads/${threadId}/runs`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${token}` },
        body: JSON.stringify({ agent_type: 'feynman', action: 'chat', input: userMsg }),
      })

      if (!resp.ok || !resp.body) {
        throw new Error(`HTTP ${resp.status}`)
      }

      const reader = resp.body.getReader()
      const decoder = new TextDecoder()
      let fullResponse = ''
      let shouldEnd = false
      let buffer = ''

      while (true) {
        const { done, value } = await reader.read()
        if (done) break

        buffer += decoder.decode(value, { stream: true })
        const lines = buffer.split('\n')
        buffer = lines.pop() || ''

        for (const line of lines) {
          if (line.startsWith('data: ')) {
            try {
              const data = JSON.parse(line.slice(6))
              if (data.type === 'token') {
                fullResponse += data.content
                setMessages((prev) => {
                  const updated = [...prev]
                  updated[streamingIdx] = { role: 'assistant', content: fullResponse, isStreaming: true }
                  return updated
                })
              } else if (data.type === 'done') {
                shouldEnd = data.should_end || false
                fullResponse = data.response || fullResponse
                setMessages((prev) => {
                  const updated = [...prev]
                  updated[streamingIdx] = { role: 'assistant', content: fullResponse, isStreaming: false }
                  return updated
                })
              } else if (data.type === 'error') {
                fullResponse = data.message || '请求失败'
                setMessages((prev) => {
                  const updated = [...prev]
                  updated[streamingIdx] = { role: 'assistant', content: fullResponse, isStreaming: false }
                  return updated
                })
              }
            } catch { /* ignore parse errors */ }
          }
        }
      }

      setThreads((prev) => prev.map((t) =>
        t.id === threadId ? { ...t, title: t.title || userMsg.slice(0, 30) } : t
      ))

      if (shouldEnd) {
        setShowEndDialog(true)
      }
    } catch {
      setMessages((prev) => {
        const updated = [...prev]
        updated[streamingIdx] = { role: 'assistant', content: '请求失败，请稍后重试。', isStreaming: false }
        return updated
      })
    } finally {
      setSending(false)
    }
  }

  const handleEndConversation = async () => {
    setShowEndDialog(false)
    if (!activeThread) return

    setEvaluating(true)
    try {
      const res = await api.post(`/feynman/evaluate`, null, { params: { thread_id: activeThread } })
      setEvaluation(res.data)

      if (res.data.review_points && res.data.review_points.length > 0) {
        setReviewItems(
          res.data.review_points.map((p: ReviewPoint) => ({
            topic: p.problem,
            answer: p.answer,
            source: 'feynman',
          }))
        )
      } else if (res.data.weaknesses && res.data.weaknesses.length > 0) {
        setReviewItems(res.data.weaknesses.map((w: string) => ({ topic: w, source: 'feynman' })))
      } else if (res.data.suggestions && res.data.suggestions.length > 0) {
        setReviewItems(res.data.suggestions.map((s: string) => ({ topic: s, source: 'feynman' })))
      }
      setShowEvaluation(true)
    } catch {
      setMessages((prev) => [...prev, { role: 'assistant', content: '评估失败，请稍后重试。' }])
    } finally {
      setEvaluating(false)
    }
  }

  const handleAddToReview = async () => {
    if (!activeThread || !evaluation || reviewItems.length === 0) return

    try {
      await api.post('/feynman/add-to-review', {
        thread_id: activeThread,
        score: evaluation.score,
        review_items: reviewItems,
      })
      setMessages((prev) => [...prev, { role: 'assistant', content: `已将 ${reviewItems.length} 个知识点加入复习计划。` }])
      setShowEvaluation(false)
    } catch {
      setMessages((prev) => [...prev, { role: 'assistant', content: '添加复习计划失败，请稍后重试。' }])
    }
  }

  const addReviewItem = () => {
    if (reviewInput.trim()) {
      setReviewItems((prev) => [...prev, { topic: reviewInput.trim(), source: 'feynman' }])
      setReviewInput('')
    }
  }

  const removeReviewItem = (index: number) => {
    setReviewItems((prev) => prev.filter((_, i) => i !== index))
  }

  const updateReviewItem = (index: number, value: string) => {
    setReviewItems((prev) => prev.map((item, i) => i === index ? { ...item, topic: value } : item))
  }

  return (
    <div className="flex h-full">
      <div
        className={`${sidebarCollapsed ? 'w-14' : 'w-60'} border-r border-slate-700 bg-slate-800/50 flex flex-col transition-all duration-200`}
      >
        <div className="p-3 flex items-center gap-2">
          {!sidebarCollapsed && (
            <button onClick={newThread} className="flex-1 flex items-center justify-center gap-2 px-3 py-2 bg-primary-600 hover:bg-primary-700 rounded-lg text-sm font-medium transition-colors">
              <Plus size={16} /> 新对话
            </button>
          )}
          <button
            onClick={() => setSidebarCollapsed((p) => !p)}
            className="p-2 text-slate-400 hover:text-white hover:bg-slate-700 rounded-lg transition-colors shrink-0"
            title={sidebarCollapsed ? '展开侧边栏' : '收起侧边栏'}
          >
            {sidebarCollapsed ? <PanelLeft size={18} /> : <PanelLeftClose size={18} />}
          </button>
        </div>
        <div className="flex-1 overflow-y-auto px-2 space-y-1">
          {threads.map((t) => (
            <button
              key={t.id}
              onClick={() => handleSelectThread(t.id)}
              title={t.title || '新对话'}
              className={`w-full text-left px-3 py-2 rounded-lg text-sm truncate transition-colors ${
                activeThread === t.id ? 'bg-slate-700 text-white' : 'text-slate-300 hover:bg-slate-700/50'
              } ${sidebarCollapsed ? 'px-2 flex justify-center' : ''}`}
            >
              {sidebarCollapsed ? <Plus size={14} /> : (t.title || '新对话')}
            </button>
          ))}
        </div>
      </div>

      <div className="flex-1 flex flex-col">
        <div className="flex items-center justify-between gap-3 px-4 py-2 border-b border-slate-700">
          <div className="flex items-center gap-1 rounded-lg bg-slate-800 border border-slate-700 p-1">
            <button
              onClick={() => setFeynmanMode(true)}
              className={`px-3 py-1.5 rounded-md text-sm transition-colors ${
                feynmanMode ? 'bg-primary-600 text-white font-medium' : 'text-slate-300 hover:text-white'
              }`}
            >
              费曼学习模式
            </button>
            <button
              onClick={() => setFeynmanMode(false)}
              className={`px-3 py-1.5 rounded-md text-sm transition-colors ${
                !feynmanMode ? 'bg-slate-600 text-white font-medium' : 'text-slate-300 hover:text-white'
              }`}
            >
              普通对话
            </button>
          </div>
          {feynmanMode && (
            <span className="text-xs text-slate-400">SSE 流式输出 + 掌握度评估</span>
          )}
        </div>

        <div ref={scrollRef} onScroll={handleScroll} className="flex-1 overflow-y-auto p-4 space-y-4">
          {loadingOlder && hasMoreOlder && (
            <div className="text-center text-slate-500 text-sm py-2">
              <Loader2 size={16} className="inline animate-spin mr-1" /> 加载更早的消息...
            </div>
          )}
          {messages.length === 0 && (
            <div className="text-center text-slate-500 mt-20">
              <p className="text-lg">开始与 AI 对话</p>
              <p className="text-sm mt-1">{feynmanMode ? '选择一个概念，用你自己的话解释' : '可以提问编程问题'}</p>
            </div>
          )}
          {messages.map((m, i) => (
            <div key={i} className={`flex ${m.role === 'user' ? 'justify-end' : 'justify-start'}`}>
              <div className={`max-w-[70%] px-4 py-2.5 rounded-xl text-sm whitespace-pre-wrap ${
                m.role === 'user' ? 'bg-primary-600 text-white' : 'bg-slate-800 border border-slate-700'
              }`}>
                {m.content}
                {m.isStreaming && <span className="animate-pulse ml-0.5">|</span>}
              </div>
            </div>
          ))}
          <div ref={messagesEnd} />
        </div>

        <div className="p-4 border-t border-slate-700">
          <div className="flex gap-2 items-end">
            <textarea
              ref={textareaRef}
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => { if (e.key === 'Enter' && !e.shiftKey && !composingRef.current) { e.preventDefault(); send() } }}
              onCompositionStart={() => { composingRef.current = true }}
              onCompositionEnd={() => { composingRef.current = false }}
              placeholder={feynmanMode ? "用你的话解释概念..." : "输入消息..."}
              rows={1}
              className="flex-1 px-4 py-2.5 bg-slate-800 border border-slate-700 rounded-xl text-sm resize-none focus:outline-none focus:ring-2 focus:ring-primary-500 leading-6"
            />
            <button
              onClick={send}
              disabled={sending || !input.trim()}
              className="p-2.5 bg-primary-600 hover:bg-primary-700 disabled:opacity-50 rounded-xl transition-colors"
            >
              {sending ? <Loader2 size={18} className="animate-spin" /> : <Send size={18} />}
            </button>
          </div>
        </div>
      </div>

      {showEndDialog && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
          <div className="bg-slate-800 rounded-xl p-6 w-96 border border-slate-700">
            <h3 className="text-lg font-medium text-white mb-2">结束本次学习？</h3>
            <p className="text-sm text-slate-400 mb-4">导师认为你已经解释得足够清楚了。是否结束对话并查看掌握度评估？</p>
            <div className="flex gap-2 justify-end">
              <button onClick={() => setShowEndDialog(false)} className="px-4 py-2 text-sm text-slate-400 hover:text-white transition-colors">
                继续对话
              </button>
              <button onClick={handleEndConversation} disabled={evaluating} className="px-4 py-2 text-sm bg-primary-600 hover:bg-primary-700 rounded-lg transition-colors disabled:opacity-50">
                {evaluating ? '评估中...' : '结束并评估'}
              </button>
            </div>
          </div>
        </div>
      )}

      {showEvaluation && evaluation && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
          <div className="bg-slate-800 rounded-xl p-6 w-[500px] border border-slate-700 max-h-[80vh] overflow-y-auto">
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-lg font-medium text-white">掌握度评估</h3>
              <div className={`text-2xl font-bold ${evaluation.score >= 60 ? 'text-green-400' : 'text-red-400'}`}>
                {evaluation.score}分
              </div>
            </div>

            <div className="grid grid-cols-3 gap-4 mb-4">
              <div className="text-center p-3 bg-slate-700/50 rounded-lg">
                <div className="text-sm text-slate-400">理解深度</div>
                <div className="text-lg font-medium text-white">{evaluation.understanding}</div>
              </div>
              <div className="text-center p-3 bg-slate-700/50 rounded-lg">
                <div className="text-sm text-slate-400">完整性</div>
                <div className="text-lg font-medium text-white">{evaluation.completeness}</div>
              </div>
              <div className="text-center p-3 bg-slate-700/50 rounded-lg">
                <div className="text-sm text-slate-400">清晰度</div>
                <div className="text-lg font-medium text-white">{evaluation.clarity}</div>
              </div>
            </div>

            {evaluation.strengths.length > 0 && (
              <div className="mb-4">
                <div className="text-sm font-medium text-green-400 mb-2">做得好的地方</div>
                <ul className="text-sm text-slate-300 space-y-1">
                  {evaluation.strengths.map((s, i) => <li key={i}>+ {s}</li>)}
                </ul>
              </div>
            )}

            {evaluation.weaknesses.length > 0 && (
              <div className="mb-4">
                <div className="text-sm font-medium text-red-400 mb-2">需要加强的地方</div>
                <ul className="text-sm text-slate-300 space-y-1">
                  {evaluation.weaknesses.map((w, i) => <li key={i}>- {w}</li>)}
                </ul>
              </div>
            )}

            {evaluation.suggestions.length > 0 && (
              <div className="mb-4">
                <div className="text-sm font-medium text-yellow-400 mb-2">改进建议</div>
                <ul className="text-sm text-slate-300 space-y-1">
                  {evaluation.suggestions.map((s, i) => <li key={i}>* {s}</li>)}
                </ul>
              </div>
            )}

            <div className="border-t border-slate-700 pt-4 mt-4">
              <div className="flex items-center justify-between mb-2">
                <span className="text-sm font-medium text-white">复习计划</span>
                <button onClick={() => setEditingReview(!editingReview)} className="text-xs text-primary-400 hover:text-primary-300 flex items-center gap-1">
                  <Edit3 size={12} /> {editingReview ? '完成编辑' : '编辑'}
                </button>
              </div>

              {editingReview && (
                <div className="flex gap-2 mb-2">
                  <input
                    value={reviewInput}
                    onChange={(e) => setReviewInput(e.target.value)}
                    onKeyDown={(e) => { if (e.key === 'Enter') addReviewItem() }}
                    placeholder="添加复习知识点..."
                    className="flex-1 px-3 py-1.5 bg-slate-700 border border-slate-600 rounded-lg text-sm focus:outline-none focus:ring-1 focus:ring-primary-500"
                  />
                  <button onClick={addReviewItem} className="px-3 py-1.5 bg-slate-700 hover:bg-slate-600 rounded-lg text-sm">
                    添加
                  </button>
                </div>
              )}

              <div className="space-y-2 max-h-40 overflow-y-auto">
                {reviewItems.map((item, i) => (
                  <div key={i} className="flex items-center gap-2 p-2 bg-slate-700/50 rounded-lg">
                    {editingReview ? (
                      <input
                        value={item.topic}
                        onChange={(e) => updateReviewItem(i, e.target.value)}
                        className="flex-1 bg-transparent text-sm focus:outline-none"
                      />
                    ) : (
                      <div className="flex-1 min-w-0">
                        <span className="text-sm text-slate-300">{item.topic}</span>
                        {item.answer && (
                          <div className="text-xs text-slate-400 mt-0.5">参考答案：{item.answer}</div>
                        )}
                      </div>
                    )}
                    <button onClick={() => removeReviewItem(i)} className="text-slate-500 hover:text-red-400">
                      <X size={14} />
                    </button>
                  </div>
                ))}
                {reviewItems.length === 0 && (
                  <p className="text-sm text-slate-500 text-center py-2">无需复习的知识点</p>
                )}
              </div>
            </div>

            <div className="flex gap-2 justify-end mt-4">
              <button onClick={() => setShowEvaluation(false)} className="px-4 py-2 text-sm text-slate-400 hover:text-white transition-colors">
                关闭
              </button>
              {reviewItems.length > 0 && (
                <button onClick={handleAddToReview} className="px-4 py-2 text-sm bg-primary-600 hover:bg-primary-700 rounded-lg transition-colors flex items-center gap-2">
                  <Check size={14} /> 加入复习计划
                </button>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
