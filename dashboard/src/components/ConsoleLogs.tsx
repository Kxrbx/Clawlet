import { useEffect, useRef } from 'react'
import { useQuery } from '@tanstack/react-query'
import { fetchConsole, type ConsoleResponse } from '@/lib/api'
import { Terminal } from 'lucide-react'

export function ConsoleLogs() {
  const { data, isLoading } = useQuery<ConsoleResponse>({
    queryKey: ['console'],
    queryFn: fetchConsole,
    refetchInterval: 3000,
    staleTime: 1500,
  })

  const containerRef = useRef<HTMLDivElement>(null)

  // Auto-scroll to bottom
  useEffect(() => {
    if (containerRef.current) {
      containerRef.current.scrollTop = containerRef.current.scrollHeight
    }
  }, [data])

  const lines = data?.output || []

  return (
    <div className="bg-gray-900 rounded-lg p-4 font-mono text-sm">
      <div className="flex items-center gap-2 mb-3 pb-2 border-b border-gray-700">
        <Terminal className="h-4 w-4 text-gray-400" />
        <span className="text-gray-300 font-medium">Live Console</span>
        {isLoading && <span className="text-xs text-gray-500 ml-2">(updating...)</span>}
      </div>
      
      <div 
        ref={containerRef}
        className="h-64 overflow-y-auto space-y-1"
      >
        {lines.map((line: string, idx: number) => (
          <div key={idx} className="text-gray-300 whitespace-pre-wrap break-all">
            {line}
          </div>
        ))}
        {lines.length === 0 && !isLoading && (
          <div className="text-gray-500 italic">No console output yet.</div>
        )}
      </div>
    </div>
  )
}
