import {useEffect, useId, useRef, useState} from 'react'
import {formatDate, formatNumber, useI18n} from '../i18n'
import './RuntimeStatusBar.css'

const POLL_MS = 30_000
const TIMEOUT_MS = 8_000
const STALE_MS = 60_000
type Group = 'memory' | 'backend' | 'activity' | 'git' | 'provider'
const groups: Group[] = ['memory', 'backend', 'activity', 'git', 'provider']
type Failure = {kind: 'http'; status: number} | {kind: 'network' | 'contract' | 'timeout'}
type Data = Record<string, unknown>
type Memory = {state: 'available' | 'unavailable'; history: {kind: 'conversation_history'; state: 'present' | 'absent' | 'unknown'}; general: {state: 'disconnected' | 'not_observed'}; checked_at: string; error_code: string | null}
type Provider = {state: string; label: string | null; model: string | null; observation: 'registration_metadata'; response_verified: false; checked_at: string; error_code: string | null}
type Git = {state: 'repository' | 'not_repository' | 'unavailable'; repo_detected: boolean | null; branch: string | null; detached: boolean | null; remote_configured: boolean | null; remote_verification: 'not_checked'; checked_at: string; cached: boolean; cache_ttl_seconds: number; error_code: string | null}
type Snapshot = {checked_at: string; backend: {responding: true} | null; activity: {state: 'active' | 'idle'; active_requests: number} | null; memory: Memory | null; provider: Provider | null; git: Git | null}
const record = (value: unknown): value is Data => value !== null && typeof value === 'object' && !Array.isArray(value)
const nullableString = (value: unknown): value is string | null => value === null || typeof value === 'string'
const nullableBool = (value: unknown): value is boolean | null => value === null || typeof value === 'boolean'
const time = (value: unknown): value is string => typeof value === 'string' && /^\d{4}-\d{2}-\d{2}T/.test(value) && /(?:Z|\+00:00)$/.test(value) && Number.isFinite(Date.parse(value))
const code = (value: unknown, expected: string) => value === null || value === expected

function readMemory(value: unknown): Memory | null {
  if (!record(value) || !['available', 'unavailable'].includes(value.state as string) || !record(value.history) || value.history.kind !== 'conversation_history' || !['present', 'absent', 'unknown'].includes(value.history.state as string) || !record(value.general) || !['disconnected', 'not_observed'].includes(value.general.state as string) || !time(value.checked_at) || !code(value.error_code, 'memory_metadata_unavailable')) return null
  return {state: value.state, history: {kind: 'conversation_history', state: value.history.state}, general: {state: value.general.state}, checked_at: value.checked_at, error_code: value.error_code} as Memory
}
function readProvider(value: unknown): Provider | null {
  if (!record(value) || !['ready', 'configured_unverified', 'not_configured', 'needs_authentication', 'error', 'unsupported_runtime', 'unavailable'].includes(value.state as string) || !nullableString(value.label) || !nullableString(value.model) || value.observation !== 'registration_metadata' || value.response_verified !== false || !time(value.checked_at) || !code(value.error_code, 'provider_metadata_unavailable')) return null
  return {state: value.state, label: value.label, model: value.model, observation: 'registration_metadata', response_verified: false, checked_at: value.checked_at, error_code: value.error_code} as Provider
}
function readGit(value: unknown): Git | null {
  if (!record(value) || !['repository', 'not_repository', 'unavailable'].includes(value.state as string) || !nullableBool(value.repo_detected) || !nullableBool(value.detached) || !nullableBool(value.remote_configured) || !nullableString(value.branch) || value.remote_verification !== 'not_checked' || !time(value.checked_at) || typeof value.cached !== 'boolean' || typeof value.cache_ttl_seconds !== 'number' || !Number.isFinite(value.cache_ttl_seconds) || value.cache_ttl_seconds < 0 || !code(value.error_code, 'git_metadata_unavailable') || (value.state === 'repository' && value.repo_detected !== true) || (value.state === 'not_repository' && value.repo_detected !== false)) return null
  return {state: value.state, repo_detected: value.repo_detected, branch: value.branch, detached: value.detached, remote_configured: value.remote_configured, remote_verification: 'not_checked', checked_at: value.checked_at, cached: value.cached, cache_ttl_seconds: value.cache_ttl_seconds, error_code: value.error_code} as Git
}
function readSnapshot(value: unknown): Snapshot {
  if (!record(value) || value.schema !== 'runtime-status.v1' || !time(value.checked_at)) throw new Error('metadata_contract')
  const raw = value.activity
  const activity = record(raw) && ['active', 'idle'].includes(raw.state as string) && typeof raw.active_requests === 'number' && Number.isInteger(raw.active_requests) && raw.active_requests >= 0 && (raw.state === 'active') === (raw.active_requests > 0) && raw.scope === 'current_process_http_api_requests' && raw.background_activity === 'not_observed'
    ? {state: raw.state, active_requests: raw.active_requests} as Snapshot['activity'] : null
  return {checked_at: value.checked_at, backend: record(value.backend) && value.backend.responding === true ? {responding: true} : null, activity, memory: readMemory(value.memory), provider: readProvider(value.provider), git: readGit(value.git)}
}

export default function RuntimeStatusBar() {
  const {locale} = useI18n()
  const say = (es: string, en: string) => locale === 'en' ? en : es
  const [snapshot, setSnapshot] = useState<Snapshot | null>(null)
  const [failure, setFailure] = useState<Failure | null>(null)
  const [loading, setLoading] = useState(false)
  const [paused, setPaused] = useState(false)
  const [expanded, setExpanded] = useState<Group | null>(null)
  const generation = useRef(0)
  const refresh = useRef<() => void>(() => {})
  const buttons = useRef<Partial<Record<Group, HTMLButtonElement | null>>>({})
  const panelId = useId()

  useEffect(() => {
    let alive = true, inFlight = false
    let controller: AbortController | null = null
    let poll: ReturnType<typeof setTimeout> | null = null, deadline: ReturnType<typeof setTimeout> | null = null
    const visible = () => document.visibilityState !== 'hidden'
    const clearPoll = () => {if (poll !== null) clearTimeout(poll); poll = null}
    const cancel = () => {generation.current++; controller?.abort(); controller = null; inFlight = false; clearPoll(); if (deadline !== null) clearTimeout(deadline); deadline = null}
    const schedule = () => {clearPoll(); if (alive && visible()) poll = setTimeout(() => {void load()}, POLL_MS)}
    const load = async () => {
      if (!alive || !visible() || inFlight) return
      clearPoll(); inFlight = true; controller = new AbortController()
      const ownedController = controller, ownGeneration = ++generation.current
      const current = () => alive && !ownedController.signal.aborted && generation.current === ownGeneration
      setLoading(true)
      deadline = setTimeout(() => {
        if (!current()) return
        generation.current++; ownedController.abort(); controller = null; inFlight = false; deadline = null
        setLoading(false); setFailure({kind: 'timeout'}); schedule()
      }, TIMEOUT_MS)
      try {
        const response = await fetch('/api/runtime/status', {method: 'GET', cache: 'no-store', signal: ownedController.signal})
        if (!current()) return
        if (!response.ok) {setFailure({kind: 'http', status: response.status}); return}
        let body: unknown
        try {body = await response.json()} catch {if (current()) setFailure({kind: 'contract'}); return}
        if (!current()) return
        try {setSnapshot(readSnapshot(body)); setFailure(null)} catch {setFailure({kind: 'contract'})}
      } catch {if (current()) setFailure({kind: 'network'})}
      finally {
        if (current()) {if (deadline !== null) clearTimeout(deadline); deadline = null; controller = null; inFlight = false; setLoading(false); schedule()}
      }
    }
    const visibility = () => {
      setPaused(!visible())
      if (!visible()) {cancel(); setLoading(false)} else void load()
    }
    refresh.current = () => {void load()}
    document.addEventListener('visibilitychange', visibility)
    setPaused(!visible()); if (visible()) void load()
    return () => {alive = false; cancel(); refresh.current = () => {}; document.removeEventListener('visibilitychange', visibility)}
  }, [])

  type View = {id: Group; title: string; value: string; tone: 'good' | 'info' | 'warning' | 'error' | 'unknown'; checkedAt: string | null; rows: Array<[string, string]>}
  const unknown = say('Sin comprobar', 'Not checked')
  const notRecorded = say('No registrado', 'Not recorded')
  const bool = (value: boolean | null) => value === null ? unknown : value ? say('Sí', 'Yes') : say('No', 'No')
  const view = (id: Group): View => {
    const titles = {memory: say('Memoria', 'Memory'), backend: 'Backend', activity: say('Actividad ADL', 'ADL activity'), git: 'Git', provider: say('Proveedores', 'Providers')}
    const base: View = {id, title: titles[id], value: unknown, tone: 'unknown', checkedAt: null, rows: []}
    if (!snapshot) return {...base, rows: [[say('Observación', 'Observation'), say('Todavía no hay una lectura válida del endpoint de metadatos.', 'There is no valid metadata endpoint reading yet.')]]}
    if (id === 'backend') return snapshot.backend ? {...base, value: say('API responde', 'API responds'), tone: 'good', checkedAt: snapshot.checked_at, rows: [[say('Alcance', 'Scope'), say('Respuesta HTTP de la API; no verifica todo el sistema.', 'API HTTP response; it does not verify the whole system.')]]} : base
    if (id === 'activity') return snapshot.activity ? {...base, value: `${formatNumber(snapshot.activity.active_requests)} ${say('solicitudes API', 'API requests')}`, tone: snapshot.activity.state === 'active' ? 'info' : 'unknown', checkedAt: snapshot.checked_at, rows: [[say('Estado observado', 'Observed state'), snapshot.activity.state], [say('Alcance', 'Scope'), say('Peticiones HTTP del proceso API actual.', 'HTTP requests in the current API process.')], [say('Fuera de observación', 'Not observed'), say('Trabajos de fondo y actividad del host Codex.', 'Background work and Codex host activity.')]]} : base
    if (id === 'memory') {
      const data = snapshot.memory
      if (!data) return base
      const history = data.history.state === 'present' ? say('Historial disponible', 'History available') : data.history.state === 'absent' ? say('Historial ausente', 'History absent') : say('Historial sin comprobar', 'History not checked')
      const general = data.general.state === 'disconnected' ? say('general sin conectar', 'general disconnected') : say('general no observada', 'general not observed')
      return {...base, value: data.state === 'available' ? `${history} · ${general}` : say('Sin datos de memoria', 'Memory data unavailable'), tone: data.state === 'available' ? 'warning' : 'error', checkedAt: data.checked_at, rows: [[say('Historial', 'History'), history], [say('Memoria general', 'General memory'), general], [say('Alcance de la observación', 'Observation scope'), data.state==='available'?say('Sólo metadatos: historial disponible no acredita mensajes ni recuperación semántica.', 'Metadata only: available history does not establish messages or semantic retrieval.'):say('No hay una lectura válida para acreditar presencia de historial.', 'There is no valid reading establishing history presence.')], ...(data.error_code ? [[say('Código', 'Code'), data.error_code] as [string, string]] : [])]}
    }
    if (id === 'git') {
      const data = snapshot.git
      if (!data) return base
      const remote = data.remote_configured === true ? say('remoto configurado', 'remote configured') : data.remote_configured === false ? say('sin remoto', 'no remote') : say('remoto sin comprobar', 'remote not checked')
      return {...base, value: data.state === 'repository' ? `${data.branch ?? (data.detached === true ? say('HEAD separado', 'Detached HEAD') : say('rama sin registrar', 'branch not recorded'))} · ${remote}` : data.state === 'not_repository' ? say('Sin repositorio local', 'No local repository') : say('Git no disponible', 'Git unavailable'), tone: data.state === 'unavailable' ? 'error' : 'info', checkedAt: data.checked_at, rows: [[say('Repositorio local', 'Local repository'), bool(data.repo_detected)], [say('Rama', 'Branch'), data.branch ?? notRecorded], ['HEAD', data.detached === null ? unknown : data.detached ? say('Separado', 'Detached') : say('Rama', 'Branch')], [say('Remoto configurado', 'Remote configured'), bool(data.remote_configured)], [say('Autenticación GitHub', 'GitHub authentication'), unknown], [say('Caché', 'Cache'), `${bool(data.cached)} · TTL ${formatNumber(data.cache_ttl_seconds)} s`], ...(data.error_code ? [[say('Código', 'Code'), data.error_code] as [string, string]] : [])]}
    }
    const data = snapshot.provider
    if (!data) return base
    const states: Record<string, string> = {ready: say('registrado, sin respuesta verificada', 'registered, response not verified'), configured_unverified: say('configurado, sin verificar', 'configured, unverified'), not_configured: say('no configurado', 'not configured'), needs_authentication: say('requiere autenticación', 'authentication required'), error: say('error de configuración', 'configuration error'), unsupported_runtime: say('runtime no compatible', 'unsupported runtime'), unavailable: say('sin datos', 'unavailable')}
    return {...base, value: `${data.label ?? say('Sin proveedor', 'No provider')}${data.model ? ` / ${data.model}` : ''} · ${states[data.state]}`, tone: ['error', 'unavailable'].includes(data.state) ? 'error' : 'warning', checkedAt: data.checked_at, rows: [[say('Proveedor', 'Provider'), data.label ?? notRecorded], [say('Modelo seleccionado', 'Selected model'), data.model ?? notRecorded], [say('Estado registrado', 'Registered state'), data.state], [say('Tipo de observación', 'Observation type'), say('Metadatos de registro, sin llamada de generación.', 'Registration metadata, without a generation call.')], [say('Respuesta actual', 'Current response'), say('No verificada', 'Not verified')], ...(data.error_code ? [[say('Código', 'Code'), data.error_code] as [string, string]] : [])]}
  }
  const views = groups.map(view)
  const selected = views.find(item => item.id === expanded)
  const freshness = (value: string | null) => value === null ? 'unknown' : Date.parse(value) - Date.now() > STALE_MS ? 'clock' : failure || Date.now() - Date.parse(value) > STALE_MS ? 'stale' : 'fresh'
  const close = () => {const previous = expanded; setExpanded(null); if (previous) buttons.current[previous]?.focus()}
  const errorText = failure?.kind === 'http' ? `${say('Lectura de metadatos no disponible', 'Metadata reading unavailable')} (HTTP ${failure.status}).` : failure?.kind === 'contract' ? say('Respuesta de metadatos incompatible.', 'Incompatible metadata response.') : failure?.kind === 'timeout' ? say('La lectura de metadatos agotó su tiempo.', 'The metadata reading timed out.') : say('No se pudo leer el estado por la red.', 'The status could not be read over the network.')

  return <footer className="runtime-status-bar" aria-label={say('Estado de BAGO5', 'BAGO5 status')} onKeyDown={event => {if (event.key === 'Escape' && expanded) {event.preventDefault(); event.stopPropagation(); close()}}}>
    <section id={panelId} className="runtime-status-bar__details" data-section={selected?.id} hidden={!selected} aria-label={selected ? `${selected.title} · ${say('detalles', 'details')}` : say('Detalles de estado', 'Status details')}>
      {selected && <div className="runtime-status-bar__detail-content">
        <div className="runtime-status-bar__detail-heading"><h3>{selected.title}</h3><button type="button" onClick={close}>{say('Cerrar detalles', 'Close details')}</button></div>
        <div className="runtime-status-bar__summary"><span>{say('Resumen observado', 'Observed summary')}</span><strong className="runtime-status-bar__state" data-tone={['stale', 'clock'].includes(freshness(selected.checkedAt)) ? 'warning' : selected.tone}>{selected.value}</strong></div>
        <dl className="runtime-status-bar__detail-grid">{selected.rows.map(([label, value]) => <div className="runtime-status-bar__detail-card" key={label}><dt>{label}</dt><dd>{value}</dd></div>)}</dl>
        <dl className="runtime-status-bar__detail-meta">
          <div><dt>{say('Comprobado UTC', 'Checked UTC')}</dt><dd>{selected.checkedAt ? <time dateTime={selected.checkedAt}>{formatDate(selected.checkedAt)} UTC</time> : unknown}</dd></div>
          <div><dt>{say('Vigencia', 'Freshness')}</dt><dd className="runtime-status-bar__freshness" data-freshness={freshness(selected.checkedAt)}>{freshness(selected.checkedAt) === 'fresh' ? say('Última observación de metadatos', 'Latest metadata observation') : freshness(selected.checkedAt) === 'clock' ? say('Fecha sin sincronizar', 'Clock not synchronized') : freshness(selected.checkedAt) === 'stale' ? say('Dato anterior; no es una comprobación actual', 'Earlier data; this is not a current check') : unknown}</dd></div>
        </dl>
      </div>}
    </section>
    {failure && <p className="runtime-status-bar__notice" role="status">{errorText} {snapshot ? say('Se conserva la observación anterior.', 'The earlier observation is retained.') : say('Estados sin comprobar.', 'States are not checked.')}</p>}
    {paused && <p className="runtime-status-bar__notice">{say('Actualización en pausa: pestaña oculta.', 'Updates paused: tab hidden.')}</p>}
    <div className="runtime-status-bar__row">
      {views.map(item => {
        const old = ['stale', 'clock'].includes(freshness(item.checkedAt))
        return <button key={item.id} ref={element => {buttons.current[item.id] = element}} type="button" className="runtime-status-bar__group" data-group={item.id} data-tone={old ? 'warning' : item.tone} aria-expanded={expanded === item.id} aria-controls={panelId} aria-label={`${item.title}: ${item.value}${old ? ` · ${say('Dato anterior', 'Earlier data')}` : ''}`} title={`${item.title}: ${item.value}`} onClick={() => setExpanded(current => current === item.id ? null : item.id)}><span className="runtime-status-bar__dot" aria-hidden="true"/><strong>{item.title}</strong><span className="runtime-status-bar__value" aria-live="polite">{item.value}</span>{old && <span className="runtime-status-bar__old">{say('Anterior', 'Earlier')}</span>}</button>
      })}
      <div className="runtime-status-bar__refresh"><button type="button" aria-label={say('Actualizar estado de BAGO5', 'Refresh BAGO5 status')} aria-disabled={loading || paused} onClick={() => {if (!loading && !paused) refresh.current()}}>{loading ? say('Consultando…', 'Reading…') : say('Actualizar', 'Refresh')}</button><span>{snapshot ? <time dateTime={snapshot.checked_at}>{formatDate(snapshot.checked_at, {hour: '2-digit', minute: '2-digit'})} UTC</time> : say('Sin lectura', 'No reading')}</span></div>
    </div>
  </footer>
}
