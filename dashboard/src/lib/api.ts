// API client for Clawlet Dashboard
const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000'

export interface HealthCheck {
  name: string
  status: 'healthy' | 'degraded' | 'unhealthy'
  message: string
  latency_ms?: number
}

export interface HealthStatus {
  status: 'healthy' | 'degraded' | 'unhealthy'
  timestamp: string
  checks: HealthCheck[]
}

export interface AgentStatus {
  running: boolean
  provider: string
  model: string
  messages_processed: number
  uptime_seconds: number
}

export interface ModelInfo {
  id: string
  name?: string
  description?: string
}

export interface ModelsResponse {
  models: ModelInfo[]
  updated_at: string
}

export interface SettingsResponse {
  provider: string
  model: string
  storage: string
  max_iterations: number
  temperature: number
}

export async function fetchHealth(): Promise<HealthStatus> {
  const res = await fetch(`${API_BASE}/health`)
  if (!res.ok) throw new Error(`Health check failed: ${res.status}`)
  return res.json()
}

export async function fetchAgentStatus(): Promise<AgentStatus> {
  const res = await fetch(`${API_BASE}/agent/status`)
  if (!res.ok) throw new Error(`Agent status failed: ${res.status}`)
  return res.json()
}

export async function startAgent(): Promise<{ success: boolean; message: string }> {
  const res = await fetch(`${API_BASE}/agent/start`, { method: 'POST' })
  return res.json()
}

export async function stopAgent(): Promise<{ success: boolean; message: string }> {
  const res = await fetch(`${API_BASE}/agent/stop`, { method: 'POST' })
  return res.json()
}

export async function fetchSettings(): Promise<SettingsResponse> {
  const res = await fetch(`${API_BASE}/settings`)
  if (!res.ok) throw new Error(`Settings fetch failed: ${res.status}`)
  return res.json()
}

export async function updateSettings(settings: {
  provider?: string
  model?: string
  max_iterations?: number
  temperature?: number
}): Promise<{ success: boolean; message: string }> {
  const res = await fetch(`${API_BASE}/settings`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(settings),
  })
  return res.json()
}

export async function fetchHealthHistory(limit: number = 50) {
  const res = await fetch(`${API_BASE}/health/history?limit=${limit}`)
  if (!res.ok) throw new Error(`Health history fetch failed: ${res.status}`)
  return res.json()
}

export async function fetchModels(provider: string = 'openrouter', force_refresh: boolean = false) {
  const url = new URL(`${API_BASE}/models`)
  url.searchParams.set('provider', provider)
  if (force_refresh) url.searchParams.set('force_refresh', 'true')
  const res = await fetch(url.toString())
  if (!res.ok) throw new Error(`Models fetch failed: ${res.status}`)
  return res.json() as Promise<ModelsResponse>
}

export async function fetchCacheInfo(provider: string = 'openrouter') {
  const url = new URL(`${API_BASE}/models/cache-info`)
  url.searchParams.set('provider', provider)
  const res = await fetch(url.toString())
  if (!res.ok) throw new Error(`Cache info failed: ${res.status}`)
  return res.json()
}

export async function fetchLogs(limit: number = 100) {
  const res = await fetch(`${API_BASE}/logs?limit=${limit}`)
  if (!res.ok) throw new Error(`Logs fetch failed: ${res.status}`)
  return res.json()
}

export interface ConsoleResponse {
  output: string[]
}

export async function fetchConsole(): Promise<ConsoleResponse> {
  const res = await fetch(`${API_BASE}/console`)
  if (!res.ok) throw new Error(`Console fetch failed: ${res.status}`)
  return res.json()
}
