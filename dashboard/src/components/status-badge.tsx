import { cn } from '@/lib/utils'

export function StatusBadge({ status, size = 'md' }: { status: string; size?: 'sm' | 'md' }) {
  const styles = {
    healthy: {
      bg: 'bg-green-100',
      text: 'text-green-800',
      icon: <CheckCircle className={cn('h-4 w-4', size === 'sm' && 'h-3 w-3')} />,
    },
    degraded: {
      bg: 'bg-yellow-100',
      text: 'text-yellow-800',
      icon: <AlertTriangle className={cn('h-4 w-4', size === 'sm' && 'h-3 w-3')} />,
    },
    unhealthy: {
      bg: 'bg-red-100',
      text: 'text-red-800',
      icon: <XCircle className={cn('h-4 w-4', size === 'sm' && 'h-3 w-3')} />,
    },
  }
  
  const style = styles[status as keyof typeof styles] || styles.unhealthy
  const sizeClasses = size === 'sm' ? 'px-1.5 py-0.5 text-xs' : 'px-2 py-1 text-sm'
  
  return (
    <span className={cn('inline-flex items-center gap-1 rounded-full font-medium', style.bg, style.text, sizeClasses)}>
      {style.icon}
      {status}
    </span>
  )
}

import { CheckCircle, AlertTriangle, XCircle } from 'lucide-react'
