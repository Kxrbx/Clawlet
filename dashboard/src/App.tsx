import { useState, useEffect } from 'react'
import { 
  Activity, MessageSquare, Terminal, Database, Heart, Settings, Zap,
  CheckCircle, AlertTriangle, XCircle, RefreshCw
} from 'lucide-react'
import { Button } from './components/ui/button'

// Types
interface HealthStatus {
  status: 'healthy' | 'degraded' | 'unhealthy'
  timestamp: string
  checks: {
    name: string
    status: string
    message: string
    latency_ms?: number
  }[]
}

interface AgentStatus {
  running: boolean
  provider: string
  model: string
  messages_processed: number
  uptime_seconds: number
}

interface ModelInfo {
  id: string
  name?: string
  description?: string
}

interface ModelsResponse {
  models: ModelInfo[]
  updated_at: string
}

// Mock data for demo
const mockHealth: HealthStatus = {
  status: 'healthy',
  timestamp: new Date().toISOString(),
  checks: [
    { name: 'provider', status: 'healthy', message: 'OpenRouter responding', latency_ms: 245 },
    { name: 'storage', status: 'healthy', message: 'SQLite connected', latency_ms: 2 },
    { name: 'memory', status: 'healthy', message: 'Memory OK: 42% used' },
  ]
}

const mockAgent: AgentStatus = {
  running: true,
  provider: 'openrouter',
  model: 'anthropic/claude-sonnet-4',
  messages_processed: 142,
  uptime_seconds: 3600,
}

export default function App() {
  const [activeTab, setActiveTab] = useState('overview')
  const [health, setHealth] = useState<HealthStatus>(mockHealth)
  const [agent, setAgent] = useState<AgentStatus>(mockAgent)
  const [loading, setLoading] = useState(false)
  const [models, setModels] = useState<ModelInfo[]>([])
  const [loadingModels, setLoadingModels] = useState(false)
  const [selectedModel, setSelectedModel] = useState(agent.model)
  const [cacheInfo, setCacheInfo] = useState<{ updated_at?: string; model_count: number; is_expired: boolean } | null>(null)

  const tabs = [
    { id: 'overview', label: 'Overview', icon: Activity },
    { id: 'health', label: 'Health', icon: Heart },
    { id: 'agents', label: 'Agents', icon: MessageSquare },
    { id: 'console', label: 'Console', icon: Terminal },
    { id: 'memory', label: 'Memory', icon: Database },
    { id: 'settings', label: 'Settings', icon: Settings },
  ]

  const refreshHealth = () => {
    setLoading(true)
    // In real app, fetch from API
    setTimeout(() => {
      setHealth({ ...mockHealth, timestamp: new Date().toISOString() })
      setLoading(false)
    }, 500)
  }

  const fetchModels = async (refresh: boolean = false) => {
    setLoadingModels(true)
    try {
      const res = await fetch(`/models?provider=openrouter&force_refresh=${refresh}`)
      if (res.ok) {
        const data: ModelsResponse = await res.json()
        setModels(data.models)
        setCacheInfo({ updated_at: data.updated_at, model_count: data.models.length, is_expired: false })
      }
    } catch (e) {
      console.error('Failed to fetch models:', e)
    } finally {
      setLoadingModels(false)
    }
  }

  // Fetch models when settings tab is active
  useEffect(() => {
    if (activeTab === 'settings') {
      fetchModels()
    }
  }, [activeTab])

  const formatUptime = (seconds: number) => {
    const hours = Math.floor(seconds / 3600)
    const minutes = Math.floor((seconds % 3600) / 60)
    return `${hours}h ${minutes}m`
  }

  const StatusBadge = ({ status }: { status: string }) => {
    const colors = {
      healthy: 'bg-green-100 text-green-800',
      degraded: 'bg-yellow-100 text-yellow-800',
      unhealthy: 'bg-red-100 text-red-800',
    }
    const icons = {
      healthy: <CheckCircle className="h-4 w-4" />,
      degraded: <AlertTriangle className="h-4 w-4" />,
      unhealthy: <XCircle className="h-4 w-4" />,
    }
    return (
      <span className={`inline-flex items-center gap-1 px-2 py-1 rounded-full text-sm ${colors[status as keyof typeof colors]}`}>
        {icons[status as keyof typeof icons]}
        {status}
      </span>
    )
  }

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Header */}
      <header className="bg-white border-b border-gray-200 px-6 py-4">
        <div className="flex items-center justify-between max-w-7xl mx-auto">
          <div className="flex items-center space-x-3">
            <Zap className="h-8 w-8 text-blue-600" />
            <h1 className="text-2xl font-bold text-gray-900">Clawlet</h1>
            <span className="text-sm text-gray-500">v0.1.0</span>
            <StatusBadge status={agent.running ? 'healthy' : 'unhealthy'} />
          </div>
          <div className="flex items-center gap-4">
            <Button 
              variant="outline" 
              size="sm" 
              onClick={refreshHealth}
              disabled={loading}
            >
              <RefreshCw className={`h-4 w-4 mr-2 ${loading ? 'animate-spin' : ''}`} />
              Refresh
            </Button>
            <Button size="sm">Documentation</Button>
          </div>
        </div>
      </header>

      {/* Main Content */}
      <main className="max-w-7xl mx-auto px-6 py-8">
        {/* Tab Navigation */}
        <div className="flex space-x-1 mb-6 border-b border-gray-200">
          {tabs.map((tab) => (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              className={`px-4 py-2 text-sm font-medium transition-colors flex items-center gap-2 ${
                activeTab === tab.id
                  ? 'text-blue-600 border-b-2 border-blue-600'
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
                  <StatusBadge status={health.status} />
                </div>
              </div>
              <div className="bg-white rounded-lg shadow p-6">
                <div className="text-sm text-gray-500 mb-1">Messages Processed</div>
                <div className="text-3xl font-bold text-gray-900">{agent.messages_processed}</div>
              </div>
              <div className="bg-white rounded-lg shadow p-6">
                <div className="text-sm text-gray-500 mb-1">Uptime</div>
                <div className="text-3xl font-bold text-gray-900">{formatUptime(agent.uptime_seconds)}</div>
              </div>
              <div className="bg-white rounded-lg shadow p-6">
                <div className="text-sm text-gray-500 mb-1">Provider</div>
                <div className="text-lg font-semibold text-gray-900">{agent.provider}</div>
                <div className="text-sm text-gray-500">{agent.model}</div>
              </div>
            </div>

            {/* Quick Actions */}
            <div className="bg-white rounded-lg shadow p-6">
              <h3 className="text-lg font-semibold mb-4">Quick Actions</h3>
              <div className="flex gap-4">
                <Button>Start Agent</Button>
                <Button variant="outline">Stop Agent</Button>
                <Button variant="outline">View Logs</Button>
              </div>
            </div>

            {/* Recent Activity */}
            <div className="bg-white rounded-lg shadow p-6">
              <h3 className="text-lg font-semibold mb-4">Recent Activity</h3>
              <div className="space-y-3">
                <div className="flex items-center justify-between py-3 border-b border-gray-100">
                  <div>
                    <div className="font-medium text-gray-700">Agent started</div>
                    <div className="text-sm text-gray-500">Telegram channel connected</div>
                  </div>
                  <div className="text-sm text-gray-500">1 hour ago</div>
                </div>
                <div className="flex items-center justify-between py-3 border-b border-gray-100">
                  <div>
                    <div className="font-medium text-gray-700">Health check passed</div>
                    <div className="text-sm text-gray-500">All systems operational</div>
                  </div>
                  <div className="text-sm text-gray-500">30 min ago</div>
                </div>
                <div className="flex items-center justify-between py-3">
                  <div>
                    <div className="font-medium text-gray-700">Configuration updated</div>
                    <div className="text-sm text-gray-500">Model changed to claude-sonnet-4</div>
                  </div>
                  <div className="text-sm text-gray-500">2 hours ago</div>
                </div>
              </div>
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
                    Last checked: {new Date(health.timestamp).toLocaleTimeString()}
                  </span>
                  <Button size="sm" variant="outline" onClick={refreshHealth}>
                    <RefreshCw className="h-4 w-4" />
                  </Button>
                </div>
              </div>

              <div className="space-y-4">
                {health.checks.map((check, i) => (
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
            </div>

            {/* Health History */}
            <div className="bg-white rounded-lg shadow p-6">
              <h3 className="text-lg font-semibold mb-4">Health History</h3>
              <p className="text-gray-500 text-center py-8">
                Health history will be displayed here once monitoring is enabled.
              </p>
            </div>
          </div>
        )}

        {/* Agents Tab */}
        {activeTab === 'agents' && (
          <div className="bg-white rounded-lg shadow p-6">
            <h3 className="text-lg font-semibold mb-4">Active Agents</h3>
            <div className="flex items-center justify-between p-4 bg-gray-50 rounded-lg mb-4">
              <div className="flex items-center gap-4">
                <div className="w-3 h-3 rounded-full bg-green-500"></div>
                <div>
                  <div className="font-medium">Main Agent</div>
                  <div className="text-sm text-gray-500">{agent.provider} / {agent.model}</div>
                </div>
              </div>
              <div className="flex items-center gap-2">
                <Button size="sm" variant="outline">Configure</Button>
                <Button size="sm" variant="outline">Stop</Button>
              </div>
            </div>
            <Button className="w-full">Start New Agent</Button>
          </div>
        )}

        {/* Console Tab */}
        {activeTab === 'console' && (
          <div className="bg-gray-900 rounded-lg shadow p-6">
            <h3 className="text-lg font-semibold mb-4 text-gray-100">Agent Console</h3>
            <div className="bg-gray-800 rounded p-4 h-64 overflow-y-auto font-mono text-sm text-gray-300">
              <div className="text-green-400">[INFO] Agent started</div>
              <div>[2026-02-10 21:00:00] Connected to OpenRouter</div>
              <div>[2026-02-10 21:00:01] Loading identity from ~/.clawlet/</div>
              <div>[2026-02-10 21:00:02] Initializing Telegram channel...</div>
              <div className="text-green-400">[2026-02-10 21:00:03] Ready to receive messages</div>
              <div className="text-yellow-400">[2026-02-10 21:05:00] Processing message from user_123</div>
              <div>[2026-02-10 21:05:01] Response sent (245ms)</div>
            </div>
            <div className="mt-4 flex gap-2">
              <input
                type="text"
                placeholder="Type a command..."
                className="flex-1 bg-gray-800 text-gray-100 rounded px-4 py-2 font-mono text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
              <Button>Send</Button>
            </div>
          </div>
        )}

        {/* Settings Tab */}
        {activeTab === 'settings' && (
          <div className="bg-white rounded-lg shadow p-6">
            <h3 className="text-lg font-semibold mb-4">Settings</h3>
            <div className="space-y-6">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Workspace Directory
                </label>
                <input
                  type="text"
                  className="w-full px-3 py-2 border border-gray-300 rounded-md"
                  defaultValue="~/.clawlet"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  LLM Provider
                </label>
                <select className="w-full px-3 py-2 border border-gray-300 rounded-md">
                  <option>OpenRouter</option>
                  <option>Ollama</option>
                  <option>LM Studio</option>
                </select>
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Model
                </label>
                {loadingModels ? (
                  <div className="w-full px-3 py-2 border border-gray-300 rounded-md text-gray-500">
                    Loading models...
                  </div>
                ) : (
                  <>
                    <select
                      className="w-full px-3 py-2 border border-gray-300 rounded-md"
                      value={selectedModel}
                      onChange={(e) => setSelectedModel(e.target.value)}
                    >
                      <option value="">Select a model</option>
                      {models.map((model) => (
                        <option key={model.id} value={model.id}>
                          {model.id}
                        </option>
                      ))}
                    </select>
                    <div className="mt-2 flex gap-2">
                      <button
                        type="button"
                        onClick={() => fetchModels(true)}
                        className="text-sm text-blue-600 hover:text-blue-800 flex items-center gap-1"
                      >
                        <RefreshCw className="h-3 w-3" />
                        Refresh models
                      </button>
                      {cacheInfo && (
                        <span className="text-xs text-gray-500">
                          {cacheInfo.model_count} models • Updated: {cacheInfo.updated_at ? new Date(cacheInfo.updated_at).toLocaleDateString() : 'Never'}
                        </span>
                      )}
                    </div>
                  </>
                )}
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Max Iterations
                </label>
                <input
                  type="number"
                  className="w-full px-3 py-2 border border-gray-300 rounded-md"
                  defaultValue="10"
                />
              </div>
              <div className="pt-4 border-t">
                <Button>Save Changes</Button>
              </div>
            </div>
          </div>
        )}
      </main>

      {/* Footer */}
      <footer className="border-t border-gray-200 py-4 mt-8">
        <div className="max-w-7xl mx-auto px-6 text-center text-sm text-gray-500">
          Clawlet v0.1.0 • 
          <a href="https://github.com/Kxrbx/Clawlet" className="text-blue-600 hover:underline ml-1">
            GitHub
          </a>
        </div>
      </footer>
    </div>
  )
}
