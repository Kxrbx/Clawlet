import { useState } from 'react'
import { Activity, MessageSquare, Terminal, Heart, Database, Settings, Zap } from 'lucide-react'
import { Button } from './components/ui/button'

export default function App() {
  const [activeTab, setActiveTab] = useState('overview')

  const tabs = [
    { id: 'overview', label: 'Overview', icon: Activity },
    { id: 'agents', label: 'Agents', icon: MessageSquare },
    { id: 'console', label: 'Console', icon: Terminal },
    { id: 'memory', label: 'Memory', icon: Database },
    { id: 'heartbeat', label: 'Heartbeat', icon: Heart },
    { id: 'settings', label: 'Settings', icon: Settings },
  ]

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Header */}
      <header className="bg-white border-b border-gray-200 px-6 py-4">
        <div className="flex items-center justify-between max-w-7xl mx-auto">
          <div className="flex items-center space-x-2">
            <Zap className="h-8 w-8 text-blue-600" />
            <h1 className="text-2xl font-bold text-gray-900">Clawlet</h1>
            <span className="text-sm text-gray-500 ml-2">Lightweight AI Agent Framework</span>
          </div>
          <Button size="sm">Documentation</Button>
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
              className={`px-4 py-2 text-sm font-medium transition-colors ${
                activeTab === tab.id
                  ? 'text-blue-600 border-b-2 border-blue-600'
                  : 'text-gray-500 hover:text-gray-700'
              }`}
            >
              <tab.icon className="h-4 w-4 mr-2 inline" />
              {tab.label}
            </button>
          ))}
        </div>

        {/* Tab Content */}
        {activeTab === 'overview' && (
          <div className="space-y-6">
            <div className="bg-white rounded-lg shadow p-6">
              <h2 className="text-xl font-semibold mb-4">Welcome to Clawlet Dashboard 💕</h2>
              <p className="text-gray-600 mb-6">
                A lightweight AI agent framework with identity awareness.
              </p>
              
              <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                <div className="bg-blue-50 rounded-lg p-4">
                  <div className="text-3xl font-bold text-blue-600">1,784+</div>
                  <div className="text-sm text-gray-600">Lines of code</div>
                </div>
                <div className="bg-green-50 rounded-lg p-4">
                  <div className="text-3xl font-bold text-green-600">26</div>
                  <div className="text-sm text-gray-600">Python files</div>
                </div>
                <div className="bg-purple-50 rounded-lg p-4">
                  <div className="text-3xl font-bold text-purple-600">3</div>
                  <div className="text-sm text-gray-600">Channels</div>
                </div>
              </div>
            </div>

            {/* Recent Activity */}
            <div className="bg-white rounded-lg shadow p-6">
              <h3 className="text-lg font-semibold mb-4">Recent Activity</h3>
              <div className="space-y-3">
                <div className="flex items-center justify-between py-3 border-b border-gray-100">
                  <span className="text-gray-700">Added Discord channel integration</span>
                  <span className="text-sm text-gray-500">2 hours ago</span>
                </div>
                <div className="flex items-center justify-between py-3 border-b border-gray-100">
                  <span className="text-gray-700">Implemented tool calling in agent loop</span>
                  <span className="text-sm text-gray-500">2 hours ago</span>
                </div>
                <div className="flex items-center justify-between py-3">
                  <span className="text-gray-700">Added PostgreSQL storage backend</span>
                  <span className="text-sm text-gray-500">2 hours ago</span>
                </div>
              </div>
            </div>
          </div>
        )}

        {activeTab === 'agents' && (
          <div className="bg-white rounded-lg shadow p-6">
            <h3 className="text-lg font-semibold mb-4">Active Agents</h3>
            <p className="text-gray-500 text-center py-12">No agents running yet</p>
            <Button className="w-full">Start Agent</Button>
          </div>
        )}

        {activeTab === 'console' && (
          <div className="bg-gray-900 rounded-lg shadow p-6">
            <h3 className="text-lg font-semibold mb-4 text-gray-100">Agent Console</h3>
            <pre className="bg-gray-800 rounded p-4 text-sm text-gray-300 font-mono">
              <code>$ clawlet agent --channel telegram</code>
            </pre>
            <p className="text-gray-400 text-sm mt-4">
              Start an agent from the command line or use the buttons below.
            </p>
          </div>
        )}

        {activeTab === 'settings' && (
          <div className="bg-white rounded-lg shadow p-6">
            <h3 className="text-lg font-semibold mb-4">Settings</h3>
            <div className="space-y-4">
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
            </div>
          </div>
        )}
      </main>
    </div>
  )
}
