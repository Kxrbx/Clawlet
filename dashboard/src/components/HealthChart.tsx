import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer } from 'recharts'

const statusToNumber = (status: string): number => {
  switch (status) {
    case 'healthy': return 3
    case 'degraded': return 2
    case 'unhealthy': return 1
    default: return 0
  }
}

const numberToStatus = (n: number): string => {
  switch (n) {
    case 3: return 'healthy'
    case 2: return 'degraded'
    case 1: return 'unhealthy'
    default: return 'unknown'
  }
}

const statusColors: Record<string, string> = {
  healthy: '#10b981',
  degraded: '#f59e0b',
  unhealthy: '#ef4444',
}

interface HealthChartProps {
  history: Array<{
    timestamp: string
    status: string
    checks: Array<{ name: string; status: string }>
  }>
  height?: number
}

export function HealthChart({ history, height = 200 }: HealthChartProps) {
  if (!history || history.length === 0) {
    return (
      <div className="flex items-center justify-center h-48 text-gray-500">
        No health history available yet.
      </div>
    )
  }

  // Transform data for Recharts
  const data = history.map((entry, index) => ({
    index,
    time: new Date(entry.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
    overall: statusToNumber(entry.status),
    ...entry.checks.reduce((acc, check) => {
      acc[check.name] = statusToNumber(check.status)
      return acc
    }, {} as Record<string, number>),
  }))

  const checksNames = [...new Set(history.flatMap(h => h.checks.map(c => c.name)))]

  return (
    <div className="w-full" style={{ height: `${height}px` }}>
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={data} margin={{ top: 5, right: 20, left: 0, bottom: 5 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
          <XAxis 
            dataKey="time" 
            tick={{ fontSize: 12 }}
            tickLine={false}
            axisLine={{ stroke: '#e5e7eb' }}
          />
          <YAxis 
            domain={[1, 3]}
            ticks={[1, 2, 3]}
            tickFormatter={numberToStatus}
            tick={{ fontSize: 12 }}
            tickLine={false}
            axisLine={{ stroke: '#e5e7eb' }}
          />
          <Tooltip 
            contentStyle={{ 
              backgroundColor: 'white', 
              border: '1px solid #e5e7eb', 
              borderRadius: '0.5rem',
              boxShadow: '0 4px 6px -1px rgba(0, 0, 0, 0.1)'
            }}
            formatter={(value: any, name: string | undefined, ..._rest: any[]) => 
              [numberToStatus(value as number), name ?? ''] as const
            }
          />
          <Legend />
          
          {/* Overall status line (thick) */}
          <Line
            type="monotone"
            dataKey="overall"
            stroke={statusColors.healthy}
            strokeWidth={3}
            dot={{ r: 4 }}
            activeDot={{ r: 6 }}
            name="Overall"
          />
          
          {/* Individual checks */}
          {checksNames.map((name) => (
            <Line
              key={name}
              type="monotone"
              dataKey={name}
              stroke={statusColors.degraded}
              strokeWidth={1.5}
              dot={false}
              name={name}
            />
          ))}
        </LineChart>
      </ResponsiveContainer>
    </div>
  )
}
