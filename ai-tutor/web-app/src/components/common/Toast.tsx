import { useEffect } from 'react'
import { CheckCircle2, XCircle } from 'lucide-react'

interface ToastProps {
  message: string
  type?: 'success' | 'error'
  onDone: () => void
  duration?: number
}

export default function Toast({ message, type = 'success', onDone, duration = 1000 }: ToastProps) {
  useEffect(() => {
    const timer = setTimeout(onDone, duration)
    return () => clearTimeout(timer)
  }, [onDone, duration])

  return (
    <div className="toast-enter pointer-events-none fixed left-1/2 top-20 z-50 -translate-x-1/2">
      <div className={`flex items-center gap-2 rounded-lg border px-4 py-2.5 text-sm shadow-xl backdrop-blur-md ${
        type === 'success'
          ? 'border-green-500/40 bg-green-950/80 text-green-200'
          : 'border-red-500/40 bg-red-950/80 text-red-200'
      }`}>
        {type === 'success' ? <CheckCircle2 size={16} /> : <XCircle size={16} />}
        {message}
      </div>
    </div>
  )
}