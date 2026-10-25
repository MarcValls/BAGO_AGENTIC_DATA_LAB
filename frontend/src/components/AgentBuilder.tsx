import {presentAgentError} from './AgentTaskForm'
import {agentStateLabel} from './AgentTaskForm'
import {AgentPresentationError} from './AgentTaskForm'
import {useI18n, getLocale, t, formatDate, formatNumber, apiError, errorMessage} from '../i18n'
import './AgentBuilder.css'
import { useCallback, useEffect, useState } from 'react'
import AgentTaskForm, { taskError, type TaskDefinition } from './AgentTaskForm'

export interface AgentConfig {
  name: string
  description: string
  task_scope?: string
  type: 'rag' | 'tool' | 'multi-agent'
  system_prompt: string
  provider_id?: 'ollama-cloud' | 'codex' | 'openai-platform' | 'github-copilot' | null
  model_id?: string | null
  tools: string[]
  task?: TaskDefinition | null
  retrieval_config?: {
    mode: 'hybrid' | 'semantic' | 'lexical'
    top_k: number
  } | null
  sandbox_profile?: string
}

interface AgentBuilderProps {
  onAgentCreated?: (agent: AgentConfig) => void
  onBack?: () => void
  initialAgent?: AgentConfig
  agentId?: string
  inline?: boolean
}

type AgentToolOption = {id:string; name:string; name_en?:string; status:string; formats?:Record<string,{available:boolean}>}
type AvailableProvider = { provider_id: NonNullable<AgentConfig['provider_id']>; label?: string; state: string; model_id: string | null; agent_types?: string[] }

export default function AgentBuilder({ onAgentCreated, onBack, initialAgent, agentId, inline = false }: AgentBuilderProps) {
  useI18n()
  const english = getLocale() === 'en'
  const [toolOptions, setToolOptions] = useState<AgentToolOption[]>([])
  const [toolCatalogError, setToolCatalogError] = useState(false)
  const [roleTemplates,setRoleTemplates]=useState<Array<{id:string;config:AgentConfig}>>([])
  useEffect(()=>{
    const controller=new AbortController()
    void fetch('/api/agent-tools/templates',{signal:controller.signal}).then(async response=>{
      if(!response.ok)return
      const value=await response.json()
      if(!controller.signal.aborted&&Array.isArray(value.templates))setRoleTemplates(value.templates.filter(item=>item.config?.type==='tool'&&Array.isArray(item.config.tools)))
    }).catch(()=>{})
    return()=>controller.abort()
  },[])
  useEffect(() => {
    const controller = new AbortController()
    void fetch('/api/capabilities', {signal:controller.signal}).then(async response => {
      if (!response.ok) throw new Error('catalog_unavailable')
      const value = await response.json()
      if (!Array.isArray(value.agent_tools) || value.agent_tools.some((item:AgentToolOption) => typeof item.id !== 'string' || typeof item.name !== 'string')) throw new Error('catalog_invalid')
      if (!controller.signal.aborted) {setToolOptions(value.agent_tools);setToolCatalogError(false)}
    }).catch(() => {if (!controller.signal.aborted) setToolCatalogError(true)})
    return () => controller.abort()
  }, [])
  const toolLabel = (item:AgentToolOption) => english ? item.name_en || item.name : item.name
  const editing = Boolean(agentId)
  const [step, setStep] = useState<'configure' | 'preview' | 'complete'>('configure')
  const [agent, setAgent] = useState<AgentConfig>(initialAgent ? { ...initialAgent, task: initialAgent.task ? { ...initialAgent.task, dates: initialAgent.task.dates.map(date => ({ ...date })) } : { prompt: initialAgent.description, dates: [] } } : {
    name: '',
    description: '',
    task_scope: '',
    type: 'rag',
    system_prompt: '',
    tools: [],
    task: { prompt: '', dates: [] },
  })
  const [createdAgents, setCreatedAgents] = useState<AgentConfig[]>([])
  const [saving, setSaving] = useState(false)
  const [saveStatus, setSaveStatus] = useState<'idle' | 'success' | 'error'>('idle')
  const [saveError, setSaveError] = useState<string | Error>('')
  const [providers, setProviders] = useState<AvailableProvider[]>([])
  const [providersLoading, setProvidersLoading] = useState(true)
  const [providerError, setProviderError] = useState<string | Error>('')
  const loadProviders = useCallback(async (signal?: AbortSignal) => {
    setProvidersLoading(true)
    setProviderError('')
    try {
      const response = await fetch('/api/providers/chat-models', { signal })
      if (!response.ok) throw new AgentPresentationError(() => t('agents.AgentBuilder.no_se_pudo_cargar_el_registro_de_proveedores'))
      const data = await response.json()
      if (!Array.isArray(data?.models)) throw new AgentPresentationError(() => t('agents.AgentBuilder.el_servidor_no_devolvio_los_proveedores_disponibles'))
      if (!signal?.aborted) setProviders(data.models)
    } catch (cause) {
      if (!signal?.aborted) setProviderError(cause instanceof Error ? cause : new AgentPresentationError(() => t('agents.AgentBuilder.no_se_pudieron_cargar_los_proveedores')))
    } finally { if (!signal?.aborted) setProvidersLoading(false) }
  }, [])
  useEffect(() => {
    const controller = new AbortController()
    void loadProviders(controller.signal)
    return () => controller.abort()
  }, [loadProviders])
  const eligibleModels = providers.filter(provider => !provider.agent_types || provider.agent_types.includes(agent.type))
  const selectedProviderId = agent.provider_id || (editing ? '' : eligibleModels[0]?.provider_id || 'ollama-cloud')
  const selectedProvider = eligibleModels.find(provider => provider.provider_id === selectedProviderId && (!agent.model_id || provider.model_id === agent.model_id))
  const selectedModelId = agent.model_id || (editing ? '' : selectedProvider?.model_id || '')
  const providerOptions = eligibleModels.filter((provider, index, items) => items.findIndex(item => item.provider_id === provider.provider_id) === index)

  const updateAgent = (updates: Partial<AgentConfig>) => {
    setAgent((prev) => ({ ...prev, ...updates }))
  }

  const toggleTool = (toolId: string) => {
    setAgent((prev) => ({
      ...prev,
      tools: prev.tools.includes(toolId)
        ? prev.tools.filter((t) => t !== toolId)
        : [...prev.tools, toolId],
    }))
  }

  const saveAgent = async () => {
    if (!agent.name || !agent.description || !agent.task || taskError(agent.task)) {
      setSaveStatus('error')
      setSaveError(new AgentPresentationError(() => !agent.task ? t('agents.AgentBuilder.escribe_una_tarea') : taskError(agent.task)))
      return
    }

    setSaving(true)
    setSaveError('')
    try {
      const response = await fetch(editing ? `/api/agents/${encodeURIComponent(agentId as string)}` : '/api/agents/create', {
        method: editing ? 'PUT' : 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(editing ? agent : { ...agent, provider_id: selectedProviderId, model_id: agent.model_id || selectedProvider?.model_id || null }),
      })

      if (response.ok) {
        const record = await response.json()
        if (!record?.config) throw new AgentPresentationError(() => t('agents.AgentBuilder.el_servidor_no_devolvio_el_perfil_guardado'))
        const saved = record.config as AgentConfig
        setAgent(saved)
        setSaveStatus('success')
        setCreatedAgents((prev) => [...prev, saved])
        setTimeout(() => {
          setStep('complete')
          if (onAgentCreated) onAgentCreated(saved)
        }, 1000)
      } else {
        const body = await response.json().catch(() => null) as { detail?: { message?: string } } | null
        setSaveError(apiError(body,response.status,'agents'))
        setSaveStatus('error')
      }
    } catch (error) {
      setSaveStatus('error')
      setSaveError(error instanceof Error ? error : new AgentPresentationError(() => t('agents.AgentBuilder.the_profile_could_not_be_saved')))
    } finally {
      setSaving(false)
    }
  }

  const reset = () => {
    setStep('configure')
    setAgent({
      name: '',
      description: '',
      type: 'rag',
      system_prompt: '',
      tools: [],
      task: { prompt: '', dates: [] },
    })
    setSaveStatus('idle')
    setSaveError('')
  }

  return (
    <div className={`agent-builder${inline ? ' agent-builder-inline' : ''}`}>
      {(!inline || editing) && <div className="wizard-header">
        <h2>{editing ? t('agents.AgentBuilder.edit_agent') : t('agents.builder.title')}</h2>
      </div>}

      {step === 'configure' && (
        <div className="wizard-step">
          <h3>{editing ? t('agents.AgentBuilder.agent_profile') : t('agents.AgentBuilder.configure_agent')}</h3>
          {roleTemplates.map(template=><button type="button" key={template.id} onClick={()=>updateAgent({...template.config,provider_id:agent.provider_id,model_id:agent.model_id})}>{t('agentTools.useTemplate')}</button>)}

          <div className="form-group">
            <label>{t('agents.AgentBuilder.agent_name')}</label>
            <input
              type="text"
              value={agent.name}
              onChange={(e) => updateAgent({ name: e.target.value })}
              placeholder={t('agents.builder.exampleName')}
              className="form-input"
            />
          </div>

          <div className="form-group">
            <label>{t('agents.AgentBuilder.description')}</label>
            <textarea
              value={agent.description}
              onChange={(e) => updateAgent({ description: e.target.value })}
              placeholder={t('agents.AgentBuilder.what_does_this_agent_do')}
              className="form-textarea"
              rows={3}
            />
          </div>

          <div className="form-group">
            <label htmlFor="agent-task-scope">{english ? 'Tasks BAGO5 may route to this agent automatically' : 'Tareas que BAGO5 puede asignar automáticamente a este agente'}</label>
            <textarea id="agent-task-scope" value={agent.task_scope || ''} onChange={event => updateAgent({ task_scope: event.target.value })}
              placeholder={english ? 'State the work this agent can accept and what it must return to BAGO5.' : 'Indica qué trabajos puede aceptar y cuáles debe devolver a BAGO5.'}
              className="form-textarea" rows={3} maxLength={8000} />
            <small>{english ? 'This scope routes conversational work. It does not authorize workspace, document, development, communication or file effects.' : 'Este alcance enruta tareas conversacionales. No autoriza el espacio de trabajo, documentos, desarrollo, comunicaciones ni efectos en archivos.'}</small>
          </div>

          <div className="form-group">
            <AgentTaskForm value={agent.task || { prompt: agent.description, dates: [] }} onChange={task => updateAgent({ task })} />
          </div>

          <div className="form-group">
            <label htmlFor="agent-type">{t('agents.AgentBuilder.agent_type')}</label>
            <select
              id="agent-type"
              value={agent.type}
              onChange={(e) => updateAgent(editing ? { type: e.target.value as AgentConfig['type'] } : { type: e.target.value as AgentConfig['type'], provider_id: null, model_id: null })}
              className="form-select"
            >
              <option value="rag">{t('agents.AgentBuilder.rag_retrieval_augmented_generation')}</option>
              <option value="tool">{t('agents.AgentBuilder.tool_based_agent')}</option>
              <option value="multi-agent">{t('agents.AgentBuilder.multi_agent_orchestrator')}</option>
            </select>
          </div>

          <div className="form-group">
            <label htmlFor="agent-provider">{t('agents.AgentBuilder.proveedor')}</label>
            {providersLoading && <p role="status">{t('agents.AgentBuilder.cargando_proveedores')}</p>}
            {providerError && <div role="alert"><p>{typeof providerError === 'string' ? providerError : presentAgentError(providerError)}</p><button type="button" className="btn btn-secondary" onClick={() => void loadProviders()}>{t('agents.AgentBuilder.reintentar')}</button></div>}
            <select id="agent-provider" value={selectedProviderId} disabled={providersLoading || Boolean(providerError)} className="form-select" onChange={event => {
              const next = eligibleModels.find(provider => provider.provider_id === event.target.value)
              if (next) updateAgent({ provider_id: next.provider_id, model_id: next.model_id })
            }}>
              {editing && !agent.provider_id && <option value="">{t('agents.AgentBuilder.sin_asignar')}</option>}
              {editing && agent.provider_id && !providerOptions.some(provider => provider.provider_id === agent.provider_id) && <option value={agent.provider_id}>{agent.provider_id} {t('agents.AgentBuilder.perfil_guardado')}</option>}
              {!editing && !providerOptions.length && <option value={selectedProviderId}>{providersLoading ? t('agents.AgentBuilder.cargando') : t('agents.AgentBuilder.sin_proveedores_disponibles')}</option>}
              {providerOptions.map(provider => <option key={provider.provider_id} value={provider.provider_id} disabled={!['ready', 'configured_unverified'].includes(provider.state) || !provider.model_id}>
                {provider.label || (provider.provider_id === 'ollama-cloud' ? 'Ollama' : provider.provider_id === 'openai-platform' ? 'OpenAI Platform' : 'GitHub Copilot')} · {provider.state === 'ready' ? t('agents.AgentBuilder.acceso_comprobado') : provider.state === 'configured_unverified' ? t('agents.AgentBuilder.registrado_sin_comprobar') : t('agents.AgentBuilder.configura_primero')}
              </option>)}
            </select>
          </div>
          <div className="form-group">
            <label htmlFor="agent-model">{t('agents.AgentBuilder.modelo')}</label>
            <select id="agent-model" value={selectedModelId} className="form-select" disabled={!eligibleModels.some(item => item.provider_id === selectedProviderId && item.model_id)}
              onChange={event => { if (selectedProviderId) updateAgent({ provider_id: selectedProviderId, model_id: event.target.value }) }}>
              {eligibleModels.filter(item => item.provider_id === selectedProviderId && item.model_id).map(item => <option key={item.model_id} value={item.model_id!}>{item.model_id}</option>)}
              {editing && agent.model_id && !eligibleModels.some(item => item.provider_id === selectedProviderId && item.model_id === agent.model_id) && <option value={agent.model_id}>{agent.model_id} {t('agents.AgentBuilder.perfil_guardado')}</option>}
              {editing && !agent.model_id && <option value="">{t('agents.AgentBuilder.sin_asignar')}</option>}
              {!editing && !selectedProvider?.model_id && <option value="">{t('agents.AgentBuilder.configura_un_modelo_en_provider_settings')}</option>}
            </select>
          </div>

          <div className="form-group">
            <label>{t('agents.AgentBuilder.system_prompt')}</label>
            <textarea
              value={agent.system_prompt}
              onChange={(e) => updateAgent({ system_prompt: e.target.value })}
              placeholder={t('agents.AgentBuilder.system_instructions_for_the_agent')}
              className="form-textarea"
              rows={4}
            />
          </div>

          <div className="form-group">
            <label>{t('agents.AgentBuilder.available_tools')}</label>
            <div className="tools-list">
              {toolOptions.map((tool) => (
                <label key={tool.id} className="checkbox-label">
                  <input
                    type="checkbox"
                    checked={agent.tools.includes(tool.id)}
                    disabled={tool.status !== 'AVAILABLE' && !agent.tools.includes(tool.id)}
                    onChange={() => toggleTool(tool.id)}
                  />
                  <span>{toolLabel(tool)}{tool.status !== 'AVAILABLE' && <small> · {t('agentTools.notConnected')}</small>}</span>
                </label>
              ))}
            </div>
            {toolCatalogError && <p role="alert">{t('agentTools.toolsUnavailable')}</p>}
            {toolOptions.some(tool => tool.formats?.['.png']?.available === false) && <p role="status">{t('agentTools.missingOcr')}</p>}
          </div>

          <div className="button-group">
            <button onClick={() => setStep('preview')} disabled={!agent.task || Boolean(taskError(agent.task)) || (!editing && !selectedProvider)} className="btn btn-primary btn-large"> {t('agents.AgentBuilder.preview')} </button>
            {(!inline || editing) && <button type="button" onClick={onBack} className="btn btn-secondary">{editing ? t('agents.AgentBuilder.cancel') : t('agents.AgentBuilder.back')}</button>}
          </div>
        </div>
      )}

      {step === 'preview' && (
        <div className="wizard-step">
          <h3>{t('agents.AgentBuilder.review_configuration')}</h3>

          <div className="preview-panel">
            <div className="preview-field">
              <strong>{t('agents.AgentBuilder.name')}</strong> {agent.name}
            </div>
            <div className="preview-field">
              <strong>{t('agents.AgentBuilder.description_2')}</strong> {agent.description}
            </div>
            <div className="preview-field"><strong>{english ? 'Automatic task scope' : 'Alcance para asignación automática'}</strong><div className="preview-code">{agent.task_scope || (english ? 'Not declared: BAGO5 will not auto-route tasks here.' : 'No declarado: BAGO5 no asignará tareas automáticamente aquí.')}</div></div>
            <div className="preview-field"><strong>{t('agents.AgentBuilder.tarea')}</strong><div className="preview-code">{agent.task?.prompt}</div>{agent.task?.dates.map(date => <div key={date.key}>{date.label}: {date.value}</div>)}</div>
            <div className="preview-field">
              <strong>{t('agents.AgentBuilder.type')}</strong> <span className="badge">{agentStateLabel(agent.type)}</span>
            </div>
            <div className="preview-field"><strong>{t('agents.AgentBuilder.proveedor_y_modelo')}</strong> {selectedProvider?.label || selectedProviderId || t('agents.AgentBuilder.sin_asignar')} · {selectedModelId || t('agents.AgentBuilder.sin_asignar')}</div>
            <div className="preview-field">
              <strong>{t('agents.AgentBuilder.system_prompt_2')}</strong>
              <div className="preview-code">{agent.system_prompt}</div>
            </div>
            <div className="preview-field">
              <strong>{t('agents.builder.toolsCount',{count:formatNumber(agent.tools.length)})}</strong>
              <div className="tools-preview">
                {agent.tools.map((tool) => (
                  <span key={tool} className="badge badge-tool">
                    {toolOptions.find(item => item.id === tool) ? toolLabel(toolOptions.find(item => item.id === tool)!) : tool}
                  </span>
                ))}
              </div>
            </div>
          </div>

          <div className="button-group">
            <button
              onClick={saveAgent}
              disabled={saving || !agent.name || !agent.task || Boolean(taskError(agent.task))}
              className={`btn btn-primary btn-large ${saving ? 'disabled' : ''}`}
            >
              {saving ? t('agents.builder.saving') : editing ? t('agents.AgentBuilder.save_changes') : t('agents.builder.save')}
            </button>
            <button onClick={() => setStep('configure')} className="btn btn-secondary"> {t('agents.AgentBuilder.back')} </button>
          </div>

          {saveStatus === 'success' && (
            <div className="status-message success">{t('agents.AgentBuilder.agent_saved_successfully')}</div>
          )}
          {saveStatus === 'error' && (
            <div className="status-message error" role="alert">✗ {saveError ? (typeof saveError === 'string' ? saveError : presentAgentError(saveError)) : t('agents.AgentBuilder.error_saving_agent_try_again')}</div>
          )}
        </div>
      )}

      {step === 'complete' && (
        <div className="wizard-step">
          <div className="completion-panel">
            <div className="completion-icon">✓</div>
            <h3>{editing ? t('agents.AgentBuilder.changes_saved') : t('agents.AgentBuilder.agent_created')}</h3>
            <p className="agent-name">{agent.name}</p>

            <div className="completion-details">
              <p><strong>{t('agents.AgentBuilder.type')}</strong> {agentStateLabel(agent.type)}</p>
              <p><strong>{t('agents.AgentBuilder.tools_2')}</strong> {t('agents.builder.availableTools',{count:formatNumber(agent.tools.length)})}</p>
            </div>

            <div className="button-group">
              <button onClick={reset} className="btn btn-primary btn-large"> {t('agents.AgentBuilder.create_another_agent')} </button>
              <button onClick={reset} className="btn btn-secondary"> {t('agents.AgentBuilder.done')} </button>
            </div>
          </div>
        </div>
      )}

      {createdAgents.length > 0 && (
        <div className="created-agents">
          <h3>{t('agents.AgentBuilder.created_agents')}</h3>
          <div className="agents-list">
            {createdAgents.map((a, idx) => (
              <div key={idx} className="agent-card">
                <div className="agent-card-header">
                  <strong>{a.name}</strong>
                  <span className="badge">{agentStateLabel(a.type)}</span>
                </div>
                <p>{a.description}</p>
                <div className="agent-card-tools">
                  {a.tools.slice(0, 3).map((tool) => (
                    <span key={tool} className="badge badge-small">
                      {tool.split('.')[1]}
                    </span>
                  ))}
                  {a.tools.length > 3 && <span className="badge badge-small">+{a.tools.length - 3}</span>}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
