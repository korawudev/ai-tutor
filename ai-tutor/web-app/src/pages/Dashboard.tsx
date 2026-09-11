import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import api from '../services/api'
import type { DashboardData } from '../types'
import { FileText, Brain, Target, TrendingUp, Upload, MessageSquare } from 'lucide-react'

export default function Dashboard() {
  const [data, setData] = useState<DashboardData | null>(null)
  const [loading, setLoading] = useState(true)
  const navigate = useNavigate()

  useEffect(() => {
    api.get('/progress/dashboard')
      .then((res) => setData(res.data))
      .catch(() => {})
      .finally(() => setLoading(false))
  }, [])

  const summary = data?.summary
  const today = data?.today
  const trend = data?.trend || []
  const maxScore = Math.max(...trend.map((t) => t.score), 1)

  return (
    <div className="p-6 space-y-6">
      <h1 className="text-2xl font-bold">仪表盘</h1>

      {loading ? (
        <div className="text-slate-400">加载中...</div>
      ) : (
        <>
          {/* Summary cards */}
          <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
            <StatCard icon={FileText} label="总文档数" value={summary?.total_documents || 0} color="text-blue-400" />
            <StatCard icon={Brain} label="总知识点" value={summary?.total_concepts || 0} color="text-purple-400" />
            <StatCard icon={Target} label="已掌握" value={summary?.mastered_concepts || 0} color="text-green-400" />
            <StatCard icon={TrendingUp} label="平均掌握度" value={`${(summary?.average_mastery || 0).toFixed(1)}%`} color="text-amber-400" />
          </div>

          {/* Today + Trend */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
            <div className="bg-slate-800 rounded-xl p-5 border border-slate-700">
              <h3 className="font-semibold mb-4">今日学习</h3>
              <div className="grid grid-cols-2 gap-3 text-sm">
                <div className="bg-slate-700/50 rounded-lg p-3">
                  <p className="text-slate-400">文档阅读</p>
                  <p className="text-xl font-bold">{today?.documents_read || 0}</p>
                </div>
                <div className="bg-slate-700/50 rounded-lg p-3">
                  <p className="text-slate-400">完成测验</p>
                  <p className="text-xl font-bold">{today?.quizzes_taken || 0}</p>
                </div>
                <div className="bg-slate-700/50 rounded-lg p-3">
                  <p className="text-slate-400">费曼对话</p>
                  <p className="text-xl font-bold">{today?.feynman_sessions || 0}</p>
                </div>
                <div className="bg-slate-700/50 rounded-lg p-3">
                  <p className="text-slate-400">复习完成</p>
                  <p className="text-xl font-bold">{today?.reviews_completed || 0}</p>
                </div>
              </div>
            </div>

            <div className="bg-slate-800 rounded-xl p-5 border border-slate-700">
              <h3 className="font-semibold mb-4">7 天趋势</h3>
              <div className="flex items-end gap-2 h-32">
                {trend.map((t, i) => (
                  <div key={i} className="flex-1 flex flex-col items-center gap-1">
                    <div
                      className="w-full bg-primary-500 rounded-t"
                      style={{ height: `${(t.score / maxScore) * 100}%`, minHeight: 4 }}
                    />
                    <span className="text-[10px] text-slate-400">{t.date.slice(5)}</span>
                  </div>
                ))}
              </div>
            </div>
          </div>

          {/* Quick actions */}
          <div className="flex gap-3">
            <button onClick={() => navigate('/documents')} className="flex items-center gap-2 px-4 py-2 bg-primary-600 hover:bg-primary-700 rounded-lg text-sm font-medium transition-colors">
              <Upload size={16} /> 上传文档
            </button>
            <button onClick={() => navigate('/chat')} className="flex items-center gap-2 px-4 py-2 bg-slate-700 hover:bg-slate-600 rounded-lg text-sm font-medium transition-colors">
              <MessageSquare size={16} /> 开始对话
            </button>
            <button onClick={() => navigate('/quiz')} className="flex items-center gap-2 px-4 py-2 bg-slate-700 hover:bg-slate-600 rounded-lg text-sm font-medium transition-colors">
              <Brain size={16} /> 进行测验
            </button>
          </div>
        </>
      )}
    </div>
  )
}

function StatCard({ icon: Icon, label, value, color }: { icon: React.ElementType; label: string; value: string | number; color: string }) {
  return (
    <div className="bg-slate-800 rounded-xl p-4 border border-slate-700">
      <div className="flex items-center gap-3">
        <div className={`p-2 bg-slate-700/50 rounded-lg ${color}`}>
          <Icon size={20} />
        </div>
        <div>
          <p className="text-xs text-slate-400">{label}</p>
          <p className="text-xl font-bold">{value}</p>
        </div>
      </div>
    </div>
  )
}
