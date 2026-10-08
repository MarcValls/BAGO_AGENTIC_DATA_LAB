import { useEffect, useState } from 'react'
import axios from 'axios'
import Summary from './components/Summary'
import Retrieval from './components/Retrieval'
import Authorization from './components/Authorization'
import Trace from './components/Trace'
import Evaluation from './components/Evaluation'
import Control from './components/Control'
import AgentBuilder from './components/AgentBuilder'
import AgentRunner from './components/AgentRunner'
import AgentChat from './components/AgentChat'
import JobHistory from './components/JobHistory'
import './App.css'

interface Artifacts {
  summary: any
  agent_run: any
  receipts: any
  trace: any
  evaluation: any
}

function App() {
  const [artifacts, setArtifacts] = useState<Artifacts | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [activeTab, setActiveTab] = useState('summary')
  const [demoRefresh, setDemoRefresh] = useState(0)

  useEffect(() => {
    const fetchArtifacts = async () => {
      try {
        const response = await axios.get('/api/artifacts')
        setArtifacts(response.data)
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Failed to load artifacts')
      } finally {
        setLoading(false)
      }
    }

    fetchArtifacts()
  }, [demoRefresh])

  const handleDemoRun = () => {
    setDemoRefresh((prev) => prev + 1)
    setActiveTab('summary')
  }

  if (loading) {
    return (
      <div className="container">
        <div style={{ textAlign: 'center', padding: '40px' }}>
          <div className="spinner"></div>
          <p>Loading artifacts...</p>
        </div>
      </div>
    )
  }

  if (error) {
    return (
      <div className="container">
        <div className="card" style={{ borderColor: '#ef4444' }}>
          <h2>Error</h2>
          <p>{error}</p>
          <p style={{ fontSize: '0.9em', color: 'rgba(255, 255, 255, 0.6)' }}>
            Make sure to run <code>python demo.py</code> first to generate the demo artifacts.
          </p>
        </div>
      </div>
    )
  }

  if (!artifacts) {
    return <div>No data</div>
  }

  return (
    <div className="container">
      <div className="header">
        <div>
          <h1>🧪 BAGO Portfolio</h1>
          <p style={{ margin: '4px 0 0 0', fontSize: '0.95em', color: 'rgba(255, 255, 255, 0.6)' }}>
            Governed Knowledge Agent Demo
          </p>
        </div>
        <div style={{ textAlign: 'right' }}>
          <span className={`badge ${artifacts.summary.status === 'PASS' ? 'success' : 'error'}`}>
            {artifacts.summary.status}
          </span>
        </div>
      </div>

      <div className="tabs">
        <button
          className={`tab ${activeTab === 'builder' ? 'active' : ''}`}
          onClick={() => setActiveTab('builder')}
        >
          🤖 Agent Builder
        </button>
        <button
          className={`tab ${activeTab === 'chat' ? 'active' : ''}`}
          onClick={() => setActiveTab('chat')}
        >
          💬 Agent Chat
        </button>
        <button
          className={`tab ${activeTab === 'runner' ? 'active' : ''}`}
          onClick={() => setActiveTab('runner')}
        >
          🎯 Agent Runner
        </button>
        <button
          className={`tab ${activeTab === 'control' ? 'active' : ''}`}
          onClick={() => setActiveTab('control')}
        >
          🚀 Control
        </button>
        <button
          className={`tab ${activeTab === 'jobs' ? 'active' : ''}`}
          onClick={() => setActiveTab('jobs')}
        >
          📊 Job History
        </button>
        <button
          className={`tab ${activeTab === 'summary' ? 'active' : ''}`}
          onClick={() => setActiveTab('summary')}
        >
          Summary
        </button>
        <button
          className={`tab ${activeTab === 'retrieval' ? 'active' : ''}`}
          onClick={() => setActiveTab('retrieval')}
        >
          Retrieval & Ontology
        </button>
        <button
          className={`tab ${activeTab === 'authorization' ? 'active' : ''}`}
          onClick={() => setActiveTab('authorization')}
        >
          Authorization
        </button>
        <button
          className={`tab ${activeTab === 'trace' ? 'active' : ''}`}
          onClick={() => setActiveTab('trace')}
        >
          Trace
        </button>
        <button
          className={`tab ${activeTab === 'evaluation' ? 'active' : ''}`}
          onClick={() => setActiveTab('evaluation')}
        >
          Evaluation
        </button>
      </div>

      {activeTab === 'builder' && <AgentBuilder onAgentCreated={handleDemoRun} />}
      {activeTab === 'chat' && <AgentChat />}
      {activeTab === 'runner' && <AgentRunner />}
      {activeTab === 'control' && <Control onDemoRun={handleDemoRun} />}
      {activeTab === 'jobs' && <JobHistory />}
      {activeTab === 'summary' && <Summary data={artifacts} />}
      {activeTab === 'retrieval' && <Retrieval data={artifacts} />}
      {activeTab === 'authorization' && <Authorization data={artifacts} />}
      {activeTab === 'trace' && <Trace data={artifacts} />}
      {activeTab === 'evaluation' && <Evaluation data={artifacts} />}
    </div>
  )
}

export default App
