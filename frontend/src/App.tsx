import { useCallback, useEffect, useState } from 'react'
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
import CapabilityManager from './components/CapabilityManager'
import JobHistory from './components/JobHistory'
import ProviderSettings from './components/ProviderSettings'
import { DecisionInspector } from './features/decision-inspector'
import './App.css'

interface Artifacts {
  summary: any
  agent_run: any
  receipts: any
  trace: any
  evaluation: any
}

type AppView = 'chat' | 'capabilities' | 'provider_settings' | 'inspector' | 'builder' | 'runner' | 'control' | 'jobs' | 'summary' | 'retrieval' | 'authorization' | 'trace' | 'evaluation'
type AssistantView = 'inspector' | 'builder' | 'chat' | 'runner' | 'control' | 'jobs' | 'traces' | 'summary' | 'retrieval' | 'authorization' | 'evaluation' | 'provider_settings' | 'capabilities'

const navigation: Array<{ id: AppView; label: string; group: 'workspace' | 'portfolio' | 'settings' }> = [
  { id: 'chat', label: 'Chat', group: 'workspace' },
  { id: 'capabilities', label: 'Capabilities', group: 'workspace' },
  { id: 'inspector', label: 'Decision Inspector', group: 'workspace' },
  { id: 'builder', label: 'Agent Builder', group: 'workspace' },
  { id: 'runner', label: 'Agent Runner', group: 'workspace' },
  { id: 'control', label: 'Control', group: 'portfolio' },
  { id: 'jobs', label: 'Job History', group: 'portfolio' },
  { id: 'summary', label: 'Summary', group: 'portfolio' },
  { id: 'retrieval', label: 'Retrieval & Ontology', group: 'portfolio' },
  { id: 'authorization', label: 'Authorization', group: 'portfolio' },
  { id: 'trace', label: 'Trace', group: 'portfolio' },
  { id: 'evaluation', label: 'Evaluation', group: 'portfolio' },
  { id: 'provider_settings', label: 'Provider Settings', group: 'settings' },
]

function App() {
  const [artifacts, setArtifacts] = useState<Artifacts | null>(null)
  const [loadingArtifacts, setLoadingArtifacts] = useState(true)
  const [artifactError, setArtifactError] = useState<string | null>(null)
  const [activeTab, setActiveTab] = useState<AppView>('chat')
  const [demoRefresh, setDemoRefresh] = useState(0)

  useEffect(() => {
    const fetchArtifacts = async () => {
      try {
        const response = await axios.get('/api/artifacts')
        setArtifacts(response.data)
        setArtifactError(null)
      } catch (error) {
        setArtifactError(error instanceof Error ? error.message : 'Run artifacts are unavailable.')
      } finally {
        setLoadingArtifacts(false)
      }
    }
    void fetchArtifacts()
  }, [demoRefresh])

  const handleDemoRun = useCallback(() => {
    setDemoRefresh((previous) => previous + 1)
    setActiveTab('inspector')
  }, [])

  const navigateFromChat = useCallback((view: AssistantView) => {
    const tab: AppView = view === 'traces' ? 'trace' : view
    setActiveTab(tab)
  }, [])

  const needsArtifacts = ['inspector', 'summary', 'retrieval', 'authorization', 'trace', 'evaluation'].includes(activeTab)

  return (
    <main className="container app-shell">
      <header className="app-header">
        <div className="brand-lockup"><span className="brand-symbol" aria-hidden="true">B</span><div><p className="app-kicker">Governed Knowledge Workspace</p><h1>Agentic Data Lab</h1></div></div>
        <div className="app-header-actions"><span className="workspace-label">Control plane</span><button type="button" className="header-provider-link" onClick={() => setActiveTab('provider_settings')}>Provider settings</button></div>
      </header>

      <nav className="primary-navigation" aria-label="Application views">
        <div className="navigation-group" aria-label="Workspace">
          {navigation.filter((item) => item.group === 'workspace').map((item) => <button key={item.id} type="button" className={`navigation-item ${activeTab === item.id ? 'active' : ''}`} aria-current={activeTab === item.id ? 'page' : undefined} onClick={() => setActiveTab(item.id)}>{item.label}</button>)}
        </div>
        <details className="portfolio-navigation">
          <summary>Other portfolio views</summary>
          <div className="portfolio-navigation-content"><span className="navigation-caption">Portfolio</span>{navigation.filter((item) => item.group === 'portfolio').map((item) => <button key={item.id} type="button" className={`navigation-item ${activeTab === item.id ? 'active' : ''}`} aria-current={activeTab === item.id ? 'page' : undefined} onClick={() => setActiveTab(item.id)}>{item.label}</button>)}<span className="navigation-caption settings-caption">Settings</span>{navigation.filter((item) => item.group === 'settings').map((item) => <button key={item.id} type="button" className={`navigation-item ${activeTab === item.id ? 'active' : ''}`} aria-current={activeTab === item.id ? 'page' : undefined} onClick={() => setActiveTab(item.id)}>{item.label}</button>)}</div>
        </details>
      </nav>

      <section className="app-view" aria-label={`${navigation.find((item) => item.id === activeTab)?.label ?? 'Application'} view`}>
        {activeTab === 'chat' && <AgentChat onNavigate={navigateFromChat} onOpenProviderSettings={() => setActiveTab('provider_settings')} />}
        {activeTab === 'capabilities' && <CapabilityManager />}
        {activeTab === 'provider_settings' && <ProviderSettings />}
        {activeTab === 'builder' && <AgentBuilder onAgentCreated={() => setDemoRefresh((previous) => previous + 1)} />}
        {activeTab === 'runner' && <AgentRunner />}
        {activeTab === 'control' && <Control onDemoRun={handleDemoRun} />}
        {activeTab === 'jobs' && <JobHistory />}
        {needsArtifacts && (loadingArtifacts
          ? <div className="app-view-state" role="status"><span className="spinner" /><p>Loading portfolio artifacts…</p></div>
          : artifactError || !artifacts
            ? <section className="artifact-unavailable" role="status"><p className="app-kicker">Portfolio evidence</p><h2>Artifacts are not available yet</h2><p>{artifactError ?? 'No artifact bundle was returned.'}</p><p>Run a governed demo from the Control view to create its artifact bundle.</p><button type="button" className="navigation-item active" onClick={() => setActiveTab('control')}>Open Control</button></section>
            : <>
              {activeTab === 'inspector' && <DecisionInspector artifacts={artifacts} />}
              {activeTab === 'summary' && <Summary data={artifacts} />}
              {activeTab === 'retrieval' && <Retrieval data={artifacts} />}
              {activeTab === 'authorization' && <Authorization data={artifacts} />}
              {activeTab === 'trace' && <Trace data={artifacts} />}
              {activeTab === 'evaluation' && <Evaluation data={artifacts} />}
            </>)}
      </section>
    </main>
  )
}

export default App
