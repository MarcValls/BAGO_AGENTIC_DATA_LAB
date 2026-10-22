import { useEffect, useState } from 'react'
import type { FormEvent } from 'react'
import './ExternalConnections.css'

type Kind = 'docker_mcp' | 'mcp' | 'http_api'
type Effect = 'READ' | 'WRITE'
type Tool = { name: string; description: string; input_schema: Record<string, unknown>; fingerprint: string }
type Connection = {
  id: string; name: string; kind: Kind; url: string | null; profile: string | null
  method: 'GET' | 'POST' | null; auth_mode: string; header_name: string | null
  allow_private: boolean; state: 'configured' | 'connected' | 'error'
  has_credential: boolean; tools: Tool[]; last_checked_at: string | null
  last_error: string | { code: string; message: string } | null; revision: string
}
type Invocation = {
  run_id: string; connection_id: string; tool_name: string
  decision: 'ALLOW' | 'DENY' | 'REQUIRE_HUMAN'; execution_outcome: 'SUCCESS' | 'DENIED' | 'ERROR'
  actual_effect: { called: boolean }; receipt_id: string; trace_id: string
  evidence: { path: string; sha256: string }; result?: unknown; error?: { code: string; message: string }
}

async function request(url: string, init?: RequestInit): Promise<unknown> {
  const response = await fetch(url, init)
  const body = await response.json()
  if (!response.ok) throw new Error(typeof body?.detail?.message === 'string' ? body.detail.message : `Solicitud rechazada (${response.status}).`)
  return body
}
const post = (body: unknown): RequestInit => ({ method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) })
const nonempty = (value: unknown): value is string => typeof value === 'string' && value.trim().length > 0
function isTool(value: unknown): value is Tool {
  if (!value || typeof value !== 'object') return false
  const tool = value as Tool
  return nonempty(tool.name) && nonempty(tool.fingerprint) && typeof tool.description === 'string'
    && !!tool.input_schema && typeof tool.input_schema === 'object' && !Array.isArray(tool.input_schema)
}
function isConnection(value: unknown): value is Connection {
  if (!value || typeof value !== 'object') return false
  const connection = value as Connection
  return nonempty(connection.id) && nonempty(connection.name) && ['docker_mcp', 'mcp', 'http_api'].includes(connection.kind)
    && ['configured', 'connected', 'error'].includes(connection.state)
    && Array.isArray(connection.tools) && connection.tools.every(isTool)
}
function isInvocation(value: unknown, connectionId: string, toolName: string): value is Invocation {
  if (!value || typeof value !== 'object') return false
  const invocation = value as Invocation
  if (!nonempty(invocation.run_id) || invocation.connection_id !== connectionId || invocation.tool_name !== toolName
    || !nonempty(invocation.receipt_id) || !nonempty(invocation.trace_id) || !nonempty(invocation.evidence?.path)
    || !/^[a-f0-9]{64}$/i.test(invocation.evidence?.sha256 ?? '') || typeof invocation.actual_effect?.called !== 'boolean'
    || !['ALLOW', 'DENY', 'REQUIRE_HUMAN'].includes(invocation.decision)) return false
  if (invocation.execution_outcome === 'SUCCESS') return invocation.decision === 'ALLOW' && invocation.actual_effect.called
  if (invocation.execution_outcome === 'DENIED') return invocation.decision !== 'ALLOW' && !invocation.actual_effect.called
  return invocation.execution_outcome === 'ERROR' && invocation.decision === 'ALLOW'
}
const stateLabels = { configured: 'Guardada · acceso sin comprobar', connected: 'Conectada', error: 'Error de conexión' }

export default function ExternalConnections() {
  const [connections, setConnections] = useState<Connection[]>([])
  const [selectedId, setSelectedId] = useState('')
  const [loading, setLoading] = useState(true)
  const [busy, setBusy] = useState('')
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')
  const [kind, setKind] = useState<Kind>('docker_mcp')
  const [name, setName] = useState('')
  const [profile, setProfile] = useState('')
  const [url, setUrl] = useState('')
  const [method, setMethod] = useState('GET')
  const [authMode, setAuthMode] = useState('none')
  const [credential, setCredential] = useState('')
  const [headerName, setHeaderName] = useState('X-API-Key')
  const [allowPrivate, setAllowPrivate] = useState(false)
  const [discoveryApproved, setDiscoveryApproved] = useState(false)
  const [toolName, setToolName] = useState('')
  const [argumentsText, setArgumentsText] = useState('{}')
  const [effect, setEffect] = useState<Effect>('WRITE')
  const [approved, setApproved] = useState(false)
  const [result, setResult] = useState<Invocation | null>(null)
  const selected = connections.find(connection => connection.id === selectedId)
  const tool = selected?.tools.find(item => item.name === toolName)
  const actualEffect: Effect = selected?.kind === 'http_api' ? selected.method === 'POST' ? 'WRITE' : 'READ' : effect

  useEffect(() => {
    let active = true
    request('/api/connections').then(body => {
      const rows = (body as { connections?: unknown })?.connections
      if (!Array.isArray(rows) || !rows.every(isConnection)) throw new Error('La lista de conexiones está incompleta o contiene tipos no compatibles.')
      if (active) setConnections(rows)
    }).catch(cause => { if (active) setError(cause instanceof Error ? cause.message : 'No se pudieron cargar las conexiones.') })
      .finally(() => { if (active) setLoading(false) })
    return () => { active = false }
  }, [])

  const resetOperation = () => { setApproved(false); setResult(null); setError(''); setNotice('') }
  const chooseConnection = (id: string) => {
    resetOperation(); setSelectedId(id); setToolName(''); setArgumentsText('{}'); setEffect('WRITE'); setDiscoveryApproved(false)
  }
  const save = async (event: FormEvent) => {
    event.preventDefault(); setBusy('save'); resetOperation()
    const payload = kind === 'docker_mcp'
      ? { name, kind, profile, auth_mode: 'none' }
      : { name, kind, url, auth_mode: authMode, ...(authMode !== 'none' ? { credential } : {}),
          ...(authMode === 'api_key' ? { header_name: headerName } : {}), allow_private: allowPrivate,
          ...(kind === 'http_api' ? { method } : {}) }
    setCredential('')
    try {
      const body = await request('/api/connections', post(payload))
      if (!isConnection(body)) throw new Error('La conexión guardada no tiene un formato compatible.')
      setConnections(rows => [...rows.filter(row => row.id !== body.id), body]); chooseConnection(body.id)
      setNotice('Configuración guardada. El servicio todavía no se ha contactado.')
      setName(''); setUrl(''); setProfile('')
    } catch (cause) { setError(cause instanceof Error ? cause.message : 'No se pudo guardar la conexión.') }
    finally { setBusy('') }
  }
  const discover = async () => {
    if (!selected || !discoveryApproved) return
    setBusy('discover'); resetOperation(); setDiscoveryApproved(false); setToolName('')
    try {
      const body = await request(`/api/connections/${encodeURIComponent(selected.id)}/discover`, post({ confirmed: true })) as { connection?: unknown; tools?: unknown }
      if (!isConnection(body?.connection) || body.connection.id !== selected.id || !Array.isArray(body.tools) || !body.tools.every(isTool)) throw new Error('El descubrimiento devolvió datos incompletos o de otra conexión.')
      const updated = { ...body.connection, tools: body.tools }
      setConnections(rows => rows.map(row => row.id === updated.id ? updated : row))
      setNotice(updated.kind === 'http_api' ? 'Endpoint preparado. El acceso se comprobará al ejecutar una solicitud.' : `${body.tools.length} herramientas descubiertas. Ninguna ejecutada.`)
    } catch (cause) { setError(cause instanceof Error ? cause.message : 'No se pudieron descubrir las herramientas.') }
    finally { setBusy('') }
  }
  const invoke = async () => {
    if (!selected || !tool || !approved) return
    setError(''); setNotice(''); setResult(null)
    let args: unknown
    try {
      args = JSON.parse(argumentsText)
      if (!args || typeof args !== 'object' || Array.isArray(args)) throw new Error()
    } catch { setApproved(false); setError('Los argumentos deben ser un objeto JSON válido.'); return }
    setBusy('invoke'); setApproved(false)
    try {
      const body = await request(`/api/connections/${encodeURIComponent(selected.id)}/invoke`, post({ tool_name: tool.name, arguments: args, effect: actualEffect, tool_fingerprint: tool.fingerprint, confirmed: true }))
      if (!isInvocation(body, selected.id, tool.name)) throw new Error('Recibo ausente, incoherente o de otra operación. No se confirma la ejecución.')
      setResult(body)
      try {
        const registry = await request('/api/connections') as { connections?: unknown }
        if (!Array.isArray(registry?.connections) || !registry.connections.every(isConnection)) throw new Error('Registro de conexiones incompleto.')
        setConnections(registry.connections)
      } catch {
        setError('Recibo recibido. No se pudo actualizar el estado de la conexión.')
      }
    } catch (cause) { setError(cause instanceof Error ? cause.message : 'No se pudo ejecutar la herramienta.') }
    finally { setBusy('') }
  }

  return <section className="external-connections" aria-labelledby="external-connections-title">
    <header><h3 id="external-connections-title">Conexiones externas</h3><p>Docker aloja servidores MCP; las herramientas las aporta cada servidor. También puedes conectar MCP HTTP y APIs.</p></header>
    {loading && <p role="status">Cargando conexiones…</p>}
    {error && <p className="external-connections-error" role="alert">{error}</p>}
    {notice && <p role="status">{notice}</p>}
    <div className="external-connections-grid">
      <form onSubmit={event => void save(event)} aria-label="Nueva conexión">
        <fieldset disabled={!!busy}><legend>Nueva conexión</legend>
          <label>Tipo<select value={kind} onChange={event => { setKind(event.target.value as Kind); setCredential(''); setAuthMode('none') }}><option value="docker_mcp">Docker MCP</option><option value="mcp">MCP HTTP</option><option value="http_api">API HTTP</option></select></label>
          <label>Nombre<input required maxLength={100} value={name} onChange={event => setName(event.target.value)} /></label>
          {kind === 'docker_mcp' ? <label>Perfil existente de Docker<input required value={profile} onChange={event => setProfile(event.target.value)} placeholder="profile" /></label> : <>
            <label>URL del endpoint<input type="url" required value={url} onChange={event => setUrl(event.target.value)} placeholder="https://servicio.example/mcp" /></label>
            {kind === 'http_api' && <label>Método<select value={method} onChange={event => setMethod(event.target.value)}><option>GET</option><option>POST</option></select></label>}
            <label>Autenticación<select value={authMode} onChange={event => { setAuthMode(event.target.value); setCredential('') }}><option value="none">Sin credencial</option><option value="bearer">Bearer token</option><option value="api_key">API key</option></select></label>
            {authMode !== 'none' && <label>Credencial · solo escritura<input type="password" autoComplete="new-password" required value={credential} onChange={event => setCredential(event.target.value)} /></label>}
            {authMode === 'api_key' && <label>Cabecera de API key<input required value={headerName} onChange={event => setHeaderName(event.target.value)} /></label>}
            <label className="external-check"><input type="checkbox" checked={allowPrivate} onChange={event => setAllowPrivate(event.target.checked)} />Permitir este servicio en red local o privada</label>
          </>}
          <button type="submit" className="secondary-action">{busy === 'save' ? 'Guardando…' : 'Guardar conexión'}</button>
        </fieldset>
      </form>
      <div className="external-connection-operation">
        <fieldset disabled={!!busy || loading}><legend>Herramientas y ejecución</legend>
          <label>Conexión<select value={selectedId} onChange={event => chooseConnection(event.target.value)}><option value="">Selecciona una conexión</option>{connections.map(connection => <option key={connection.id} value={connection.id}>{connection.name}</option>)}</select></label>
          {!loading && connections.length === 0 && <p>No hay conexiones guardadas.</p>}
          {selected && <>
            <p className="external-connection-state" role="status">{stateLabels[selected.state]}{selected.has_credential ? ' · Credencial guardada' : ''}</p>
            <p className="external-connection-target">{selected.kind === 'docker_mcp' ? 'Perfil de Docker: ' : selected.kind === 'http_api' ? `${selected.method} ` : 'MCP HTTP: '}<code>{selected.kind === 'docker_mcp' ? selected.profile : selected.url}</code></p>
            {selected.last_error && <p className="external-connections-error">{typeof selected.last_error === 'string' ? selected.last_error : JSON.stringify(selected.last_error)}</p>}
            <label className="external-check"><input type="checkbox" checked={discoveryApproved} onChange={event => setDiscoveryApproved(event.target.checked)} />Autorizo contactar este servicio para descubrir herramientas</label>
            <button type="button" className="secondary-action" disabled={!discoveryApproved} onClick={() => void discover()}>{busy === 'discover' ? 'Descubriendo…' : 'Descubrir herramientas'}</button>
            {selected.tools.length === 0 ? <p>Sin herramientas disponibles. Descubre las del servicio.</p> : <>
              <label>Herramienta<select value={toolName} onChange={event => { resetOperation(); setToolName(event.target.value); setArgumentsText('{}') }}><option value="">Selecciona una herramienta</option>{selected.tools.map(item => <option key={item.name} value={item.name}>{item.name}</option>)}</select></label>
              {tool && <>
                <p>{tool.description}</p>
                <details><summary>Esquema de argumentos</summary><p>Huella: <code>{tool.fingerprint}</code></p><pre>{JSON.stringify(tool.input_schema, null, 2)}</pre></details>
                <label>Argumentos JSON<textarea rows={4} value={argumentsText} spellCheck={false} onChange={event => { resetOperation(); setArgumentsText(event.target.value) }} /></label>
                <label>Efecto<select value={actualEffect} disabled={selected.kind === 'http_api'} onChange={event => { resetOperation(); setEffect(event.target.value as Effect) }}><option value="WRITE">WRITE · puede modificar datos</option><option value="READ">READ · solo lectura</option></select></label>
                <label className="external-check"><input type="checkbox" checked={approved} onChange={event => setApproved(event.target.checked)} />Autorizo esta herramienta con estos argumentos y este efecto</label>
                <button type="button" className="primary-action" disabled={!approved} onClick={() => void invoke()}>{busy === 'invoke' ? 'Ejecutando…' : 'Ejecutar herramienta'}</button>
              </>}
            </>}
          </>}
        </fieldset>
      </div>
    </div>
    {busy && <p role="status" aria-live="polite">{busy === 'invoke' ? 'Ejecutando la operación autorizada…' : busy === 'discover' ? 'Contactando el servicio…' : 'Guardando la configuración…'}</p>}
    {result && <section className="external-invocation" aria-label="Recibo de ejecución">
      <h4>{result.execution_outcome === 'SUCCESS' ? 'Solicitud completada · recibo de ADL' : result.execution_outcome === 'DENIED' ? 'Operación denegada' : 'La operación devolvió un error'}</h4>
      <dl>{Object.entries({ 'Ejecución': result.run_id, 'Conexión': result.connection_id, 'Herramienta': result.tool_name, 'Decisión': result.decision, 'Resultado': result.execution_outcome, 'Llamada realizada': result.actual_effect.called ? 'Sí' : 'No', 'Recibo': result.receipt_id, 'Traza': result.trace_id, 'Evidencia': result.evidence.path, 'SHA-256': result.evidence.sha256 }).map(([label, value]) => <div key={label}><dt>{label}</dt><dd>{value}</dd></div>)}</dl>
      {result.error && <p role="alert">{result.error.code}: {result.error.message}</p>}
      {result.result !== undefined && <details open><summary>Respuesta del servicio</summary><pre>{JSON.stringify(result.result, null, 2)}</pre></details>}
      <p>El recibo registra la llamada observada. No verifica la veracidad del contenido remoto ni habilita su uso automático desde el chat.</p>
    </section>}
  </section>
}
