import { useState, useEffect } from 'react'
import { 
  Activity, MessageSquare, Terminal, Heart, Settings, Zap,
  RefreshCw, Play, Square
} from 'lucide-react'
import { useHealth, useHealthHistory, useAgentStatus, useSettings, useUpdateSettings } from '@/hooks/useClawletAPI'
import type { HealthCheck } from '@/lib/api'
import { StatusBadge } from '@/components/status-badge'
import { HealthChart } from '@/components/HealthChart'
import { ConsoleLogs } from '@/components/ConsoleLogs'
import { Button } from './components/ui/button'

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
    setLastRefresh(new Date())
  }

  const formatUptime = (seconds: number) => {
    const hours = Math.floor(seconds / 3600)
    const minutes = Math.floor((seconds % 3600) / 60)
    return `${hours}h ${minutes}m`
  }

  const handleStartAgent = async () => {
    try {
      const res = await fetch('/agent/start', { method: 'POST' })
      const data = await res.json()
      alert(data.message)
      agentQuery.refetch()
    } catch (e) {
      alert('Failed to start agent')
    }
  }

  const handleStopAgent = async () => {
    try {
      const res = await fetch('/agent/stop', { method: 'POST' })
      const data = await res.json()
      alert(data.message)
      agentQuery.refetch()
    } catch (e) {
      alert('Failed to stop agent')
    }
  }

  // Settings form state
  const [provider, setProvider] = useState(settingsQuery.data?.provider || 'openrouter')
  const [model, setModel] = useState(settingsQuery.data?.model || '')
  const [maxIterations, setMaxIterations] = useState(settingsQuery.data?.max_iterations || 10)
  const [temperature, setTemperature] = useState(settingsQuery.data?.temperature || 0.7)
  const [saveStatus, setSaveStatus] = useState<'idle' | 'saving' | 'saved' | 'error'>('idle')

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
    setSaveStatus('saving')
    try {
      await updateSettingsMutation.mutateAsync({
        provider,
        model,
        max_iterations: maxIterations,
        temperature,
      })
      setSaveStatus('saved')
      setTimeout(() => setSaveStatus('idle'), 3000)
    } catch (err) {
      setSaveStatus('error')
    }
  }

  const handleReset = () => {
    if (settingsQuery.data) {
      setProvider(settingsQuery.data.provider)
      setModel(settingsQuery.data.model)
      setMaxIterations(settingsQuery.data.max_iterations)
      setTemperature(settingsQuery.data.temperature)
    }
  }

  return (
    <div className="min-h-screen bg-sakura-bg">
      {/* Header */}
      <header className="bg-white border-b border-sakura-border px-6 py-4 shadow-sm">
        <div className="flex items-center justify-between max-w-7xl mx-auto">
          <div className="flex items-center space-x-3">
            <Zap className="h-8 w-8 text-sakura-pink" />
            <h1 className="text-2xl font-bold text-gray-900">Clawlet</h1>
            <span className="text-sm text-gray-500">v0.1.0</span>
            <StatusBadge status={agentQuery.data?.running ? 'healthy' : 'unhealthy'} />
          </div>
          <div className="flex items-center gap-4">
            <Button 
              variant="outline" 
              size="sm" 
              onClick={refreshAll}
              disabled={healthQuery.isLoading}
            >
              <RefreshCw className={`h-4 w-4 mr-2 ${healthQuery.isLoading ? 'animate-spin' : ''}`} />
              Refresh
            </Button>
            <Button size="sm" variant="outline" asChild>
              <a href="https://github.com/Kxrbx/Clawlet" target="_blank" rel="noopener noreferrer">Documentation</a>
            </Button>
          </div>
        </div>
      </header>

      {/* Main Content */}
      <main className="max-w-7xl mx-auto px-6 py-8">
        {/* Tab Navigation */}
        <div className="flex space-x-1 mb-6 border-b border-sakura-border">
          {tabs.map((tab) => (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              className={`px-4 py-2 text-sm font-medium transition-colors flex items-center gap-2 ${
                activeTab === tab.id
                  ? 'text-sakura-magenta border-b-2 border-sakura-magenta'
                  : 'text-gray-500 hover:text-gray-700'
              }`}
            >
              <tab.icon className="h-4 w-4" />
              {tab.label}
            </button>
          ))}
        </div>

        {/* Overview Tab */}
        {activeTab === 'overview' && (
          <div className="space-y-6">
            {/* Stats Cards */}
            <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
              <div className="bg-white rounded-lg shadow p-6">
                <div className="text-sm text-gray-500 mb-1">Status</div>
                <div className="flex items-center gap-2">
                  <StatusBadge status={agentQuery.data?.running ? 'healthy' : 'unhealthy'} />
                </div>
              </div>
              <div className="bg-white rounded-lg shadow p-6">
                <div className="text-sm text-gray-500 mb-1">Messages Processed</div>
                <div className="text-3xl font-bold text-gray-900">{agentQuery.data?.messages_processed || 0}</div>
              </div>
              <div className="bg-white rounded-lg shadow p-6">
                <div className="text-sm text-gray-500 mb-1">Uptime</div>
                <div className="text-3xl font-bold text-gray-900">
                  {agentQuery.data ? formatUptime(agentQuery.data.uptime_seconds) : '--'}
                </div>
              </div>
              <div className="bg-white rounded-lg shadow p-6">
                <div className="text-sm text-gray-500 mb-1">Provider</div>
                <div className="text-lg font-semibold text-gray-900">{agentQuery.data?.provider || '--'}</div>
                <div className="text-sm text-gray-500 truncate">{agentQuery.data?.model || '--'}</div>
              </div>
            </div>

            {/* Quick Actions */}
            <div className="bg-white rounded-lg shadow p-6">
              <h3 className="text-lg font-semibold mb-4">Quick Actions</h3>
              <div className="flex flex-wrap gap-4">
                <Button onClick={handleStartAgent} disabled={agentQuery.data?.running}>
                  <Play className="h-4 w-4 mr-2" />
                  Start Agent
                </Button>
                <Button variant="outline" onClick={handleStopAgent} disabled={!agentQuery.data?.running}>
                  <Square className="h-4 w-4 mr-2" />
                  Stop Agent
                </Button>
                <Button variant="outline" asChild>
                  <a href="http://localhost:8000/docs" target="_blank" rel="noopener noreferrer">
                    API Docs
                  </a>
                </Button>
              </div>
            </div>

            {/* Recent Health */}
            <div className="bg-white rounded-lg shadow p-6">
              <div className="flex items-center justify-between mb-4">
                <h3 className="text-lg font-semibold">Recent Health</h3>
                <Button size="sm" variant="ghost" onClick={() => setActiveTab('health')}>
                  View Details
                </Button>
              </div>
              {healthQuery.data ? (
                <div className="space-y-3">
                  {(healthQuery.data.checks as any[]).map((check: any, i: number) => (
                    <div key={i} className="flex items-center justify-between py-2 border-b border-gray-100 last:border-0">
                      <div className="flex items-center gap-3">
                        <StatusBadge status={check.status} size="sm" />
                        <div>
                          <div className="font-medium text-gray-700 capitalize">{check.name}</div>
                          <div className="text-sm text-gray-500">{check.message}</div>
                        </div>
                      </div>
                      {check.latency_ms && (
                        <div className="text-sm text-gray-500">{check.latency_ms}ms</div>
                      )}
                    </div>
                  ))}
                </div>
              ) : (
                <div className="text-gray-500 text-center py-8">Loading health data...</div>
              )}
            </div>
          </div>
        )}

        {/* Health Tab */}
        {activeTab === 'health' && (
          <div className="space-y-6">
            <div className="bg-white rounded-lg shadow p-6">
              <div className="flex items-center justify-between mb-6">
                <h3 className="text-lg font-semibold">System Health</h3>
                <div className="flex items-center gap-2">
                  <span className="text-sm text-gray-500">
                    Last checked: {new Date(healthQuery.data?.timestamp || Date.now()).toLocaleTimeString()}
                  </span>
                  <Button size="sm" variant="outline" onClick={refreshAll} disabled={healthQuery.isLoading}>
                    <RefreshCw className={`h-4 w-4 ${healthQuery.isLoading ? 'animate-spin' : ''}`} />
                  </Button>
                </div>
              </div>

              {healthQuery.data ? (
                <div className="space-y-4 mb-8">
                  {healthQuery.data.checks.map((check: HealthCheck, i: number) => (
                    <div key={i} className="flex items-center justify-between p-4 bg-gray-50 rounded-lg">
                      <div className="flex items-center gap-4">
                        <StatusBadge status={check.status} />
                        <div>
                          <div className="font-medium text-gray-900 capitalize">{check.name}</div>
                          <div className="text-sm text-gray-500">{check.message}</div>
                        </div>
                      </div>
                      {check.latency_ms && (
                        <div className="text-sm text-gray-500">
                          {check.latency_ms.toFixed(0)}ms
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              ) : (
                <div className="text-center py-8 text-gray-500">Loading health checks...</div>
              )}
            </div>

            {/* Health History Chart */}
            <div className="bg-white rounded-lg shadow p-6">
              <h3 className="text-lg font-semibold mb-4">Health History</h3>
              {historyQuery.data?.history && historyQuery.data.history.length > 0 ? (
                <HealthChart history={historyQuery.data.history} height={250} />
              ) : (
                <div className="h-64 flex items-center justify-center text-gray-500">
                  No historical data yet. Checks will be recorded over time.
                </div>
              )}
            </div>
          </div>
        )}

        {/* Agents Tab */}
        {activeTab === 'agents' && (
          <div className="space-y-6">
            <div className="bg-white rounded-lg shadow p-6">
              <h3 className="text-lg font-semibold mb-4">Active Agents</h3>
              {agentQuery.data ? (
                <div className="space-y-4">
                  <div className="flex items-center justify-between p-4 bg-gray-50 rounded-lg">
                    <div className="flex items-center gap-4">
                      <div className={`w-3 h-3 rounded-full ${agentQuery.data.running ? 'bg-green-500' : 'bg-red-500'}`}></div>
                      <div>
                        <div className="font-medium">Main Agent</div>
                        <div className="text-sm text-gray-500">{agentQuery.data.provider} / {agentQuery.data.model}</div>
                      </div>
                    </div>
                    <div className="flex items-center gap-2">
                      <Button size="sm" variant="outline">Configure</Button>
                      <Button size="sm" variant="outline" onClick={handleStopAgent} disabled={!agentQuery.data.running}>
                        <Square className="h-4 w-4 mr-1" /> Stop
                      </Button>
                      <Button size="sm" onClick={handleStartAgent} disabled={agentQuery.data.running}>
                        <Play className="h-4 w-4 mr-1" /> Start
                      </Button>
                    </div>
                  </div>
                </div>
              ) : (
                <div className="text-center py-8 text-gray-500">Loading agent status...</div>
              )}
            </div>
          </div>
        )}

        {/* Console Tab */}
        {activeTab === 'console' && (
          <div className="space-y-6">
            <ConsoleLogs />
          </div>
        )}

        {/* Settings Tab */}
        {activeTab === 'settings' && (
          <div className="bg-white rounded-lg shadow p-6">
            <h3 className="text-lg font-semibold mb-4">Settings</h3>
            <p className="text-gray-500 mb-6">Configure Clawlet preferences. Changes are saved to your config.yaml.</p>
            
            {settingsQuery.isLoading ? (
              <div className="text-center py-8 text-gray-500">Loading settings...</div>
            ) : settingsQuery.error ? (
              <div className="text-center py-8 text-red-500">Failed to load settings.</div>
            ) : (
              <form className="space-y-6" onSubmit={handleSaveSettings}>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    Workspace Directory
                  </label>
                  <input
                    type="text"
                    className="w-full px-3 py-2 border border-gray-300 rounded-md bg-gray-50"
                    value="~/.clawlet"
                    disabled
                  />
                  <p className="text-xs text-gray-500 mt-1">Set via CLAWLET_WORKSPACE environment variable.</p>
                </div>
                
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    LLM Provider
                  </label>
                  <select 
                    className="w-full px-3 py-2 border border-gray-300 rounded-md"
                    value={provider}
                    onChange={(e) => setProvider(e.target.value)}
                  >
                    <option value="openrouter">OpenRouter</option>
                    <option value="ollama">Ollama</option>
                    <option value="lmstudio">LM Studio</option>
                  </select>
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    Model
                  </label>
                  <input
                    type="text"
                    className="w-full px-3 py-2 border border-gray-300 rounded-md"
                    value={model}
                    onChange={(e) => setModel(e.target.value)}
                    placeholder="e.g., openai/gpt-4o, meta-llama/llama-3.3-70b"
                  />
                  <p className="text-xs text-gray-500 mt-1">
                    See <a href="https://openrouter.ai/models" target="_blank" rel="noopener noreferrer" className="text-sakura-pink hover:underline">OpenRouter models</a> for available options.
                  </p>
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    Max Iterations
                  </label>
                  <input
                    type="number"
                    className="w-full px-3 py-2 border border-gray-300 rounded-md"
                    value={maxIterations}
                    onChange={(e) => setMaxIterations(Number(e.target.value))}
                    min="1"
                    max="100"
                  />
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    Temperature
                  </label>
                  <input
                    type="range"
                    className="w-full"
                    min="0"
                    max="1"
                    step="0.1"
                    value={temperature}
                    onChange={(e) => setTemperature(Number(e.target.value))}
                  />
                  <div className="flex justify-between text-xs text-gray-500">
                    <span>Precise ({temperature})</span>
                    <span>Creative</span>
                  </div>
                </div>

                <div className="pt-4 border-t flex items-center gap-2">
                  <Button type="submit" disabled={updateSettingsMutation.isPending}>
                    {updateSettingsMutation.isPending ? 'Saving...' : 'Save Changes'}
                  </Button>
                  <Button type="button" variant="outline" onClick={handleReset}>Reset to Defaults</Button>
                  {saveStatus && (
                    <span className={`text-sm ${saveStatus === 'saved' ? 'text-green-600' : 'text-red-600'}`}>
                      {saveStatus === 'saved' ? '✓ Saved' : saveStatus === 'error' ? '✗ Error' : ''}
                    </span>
                  )}
                </div>
              </form>
            )}
          </div>
        )}
      </main>

      {/* Footer */}
      <footer className="border-t border-sakura-border py-4 mt-8">
        <div className="max-w-7xl mx-auto px-6 text-center text-sm text-gray-500">
          Clawlet v0.1.0 • 
          <a href="https://github.com/Kxrbx/Clawlet" className="text-sakura-pink hover:underline ml-1">
            GitHub
          </a>
          <span className="mx-2">•</span>
          <span>Last refreshed: {lastRefresh.toLocaleTimeString()}</span>
        </div>
      </footer>
    </div>
  )
}
