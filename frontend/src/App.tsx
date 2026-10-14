import './App.css'
import { useCallback, useEffect, useRef, useState } from 'react'
import axios from 'axios'
import Summary from './components/Summary'
import Retrieval from './components/Retrieval'
import Authorization from './components/Authorization'
import Trace from './components/Trace'
import Evaluation from './components/Evaluation'
import AgentBuilder from './components/AgentBuilder'
import AgentRunner from './components/AgentRunner'
import AgentChat from './components/AgentChat'
import CapabilityManager from './components/CapabilityManager'
import JobHistory from './components/JobHistory'
import AgentEvaluationLab from './components/AgentEvaluationLab'
import ProviderSettings, { type ProviderStatusSummary } from './components/ProviderSettings'
import CognitionSettings, { readCognitiveMode, type CognitiveMode } from './components/CognitionSettings'
import { DecisionInspector } from './features/decision-inspector'

interface Artifacts {
  summary: any
  agent_run: any
  receipts: any
  trace: any
  evaluation: any
}

type AppView = 'chat' | 'capabilities' | 'provider_settings' | 'inspector' | 'builder' | 'runner' | 'control' | 'jobs' | 'summary' | 'retrieval' | 'authorization' | 'trace' | 'evaluation' | 'evaluation_lab'
type DataView = Extract<AppView, 'inspector' | 'jobs' | 'summary' | 'retrieval' | 'authorization' | 'trace' | 'evaluation'>
type InteractionView = Exclude<AppView, DataView | 'provider_settings'>
type AssistantView = 'inspector' | 'builder' | 'chat' | 'runner' | 'control' | 'jobs' | 'traces' | 'summary' | 'retrieval' | 'authorization' | 'evaluation' | 'evaluation_lab' | 'provider_settings' | 'capabilities'

const navigation: Array<{ id: AppView; label: string; layer: 'interaction' | 'data' }> = [
  { id: 'chat', label: 'Chat', layer: 'interaction' },
  { id: 'capabilities', label: 'Capabilities', layer: 'interaction' },
  { id: 'builder', label: 'Agent Builder', layer: 'interaction' },
  { id: 'runner', label: 'Agent Runs', layer: 'interaction' },
  { id: 'evaluation_lab', label: 'Agent Evaluation Lab', layer: 'interaction' },
  { id: 'inspector', label: 'Decision Inspector', layer: 'data' },
  { id: 'jobs', label: 'Job History', layer: 'data' },
  { id: 'summary', label: 'Summary', layer: 'data' },
  { id: 'retrieval', label: 'Retrieval & Ontology', layer: 'data' },
  { id: 'authorization', label: 'Authorization', layer: 'data' },
  { id: 'trace', label: 'Trace', layer: 'data' },
  { id: 'evaluation', label: 'Evaluation', layer: 'data' },
]

const interactionNavigation = navigation.filter((item) => item.layer === 'interaction')
const dataNavigation = navigation.filter((item) => item.layer === 'data')
const interactionIcons: Record<InteractionView, string> = {
  chat: '◌',
  capabilities: '◇',
  builder: '⊞',
  runner: '▷',
  evaluation_lab: '▦',
  control: '⌘',
}

function isDataView(view: AppView): view is DataView {
  return dataNavigation.some((item) => item.id === view)
}

function useScrollActivity() {
  const [scrolling, setScrolling] = useState(false)
  const idleTimer = useRef<number | null>(null)

  const onScroll = useCallback(() => {
    setScrolling(true)
    if (idleTimer.current !== null) window.clearTimeout(idleTimer.current)
    idleTimer.current = window.setTimeout(() => {
      idleTimer.current = null
      setScrolling(false)
    }, 700)
  }, [])

  useEffect(() => () => {
    if (idleTimer.current !== null) window.clearTimeout(idleTimer.current)
  }, [])

  return { scrolling, onScroll }
}

function App() {
  const [artifacts, setArtifacts] = useState<Artifacts | null>(null)
  const [loadingArtifacts, setLoadingArtifacts] = useState(true)
  const [artifactError, setArtifactError] = useState<string | null>(null)
  const [activeInteractionView, setActiveInteractionView] = useState<InteractionView>('chat')
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false)
  const [activeDataView, setActiveDataView] = useState<DataView>('inspector')
  const [dataLayerOpen, setDataLayerOpen] = useState(false)
  const [settingsOpen, setSettingsOpen] = useState(false)
  const [settingsSection, setSettingsSection] = useState<'provider' | 'cognition'>('provider')
  const [providerNavStatus, setProviderNavStatus] = useState<ProviderStatusSummary | null>(null)
  const [cognitiveMode, setCognitiveMode] = useState<CognitiveMode>(readCognitiveMode)
  const [demoRefresh, setDemoRefresh] = useState(0)
  const dataLayerRef = useRef<HTMLDialogElement>(null)
  const settingsDialogRef = useRef<HTMLDialogElement>(null)
  const appScroll = useScrollActivity()
  const settingsScroll = useScrollActivity()
  const dataScroll = useScrollActivity()

  useEffect(() => {
    if (!settingsOpen) return
    const controller = new AbortController()
    void fetch('/api/providers/ollama/status', { signal: controller.signal }).then(async (response) => {
      if (!response.ok) return
      setProviderNavStatus(await response.json() as ProviderStatusSummary)
    }).catch(() => { /* Retain the last known provider summary if the status endpoint is unavailable. */ })
    return () => controller.abort()
  }, [settingsOpen])

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

  const navigateFromChat = useCallback((view: AssistantView) => {
    const tab: AppView = view === 'traces' ? 'trace' : view === 'control' ? 'runner' : view
    if (isDataView(tab)) {
      setActiveDataView(tab)
      setDataLayerOpen(true)
    } else if (tab === 'provider_settings') {
      setSettingsSection('provider')
      setSettingsOpen(true)
    } else {
      setActiveInteractionView(tab)
    }
  }, [])

  const openSettings = useCallback(() => setSettingsOpen(true), [])
  const openProviderSettings = useCallback(() => { setSettingsSection('provider'); setSettingsOpen(true) }, [])
  const openCognitionSettings = useCallback(() => { setSettingsSection('cognition'); setSettingsOpen(true) }, [])
  const openInspect = useCallback(() => setDataLayerOpen(true), [])

  useEffect(() => {
    const dialog = dataLayerRef.current
    if (!dialog) return

    if (dataLayerOpen && !dialog.open) dialog.showModal()
    if (!dataLayerOpen && dialog.open) dialog.close()
  }, [dataLayerOpen])

  useEffect(() => {
    const dialog = settingsDialogRef.current
    if (!dialog) return

    if (settingsOpen && !dialog.open) dialog.showModal()
    if (!settingsOpen && dialog.open) dialog.close()
  }, [settingsOpen])

  const activeInteractionLabel = interactionNavigation.find((item) => item.id === activeInteractionView)?.label ?? 'Workspace'

  return (
    <div className={`app-shell ${activeInteractionView === 'chat' ? 'app-shell--chat' : ''} ${sidebarCollapsed ? 'app-shell--sidebar-collapsed' : ''}`}>
      <aside id="workspace-sidebar-content" className={`workspace-sidebar ${activeInteractionView === 'chat' ? 'workspace-sidebar--chat' : ''} ${sidebarCollapsed ? 'workspace-sidebar--collapsed' : ''}`} aria-label="Workspace sidebar">
        <div className="workspace-sidebar-brand">
          <img className="workspace-sidebar-logo" src="/brand/BAGO_logotipo_horizontal.svg" alt="BAGO" />
          <img className="workspace-sidebar-symbol" src="/brand/BAGO_simbolo_negativo.svg" alt="" aria-hidden="true" />
        </div>
        <nav className="primary-navigation" aria-label="Interaction layer">
          <div className="navigation-group">
            {interactionNavigation.map((item) => (
              <button
                key={item.id}
                type="button"
                className={`navigation-item ${activeInteractionView === item.id ? 'active' : ''}`}
                aria-label={item.label}
                title={sidebarCollapsed ? item.label : undefined}
                aria-current={activeInteractionView === item.id ? 'page' : undefined}
                onClick={() => setActiveInteractionView(item.id as InteractionView)}
              >
                <span className="navigation-item-icon" aria-hidden="true">{interactionIcons[item.id as InteractionView]}</span>
                <span>{item.label}</span>
              </button>
            ))}
            <button
              type="button"
              className={`navigation-item ${dataLayerOpen ? 'active' : ''}`}
              aria-label="Open Inspect"
              title={sidebarCollapsed ? 'Inspect' : undefined}
              aria-pressed={dataLayerOpen}
              aria-haspopup="dialog"
              aria-controls="data-layer"
              onClick={openInspect}
            >
              <span className="navigation-item-icon" aria-hidden="true">◫</span>
              <span>Inspect</span>
            </button>
          </div>
        </nav>

        <footer className="workspace-sidebar-footer">
          <button
            type="button"
            className="navigation-item settings-trigger"
            aria-label="Open settings"
            title={sidebarCollapsed ? 'Settings' : undefined}
            aria-haspopup="dialog"
            aria-expanded={settingsOpen}
            aria-controls="settings-layer"
            onClick={openSettings}
          >
            <span className="navigation-item-icon" aria-hidden="true">⚙</span>
            <span>Settings</span>
          </button>
          <button
            type="button"
            className="sidebar-collapse-button"
            aria-label={sidebarCollapsed ? 'Expand sidebar' : 'Collapse sidebar'}
            aria-expanded={!sidebarCollapsed}
            aria-controls="workspace-sidebar-content"
            title={sidebarCollapsed ? 'Expand sidebar' : 'Collapse sidebar'}
            onClick={() => setSidebarCollapsed((collapsed) => !collapsed)}
          >
            <span aria-hidden="true">{sidebarCollapsed ? '›' : '‹'}</span>
          </button>
        </footer>
      </aside>

      <div className="app-main">
        <main className={`app-view ${activeInteractionView === 'chat' ? 'app-view--chat' : ''} ${appScroll.scrolling ? 'scroll-active' : ''}`} aria-label={`${activeInteractionLabel} view`} tabIndex={0} onScroll={appScroll.onScroll}>
          {activeInteractionView === 'chat' && <AgentChat onNavigate={navigateFromChat} onOpenProviderSettings={openProviderSettings} onOpenCognitionSettings={openCognitionSettings} cognitiveMode={cognitiveMode} />}
          {activeInteractionView === 'capabilities' && <CapabilityManager />}
          {activeInteractionView === 'builder' && <AgentBuilder onAgentCreated={() => setDemoRefresh((previous) => previous + 1)} />}
          {activeInteractionView === 'runner' && <AgentRunner />}
          {activeInteractionView === 'evaluation_lab' && <AgentEvaluationLab />}
        </main>
      </div>

      <dialog
        ref={settingsDialogRef}
        id="settings-layer"
        className="settings-layer"
        aria-labelledby="settings-layer-title"
        onCancel={() => setSettingsOpen(false)}
        onClose={() => setSettingsOpen(false)}
      >
        <header className="settings-layer-header">
          <div><p className="app-kicker">Preferences</p><h2 id="settings-layer-title">Settings</h2></div>
          <button type="button" className="settings-layer-close" autoFocus onClick={() => setSettingsOpen(false)} aria-label="Close settings">
            <span aria-hidden="true">×</span>
          </button>
        </header>
        <div className="settings-layer-layout">
          <nav className="settings-layer-navigation" aria-label="Settings sections">
            <span className="navigation-caption">Configuration</span>
            <button type="button" className={`navigation-item ${settingsSection === 'provider' ? 'active' : ''}`} aria-current={settingsSection === 'provider' ? 'page' : undefined} onClick={() => setSettingsSection('provider')}>Provider & models</button>
            <button type="button" className={`navigation-item ${settingsSection === 'cognition' ? 'active' : ''}`} aria-current={settingsSection === 'cognition' ? 'page' : undefined} onClick={() => setSettingsSection('cognition')}>Cognition & context</button>
            <div className="settings-provider-summary" aria-live="polite" aria-label={`Auth: ${providerNavStatus?.auth_mode === 'api_key' ? 'API key' : providerNavStatus?.auth_mode === 'local_cli' ? 'Local CLI session' : 'Not selected'}`}>
              <span aria-hidden="true" className={`provider-status-dot ${providerNavStatus?.state ?? 'unknown'}`} />
              <span>Auth: {providerNavStatus?.auth_mode === 'api_key' ? 'API key' : providerNavStatus?.auth_mode === 'local_cli' ? 'Local CLI session' : 'Not selected'}</span>
            </div>
          </nav>
          <section className={`settings-layer-content ${settingsScroll.scrolling ? 'scroll-active' : ''}`} aria-label={settingsSection === 'provider' ? 'Provider and model settings' : 'Cognition and context settings'} tabIndex={0} onScroll={settingsScroll.onScroll}>
            {settingsSection === 'provider' ? <ProviderSettings onStatusChange={setProviderNavStatus} /> : <CognitionSettings mode={cognitiveMode} onModeChange={setCognitiveMode} />}
          </section>
        </div>
      </dialog>

      <dialog
        ref={dataLayerRef}
        id="data-layer"
        className="data-layer"
        aria-labelledby="data-layer-title"
        onCancel={() => setDataLayerOpen(false)}
        onClose={() => setDataLayerOpen(false)}
      >
        <header className="data-layer-header">
          <div className="data-layer-heading">
            <p className="app-kicker">Inspect</p>
            <h2 id="data-layer-title">{dataNavigation.find((item) => item.id === activeDataView)?.label ?? 'Data layer'}</h2>
          </div>
          <button
            type="button"
            className="settings-layer-close"
            aria-label="Back to Workspace"
            title="Back to Workspace"
            autoFocus
            onClick={() => setDataLayerOpen(false)}
          >
            <span aria-hidden="true">×</span>
          </button>
        </header>

        <div className="data-layer-layout">
          <nav className="data-layer-navigation" aria-label="Data views">
            <span className="navigation-caption">Observe</span>
            {dataNavigation.map((item) => (
              <button
                key={item.id}
                type="button"
                className={`navigation-item ${activeDataView === item.id ? 'active' : ''}`}
                aria-current={activeDataView === item.id ? 'page' : undefined}
                onClick={() => setActiveDataView(item.id as DataView)}
              >
                {item.label}
              </button>
            ))}
          </nav>

          <section className={`data-layer-content ${dataScroll.scrolling ? 'scroll-active' : ''}`} aria-label={`${dataNavigation.find((item) => item.id === activeDataView)?.label ?? 'Data'} view`} tabIndex={0} onScroll={dataScroll.onScroll}>
            {activeDataView === 'jobs' ? <JobHistory /> : loadingArtifacts
              ? <div className="app-view-state" role="status"><span className="spinner" /><p>Loading portfolio artifacts…</p></div>
              : artifactError || !artifacts
                ? <section className="artifact-unavailable" role="status"><p className="app-kicker">Portfolio evidence</p><h2>Artifacts are not available yet</h2><p>{artifactError ?? 'No artifact bundle was returned.'}</p><p>No portfolio artifact bundle is available. Directory scan reports are shown in Agent Runs.</p><button type="button" className="navigation-item active" onClick={() => { setDataLayerOpen(false); setActiveInteractionView('runner') }}>Open Agent Runs</button></section>
                : <>
                  {activeDataView === 'inspector' && <DecisionInspector artifacts={artifacts} />}
                  {activeDataView === 'summary' && <Summary data={artifacts} />}
                  {activeDataView === 'retrieval' && <Retrieval data={artifacts} />}
                  {activeDataView === 'authorization' && <Authorization data={artifacts} />}
                  {activeDataView === 'trace' && <Trace data={artifacts} />}
                  {activeDataView === 'evaluation' && <Evaluation data={artifacts} />}
                </>}
          </section>
        </div>
      </dialog>
    </div>
  )
}

export default App
