import { useEffect, useState } from 'react'
import './ModelAssignments.css'

type Use = { provider_id: string; model_id: string; chat: boolean; orchestrator: boolean; agent_types: string[] }
type Model = { provider_id: string; model_id: string; display_name?: string; label: string; state: string }
type Policy = { models: Use[]; main_chat: string | null; revision: string; catalog: Model[]; warnings?: string[] }
const key = (item: { provider_id: string; model_id: string }) => `${item.provider_id}|${item.model_id}`
const roles = [['rag', 'RAG'], ['tool', 'Herramientas'], ['multi-agent', 'Multiagente']]
const allRoles = roles.map(([id]) => id)
async function body(response: Response) {
  const data = await response.json()
  if (!response.ok) throw new Error(data.detail?.message || 'No se pudo guardar la selección de modelos.')
  return data
}

export default function ModelAssignments({ onExit }: { onExit: () => void }) {
  const [policy, setPolicy] = useState<Policy | null>(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')
  const [filter, setFilter] = useState('')
  const load = async () => {
    setBusy(true); setError(''); setNotice('')
    try { setPolicy(await body(await fetch('/api/providers/model-policy'))) }
    catch (cause) { setError(cause instanceof Error ? cause.message : 'No se pudieron cargar los modelos.') }
    finally { setBusy(false) }
  }
  useEffect(() => { void load() }, [])
  const update = (model: Model, column: string, checked: boolean) => {
    setNotice('')
    setPolicy(current => {
      if (!current) return current
      const id = key(model)
      const previous = current.models.find(item => key(item) === id) || { provider_id: model.provider_id, model_id: model.model_id, chat: false, orchestrator: false, agent_types: [] }
      const next = column === 'orchestrator'
        ? { ...previous, chat: checked, orchestrator: checked }
        : column === 'all_agents'
          ? { ...previous, agent_types: checked ? allRoles : [] }
          : { ...previous, agent_types: checked ? [...new Set([...previous.agent_types, column])] : previous.agent_types.filter(role => role !== column) }
      const mainChatInvalidated = column === 'orchestrator' && !checked && current.main_chat === id
      return { ...current, models: [...current.models.filter(item => key(item) !== id), next], main_chat: mainChatInvalidated ? null : current.main_chat }
    })
  }
  const save = async () => {
    if (!policy) return
    setBusy(true); setError(''); setNotice('')
    try {
      const models = policy.models.map(item => ({ ...item, chat: item.orchestrator }))
      const saved = await body(await fetch('/api/providers/model-policy', { method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ models, main_chat: policy.main_chat, expected_revision: policy.revision }) }))
      setPolicy({ ...policy, ...saved })
      setNotice('Selección guardada.')
      window.dispatchEvent(new Event('adl-model-policy-changed'))
    } catch (cause) { setError(cause instanceof Error ? cause.message : 'No se pudo guardar.') }
    finally { setBusy(false) }
  }
  const catalog = policy?.catalog || []
  const missing: Model[] = (policy?.models || []).filter(item => !catalog.some(model => key(model) === key(item))).map(item => ({ ...item, label: item.provider_id, state: 'unavailable' }))
  const models = [...catalog, ...missing].filter(model => `${model.label} ${model.display_name || model.model_id}`.toLowerCase().includes(filter.toLowerCase()))
  const groups = [...models.reduce((result, model) => {
    const provider = model.label || model.provider_id
    result.set(provider, [...(result.get(provider) || []), model])
    return result
  }, new Map<string, Model[]>())]
  const valid = policy && (!policy.models.some(item => item.orchestrator) || policy.models.some(item => item.orchestrator && key(item) === policy.main_chat))
  return <section className="model-assignments" aria-label="Modelos activos y asignación">
    <header><h3>Modelos activos</h3><button type="button" onClick={() => void load()} disabled={busy}>Actualizar</button></header>
    <div className="model-assignments-content">
    {error && <p role="alert">{error}</p>}{notice && <p role="status">{notice}</p>}
    {busy && <p role="status">Cargando…</p>}
    {policy && <>
      <label className="model-filter">Buscar modelo<input value={filter} onChange={event => setFilter(event.target.value)} placeholder="Proveedor o modelo" /></label>
      <p className="model-policy-hint">El chat usa los modelos marcados como orquestador. Cada modelo también puede asignarse a todos los agentes o solo a ciertos tipos.</p>
      {groups.map(([provider, providerModels]) => <section className="model-provider-group" key={provider} aria-label={`Modelos de ${provider}`}>
        <header><h4>{provider}</h4><span>{providerModels.length} modelos</span></header>
        <div className="model-assignment-scroll"><table><thead><tr><th scope="col">Modelo</th><th scope="col">Orquestador</th><th scope="col">Todos los agentes</th>{roles.map(([id, label]) => <th key={id} scope="col">{label}</th>)}<th scope="col">Principal</th></tr></thead><tbody>
          {providerModels.map(model => {
            const id = key(model), use = policy.models.find(item => key(item) === id)
            const allAgents = allRoles.every(role => use?.agent_types.includes(role))
            const active = Boolean(use?.orchestrator || use?.agent_types.length)
            return <tr key={id} data-model={id}>
              <th scope="row"><strong>{model.display_name || model.model_id}</strong><small><span className={active ? 'model-policy-state active' : 'model-policy-state'}>{active ? 'Activo' : 'Desactivado'}</span>{model.state === 'unavailable' ? ' · No disponible' : model.state !== 'ready' ? ' · Sin comprobar' : ''}</small></th>
              <td><input type="checkbox" aria-label={`Orquestador · ${id}`} checked={use?.orchestrator || false} disabled={busy || (model.state === 'unavailable' && !use?.orchestrator)} onChange={event => update(model, 'orchestrator', event.target.checked)} /></td>
              <td><input type="checkbox" aria-label={`Todos los agentes · ${id}`} checked={allAgents} disabled={busy || (model.state === 'unavailable' && !allAgents)} onChange={event => update(model, 'all_agents', event.target.checked)} /></td>
              {roles.map(([role, label]) => <td key={role}><input type="checkbox" aria-label={`${label} · ${id}`} checked={use?.agent_types.includes(role) || false} disabled={busy || (model.state === 'unavailable' && !use?.agent_types.includes(role))} onChange={event => update(model, role, event.target.checked)} /></td>)}
              <td><input type="radio" name="main-chat-model" aria-label={`Principal · ${id}`} checked={policy.main_chat === id} disabled={busy || !use?.orchestrator || model.state === 'unavailable'} onChange={() => { setPolicy({ ...policy, main_chat: id }); setNotice('') }} /></td>
            </tr>
          })}
        </tbody></table></div>
      </section>)}
      {!models.length && <p>No hay modelos disponibles. Configura un proveedor.</p>}
      {!valid && <p role="status">Elige el modelo principal entre los disponibles para orquestar.</p>}
      {policy.warnings?.map(warning => <p key={warning} role="status">{warning}</p>)}
    </>}
    </div>
    <footer className="model-assignments-actions" aria-label="Acciones de modelos activos">
      <button type="button" className="model-assignments-save" onClick={() => void save()} disabled={busy || !valid}>Guardar</button>
      <button type="button" onClick={onExit} disabled={busy}>Salir</button>
    </footer>
  </section>
}
