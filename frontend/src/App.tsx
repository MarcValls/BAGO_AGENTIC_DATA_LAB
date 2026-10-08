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
import { DecisionInspector } from './features/decision-inspector'
import './App.css'

interface Artifacts {
  summary: any
  agent_run: any
  receipts: any
  trace: any
  evaluation: any
}

const portfolioViews = [
  { id: 'builder', label: 'Agent Builder' },
  { id: 'chat', label: 'Agent Chat' },
  { id: 'runner', label: 'Agent Runner' },
  { id: 'control', label: 'Control' },
  { id: 'jobs', label: 'Job History' },
  { id: 'summary', label: 'Summary' },
  { id: 'retrieval', label: 'Retrieval & Ontology' },
  { id: 'authorization', label: 'Authorization' },
  { id: 'trace', label: 'Trace' },
  { id: 'evaluation', label: 'Evaluation' },
]

function App() {
  const [artifacts, setArtifacts] = useState<Artifacts | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [activeTab, setActiveTab] = useState('inspector')
  const [demoRefresh, setDemoRefresh] = useState(0)

  useEffect(() => {
    const fetchArtifacts = async () => {
      try {
        const response = await axios.get('/api/artifacts')
        setArtifacts(response.data)
        setError(null)
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Failed to load artifacts')
      } finally {
        setLoading(false)
      }
    }
    fetchArtifacts()
  }, [demoRefresh])

  const handleDemoRun = () => {
    setDemoRefresh((previous) => previous + 1)
    setActiveTab('inspector')
  }

  if (loading) return <main className="container app-state"><div className="spinner" role="status" /><p>Loading run artifacts…</p></main>
  if (error) return <main className="container app-state"><section className="card" role="alert"><h1>Run artifacts unavailable</h1><p>{error}</p><p>Run <code>python demo.py</code> to create a governed demo artifact bundle.</p></section></main>
  if (!artifacts) return <main className="container app-state"><p role="status">No run data was provided.</p></main>

  return (
    <main className="container">
      <header className="header">
        <div><p className="app-kicker">BAGO · Governed Knowledge Agent</p><h1>Agentic Data Lab</h1></div>
        <span className={`badge ${artifacts.summary.status === 'PASS' ? 'success' : 'error'}`}>{artifacts.summary.status}</span>
      </header>

      <button className="inspector-home" type="button" aria-current={activeTab === 'inspector' ? 'page' : undefined} onClick={() => setActiveTab('inspector')}>Decision Inspector</button>

      {activeTab === 'inspector' && <DecisionInspector artifacts={artifacts} />}

      <details className="portfolio-views">
        <summary>Other portfolio views</summary>
        <nav className="tabs" aria-label="Other portfolio views">
          {portfolioViews.map((view) => <button key={view.id} className={`tab ${activeTab === view.id ? 'active' : ''}`} onClick={() => setActiveTab(view.id)}>{view.label}</button>)}
        </nav>
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
      </details>
    </main>
  )
}

export default App
