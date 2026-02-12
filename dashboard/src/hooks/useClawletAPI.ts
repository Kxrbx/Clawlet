import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import type { HealthStatus, AgentStatus, SettingsResponse } from '@/lib/api'
import { fetchHealth, fetchHealthHistory, fetchAgentStatus, fetchLogs, fetchConsole, fetchSettings, updateSettings, type ConsoleResponse } from '@/lib/api'

export function useHealth() {
  return useQuery<HealthStatus>({
    queryKey: ['health'],
    queryFn: fetchHealth,
    refetchInterval: 10000,
    staleTime: 5000,
  })
}

export function useHealthHistory(limit = 50) {
  return useQuery<{ history: any[] }>({
    queryKey: ['health-history', limit],
    queryFn: () => fetchHealthHistory(limit),
    refetchInterval: 30000,
    staleTime: 15000,
  })
}

export function useAgentStatus() {
  return useQuery<AgentStatus>({
    queryKey: ['agent-status'],
    queryFn: fetchAgentStatus,
    refetchInterval: 5000,
    staleTime: 2000,
  })
}

export function useLogs(limit = 100) {
  return useQuery<{ logs: any[]; limit: number }>({
    queryKey: ['logs', limit],
    queryFn: () => fetchLogs(limit),
    refetchInterval: 2000,
    staleTime: 1000,
  })
}

export function useConsole() {
  return useQuery<ConsoleResponse>({
    queryKey: ['console'],
    queryFn: fetchConsole,
    refetchInterval: 3000,
    staleTime: 1500,
  })
}

export function useSettings() {
  return useQuery<SettingsResponse>({
    queryKey: ['settings'],
    queryFn: fetchSettings,
    staleTime: 10000,
  })
}

export function useUpdateSettings() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: updateSettings,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['settings'] })
      queryClient.invalidateQueries({ queryKey: ['agent-status'] })
    },
  })
}
