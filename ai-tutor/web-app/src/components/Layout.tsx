import { useState } from 'react'
import { Outlet, NavLink, useNavigate } from 'react-router-dom'
import { useAuthStore } from '../stores/authStore'
import {
  LayoutDashboard, FileText, MessageSquare, Brain,
  BookOpen, BookMarked, BarChart3, LogOut, PanelLeftClose, PanelLeft
} from 'lucide-react'

const navItems = [
  { to: '/', icon: LayoutDashboard, label: '仪表盘' },
  { to: '/documents', icon: FileText, label: '文档管理' },
  { to: '/chat', icon: MessageSquare, label: 'AI 对话' },
  { to: '/quiz', icon: Brain, label: '智能测验' },
  { to: '/wrong-book', icon: BookMarked, label: '错题本' },
  { to: '/review', icon: BookOpen, label: '复习计划' },
  { to: '/progress', icon: BarChart3, label: '学习进度' },
]

export default function Layout() {
  const logout = useAuthStore((s) => s.logout)
  const user = useAuthStore((s) => s.user)
  const navigate = useNavigate()
  const [collapsed, setCollapsed] = useState(false)

  const handleLogout = () => {
    logout()
    navigate('/login')
  }

  return (
    <div className="flex h-screen">
      {/* Sidebar */}
      <aside
        className={`${collapsed ? 'w-14' : 'w-60'} bg-slate-800 border-r border-slate-700 flex flex-col transition-all duration-200 shrink-0`}
      >
        <div className={`p-4 border-b border-slate-700 flex items-center gap-2 ${collapsed ? 'justify-center px-2' : ''}`}>
          {!collapsed && (
            <div className="flex-1 min-w-0">
              <h1 className="text-xl font-bold text-primary-400 truncate">AI 私教</h1>
              <p className="text-xs text-slate-400 mt-1 truncate">智能编程学习助手</p>
            </div>
          )}
          <button
            onClick={() => setCollapsed((p) => !p)}
            className="p-2 text-slate-400 hover:text-white hover:bg-slate-700 rounded-lg transition-colors shrink-0"
            title={collapsed ? '展开侧边栏' : '收起侧边栏'}
          >
            {collapsed ? <PanelLeft size={18} /> : <PanelLeftClose size={18} />}
          </button>
        </div>

        <nav className="flex-1 p-3 space-y-1">
          {navItems.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.to === '/'}
              className={({ isActive }) =>
                `relative group flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm transition-colors ${
                  isActive
                    ? 'bg-primary-600/20 text-primary-400'
                    : 'text-slate-300 hover:bg-slate-700/50 hover:text-white'
                } ${collapsed ? 'justify-center px-0' : ''}`
              }
            >
              <item.icon size={18} className="shrink-0" />
              {!collapsed && <span>{item.label}</span>}
              {collapsed && (
                <div className="absolute left-full ml-2 px-2 py-1 bg-slate-700 text-white text-xs rounded whitespace-nowrap opacity-0 group-hover:opacity-100 transition-opacity pointer-events-none shadow-lg z-50">
                  {item.label}
                </div>
              )}
            </NavLink>
          ))}
        </nav>

        <div className={`p-3 border-t border-slate-700 ${collapsed ? 'px-2' : ''}`}>
          <div className={`flex items-center gap-3 ${collapsed ? 'justify-center' : 'px-3 py-2'}`}>
            <div className="w-8 h-8 rounded-full bg-primary-600 flex items-center justify-center text-sm font-medium shrink-0">
              {user?.username?.[0]?.toUpperCase() || 'U'}
            </div>
            {!collapsed && (
              <>
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-medium truncate">{user?.username || '用户'}</p>
                  <p className="text-xs text-slate-400 truncate">{user?.email}</p>
                </div>
                <button
                  onClick={handleLogout}
                  className="p-1.5 text-slate-400 hover:text-white hover:bg-slate-700 rounded transition-colors"
                  title="退出登录"
                >
                  <LogOut size={16} />
                </button>
              </>
            )}
          </div>
        </div>
      </aside>

      {/* Main content */}
      <main className="flex-1 overflow-y-auto bg-slate-900">
        <Outlet />
      </main>
    </div>
  )
}
