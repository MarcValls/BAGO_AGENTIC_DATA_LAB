import {useI18n,t,localMessage,errorMessage,apiError,formatDate,formatNumber} from '../i18n'
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
  if (!response.ok) throw apiError(body,response.status,'agents')
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
const stateLabels = { get configured(){return t('agents.aux.ExternalConnections.guardada_acceso_sin_comprobar')}, get connected(){return t('agents.aux.ExternalConnections.conectada')}, get error(){return t('agents.aux.ExternalConnections.error_de_conexion')} }

export default function ExternalConnections() {
  useI18n()

  const [connections, setConnections] = useState<Connection[]>([])
  const [selectedId, setSelectedId] = useState('')
  const [loading, setLoading] = useState(true)
  const [busy, setBusy] = useState('')
  const [error, setError] = useState<any>('')
  const [notice, setNotice] = useState<any>('')
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
      if (!Array.isArray(rows) || !rows.every(isConnection)) throw localMessage("core.ExternalConnections.the_connection_list_is_incomplete_or_includes_e2e2f0")
      if (active) setConnections(rows)
    }).catch(cause => { if (active) setError(cause instanceof Error ? cause : localMessage('agents.aux.ExternalConnections.no_se_pudieron_cargar_las_conexiones')) })
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
      if (!isConnection(body)) throw localMessage("core.ExternalConnections.the_saved_connection_does_not_have_a_1c0496")
      setConnections(rows => [...rows.filter(row => row.id !== body.id), body]); chooseConnection(body.id)
      setNotice("core.ExternalConnections.configuration_saved_the_service_has_not_been_0332dc")
      setName(''); setUrl(''); setProfile('')
    } catch (cause) { setError(cause instanceof Error ? cause : localMessage('agents.aux.ExternalConnections.no_se_pudo_guardar_la_conexion')) }
    finally { setBusy('') }
  }
  const discover = async () => {
    if (!selected || !discoveryApproved) return
    setBusy('discover'); resetOperation(); setDiscoveryApproved(false); setToolName('')
    try {
      const body = await request(`/api/connections/${encodeURIComponent(selected.id)}/discover`, post({ confirmed: true })) as { connection?: unknown; tools?: unknown }
      if (!isConnection(body?.connection) || body.connection.id !== selected.id || !Array.isArray(body.tools) || !body.tools.every(isTool)) throw localMessage("core.ExternalConnections.discovery_returned_incomplete_data_or_data_from_cbdd76")
      const updated = { ...body.connection, tools: body.tools }
      setConnections(rows => rows.map(row => row.id === updated.id ? updated : row))
      setNotice(updated.kind === 'http_api' ? localMessage('agents.aux.ExternalConnections.endpoint_preparado_el_acceso_se_comprobara_al_ejecutar_una_solicitud') : localMessage('agents.aux.ExternalConnections.p0_herramientas_descubiertas_ninguna_ejecutada',{p0:body.tools.length}))
    } catch (cause) { setError(cause instanceof Error ? cause : localMessage('agents.aux.ExternalConnections.no_se_pudieron_descubrir_las_herramientas')) }
    finally { setBusy('') }
  }
  const invoke = async () => {
    if (!selected || !tool || !approved) return
    setError(''); setNotice(''); setResult(null)
    let args: unknown
    try {
      args = JSON.parse(argumentsText)
      if (!args || typeof args !== 'object' || Array.isArray(args)) throw new Error()
    } catch { setApproved(false); setError("core.ExternalConnections.arguments_must_be_a_valid_json_object_a85f3d"); return }
    setBusy('invoke'); setApproved(false)
    try {
      const body = await request(`/api/connections/${encodeURIComponent(selected.id)}/invoke`, post({ tool_name: tool.name, arguments: args, effect: actualEffect, tool_fingerprint: tool.fingerprint, confirmed: true }))
      if (!isInvocation(body, selected.id, tool.name)) throw localMessage("core.ExternalConnections.the_receipt_is_missing_inconsistent_or_belongs_51d211")
      setResult(body)
      try {
        const registry = await request('/api/connections') as { connections?: unknown }
        if (!Array.isArray(registry?.connections) || !registry.connections.every(isConnection)) throw localMessage("core.ExternalConnections.incomplete_connection_record_df013e")
        setConnections(registry.connections)
      } catch {
        setError("core.ExternalConnections.receipt_received_the_connection_state_could_not_54881f")
      }
    } catch (cause) { setError(cause instanceof Error ? cause : localMessage('agents.aux.ExternalConnections.no_se_pudo_ejecutar_la_herramienta')) }
    finally { setBusy('') }
  }

  return <section className="external-connections" aria-labelledby="external-connections-title">
    <header><h3 id="external-connections-title">{t("core.ExternalConnections.external_connections_6285bd")}</h3><p>{t("core.ExternalConnections.docker_hosts_mcp_servers_each_server_provides_f8cef7")}</p></header>
    {loading && <p role="status">{t("core.ExternalConnections.loading_connections_18736c")}</p>}
    {error && <p className="external-connections-error" role="alert">{errorMessage(error)}</p>}
    {notice && <p role="status">{errorMessage(notice)}</p>}
    <div className="external-connections-grid">
      <form onSubmit={event => void save(event)} aria-label={t("core.ExternalConnections.new_connection_496567")}>
        <fieldset disabled={!!busy}><legend>{t("core.ExternalConnections.new_connection_496567")}</legend>
          <label>{t("core.ExternalConnections.type_3868d2")}<select value={kind} onChange={event => { setKind(event.target.value as Kind); setCredential(''); setAuthMode('none') }}><option value="docker_mcp">{t("core.ExternalConnections.docker_mcp_8fb8d9")}</option><option value="mcp">{t("core.ExternalConnections.http_mcp_ef10e7")}</option><option value="http_api">{t("core.ExternalConnections.http_api_e59b3d")}</option></select></label>
          <label>{t("core.ExternalConnections.name_562bb1")}<input required maxLength={100} value={name} onChange={event => setName(event.target.value)} /></label>
          {kind === 'docker_mcp' ? <label>{t("core.ExternalConnections.existing_docker_profile_227daf")}<input required value={profile} onChange={event => setProfile(event.target.value)} placeholder="profile" /></label> : <>
            <label>{t('agents.aux.ExternalConnections.url_del_endpoint')}<input type="url" required value={url} onChange={event => setUrl(event.target.value)} placeholder={t("core.ExternalConnections.https_service_example_mcp_5f0b4a")} /></label>
            {kind === 'http_api' && <label>{t('agents.aux.ExternalConnections.metodo')}<select value={method} onChange={event => setMethod(event.target.value)}><option>GET</option><option>POST</option></select></label>}
            <label>{t("core.ExternalConnections.authentication_ec4bc9")}<select value={authMode} onChange={event => { setAuthMode(event.target.value); setCredential('') }}><option value="none">{t("core.ExternalConnections.no_credential_46d372")}</option><option value="bearer">{t("core.ExternalConnections.bearer_token_b22ac3")}</option><option value="api_key">{t("core.ExternalConnections.api_key_16f0ee")}</option></select></label>
            {authMode !== 'none' && <label>{t("core.ExternalConnections.credential_write_only_8caf83")}<input type="password" autoComplete="new-password" required value={credential} onChange={event => setCredential(event.target.value)} /></label>}
            {authMode === 'api_key' && <label>{t("core.ExternalConnections.api_key_header_3700ea")}<input required value={headerName} onChange={event => setHeaderName(event.target.value)} /></label>}
            <label className="external-check"><input type="checkbox" checked={allowPrivate} onChange={event => setAllowPrivate(event.target.checked)} />{t("core.ExternalConnections.allow_this_service_on_a_local_or_866ae3")}</label>
          </>}
          <button type="submit" className="secondary-action">{busy === 'save' ? t("core.ExternalConnections.saving_3c8dc4") : t("core.ExternalConnections.save_connection_021985")}</button>
        </fieldset>
      </form>
      <div className="external-connection-operation">
        <fieldset disabled={!!busy || loading}><legend>{t("core.ExternalConnections.tools_and_execution_282e28")}</legend>
          <label>{t("core.ExternalConnections.connection_a7f534")}<select value={selectedId} onChange={event => chooseConnection(event.target.value)}><option value="">{t("core.ExternalConnections.select_a_connection_a32e15")}</option>{connections.map(connection => <option key={connection.id} value={connection.id}>{connection.name}</option>)}</select></label>
          {!loading && connections.length === 0 && <p>{t("core.ExternalConnections.no_connections_are_saved_8b3a0d")}</p>}
          {selected && <>
            <p className="external-connection-state" role="status">{stateLabels[selected.state]}{selected.has_credential ? t("core.ExternalConnections.credential_saved_b721c0") : ''}</p>
            <p className="external-connection-target">{selected.kind === 'docker_mcp' ? t("core.ExternalConnections.docker_profile_606fdd") : selected.kind === 'http_api' ? `${selected.method} ` : t("core.ExternalConnections.http_mcp_4ecd26")}<code>{selected.kind === 'docker_mcp' ? selected.profile : selected.url}</code></p>
            {selected.last_error && <p className="external-connections-error">{errorMessage(apiError({detail:selected.last_error},0,'agents'))}</p>}
            <label className="external-check"><input type="checkbox" checked={discoveryApproved} onChange={event => setDiscoveryApproved(event.target.checked)} />{t("core.ExternalConnections.i_authorize_contacting_this_service_to_discover_03b14b")}</label>
            <button type="button" className="secondary-action" disabled={!discoveryApproved} onClick={() => void discover()}>{busy === 'discover' ? t("core.ExternalConnections.discovering_d63420") : t("core.ExternalConnections.discover_tools_41eb80")}</button>
            {selected.tools.length === 0 ? <p>{t("core.ExternalConnections.no_tools_are_available_discover_the_service_a53080")}</p> : <>
              <label>{t("core.ExternalConnections.tool_d96883")}<select value={toolName} onChange={event => { resetOperation(); setToolName(event.target.value); setArgumentsText('{}') }}><option value="">{t("core.ExternalConnections.select_a_tool_c57751")}</option>{selected.tools.map(item => <option key={item.name} value={item.name}>{item.name}</option>)}</select></label>
              {tool && <>
                <p>{tool.description}</p>
                <details><summary>{t("core.ExternalConnections.argument_schema_7f2c0b")}</summary><p>{t("core.ExternalConnections.fingerprint_613fe8")}{' '}<code>{tool.fingerprint}</code></p><pre>{JSON.stringify(tool.input_schema, null, 2)}</pre></details>
                <label>{t("core.ExternalConnections.json_arguments_effac4")}<textarea rows={4} value={argumentsText} spellCheck={false} onChange={event => { resetOperation(); setArgumentsText(event.target.value) }} /></label>
                <label>{t("core.ExternalConnections.effect_315ea9")}<select value={actualEffect} disabled={selected.kind === 'http_api'} onChange={event => { resetOperation(); setEffect(event.target.value as Effect) }}><option value="WRITE">{t("core.ExternalConnections.write_may_modify_data_40d1d1")}</option><option value="READ">{t("core.ExternalConnections.read_read_only_fe822c")}</option></select></label>
                <label className="external-check"><input type="checkbox" checked={approved} onChange={event => setApproved(event.target.checked)} />{t("core.ExternalConnections.i_authorize_this_tool_with_these_arguments_1ddfd0")}</label>
                <button type="button" className="primary-action" disabled={!approved} onClick={() => void invoke()}>{busy === 'invoke' ? t("core.ExternalConnections.running_457239") : t("core.ExternalConnections.run_tool_35cb23")}</button>
              </>}
            </>}
          </>}
        </fieldset>
      </div>
    </div>
    {busy && <p role="status" aria-live="polite">{busy === 'invoke' ? t("core.ExternalConnections.running_the_authorized_operation_fc4f8e") : busy === 'discover' ? t("core.ExternalConnections.contacting_the_service_27cb07") : t("core.ExternalConnections.saving_the_configuration_2c6f8b")}</p>}
    {result && <section className="external-invocation" aria-label={t("core.ExternalConnections.execution_receipt_fedb8a")}>
      <h4>{result.execution_outcome === 'SUCCESS' ? t("core.ExternalConnections.request_completed_adl_receipt_f3e4b4") : result.execution_outcome === 'DENIED' ? t("core.ExternalConnections.operation_denied_452835") : t("core.ExternalConnections.the_operation_returned_an_error_d04588")}</h4>
      <dl>{Object.entries({ [t('agents.aux.ExternalConnections.ejecucion')]: result.run_id, [t('agents.aux.ExternalConnections.conexion')]: result.connection_id, [t('agents.aux.ExternalConnections.herramienta')]: result.tool_name, [t('agents.aux.ExternalConnections.decision')]: observedStateLabel(result.decision), [t('agents.aux.ExternalConnections.resultado')]: observedStateLabel(result.execution_outcome), [t('agents.aux.ExternalConnections.llamada_realizada')]: result.actual_effect.called ? t('agents.aux.ExternalConnections.si') : t('agents.aux.ExternalConnections.no'), [t('agents.aux.ExternalConnections.recibo')]: result.receipt_id, [t('agents.aux.ExternalConnections.traza')]: result.trace_id, [t('agents.aux.ExternalConnections.evidencia')]: result.evidence.path, 'SHA-256': result.evidence.sha256 }).map(([label, value]) => <div key={label}><dt>{label}</dt><dd>{value}</dd></div>)}</dl>
      {result.error && <p role="alert">{errorMessage(apiError({detail:result.error},0,'agents'))}</p>}
      {result.result !== undefined && <details open><summary>{t("core.ExternalConnections.service_response_1a7de5")}</summary><pre>{JSON.stringify(result.result, null, 2)}</pre></details>}
      <p>{t("core.ExternalConnections.the_receipt_records_the_observed_call_it_d77186")}</p>
    </section>}
  </section>
}

/** Presentation only: preserve the exact observed protocol value alongside its label. */
function observedStateLabel(value: string): string {
  const labels: Record<string, () => string> = {
"running":()=>t('agents.aux.state.running'),
"success":()=>t('agents.aux.state.success'),
"failed":()=>t('agents.aux.state.failed'),
"timeout":()=>t('agents.aux.state.timeout'),
"demo":()=>t('agents.aux.state.demo'),
"agent":()=>t('agents.aux.state.agent'),
"PROPOSED":()=>t('agents.aux.state.PROPOSED'),
"VERIFIED":()=>t('agents.aux.state.VERIFIED'),
"PENDING_REVIEW":()=>t('agents.aux.state.PENDING_REVIEW'),
"CANCELLED":()=>t('agents.aux.state.CANCELLED'),
"EXPIRED":()=>t('agents.aux.state.EXPIRED'),
"AVAILABLE":()=>t('agents.aux.state.AVAILABLE'),
"UNAVAILABLE":()=>t('agents.aux.state.UNAVAILABLE'),
"READY":()=>t('agents.aux.state.READY'),
"NOT_READY":()=>t('agents.aux.state.NOT_READY'),
"AWAITING_APPROVAL":()=>t('agents.aux.state.AWAITING_APPROVAL'),
"APPROVED":()=>t('agents.aux.state.APPROVED'),
"REJECTED":()=>t('agents.aux.state.REJECTED'),
"SUCCEEDED":()=>t('agents.aux.state.SUCCEEDED'),
"FAILED":()=>t('agents.aux.state.FAILED'),
"REVOKED":()=>t('agents.aux.state.REVOKED'),
"UNKNOWN":()=>t('agents.aux.state.UNKNOWN'),
"PASS":()=>t('agents.aux.state.PASS'),
"FAIL":()=>t('agents.aux.state.FAIL'),
"ERROR":()=>t('agents.aux.state.ERROR'),
"healthy":()=>t('agents.aux.state.healthy'),
"unavailable":()=>t('agents.aux.state.unavailable'),
"ALLOW":()=>t('agents.aux.state.ALLOW'),
"DENY":()=>t('agents.aux.state.DENY'),
"REQUIRE_HUMAN":()=>t('agents.aux.state.REQUIRE_HUMAN'),
"SUCCESS":()=>t('agents.aux.state.SUCCESS'),
"DENIED":()=>t('agents.aux.state.DENIED'),
"configured":()=>t('agents.aux.state.configured'),
"connected":()=>t('agents.aux.state.connected'),
"present":()=>t('agents.aux.state.present'),
"absent":()=>t('agents.aux.state.absent')
  }
  return Object.prototype.hasOwnProperty.call(labels,value) ? `${labels[value]()} (${value})` : t('agents.aux.state.unknownCode',{value})
}
