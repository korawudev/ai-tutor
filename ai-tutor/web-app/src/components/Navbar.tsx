import { useAuthStore } from '../stores/authStore'

export default function Navbar() {
  const user = useAuthStore((s) => s.user)

  return (
    <header className="h-14 bg-slate-800 border-b border-slate-700 flex items-center justify-between px-6">
      <h2 className="text-lg font-semibold">AI 私教</h2>
      <div className="flex items-center gap-3">
        <div className="w-8 h-8 rounded-full bg-primary-600 flex items-center justify-center text-sm font-medium">
          {user?.username?.[0]?.toUpperCase() || 'U'}
        </div>
      </div>
    </header>
  )
}
