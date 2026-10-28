import {useI18n,t,localMessage,errorMessage,apiError,formatDate,formatNumber} from './i18n'
import './App.css'
import './NavigationOrder.css'
import './components/NavMenu.css'
import LanguageSelector from './i18n/LanguageSelector'
import { useCallback, useEffect, useRef, useState } from 'react'
import axios from 'axios'
import Summary from './components/Summary'
import Retrieval from './components/Retrieval'
import Authorization from './components/Authorization'
import Trace from './components/Trace'
import Evaluation from './components/Evaluation'
import AgentBuilder from './components/AgentBuilder'
import AgentManagement from './components/AgentManagement'
import AgentToolsView from './components/AgentToolsView'
import AgentNavigation, { AGENT_SECTIONS, isAgentSection } from './components/AgentNavigation'
import ChatNavigation, { CHAT_SECTIONS } from './components/ChatNavigation'
import CommunicationsNavigation, {COMMUNICATION_SECTIONS,isCommunicationSection,type CommunicationSection} from './components/CommunicationsNavigation'
import GovernedFixtureRunner from './components/GovernedFixtureRunner'
import AgentTasks from './components/AgentTasks'
import AgentChat, {type PreparedChatPrompt} from './components/AgentChat'
import Communications from './components/Communications'
import type { Contact as CommunicationContact } from './types/communications'
import WhatsAppSettings from './components/WhatsAppSettings'
import WorkspaceManager from './components/WorkspaceManager'
import ChatInspection from './components/ChatInspection'
import type {InspectionSelection} from './types/inspection'
import CapabilityManager, {type CapabilityChatRequest, type CapabilityDestination} from './components/CapabilityManager'
import ToolsConnectionsView from './components/ToolsConnectionsView'
import JobHistory from './components/JobHistory'
import RuntimeStatusBar from './components/RuntimeStatusBar'
import AgentEvaluationLab from './components/AgentEvaluationLab'
import Contacts from './components/Contacts'
import ProviderSettings from './components/ProviderSettings'
import CognitionSettings, { readCognitiveMode, type CognitiveMode } from './components/CognitionSettings'
import { DecisionInspector } from './features/decision-inspector'
import { BerEffectRecordInspector } from './features/ber-effect-inspector/BerEffectRecordInspector'
import './ServiceSurfaces.css'
import './VisualSystem.css'
import './AppOverrides.css'

interface Artifacts {
  summary: any
  agent_run: any
  receipts: any
  trace: any
  evaluation: any
}

type AppView = 'communications' | 'communications_history' | 'contacts' | 'chat' | 'workspace' | 'capabilities' | 'tools' | 'agents' | 'inspector' | 'ber_record' | 'builder' | 'runner' | 'control' | 'jobs' | 'summary' | 'retrieval' | 'authorization' | 'trace' | 'evaluation' | 'evaluation_lab'
type DataView = Extract<AppView, 'inspector' | 'ber_record' | 'jobs' | 'summary' | 'retrieval' | 'authorization' | 'trace' | 'evaluation'>
type InteractionView = Exclude<AppView, DataView>
type AssistantView = 'communications' | 'whatsapp_settings' | 'inspector' | 'builder' | 'chat' | 'workspace' | 'runner' | 'control' | 'jobs' | 'traces' | 'summary' | 'retrieval' | 'authorization' | 'evaluation' | 'evaluation_lab' | 'provider_settings' | 'cognition_settings' | 'capabilities'
type SettingsView = 'cognition' | 'providers' | 'whatsapp' | 'connections'

const navigation: Array<{ id: AppView; label: string; layer: 'interaction' | 'data' }> = [
  { id: 'workspace', get label(){return t("core.App.workspace_87bb59")}, layer: 'interaction' },
  { id: 'chat', get label(){return t("core.App.chat_460b3a")}, layer: 'interaction' },
  ...AGENT_SECTIONS.map(section => ({ id: section.id, get label(){return section.label}, layer: 'interaction' as const })),
  ...COMMUNICATION_SECTIONS.map(section=>({id:section.id,get label(){return section.label},layer:'interaction' as const})),
  { id: 'inspector', get label(){return t("core.App.decision_inspector_2bc4a6")}, layer: 'data' },
  { id: 'ber_record', get label(){return t("core.App.ber_effect_record_76c485")}, layer: 'data' },
  { id: 'jobs', get label(){return t("core.App.job_history_17be0b")}, layer: 'data' },
  { id: 'summary', get label(){return t("core.App.summary_8e76a9")}, layer: 'data' },
  { id: 'retrieval', get label(){return t("core.App.retrieval_ontology_608937")}, layer: 'data' },
  { id: 'authorization', get label(){return t("core.App.authorization_ca5839")}, layer: 'data' },
  { id: 'trace', get label(){return t("core.App.trace_7e14c3")}, layer: 'data' },
  { id: 'evaluation', get label(){return t("core.App.evaluation_163e44")}, layer: 'data' },
]

const interactionNavigation = navigation.filter((item) => item.layer === 'interaction')
const dataNavigation = navigation.filter((item) => item.layer === 'data')
const interactionIcons: Record<InteractionView, string> = {
  communications: '✉',
  communications_history: '◷',
  contacts: '▤',
  chat: '◌',
  workspace: '▣',
  capabilities: '◇',
  tools: '⚙',
  agents: '◈',
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
  const {locale}=useI18n()
  useEffect(()=>{document.documentElement.lang=locale;document.title=t('common.applicationTitle')},[locale])

  const [communicationContact, setCommunicationContact] = useState<CommunicationContact | undefined>()
  const [communicationsSection,setCommunicationsSection]=useState<'message'|'history'>('message')
  const [communicationsDraftId, setCommunicationsDraftId] = useState<string | undefined>()
  const [inspectionSource,setInspectionSource] = useState<'conversation'|'demo'>('conversation')
  const [inspectionSelection,setInspectionSelection] = useState<InspectionSelection|null>(null)
  const [artifacts, setArtifacts] = useState<Artifacts | null>(null)
  const [loadingArtifacts, setLoadingArtifacts] = useState(true)
  const [artifactError, setArtifactError] = useState<any>(null)
  const [activeInteractionView, setActiveInteractionView] = useState<InteractionView>('chat')
  const [preparedChatPrompt,setPreparedChatPrompt] = useState<PreparedChatPrompt|null>(null)
  const preparedPromptSequence=useRef(0)
  const prepareCapabilityChat=useCallback((request:CapabilityChatRequest)=>{setPreparedChatPrompt({id:'capability-prompt-'+(++preparedPromptSequence.current),text:request.prompt,...(request.capabilityId==='workspace.scan_duplicates'?{capabilityId:request.capabilityId}:{})});setActiveInteractionView('chat')},[])
  const consumePreparedPrompt=useCallback((id:string)=>setPreparedChatPrompt(current=>current?.id===id?null:current),[])
  const navigateCapability=useCallback((destination:CapabilityDestination)=>{if(destination==='connections'){setSettingsView('connections');setSettingsOpen(true)}else{setSidebarCollapsed(false);setActiveInteractionView(destination)}},[])
  const [managedAgentId, setManagedAgentId] = useState('')
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false)
  const sidebarToggleRef = useRef<HTMLButtonElement>(null)
  const returnToChatRef = useRef<HTMLButtonElement>(null)
  const sidebarMenuRef = useRef<HTMLDivElement>(null)
  const primaryNavigationFrameRef = useRef<HTMLDivElement>(null)
  const [primaryNavigationMoreDirection, setPrimaryNavigationMoreDirection] = useState<'down' | 'right' | null>(null)
  const [activeDataView, setActiveDataView] = useState<DataView>('inspector')
  const [dataLayerOpen, setDataLayerOpen] = useState(false)
  const [settingsOpen, setSettingsOpen] = useState(false)
  const [settingsView, setSettingsView] = useState<SettingsView>('cognition')
  const [cognitiveMode, setCognitiveMode] = useState<CognitiveMode>(readCognitiveMode)
  const [workspaceRefresh, setWorkspaceRefresh] = useState(0)
  const [demoRefresh, setDemoRefresh] = useState(0)
  const [advancedRunsOpen, setAdvancedRunsOpen] = useState(false)
  const dataLayerRef = useRef<HTMLDialogElement>(null)
  const dataLayerTriggerRef = useRef<HTMLElement|null>(null)
  const settingsDialogRef = useRef<HTMLDialogElement>(null)
  const appScroll = useScrollActivity()
  const settingsScroll = useScrollActivity()
  const dataScroll = useScrollActivity()

  useEffect(() => {
    const navigation = primaryNavigationFrameRef.current?.querySelector<HTMLElement>('.primary-navigation')
    if (!navigation) return

    const updateOverflowCue = () => {
      const horizontal = window.innerWidth <= 760
      const remaining = horizontal
        ? navigation.scrollWidth - navigation.clientWidth - navigation.scrollLeft > 1
        : navigation.scrollHeight - navigation.clientHeight - navigation.scrollTop > 1
      setPrimaryNavigationMoreDirection(remaining ? (horizontal ? 'right' : 'down') : null)
    }

    navigation.addEventListener('scroll', updateOverflowCue, { passive: true })
    window.addEventListener('resize', updateOverflowCue)
    const mutations = new MutationObserver(updateOverflowCue)
    mutations.observe(navigation, { attributes: true, childList: true, subtree: true, attributeFilter: ['hidden', 'aria-expanded', 'class'] })
    const sizes = typeof ResizeObserver === 'undefined' ? null : new ResizeObserver(updateOverflowCue)
    sizes?.observe(navigation)
    const navigationGroup = navigation.firstElementChild
    if (navigationGroup) sizes?.observe(navigationGroup)
    updateOverflowCue()

    return () => {
      navigation.removeEventListener('scroll', updateOverflowCue)
      window.removeEventListener('resize', updateOverflowCue)
      mutations.disconnect()
      sizes?.disconnect()
    }
  }, [])

  useEffect(() => {
    if (inspectionSource !== 'demo') {setArtifacts(null);setLoadingArtifacts(false);setArtifactError(null);return}
    let current = true
    setArtifacts(null);setLoadingArtifacts(true);setArtifactError(null)
    const fetchArtifacts = async () => {
      try {
        const response = await axios.get('/api/artifacts')
        if (current) {
          setArtifacts(response.data)
          setArtifactError(null)
        }
      } catch (error) {
        if (current) setArtifactError(apiError((error as any)?.response?.data??{detail:{message:error instanceof Error?error.message:''}},(error as any)?.response?.status))
      } finally {
        if (current) setLoadingArtifacts(false)
      }
    }
    void fetchArtifacts()
    return () => {current = false}
  }, [demoRefresh, inspectionSource])

  const navigateFromChat = useCallback((view: AssistantView) => {
    if (view === 'whatsapp_settings') { setSettingsView('whatsapp'); setSettingsOpen(true); return }
    if (view === 'provider_settings') {
      setSettingsView('providers')
      setSettingsOpen(true)
      return
    }
    if (view === 'cognition_settings') {
      setSettingsView('cognition')
      setSettingsOpen(true)
      return
    }
    const tab: AppView = view === 'traces' ? 'trace' : view === 'control' ? 'runner' : view
    if (isDataView(tab)) {
      setActiveDataView(tab)
      setDataLayerOpen(true)
    } else {
      if (isAgentSection(tab)) setSidebarCollapsed(false)
      if (tab==='communications') setCommunicationsSection('message')
      setActiveInteractionView(tab)
    }
  }, [])

  const openSettings = useCallback(() => { setSettingsView('cognition'); setSettingsOpen(true) }, [])
  const openProviderSettings = useCallback(() => { setSettingsView('providers'); setSettingsOpen(true) }, [])
  const openCognitionSettings = useCallback(() => { setSettingsView('cognition'); setSettingsOpen(true) }, [])
  const openInspect = useCallback(() => {setInspectionSource('conversation');setActiveDataView('inspector');setDataLayerOpen(true)}, [])
  const selectInspection = useCallback((selection: InspectionSelection|null) => {setInspectionSelection(selection);setInspectionSource('conversation')}, [])
  const inspectExecution = useCallback((selection: InspectionSelection) => {setInspectionSelection(selection);setInspectionSource('conversation');setActiveDataView('inspector');setDataLayerOpen(true)}, [])

  useEffect(() => {
    const dialog = dataLayerRef.current
    if (!dialog) return

    if (dataLayerOpen && !dialog.open) {
      const trigger=document.activeElement
      dataLayerTriggerRef.current=trigger instanceof HTMLElement&&!dialog.contains(trigger)?trigger:null
      dialog.showModal()
    }
    if (!dataLayerOpen && dialog.open) dialog.close()
  }, [dataLayerOpen])

  useEffect(() => {
    const dialog = settingsDialogRef.current
    if (!dialog) return

    if (settingsOpen && !dialog.open) dialog.showModal()
    if (!settingsOpen && dialog.open) dialog.close()
  }, [settingsOpen])

  const navigateCommunications=(view:CommunicationSection)=>{
    if(view!=='contacts')setCommunicationsSection(view==='communications_history'?'history':'message')
    setActiveInteractionView(view)
  }

  const returnToChat = useCallback(() => {
    setActiveInteractionView('chat')
    window.requestAnimationFrame(() => document.querySelector<HTMLTextAreaElement>('.app-view--chat #control-chat-input')?.focus())
  }, [])
  useEffect(() => {
    const handleEscape = (event: KeyboardEvent) => {
      if (event.key !== 'Escape' || event.defaultPrevented || activeInteractionView === 'chat' || document.querySelector('dialog[open], [role="dialog"][aria-modal="true"]')) return
      event.preventDefault()
      event.stopPropagation()
      returnToChat()
    }
    document.addEventListener('keydown', handleEscape, true)
    return () => document.removeEventListener('keydown', handleEscape, true)
  }, [activeInteractionView, returnToChat])

  useEffect(() => {
    if (activeInteractionView === 'chat') return
    returnToChatRef.current?.focus()
  }, [activeInteractionView])

  const activeInteractionLabel = interactionNavigation.find((item) => item.id === activeInteractionView)?.label ?? AGENT_SECTIONS.find(section => section.id === activeInteractionView)?.label ?? CHAT_SECTIONS.find(section => section.id === activeInteractionView)?.label ?? 'Workspace'

  return (
    <div className={`app-shell app-shell--navmenu ${activeInteractionView === 'chat' ? 'app-shell--chat' : ''} ${sidebarCollapsed ? 'app-shell--sidebar-collapsed' : ''}`}>
      <aside className="app-navigation-shell" aria-label={t("core.App.workspace_sidebar_bc2716")}>
        <div className="workspace-sidebar-brand">
        <div className="app-menu-brand">
          <img className="workspace-sidebar-logo" src="/brand/BAGO_logotipo_horizontal.svg" alt="BAGO" width="208" height="53.404" />
        <button ref={sidebarToggleRef} type="button" className="app-menu-toggle"
          aria-label={sidebarCollapsed ? t("core.App.expand_sidebar_37a5d6") : t("core.App.collapse_sidebar_aab31c")}
          aria-expanded={!sidebarCollapsed} aria-controls="workspace-sidebar-content"
          title={sidebarCollapsed ? t("core.App.expand_sidebar_37a5d6") : t("core.App.collapse_sidebar_aab31c")}
          onClick={() => setSidebarCollapsed(current => !current)}
          onKeyDown={event => {
            if (event.key === 'Escape' && !sidebarCollapsed) { event.preventDefault(); setSidebarCollapsed(true) }
            if (event.key === 'ArrowDown') {
              event.preventDefault(); setSidebarCollapsed(false)
              window.requestAnimationFrame(() => sidebarMenuRef.current?.querySelector<HTMLButtonElement>('.primary-navigation button')?.focus())
            }
          }} />
        </div>
        </div>
      <div ref={sidebarMenuRef} onKeyDown={event => {
        if (event.key === 'Escape' && !event.defaultPrevented) { event.preventDefault(); setSidebarCollapsed(true); sidebarToggleRef.current?.focus() }
      }} id="workspace-sidebar-content" className={`workspace-sidebar ${activeInteractionView === 'chat' ? 'workspace-sidebar--chat' : ''} ${sidebarCollapsed ? 'workspace-sidebar--collapsed' : ''}`} aria-label={t("core.App.workspace_sidebar_bc2716")}>
        <div ref={primaryNavigationFrameRef} className="primary-navigation-frame">
          <nav className="primary-navigation" aria-label={t("core.App.interaction_layer_b8f1ed")}>
            <div className="navigation-group">
            {interactionNavigation.filter(item => (!isAgentSection(item.id)||item.id==='agents')&&item.id!=='contacts'&&item.id!=='communications_history').map((item) => item.id==='agents' ? <AgentNavigation key={item.id} activeView={activeInteractionView} collapsed={sidebarCollapsed} onExpandSidebar={() => setSidebarCollapsed(false)} onNavigate={view => setActiveInteractionView(view)} /> : item.id==='chat' ? <ChatNavigation key={item.id} activeView={activeInteractionView} collapsed={sidebarCollapsed} onExpandSidebar={() => setSidebarCollapsed(false)} onNavigate={view => setActiveInteractionView(view)} /> : item.id==='communications' ? <CommunicationsNavigation key={item.id} activeView={activeInteractionView} collapsed={sidebarCollapsed} onExpandSidebar={()=>setSidebarCollapsed(false)} onNavigate={navigateCommunications}/> : (
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
              aria-label={t("core.App.open_inspector_f351c3")}
              title={sidebarCollapsed ? t("core.App.inspector_e0723a") : undefined}
              aria-pressed={dataLayerOpen}
              aria-haspopup="dialog"
              aria-controls="data-layer"
              onClick={openInspect}
            >
              <span className="navigation-item-icon" aria-hidden="true">◫</span>
              <span>{t("core.App.inspector_e0723a")}</span>
            </button>
            <a className="navigation-item" href="/manual" aria-label={t("core.App.manual_b0b9fe")} target="_blank" rel="noreferrer" title={t("core.App.manual_b0b9fe")}><span className="navigation-item-icon" aria-hidden="true">?</span><span>{t("core.App.manual_b0b9fe")}</span></a>
            </div>
          </nav>
          {primaryNavigationMoreDirection && <span className="primary-navigation-more" data-direction={primaryNavigationMoreDirection} aria-hidden="true" />}
        </div>

        <footer className="workspace-sidebar-footer">
          <button
            type="button"
            className="navigation-item settings-trigger"
            aria-label={t("core.App.open_settings_ca381c")}
            title={sidebarCollapsed ? t("core.App.settings_74a883") : undefined}
            aria-haspopup="dialog"
            aria-expanded={settingsOpen}
            aria-controls="settings-layer"
            onClick={openSettings}
          >
            <span className="navigation-item-icon" aria-hidden="true">⚙</span>
            <span>{t("core.App.settings_74a883")}</span>
          </button>
        </footer>
      </div>
      </aside>

      <div className="app-main">
        <main className={`app-view ${activeInteractionView === 'chat' ? 'app-view--chat' : ''} ${appScroll.scrolling ? 'scroll-active' : ''}`} aria-label={t("core.App.p0_view_b10ac6",{p0:String(activeInteractionLabel)})} tabIndex={0} onScroll={appScroll.onScroll}>
          {activeInteractionView !== 'chat' && <header className="app-view-return-bar"><button ref={returnToChatRef} type="button" className="app-view-return-chat" onClick={returnToChat} aria-label={t('core.App.return_to_chat')}><span aria-hidden="true">×</span>{t('core.App.return_to_chat')}</button></header>}
          {<AgentChat hidden={activeInteractionView !== 'chat'} preparedPrompt={preparedChatPrompt} onPreparedPromptHandled={consumePreparedPrompt} historySelection="explicit" workspaceScopeVersion={workspaceRefresh} onInspectionSelection={selectInspection} onInspectExecution={inspectExecution} onOpenCommunication={(id) => { setCommunicationsDraftId(id); setCommunicationsSection('message'); setActiveInteractionView('communications') }} onNavigate={navigateFromChat} onManageAgents={() => { setSidebarCollapsed(false); setActiveInteractionView('agents') }} onOpenProviderSettings={openProviderSettings} onOpenCognitionSettings={openCognitionSettings} cognitiveMode={cognitiveMode} />}
          {isCommunicationSection(activeInteractionView) && <div className="communications-section-host">
            <div className="communications-section-panel" hidden={activeInteractionView==='contacts'}><Communications activeSection={communicationsSection} draftId={communicationsDraftId} initialContact={communicationContact}/></div>
            <div className="communications-section-panel" hidden={activeInteractionView!=='contacts'}><Contacts onUseContact={contact=>{setCommunicationContact({...contact});setCommunicationsSection('message');setActiveInteractionView('communications')}}/></div>
          </div>}
          {activeInteractionView === 'workspace' && <WorkspaceManager refreshKey={workspaceRefresh} onSelected={() => setWorkspaceRefresh(value => value + 1)} contextPanel={({openProjectSelection,refreshKey})=><div className="context-memory-details context-memory-panel"><CognitionSettings key={`${workspaceRefresh}:${refreshKey}`} mode={cognitiveMode} onModeChange={setCognitiveMode} workspaceOnly onRequestWorkspaceSelection={openProjectSelection} /></div>} />}

          {activeInteractionView === 'capabilities' && <CapabilityManager onPrepareChat={prepareCapabilityChat} onNavigate={navigateCapability} />}
          {activeInteractionView === 'agents' && <AgentManagement onCreate={() => setActiveInteractionView('builder')} onTest={id => { setManagedAgentId(id); setActiveInteractionView('runner') }} onEvaluate={id => { setManagedAgentId(id); setActiveInteractionView('evaluation_lab') }} />}
          {activeInteractionView === 'tools' && <AgentToolsView onOpenConnections={() => { setSettingsView('connections'); setSettingsOpen(true) }} onCreateAgent={() => setActiveInteractionView('builder')} />}
          {activeInteractionView === 'builder' && <AgentBuilder onBack={() => setActiveInteractionView('agents')} onAgentCreated={() => setDemoRefresh((previous) => previous + 1)} />}
          {activeInteractionView === 'runner' && <><AgentTasks initialAgentId={managedAgentId} /><details className="agent-tasks-advanced" open={advancedRunsOpen} onToggle={event => setAdvancedRunsOpen(event.currentTarget.open)}><summary>{t("core.App.advanced_governed_demonstration_execution_b685a6")}</summary>{advancedRunsOpen && <GovernedFixtureRunner apiBase={window.location.origin} />}</details></>}
          {activeInteractionView === 'evaluation_lab' && <AgentEvaluationLab initialAgentId={managedAgentId} />}
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
          <div><p className="app-kicker">{t("core.App.preferences_66962f")}</p><h2 id="settings-layer-title">{t("core.App.settings_74a883")}</h2></div>
          <LanguageSelector compact />
          <button type="button" className="settings-layer-close" autoFocus onClick={() => setSettingsOpen(false)} aria-label={t("core.App.close_settings_0ccfef")}>
            <span aria-hidden="true">×</span>
          </button>
        </header>
        <div className="settings-layer-layout">
          <nav className="settings-layer-navigation" aria-label={t("core.App.settings_sections_e26d51")}>
            <span className="navigation-caption">{t("core.App.configure_6defaf")}</span>
            <button type="button" className={`navigation-item ${settingsView === 'cognition' ? 'active' : ''}`} aria-current={settingsView === 'cognition' ? 'page' : undefined} onClick={() => setSettingsView('cognition')}>{t("core.App.cognition_and_context_8fb65b")}</button>
            <button type="button" className={`navigation-item ${settingsView === 'providers' ? 'active' : ''}`} aria-current={settingsView === 'providers' ? 'page' : undefined} onClick={() => setSettingsView('providers')}>{t("core.App.providers_and_models_740468")}</button>
            <button type="button" className={`navigation-item ${settingsView === 'connections' ? 'active' : ''}`} aria-current={settingsView === 'connections' ? 'page' : undefined} onClick={()=>setSettingsView('connections')}>{t('commerce.capability_ui.connections')}</button>
            <button type="button" className={`navigation-item ${settingsView === 'whatsapp' ? 'active' : ''}`} aria-current={settingsView === 'whatsapp' ? 'page' : undefined} onClick={() => setSettingsView('whatsapp')}>WhatsApp</button>
          </nav>
          <section className={`settings-layer-content ${settingsScroll.scrolling ? 'scroll-active' : ''}`} aria-label={settingsView === 'connections' ? t('commerce.capability_ui.connections') : settingsView === 'whatsapp' ? t("core.App.whatsapp_settings_4c4831") : settingsView === 'providers' ? t("core.App.provider_and_model_settings_d104f0") : t("core.App.cognition_and_context_settings_ab7e3e")} tabIndex={0} onScroll={settingsScroll.onScroll}>
            {settingsView === 'connections' ? (settingsOpen ? <ToolsConnectionsView /> : null) : settingsView === 'whatsapp' ? (settingsOpen ? <WhatsAppSettings /> : null) : settingsView === 'providers'
              ? <ProviderSettings />
              : <CognitionSettings mode={cognitiveMode} onModeChange={setCognitiveMode} showWorkspaceLocations />}
          </section>
        </div>
      </dialog>

      <dialog
        ref={dataLayerRef}
        id="data-layer"
        className="data-layer"
        aria-labelledby="data-layer-title"
        onCancel={() => setDataLayerOpen(false)}
        onClose={() => {setDataLayerOpen(false);const trigger=dataLayerTriggerRef.current;dataLayerTriggerRef.current=null;if(trigger?.isConnected)trigger.focus()}}
      >
        <header className="data-layer-header">
          <div className="data-layer-heading">
            {activeDataView === 'ber_record' || activeDataView === 'jobs'
              ? <p role="status">{t("core.App.independent_global_view_not_linked_to_the_500e90")}</p>
              : <div className="inspection-source-switch" role="group" aria-label={t("core.App.inspection_source_48862b")}><button type="button" aria-pressed={inspectionSource === 'conversation'} onClick={() => setInspectionSource('conversation')}>{t("core.App.current_conversation_cb100e")}</button><button type="button" aria-pressed={inspectionSource === 'demo'} onClick={() => setInspectionSource('demo')}>{t("core.App.historical_demonstration_independent_of_chat_3b2e02")}</button></div>}
            <h2 id="data-layer-title">{dataNavigation.find((item) => item.id === activeDataView)?.label ?? 'Data layer'}</h2>
          </div>

        </header>

        <div className="data-layer-layout">
          <nav className="data-layer-navigation" aria-label={t("core.App.data_views_bd550f")}>
            <div className="data-layer-navigation-items">
            <span className="navigation-caption">{t("core.App.observe_744ea7")}</span>
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
            </div>
            <div className="data-layer-navigation-footer">
              <button type="button" className="navigation-item inspector-exit" autoFocus onClick={()=>setDataLayerOpen(false)}>{t('core.App.exit_inspector')}</button>
            </div>
          </nav>

          <section className={`data-layer-content ${dataScroll.scrolling ? 'scroll-active' : ''}`} aria-label={t("core.App.p0_view_b10ac6",{p0:String(dataNavigation.find((item) => item.id === activeDataView)?.label ?? 'Data')})} tabIndex={0} onScroll={dataScroll.onScroll}>
            {inspectionSource === 'conversation' && activeDataView !== 'ber_record' && activeDataView !== 'jobs' ? <ChatInspection view={activeDataView} selection={inspectionSelection} onSelect={setInspectionSelection} onViewChange={setActiveDataView} embedded /> : activeDataView === 'ber_record' ? <BerEffectRecordInspector /> : activeDataView === 'jobs' ? <JobHistory /> : loadingArtifacts
              ? <div className="app-view-state" role="status"><span className="spinner" /><p>{t("core.App.loading_project_evidence_f1d4b9")}</p></div>
              : artifactError || !artifacts
                ? <section className="artifact-unavailable" role="status"><p className="app-kicker">{t("core.App.project_evidence_f0eaa4")}</p><h2>{t("core.App.artifacts_are_not_available_yet_8ac485")}</h2>{artifactError&&<p>{errorMessage(artifactError)}</p>}<p>{t("core.App.no_evidence_bundle_is_available_directory_scan_4ff75c")}</p><button type="button" className="navigation-item active" onClick={() => { setDataLayerOpen(false); setActiveInteractionView('runner') }}>{t("core.App.open_agent_runs_1bfddc")}</button></section>
                : <>
                  {activeDataView === 'inspector' && <DecisionInspector artifacts={artifacts} embedded />}
                  {activeDataView === 'summary' && <Summary data={artifacts} />}
                  {activeDataView === 'retrieval' && <Retrieval data={artifacts} />}
                  {activeDataView === 'authorization' && <Authorization data={artifacts} />}
                  {activeDataView === 'trace' && <Trace data={artifacts} />}
                  {activeDataView === 'evaluation' && <Evaluation data={artifacts} />}
                </>}
          </section>
        </div>
      </dialog>
      <RuntimeStatusBar />
    </div>
  )
}

export default App
