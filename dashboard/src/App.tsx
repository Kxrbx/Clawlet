import { useState, useEffect } from 'react'
import { 
  Activity, MessageSquare, Terminal, Heart, Settings, Zap,
  RefreshCw, Play, Square, ChevronRight, Server, Cpu, Clock,
  Network, Shield, Database, Sparkles
} from 'lucide-react'
import { useHealth, useHealthHistory, useAgentStatus, useSettings, useUpdateSettings } from '@/hooks/useClawletAPI'
import type { HealthCheck } from '@/lib/api'
import { StatusBadge } from '@/components/status-badge'
import { HealthChart } from '@/components/HealthChart'
import { ConsoleLogs } from '@/components/ConsoleLogs'
import { Button } from './components/ui/button'
import { cn } from '@/lib/utils'

// Types
type TabId = 'overview' | 'health' | 'agents' | 'console' | 'settings'

const tabs = [
  { id: 'overview', label: 'Overview', icon: Activity },
  { id: 'health', label: 'Health', icon: Heart },
  { id: 'agents', label: 'Agents', icon: MessageSquare },
  { id: 'console', label: 'Console', icon: Terminal },
  { id: 'settings', label: 'Settings', icon: Settings },
] as const

export default function App() {
  const [activeTab, setActiveTab] = useState<TabId>('overview')
  const [sidebarOpen, setSidebarOpen] = useState(true)
  const [lastRefresh, setLastRefresh] = useState<Date>(new Date())

  // Queries
  const healthQuery = useHealth()
  const historyQuery = useHealthHistory(50)
  const agentQuery = useAgentStatus()
  const settingsQuery = useSettings()
  const updateSettingsMutation = useUpdateSettings()

  const refreshAll = () => {
    healthQuery.refetch()
    historyQuery.refetch()
    agentQuery.refetch()
    settingsQuery.refetch()
    setLastRefresh(new Date())
  }

  const formatUptime = (seconds: number) => {
    const hours = Math.floor(seconds / 3600)
    const minutes = Math.floor((seconds % 3600) / 60)
    const secs = seconds % 60
    if (hours > 0) return `${hours}h ${minutes}m`
    return `${minutes}m ${secs}s`
  }

  const formatTimestamp = (timestamp: string) => {
    return new Date(timestamp).toLocaleString()
  }

  const handleStartAgent = async () => {
    try {
      const res = await fetch('/agent/start', { method: 'POST' })
      const data = await res.json()
      if (data.success) {
        agentQuery.refetch()
      }
    } catch (e) {
      console.error('Failed to start agent:', e)
    }
  }

  const handleStopAgent = async () => {
    try {
      const res = await fetch('/agent/stop', { method: 'POST' })
      const data = await res.json()
      if (data.success) {
        agentQuery.refetch()
      }
    } catch (e) {
      console.error('Failed to stop agent:', e)
    }
  }

  // Settings form state
  const [provider, setProvider] = useState(settingsQuery.data?.provider || 'openrouter')
  const [model, setModel] = useState(settingsQuery.data?.model || '')
  const [maxIterations, setMaxIterations] = useState(settingsQuery.data?.max_iterations || 10)
  const [temperature, setTemperature] = useState(settingsQuery.data?.temperature || 0.7)

  // Sync settings when data loads
  useEffect(() => {
    if (settingsQuery.data) {
      setProvider(settingsQuery.data.provider)
      setModel(settingsQuery.data.model)
      setMaxIterations(settingsQuery.data.max_iterations)
      setTemperature(settingsQuery.data.temperature)
    }
  }, [settingsQuery.data])

  const handleSaveSettings = async (e: React.FormEvent) => {
    e.preventDefault()
    try {
      await updateSettingsMutation.mutateAsync({
        provider,
        model,
        max_iterations: maxIterations,
        temperature,
      })
    } catch (err) {
      console.error('Failed to save settings:', err)
    }
  }

  const getHealthColor = (status: string) => {
    switch (status) {
      case 'healthy': return 'text-green-500'
      case 'degraded': return 'text-yellow-500'
      case 'unhealthy': return 'text-red-500'
      default: return 'text-gray-500'
    }
  }

  const getHealthBg = (status: string) => {
    switch (status) {
      case 'healthy': return 'bg-green-50 border-green-200'
      case 'degraded': return 'bg-yellow-50 border-yellow-200'
      case 'unhealthy': return 'bg-red-50 border-red-200'
      default: return 'bg-gray-50 border-gray-200'
    }
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-pink-50 to-white">
      {/* Sidebar */}
      <aside className={cn(
        "fixed left-0 top-0 h-full bg-white shadow-xl z-50 transition-all duration-300",
        sidebarOpen ? "w-64" : "w-20"
      )}>
        {/* Logo */}
        <div className="flex items-center gap-3 px-6 py-5 border-b border-gray-100">
          <div className="w-10 h-10 bg-gradient-to-br from-pink-500 to-pink-600 rounded-xl flex items-center justify-center shadow-lg shadow-pink-200">
            <Zap className="h-6 w-6 text-white" />
          </div>
          {sidebarOpen && (
            <div className="animate-fadeIn">
              <h1 className="text-xl font-bold text-gray-900">Clawlet</h1>
              <p className="text-xs text-gray-400">AI Agent Dashboard</p>
            </div>
          )}
        </div>

        {/* Navigation */}
        <nav className="p-4 space-y-2">
          {tabs.map((tab) => {
            const Icon = tab.icon
            const isActive = activeTab === tab.id
            return (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id)}
                className={cn(
                  "w-full flex items-center gap-3 px-4 py-3 rounded-xl transition-all duration-200",
                  isActive 
                    ? "bg-gradient-to-r from-pink-100 to-pink-50 text-pink-600 shadow-sm" 
                    : "text-gray-600 hover:bg-gray-50 hover:text-gray-900"
                )}
              >
                <Icon className={cn("h-5 w-5 flex-shrink-0", isActive && "text-pink-500")} />
                {sidebarOpen && (
                  <span className="font-medium animate-fadeIn">{tab.label}</span>
                )}
                {isActive && sidebarOpen && (
                  <ChevronRight className="h-4 w-4 ml-auto text-pink-500" />
                )}
              </button>
            )
          })}
        </nav>

        {/* Toggle Button */}
        <button
          onClick={() => setSidebarOpen(!sidebarOpen)}
          className="absolute bottom-6 right-0 translate-x-1/2 w-8 h-8 bg-white rounded-full shadow-lg flex items-center justify-center text-gray-400 hover:text-gray-600 hover:scale-110 transition-all"
        >
          <ChevronRight className={cn("h-4 w-4 transition-transform", sidebarOpen && "rotate-180")} />
        </button>
      </aside>

      {/* Main Content */}
      <main className={cn(
        "transition-all duration-300 min-h-screen",
        sidebarOpen ? "ml-64" : "ml-20"
      )}>
        {/* Header */}
        <header className="sticky top-0 z-40 bg-white/80 backdrop-blur-lg border-b border-gray-100 px-8 py-4">
          <div className="flex items-center justify-between">
            <div>
              <h2 className="text-2xl font-bold text-gray-900">
                {tabs.find(t => t.id === activeTab)?.label}
              </h2>
              <p className="text-sm text-gray-500">
                {lastRefresh.toLocaleTimeString()} • Real-time monitoring
              </p>
            </div>
            <div className="flex items-center gap-4">
              <div className="flex items-center gap-2 px-4 py-2 bg-gray-50 rounded-full">
                <div className={cn(
                  "w-2 h-2 rounded-full animate-pulse",
                  agentQuery.data?.running ? "bg-green-500" : "bg-gray-400"
                )} />
                <span className="text-sm font-medium text-gray-600">
                  {agentQuery.data?.running ? 'Agent Running' : 'Agent Stopped'}
                </span>
              </div>
              <Button 
                variant="outline" 
                size="sm"
                onClick={refreshAll}
                disabled={healthQuery.isLoading}
                className="gap-2"
              >
                <RefreshCw className={cn("h-4 w-4", healthQuery.isLoading && "animate-spin")} />
                Refresh
              </Button>
            </div>
          </div>
        </header>

        {/* Content */}
        <div className="p-8">
          {/* Overview Tab */}
          {activeTab === 'overview' && (
            <div className="space-y-6 animate-fadeIn">
              {/* Stats Grid */}
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
                {/* Status Card */}
                <div className="bg-white rounded-2xl shadow-sm border border-gray-100 p-6 hover:shadow-md transition-shadow">
                  <div className="flex items-center justify-between mb-4">
                    <div className="w-12 h-12 bg-green-100 rounded-xl flex items-center justify-center">
                      <Server className="h-6 w-6 text-green-600" />
                    </div>
                    <StatusBadge status={agentQuery.data?.running ? 'healthy' : 'unhealthy'} />
                  </div>
                  <h3 className="text-sm font-medium text-gray-500">Agent Status</h3>
                  <p className="text-2xl font-bold text-gray-900 mt-1">
                    {agentQuery.data?.running ? 'Running' : 'Stopped'}
                  </p>
                </div>

                {/* Messages Card */}
                <div className="bg-white rounded-2xl shadow-sm border border-gray-100 p-6 hover:shadow-md transition-shadow">
                  <div className="flex items-center justify-between mb-4">
                    <div className="w-12 h-12 bg-blue-100 rounded-xl flex items-center justify-center">
                      <MessageSquare className="h-6 w-6 text-blue-600" />
                    </div>
                    <span className="text-xs font-medium text-blue-600 bg-blue-50 px-2 py-1 rounded-full">
                      Total
                    </span>
                  </div>
                  <h3 className="text-sm font-medium text-gray-500">Messages</h3>
                  <p className="text-2xl font-bold text-gray-900 mt-1">
                    {agentQuery.data?.messages_processed?.toLocaleString() || 0}
                  </p>
                </div>

                {/* Uptime Card */}
                <div className="bg-white rounded-2xl shadow-sm border border-gray-100 p-6 hover:shadow-md transition-shadow">
                  <div className="flex items-center justify-between mb-4">
                    <div className="w-12 h-12 bg-purple-100 rounded-xl flex items-center justify-center">
                      <Clock className="h-6 w-6 text-purple-600" />
                    </div>
                    <span className="text-xs font-medium text-purple-600 bg-purple-50 px-2 py-1 rounded-full">
                      Active
                    </span>
                  </div>
                  <h3 className="text-sm font-medium text-gray-500">Uptime</h3>
                  <p className="text-2xl font-bold text-gray-900 mt-1">
                    {agentQuery.data ? formatUptime(agentQuery.data.uptime_seconds) : '--'}
                  </p>
                </div>

                {/* Provider Card */}
                <div className="bg-white rounded-2xl shadow-sm border border-gray-100 p-6 hover:shadow-md transition-shadow">
                  <div className="flex items-center justify-between mb-4">
                    <div className="w-12 h-12 bg-pink-100 rounded-xl flex items-center justify-center">
                      <Network className="h-6 w-6 text-pink-600" />
                    </div>
                    <span className="text-xs font-medium text-pink-600 bg-pink-50 px-2 py-1 rounded-full">
                      LLM
                    </span>
                  </div>
                  <h3 className="text-sm font-medium text-gray-500">Provider</h3>
                  <p className="text-lg font-bold text-gray-900 mt-1 truncate">
                    {agentQuery.data?.provider || '--'}
                  </p>
                </div>
              </div>

              {/* Two Column Layout */}
              <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                {/* Health Overview */}
                <div className="bg-white rounded-2xl shadow-sm border border-gray-100 p-6">
                  <div className="flex items-center justify-between mb-6">
                    <h3 className="text-lg font-semibold text-gray-900">System Health</h3>
                    <Button size="sm" variant="ghost" onClick={() => setActiveTab('health')}>
                      View All
                    </Button>
                  </div>
                  {healthQuery.data ? (
                    <div className="space-y-3">
                      {healthQuery.data.checks.map((check: HealthCheck, i: number) => (
                        <div 
                          key={i} 
                          className={cn(
                            "flex items-center justify-between p-4 rounded-xl border transition-all hover:scale-[1.02]",
                            getHealthBg(check.status)
                          )}
                        >
                          <div className="flex items-center gap-3">
                            <div className={cn("w-2 h-2 rounded-full", getHealthColor(check.status))} />
                            <div>
                              <div className="font-medium text-gray-900 capitalize">{check.name}</div>
                              <div className="text-sm text-gray-500">{check.message}</div>
                            </div>
                          </div>
                          {check.latency_ms && (
                            <span className="text-sm font-mono text-gray-500">
                              {check.latency_ms.toFixed(0)}ms
                            </span>
                          )}
                        </div>
                      ))}
                    </div>
                  ) : (
                    <div className="text-center py-8 text-gray-500">
                      Loading health data...
                    </div>
                  )}
                </div>

                {/* Quick Actions */}
                <div className="bg-white rounded-2xl shadow-sm border border-gray-100 p-6">
                  <h3 className="text-lg font-semibold text-gray-900 mb-6">Quick Actions</h3>
                  <div className="space-y-4">
                    <div className="flex gap-4">
                      <Button 
                        onClick={handleStartAgent} 
                        disabled={agentQuery.data?.running}
                        className="flex-1 gap-2 bg-green-600 hover:bg-green-700"
                      >
                        <Play className="h-4 w-4" />
                        Start Agent
                      </Button>
                      <Button 
                        variant="outline" 
                        onClick={handleStopAgent} 
                        disabled={!agentQuery.data?.running}
                        className="flex-1 gap-2"
                      >
                        <Square className="h-4 w-4" />
                        Stop Agent
                      </Button>
                    </div>
                    <div className="flex gap-4">
                      <Button variant="outline" asChild className="flex-1">
                        <a href="http://localhost:8000/docs" target="_blank" rel="noopener noreferrer">
                          <Terminal className="h-4 w-4 mr-2" />
                          API Docs
                        </a>
                      </Button>
                      <Button variant="outline" asChild className="flex-1">
                        <a href="https://github.com/Kxrbx/Clawlet" target="_blank" rel="noopener noreferrer">
                          <Sparkles className="h-4 w-4 mr-2" />
                          GitHub
                        </a>
                      </Button>
                    </div>
                  </div>

                  {/* Model Info */}
                  <div className="mt-6 p-4 bg-gray-50 rounded-xl">
                    <div className="flex items-center gap-2 mb-2">
                      <Cpu className="h-4 w-4 text-gray-500" />
                      <span className="text-sm font-medium text-gray-700">Current Model</span>
                    </div>
                    <p className="text-sm text-gray-600 font-mono truncate">
                      {agentQuery.data?.model || 'Not configured'}
                    </p>
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* Health Tab */}
          {activeTab === 'health' && (
            <div className="space-y-6 animate-fadeIn">
              {/* Health Status Card */}
              <div className="bg-white rounded-2xl shadow-sm border border-gray-100 p-6">
                <div className="flex items-center justify-between mb-6">
                  <div>
                    <h3 className="text-lg font-semibold text-gray-900">System Health</h3>
                    <p className="text-sm text-gray-500">
                      Last checked: {healthQuery.data ? formatTimestamp(healthQuery.data.timestamp) : 'Loading...'}
                    </p>
                  </div>
                  <StatusBadge status={healthQuery.data?.status || 'unknown'} />
                </div>

                {healthQuery.data ? (
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    {healthQuery.data.checks.map((check: HealthCheck, i: number) => (
                      <div 
                        key={i} 
                        className={cn(
                          "p-4 rounded-xl border transition-all hover:shadow-md",
                          getHealthBg(check.status)
                        )}
                      >
                        <div className="flex items-center justify-between mb-2">
                          <div className="flex items-center gap-2">
                            <div className={cn("w-3 h-3 rounded-full", getHealthColor(check.status))} />
                            <span className="font-medium text-gray-900 capitalize">{check.name}</span>
                          </div>
                          {check.latency_ms && (
                            <span className="text-sm font-mono text-gray-500">
                              {check.latency_ms.toFixed(0)}ms
                            </span>
                          )}
                        </div>
                        <p className="text-sm text-gray-600">{check.message}</p>
                      </div>
                    ))}
                  </div>
                ) : (
                  <div className="text-center py-12 text-gray-500">
                    Loading health checks...
                  </div>
                )}
              </div>

              {/* Health History Chart */}
              <div className="bg-white rounded-2xl shadow-sm border border-gray-100 p-6">
                <h3 className="text-lg font-semibold text-gray-900 mb-6">Health History</h3>
                {historyQuery.data?.history && historyQuery.data.history.length > 0 ? (
                  <HealthChart history={historyQuery.data.history} height={300} />
                ) : (
                  <div className="h-64 flex flex-col items-center justify-center text-gray-500">
                    <Activity className="h-12 w-12 mb-4 text-gray-300" />
                    <p>No historical data yet. Health checks will be recorded over time.</p>
                  </div>
                )}
              </div>
            </div>
          )}

          {/* Agents Tab */}
          {activeTab === 'agents' && (
            <div className="space-y-6 animate-fadeIn">
              <div className="bg-white rounded-2xl shadow-sm border border-gray-100 p-6">
                <div className="flex items-center justify-between mb-6">
                  <h3 className="text-lg font-semibold text-gray-900">Agent Management</h3>
                  <div className="flex items-center gap-2">
                    <div className={cn(
                      "w-3 h-3 rounded-full animate-pulse",
                      agentQuery.data?.running ? "bg-green-500" : "bg-red-500"
                    )} />
                    <span className="text-sm font-medium text-gray-600">
                      {agentQuery.data?.running ? 'Active' : 'Inactive'}
                    </span>
                  </div>
                </div>

                {agentQuery.data ? (
                  <div className="space-y-4">
                    {/* Main Agent Card */}
                    <div className="p-6 bg-gradient-to-r from-gray-50 to-gray-100 rounded-xl border border-gray-200">
                      <div className="flex items-center justify-between">
                        <div className="flex items-center gap-4">
                          <div className={cn(
                            "w-14 h-14 rounded-2xl flex items-center justify-center",
                            agentQuery.data.running ? "bg-green-100" : "bg-gray-100"
                          )}>
                            <Sparkles className={cn(
                              "h-7 w-7",
                              agentQuery.data.running ? "text-green-600" : "text-gray-400"
                            )} />
                          </div>
                          <div>
                            <h4 className="text-lg font-semibold text-gray-900">Main Agent</h4>
                            <p className="text-sm text-gray-500 font-mono">{agentQuery.data.model || 'Not configured'}</p>
                          </div>
                        </div>
                        <div className="flex items-center gap-3">
                          <div className="text-right mr-4">
                            <p className="text-2xl font-bold text-gray-900">
                              {formatUptime(agentQuery.data.uptime_seconds)}
                            </p>
                            <p className="text-xs text-gray-500">Uptime</p>
                          </div>
                          {agentQuery.data.running ? (
                            <Button variant="destructive" onClick={handleStopAgent} className="gap-2">
                              <Square className="h-4 w-4" />
                              Stop
                            </Button>
                          ) : (
                            <Button onClick={handleStartAgent} className="gap-2 bg-green-600 hover:bg-green-700">
                              <Play className="h-4 w-4" />
                              Start
                            </Button>
                          )}
                        </div>
                      </div>

                      {/* Stats Grid */}
                      <div className="grid grid-cols-4 gap-4 mt-6 pt-6 border-t border-gray-200">
                        <div className="text-center">
                          <p className="text-2xl font-bold text-gray-900">{agentQuery.data.messages_processed}</p>
                          <p className="text-xs text-gray-500">Messages</p>
                        </div>
                        <div className="text-center">
                          <p className="text-2xl font-bold text-gray-900 capitalize">{agentQuery.data.provider}</p>
                          <p className="text-xs text-gray-500">Provider</p>
                        </div>
                        <div className="text-center">
                          <p className="text-2xl font-bold text-gray-900">{formatUptime(agentQuery.data.uptime_seconds)}</p>
                          <p className="text-xs text-gray-500">Session Time</p>
                        </div>
                        <div className="text-center">
                          <p className="text-2xl font-bold text-gray-900">
                            {agentQuery.data.running ? 'Active' : 'Idle'}
                          </p>
                          <p className="text-xs text-gray-500">Status</p>
                        </div>
                      </div>
                    </div>
                  </div>
                ) : (
                  <div className="text-center py-12 text-gray-500">
                    Loading agent status...
                  </div>
                )}
              </div>
            </div>
          )}

          {/* Console Tab */}
          {activeTab === 'console' && (
            <div className="animate-fadeIn">
              <ConsoleLogs />
            </div>
          )}

          {/* Settings Tab */}
          {activeTab === 'settings' && (
            <div className="max-w-2xl animate-fadeIn">
              <div className="bg-white rounded-2xl shadow-sm border border-gray-100 p-8">
                <div className="mb-8">
                  <h3 className="text-xl font-semibold text-gray-900 mb-2">Settings</h3>
                  <p className="text-gray-500">Configure Clawlet preferences. Changes are saved to your config.yaml.</p>
                </div>
                
                {settingsQuery.isLoading ? (
                  <div className="text-center py-12 text-gray-500">Loading settings...</div>
                ) : settingsQuery.error ? (
                  <div className="text-center py-12 text-red-500">Failed to load settings.</div>
                ) : (
                  <form className="space-y-8" onSubmit={handleSaveSettings}>
                    {/* Provider Selection */}
                    <div className="space-y-3">
                      <label className="block text-sm font-medium text-gray-700">
                        LLM Provider
                      </label>
                      <div className="grid grid-cols-3 gap-3">
                        {['openrouter', 'ollama', 'lmstudio'].map((p) => (
                          <button
                            key={p}
                            type="button"
                            onClick={() => setProvider(p)}
                            className={cn(
                              "p-4 rounded-xl border-2 transition-all text-center capitalize",
                              provider === p
                                ? "border-pink-500 bg-pink-50 text-pink-600"
                                : "border-gray-200 hover:border-gray-300 text-gray-600"
                            )}
                          >
                            {p}
                          </button>
                        ))}
                      </div>
                    </div>

                    {/* Model */}
                    <div className="space-y-3">
                      <label className="block text-sm font-medium text-gray-700">
                        Model
                      </label>
                      <input
                        type="text"
                        className="w-full px-4 py-3 border border-gray-300 rounded-xl focus:ring-2 focus:ring-pink-200 focus:border-pink-400 transition-all"
                        value={model}
                        onChange={(e) => setModel(e.target.value)}
                        placeholder="e.g., openai/gpt-4o, meta-llama/llama-3.3-70b"
                      />
                      <p className="text-xs text-gray-500">
                        See <a href="https://openrouter.ai/models" target="_blank" rel="noopener noreferrer" className="text-pink-500 hover:underline">OpenRouter models</a> for available options.
                      </p>
                    </div>

                    {/* Max Iterations */}
                    <div className="space-y-3">
                      <div className="flex justify-between">
                        <label className="block text-sm font-medium text-gray-700">
                          Max Iterations
                        </label>
                        <span className="text-sm font-mono text-gray-600">{maxIterations}</span>
                      </div>
                      <input
                        type="range"
                        className="w-full h-2 bg-gray-200 rounded-lg appearance-none cursor-pointer accent-pink-500"
                        min="1"
                        max="100"
                        value={maxIterations}
                        onChange={(e) => setMaxIterations(Number(e.target.value))}
                      />
                    </div>

                    {/* Temperature */}
                    <div className="space-y-3">
                      <div className="flex justify-between">
                        <label className="block text-sm font-medium text-gray-700">
                          Temperature
                        </label>
                        <span className="text-sm font-mono text-gray-600">{temperature.toFixed(1)}</span>
                      </div>
                      <input
                        type="range"
                        className="w-full h-2 bg-gray-200 rounded-lg appearance-none cursor-pointer accent-pink-500"
                        min="0"
                        max="1"
                        step="0.1"
                        value={temperature}
                        onChange={(e) => setTemperature(Number(e.target.value))}
                      />
                      <div className="flex justify-between text-xs text-gray-400">
                        <span>Precise</span>
                        <span>Balanced</span>
                        <span>Creative</span>
                      </div>
                    </div>

                    {/* Actions */}
                    <div className="pt-6 border-t flex items-center gap-4">
                      <Button type="submit" disabled={updateSettingsMutation.isPending}>
                        {updateSettingsMutation.isPending ? 'Saving...' : 'Save Changes'}
                      </Button>
                      <Button 
                        type="button" 
                        variant="outline" 
                        onClick={() => {
                          if (settingsQuery.data) {
                            setProvider(settingsQuery.data.provider)
                            setModel(settingsQuery.data.model)
                            setMaxIterations(settingsQuery.data.max_iterations)
                            setTemperature(settingsQuery.data.temperature)
                          }
                        }}
                      >
                        Reset
                      </Button>
                    </div>
                  </form>
                )}
              </div>
            </div>
          )}
        </div>
      </main>

      {/* CSS for animations */}
      <style>{`
        @keyframes fadeIn {
          from { opacity: 0; transform: translateY(10px); }
          to { opacity: 1; transform: translateY(0); }
        }
        .animate-fadeIn {
          animation: fadeIn 0.3s ease-out forwards;
        }
      `}</style>
    </div>
  )
}
