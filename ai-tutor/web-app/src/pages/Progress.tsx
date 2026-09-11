import { useEffect, useState } from 'react'
import api from '../services/api'
import type { DashboardData, MasteryRecord } from '../types'
import { BarChart3 } from 'lucide-react'

export default function Progress() {
  const [data, setData] = useState<DashboardData | null>(null)
  const [mastery, setMastery] = useState<MasteryRecord[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    Promise.all([
      api.get('/progress/dashboard'),
      api.get('/progress/mastery'),
    ])
      .then(([d, m]) => { setData(d.data); setMastery(m.data || []) })
      .finally(() => setLoading(false))
  }, [])

  if (loading) return <div className="p-6 text-slate-400">加载中...</div>

  const s = data?.summary

  return (
    <div className="p-6 space-y-6">
      <h1 className="text-2xl font-bold flex items-center gap-2"><BarChart3 size={24} /> 学习进度</h1>

      {/* Overview */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <Card label="总文档" value={s?.total_documents || 0} />
        <Card label="知识点" value={s?.total_concepts || 0} />
        <Card label="已掌握" value={s?.mastered_concepts || 0} />
        <Card label="掌握率" value={`${(s?.mastery_rate || 0).toFixed(1)}%`} />
      </div>

      {/* Mastery list */}
      <div className="bg-slate-800 rounded-xl border border-slate-700">
        <div className="px-5 py-3 border-b border-slate-700">
          <h3 className="font-semibold">知识点掌握详情</h3>
        </div>
        {mastery.length === 0 ? (
          <div className="p-8 text-center text-slate-500">暂无数据</div>
        ) : (
          <div className="divide-y divide-slate-700">
            {mastery.map((m) => (
              <div key={m.id} className="px-5 py-3 flex items-center gap-4">
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-medium truncate">{m.topic}</p>
                  <p className="text-xs text-slate-400">测验 {m.quiz_accuracy.toFixed(0)}% &middot; 费曼 {m.feynman_score.toFixed(0)}%</p>
                </div>
                <div className="w-32">
                  <div className="w-full bg-slate-700 rounded-full h-1.5">
                    <div
                      className={`h-1.5 rounded-full ${m.mastery_score >= 80 ? 'bg-green-500' : m.mastery_score >= 50 ? 'bg-primary-500' : 'bg-amber-500'}`}
                      style={{ width: `${m.mastery_score}%` }}
                    />
                  </div>
                </div>
                <span className="text-sm font-medium w-12 text-right">{m.mastery_score.toFixed(0)}%</span>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}

function Card({ label, value }: { label: string; value: string | number }) {
  return (
    <div className="bg-slate-800 rounded-xl p-4 border border-slate-700">
      <p className="text-xs text-slate-400">{label}</p>
      <p className="text-2xl font-bold mt-1">{value}</p>
    </div>
  )
}
