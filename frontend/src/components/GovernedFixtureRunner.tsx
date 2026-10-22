import { useEffect, useRef, useState } from 'react'
import './GovernedFixtureRunner.css'

type JsonObject = Record<string, unknown>
type Session = { session_id: string; session_token: string; principal_id: string; workspace_id: string; agent_id: string; issued_at: string; expires_at: string }
type Decision = 'APPROVED' | 'REJECTED' | 'CANCELLED'
export type GexRequestView = {
  contract_version: 'gex-runtime/v1'; request_id: string; run_id: string; proposal_id: string; state: string; task: string
  provider: { provider_id: string; model_id: string }
  proposal: { tool_name: string; arguments: JsonObject; proposal_digest: string }
  request: JsonObject | null; request_digest: string | null; policy_decision: JsonObject | null
  approval: JsonObject | null; permit: JsonObject | null
  receipt: null | { receipt_id: string; request_digest: string; attempt_id: string | null; permit_id: string | null; status: string; verification_state: string; verification_result_id: string | null; observed_sha256: string | null; executor_output_sha256: string | null; fixture_id: string; synthetic: true; output: string | null; sandbox_receipt: JsonObject | null; persisted_at: string; evidence_refs: string[]; error_code: string | null }
  events: Array<{ event_id: string; kind: string; timestamp: string; seq: number; prev_hash: string | null; event_digest: string; request_id: string; request_digest: string | null; attempt_id: string | null; permit_id: string | null; payload_ref: string }>
  integrity: { request_digest_valid: boolean | null; event_chain_valid: boolean; approval_signature_valid: boolean | null; permit_signature_valid: boolean | null; receipt_verified: boolean }
  error: { code: string; message: string } | null; synthetic: true
}
const fixtureId = 'adl.synthetic.customer-summary.v1'
const fixtureOutput = '{"customer_id":"fixture-customer-001","status":"synthetic","open_invoice_count":2}\n'
const fixtureSha = '1ae8dee0e30cde63635ef7696020d1d8ff731346660ff8b1be8bca4ad82cdb7d'
const object = (v: unknown): v is JsonObject => !!v && typeof v === 'object' && !Array.isArray(v)
const text = (v: unknown): v is string => typeof v === 'string' && v.length > 0
const digest = (v: unknown): v is string => typeof v === 'string' && /^[a-f0-9]{64}$/.test(v)
const signature = (v: unknown) => typeof v === 'string' && /^[A-Za-z0-9_-]{86}$/.test(v)
const json = (v: unknown) => JSON.stringify(v, null, 2)
const child = (v: JsonObject | null, key: string): JsonObject => v && object(v[key]) ? v[key] as JsonObject : {}
const verifiedLabel = (v: unknown) => v === true ? 'Válido (backend)' : v === false ? 'NO VÁLIDO' : 'No comprobado'

export function readGexView(value: unknown): GexRequestView | null {
  if (!object(value) || value.contract_version !== 'gex-runtime/v1' || value.synthetic !== true
    || !['request_id', 'run_id', 'proposal_id', 'state', 'task'].every(k => text(value[k]))
    || !object(value.provider) || !text(value.provider.provider_id) || !text(value.provider.model_id)
    || !object(value.proposal) || !text(value.proposal.tool_name) || !object(value.proposal.arguments)
    || !object(value.integrity) || !Array.isArray(value.events)
    || !['request', 'request_digest', 'policy_decision', 'approval', 'permit', 'receipt', 'error'].every(k => k in value)
    || ['request', 'policy_decision', 'approval', 'permit', 'receipt', 'error'].some(k => value[k] !== null && !object(value[k]))
    || value.events.some(e => !object(e) || !text(e.event_id) || !text(e.kind) || !Number.isInteger(e.seq))) return null
  return value as unknown as GexRequestView
}

// UI consistency checks supplement the authenticated backend checks; no browser signing authority.
export function reviewableGex(view: GexRequestView, agentId: string): boolean {
  const r = view.request
  return !!r && r.contract_version === 'gex-request/v1' && r.request_id === view.request_id
    && ['principal', 'agent', 'workspace', 'capability', 'operation', 'constraints', 'policy'].every(k => object(r[k]))
    && ['context_revision', 'proposed_at', 'expires_at', 'nonce'].every(k => text(r[k]))
    && r.run_id === view.run_id && r.proposal_id === view.proposal_id
    && child(r, 'agent').agent_id === agentId && digest(child(r, 'agent').config_digest) && text(child(r, 'agent').revision) && digest(view.request_digest)
    && view.integrity.request_digest_valid === true && view.integrity.event_chain_valid === true
    && child(r, 'capability').id === 'fixture.read' && child(r, 'capability').version === '1'
    && digest(child(r, 'capability').registry_digest) && digest(child(r, 'capability').schema_digest) && child(r, 'capability').executor_kind === 'local'
    && child(r, 'capability').effect === 'READ' && child(r, 'operation').target === 'registered-immutable-fixture'
    && child(r, 'operation').effect_scope === 'read:fixture:sample'
    && json(child(child(r, 'operation'), 'arguments')) === json({ fixture_id: fixtureId })
    && view.proposal.tool_name === 'fixture.read' && json(view.proposal.arguments) === json({ fixture_id: fixtureId })
    && child(r, 'constraints').network === 'deny' && child(r, 'constraints').write_scope === 'none'
    && child(r, 'constraints').sandbox_profile === 'read_only_agent'
    && child(r, 'constraints').timeout_ms === 1000 && child(r, 'constraints').max_output_bytes === 65536
    && Array.isArray(child(r, 'constraints').egress_allowlist) && (child(r, 'constraints').egress_allowlist as unknown[]).length === 0
    && digest(child(r, 'workspace').binding_fingerprint) && text(child(r, 'workspace').workspace_id)
    && ['repository_identity', 'branch', 'commit_sha', 'context_revision', 'root_identity'].every(k => text(child(r, 'workspace')[k]))
    && text(child(r, 'principal').subject) && child(r, 'principal').auth_strength === 'verified'
    && text(child(r, 'principal').issuer) && digest(child(r, 'principal').session_binding)
    && text(child(r, 'policy').revision) && digest(child(r, 'policy').policy_digest)
    && object(view.policy_decision) && view.policy_decision.request_digest === view.request_digest
    && text(view.policy_decision.decision_id)
    && view.policy_decision.result === 'REQUIRE_HUMAN'
}

export function verifiedGexSuccess(view: GexRequestView, agentId: string): boolean {
  const { receipt: r, permit: p, approval: a, integrity: i } = view
  const request = view.request
  const source = child(p, 'authorization_source')
  return reviewableGex(view, agentId) && view.state === 'SUCCEEDED' && !!request && !!r && !!p && !!a
    && i.approval_signature_valid === true && i.permit_signature_valid === true && i.receipt_verified === true
    && r.status === 'SUCCESS' && r.verification_state === 'VERIFIED_SUCCESS' && text(r.verification_result_id)
    && text(r.receipt_id) && text(r.attempt_id) && text(r.permit_id) && text(r.persisted_at)
    && r.synthetic === true && r.fixture_id === fixtureId && r.output === fixtureOutput
    && r.observed_sha256 === fixtureSha && r.executor_output_sha256 === fixtureSha
    && r.request_digest === view.request_digest && p.request_digest === view.request_digest && a.request_digest === view.request_digest
    && p.permit_id === r.permit_id && text(a.approval_id) && source.approval_id === a.approval_id
    && a.contract_version === 'gex-approval/v1' && p.contract_version === 'gex-permit/v1'
    && a.decision_id === view.policy_decision?.decision_id && source.decision_id === a.decision_id && source.auto_rule_id === null
    && a.principal_subject === child(request, 'principal').subject && text(a.actor)
    && digest(a.operation_summary_digest) && text(a.auth_context_ref) && text(a.evidence_ref) && text(a.key_id)
    && a.decision === 'APPROVED' && p.signature_algorithm === 'Ed25519' && a.signature_algorithm === 'Ed25519'
    && signature(p.signature) && signature(a.signature) && p.agent_id === agentId
    && p.agent_config_digest === child(request, 'agent').config_digest
    && p.principal_subject === child(request, 'principal').subject && p.session_binding === child(request, 'principal').session_binding
    && p.capability_id === 'fixture.read' && p.capability_version === '1' && p.max_uses === 1
    && p.registry_digest === child(request, 'capability').registry_digest
    && a.workspace_binding_fingerprint === child(request, 'workspace').binding_fingerprint
    && p.workspace_binding_fingerprint === child(request, 'workspace').binding_fingerprint
    && view.events.some(e => e.kind === 'DISPATCH_INTENT' && e.attempt_id === r.attempt_id && e.permit_id === r.permit_id && e.request_id === view.request_id && e.request_digest === view.request_digest)
    && view.events.some(e => e.kind === 'RECEIPT_PERSISTED' && e.request_id === view.request_id && e.request_digest === view.request_digest && e.attempt_id === r.attempt_id && e.permit_id === r.permit_id)
}

export default function GovernedFixtureRunner({ apiBase = 'http://localhost:8081', agentId }: { apiBase?: string; agentId?: string }) {
  const base = `${apiBase.replace(/\/$/, '')}/api/gex`
  const [selectedAgent, setSelectedAgent] = useState(agentId || '')
  const [apiKey, setApiKey] = useState('')
  const [session, setSession] = useState<Session | null>(null)
  const sessionRef = useRef<Session | null>(null)
  const [task, setTask] = useState('Lee el resumen de cliente de la fixture sintética registrada.')
  const [requestId, setRequestId] = useState('')
  const [view, setView] = useState<GexRequestView | null>(null)
  const [status, setStatus] = useState('Consultando disponibilidad…')
  const [ready, setReady] = useState(false)
  const [busy, setBusy] = useState(false)
  const busyRef = useRef(false)
  const [error, setError] = useState('')
  const [uncertain, setUncertain] = useState(false)
  const [now, setNow] = useState(Date.now())
  const controllerRef = useRef<AbortController | null>(null)
  const mounted = useRef(true)

  useEffect(() => {
    mounted.current = true
    const c = new AbortController()
    fetch(`${base}/status`, { signal: c.signal, cache: 'no-store', credentials: 'omit' })
      .then(async r => { const s: unknown = await r.json(); if (!mounted.current) return
        if (r.ok && object(s) && s.contract_version === 'gex-runtime/v1' && s.synthetic === true && s.capability_id === 'fixture.read') {
          setStatus(String(s.state)); setReady(s.state === 'READY')
        } else { setStatus('Respuesta de disponibilidad no válida'); setReady(false) }
      }).catch(() => { if (mounted.current && !c.signal.aborted) setStatus('No se pudo consultar el servicio') })
    const clock = window.setInterval(() => setNow(Date.now()), 1000)
    return () => {
      mounted.current = false; c.abort(); controllerRef.current?.abort(); window.clearInterval(clock)
      const current = sessionRef.current; sessionRef.current = null
      if (current) void fetch(`${base}/sessions/current`, { method: 'DELETE', credentials: 'omit', cache: 'no-store', keepalive: true,
        headers: { Authorization: `Bearer ${current.session_token}`, 'X-GEX-Agent-ID': current.agent_id } }).catch(() => {})
    }
  }, [base])

  function clearAuth() { sessionRef.current = null; setSession(null); setApiKey('') }
  async function action(kind: 'session' | 'propose' | 'reload' | 'revoke' | Decision) {
    if (busyRef.current) return
    const current = sessionRef.current
    if (kind !== 'session' && !current) return
    busyRef.current = true; setBusy(true); setError('')
    const c = new AbortController(); controllerRef.current = c
    const timer = window.setTimeout(() => c.abort(), 30000)
    let path = '/sessions'; let method = 'POST'; let body: unknown = { agent_id: selectedAgent.trim() }
    if (kind === 'propose') { path = '/requests'; body = { task: task.trim() }; setView(null); setUncertain(false) }
    if (kind === 'reload') { path = `/requests/${encodeURIComponent(requestId.trim())}`; method = 'GET'; body = undefined }
    if (kind === 'revoke') { path = '/sessions/current'; method = 'DELETE'; body = undefined }
    if (['APPROVED', 'REJECTED', 'CANCELLED'].includes(kind)) {
      path = `/requests/${encodeURIComponent(view!.request_id)}/decision`
      body = { request_digest: view!.request_digest, decision: kind, reason: kind === 'APPROVED' ? 'Apruebo la solicitud exacta mostrada y su ejecución ahora.' : kind === 'REJECTED' ? 'Rechazo la solicitud mostrada.' : 'Cancelo la solicitud mostrada.' }
    }
    try {
      const r = await fetch(`${base}${path}`, { method, signal: c.signal, credentials: 'omit', cache: 'no-store',
        headers: { Authorization: `Bearer ${kind === 'session' ? apiKey : current!.session_token}`, ...(kind === 'session' ? {} : { 'X-GEX-Agent-ID': current!.agent_id }), ...(body === undefined ? {} : { 'Content-Type': 'application/json' }) },
        ...(body === undefined ? {} : { body: JSON.stringify(body) }) })
      const data: unknown = await r.json()
      if (!mounted.current) return
      if (!r.ok) {
        if (r.status === 401 || r.status === 403) clearAuth()
        const detail = object(data) && object(data.detail) ? data.detail : {}
        const code = typeof detail.code === 'string' && /^[A-Z0-9_]{1,80}$/.test(detail.code) ? detail.code : `HTTP_${r.status}`
        const durable = readGexView(detail.view)
        if (durable && (!view || durable.request_id === view.request_id)) { setView(durable); setRequestId(durable.request_id) }
        if (kind === 'APPROVED' || kind === 'REJECTED' || kind === 'CANCELLED') setUncertain(true)
        setError(`${code}. ${detail.persisted === false ? 'Sin persistencia confirmada.' : 'Operación no confirmada.'} Recarga por ID para consultar el estado durable.`)
        return
      }
      if (kind === 'session') {
        setApiKey('')
        if (!object(data) || !['session_id', 'session_token', 'principal_id', 'workspace_id', 'agent_id', 'issued_at', 'expires_at'].every(k => text(data[k])) || data.agent_id !== selectedAgent.trim() || !Number.isFinite(Date.parse(String(data.expires_at)))) throw new Error('invalid')
        const s = data as unknown as Session; sessionRef.current = s; setSession(s); setView(null); setUncertain(false)
      } else if (kind === 'revoke') {
        clearAuth(); setView(null)
        if (!object(data) || data.status !== 'REVOKED') setError('Revocación no confirmada por el servicio; credenciales borradas de esta vista.')
      } else {
        const next = readGexView(data)
        const expected = kind === 'reload' ? requestId.trim() : kind === 'propose' ? null : view?.request_id
        if (!next || (expected && expected !== next.request_id)) throw new Error('invalid')
        setView(next); setRequestId(next.request_id); setUncertain(false)
      }
    } catch {
      if (mounted.current) { setError('Respuesta no confirmada o tiempo agotado. Recarga por ID; no repitas la aprobación.'); setUncertain(true); if (kind === 'session' || kind === 'revoke') clearAuth() }
    } finally {
      window.clearTimeout(timer); busyRef.current = false
      if (kind === 'revoke' && mounted.current) clearAuth()
      if (mounted.current) setBusy(false)
    }
  }

  const sessionActive = !!session && Date.parse(session.expires_at) > now
  const r = view?.request || null
  const reviewable = !!view && reviewableGex(view, session?.agent_id || selectedAgent)
  const pending = !!view && view.state === 'AWAITING_APPROVAL' && reviewable && sessionActive && !uncertain
    && typeof r?.expires_at === 'string' && Date.parse(r.expires_at) > now
    && child(r, 'workspace').workspace_id === session?.workspace_id && child(r, 'principal').subject === session?.principal_id
  const success = !!view && verifiedGexSuccess(view, session?.agent_id || selectedAgent)

  return <section className="governed-fixture" aria-labelledby="gex-title">
    <header><h2 id="gex-title">Acción gobernada · lectura de fixture</h2>
      <p>Proveedor real configurado en tu agente → propuesta → revisión humana → permiso firmado → lectura → recibo durable.</p>
      <p className="gex-scope">Datos sintéticos: {fixtureId}. Solo lectura registrada, sin red ni escritura. Sandbox lógico; perfil local de un único proceso.</p>
      <p role="status">Disponibilidad: {status}</p></header>
    <fieldset disabled={busy}><legend>1. Autenticar al operador</legend>
      <label>ID del agente guardado<input value={selectedAgent} disabled={!!session} onChange={e => setSelectedAgent(e.target.value)} autoComplete="off" spellCheck={false} /></label>
      {!session ? <><label>Clave de operador<input type="password" value={apiKey} onChange={e => setApiKey(e.target.value)} autoComplete="off" /></label>
        <button disabled={!ready || !apiKey || !selectedAgent.trim()} onClick={() => void action('session')}>Crear sesión</button></> : <>
        <p>Operador: {session.principal_id} · Workspace: {session.workspace_id}</p><p>Sesión {session.session_id} · Caduca: {session.expires_at}{!sessionActive ? ' · CADUCADA' : ''}</p>
        <button onClick={() => void action('revoke')}>Revocar y borrar sesión</button></>}
      <p>La clave y el token permanecen en memoria de esta vista. Tras recargar, autentícate y recupera la solicitud por su ID.</p>
    </fieldset>
    <fieldset disabled={busy || !sessionActive}><legend>2. Pedir propuesta al agente</legend>
      <label>Tarea<textarea maxLength={4000} value={task} onChange={e => setTask(e.target.value)} /></label>
      <button disabled={!ready || !task.trim()} onClick={() => void action('propose')}>Solicitar propuesta</button>
      <label>ID de solicitud para recuperar<input value={requestId} maxLength={256} onChange={e => setRequestId(e.target.value)} autoComplete="off" spellCheck={false} /></label>
      <button disabled={!requestId.trim()} onClick={() => void action('reload')}>Recargar estado durable</button>
    </fieldset>
    {busy ? <p role="status">Esperando al servicio…</p> : null}
    {error ? <p role="alert" className="gex-warning">{error}</p> : null}
    {!view ? <p>Aún no hay una solicitud recuperada.</p> : <>
      <article><h3>3. Revisar solicitud exacta</h3>
        <dl><dt>Estado durable</dt><dd>{view.state}</dd><dt>Solicitud</dt><dd>{view.request_id}</dd><dt>Run / propuesta</dt><dd>{view.run_id} / {view.proposal_id}</dd>
          <dt>Proveedor / modelo</dt><dd>{view.provider.provider_id} / {view.provider.model_id}</dd><dt>Tarea</dt><dd>{view.task}</dd><dt>Digest de solicitud completa</dt><dd>{view.request_digest || 'No registrado'}</dd>
          <dt>Propuesta del modelo</dt><dd><pre>{json(view.proposal)}</pre></dd><dt>Capacidad / versión</dt><dd><pre>{json(child(r, 'capability'))}</pre></dd>
          <dt>Workspace vinculado</dt><dd><pre>{json(child(r, 'workspace'))}</pre></dd><dt>Argumentos y alcance exactos</dt><dd><pre>{json(child(r, 'operation'))}</pre></dd>
          <dt>Restricciones efectivas</dt><dd><pre>{json(child(r, 'constraints'))}</pre></dd><dt>Política y decisión</dt><dd><pre>{json({ policy: child(r, 'policy'), decision: view.policy_decision })}</pre></dd><dt>Caducidad</dt><dd>{String(r?.expires_at || 'No registrada')}</dd></dl>
        <details><summary>Objeto completo inmutable</summary><pre>{json(r)}</pre></details>
        {!reviewable ? <p className="gex-warning">Solicitud incompleta o integridad/alcance no comprobados. Aprobación bloqueada.</p> : null}
        {uncertain ? <p className="gex-warning">Estado incierto: recupera el registro antes de decidir.</p> : null}
        <div className="gex-actions"><button disabled={busy || !pending} onClick={() => void action('APPROVED')}>Aprobar solicitud exacta y ejecutar ahora</button>
          <button disabled={busy || !pending} onClick={() => void action('REJECTED')}>Rechazar</button><button disabled={busy || !pending} onClick={() => void action('CANCELLED')}>Cancelar solicitud</button></div>
      </article>
      <article><h3>4. Recibo y comprobación</h3>
        <p className={success ? 'gex-success' : 'gex-warning'} role="status">{success ? 'Resultado de fixture VERIFICADO por el backend y vinculaciones comprobadas en esta vista.' : 'Sin resultado de ejecución verificado.'}</p>
        <dl>{Object.entries(view.integrity).map(([key, value]) => <div key={key}><dt>{key}</dt><dd>{verifiedLabel(value)}</dd></div>)}</dl>
        <p>Las firmas y la cadena las verifica el backend; esta vista comprueba la correspondencia de IDs, alcance y hashes de la fixture publicada.</p>
        <details><summary>Aprobación firmada</summary><pre>{json(view.approval)}</pre></details><details><summary>Permiso firmado</summary><pre>{json(view.permit)}</pre></details>
        {view.receipt ? <><dl><dt>ID del recibo</dt><dd>{view.receipt.receipt_id}</dd><dt>Intento / permiso</dt><dd>{view.receipt.attempt_id || 'No registrado'} / {view.receipt.permit_id || 'No registrado'}</dd>
          <dt>Hash esperado de fixture</dt><dd>{fixtureSha}</dd><dt>Hash del ejecutor</dt><dd>{view.receipt.executor_output_sha256 || 'No registrado'}</dd><dt>Hash del observador independiente</dt><dd>{view.receipt.observed_sha256 || 'No registrado'}</dd><dt>Persistido</dt><dd>{view.receipt.persisted_at}</dd></dl>
          <details><summary>Recibo completo y salida sintética</summary><pre>{json(view.receipt)}</pre></details></> : <p>No hay recibo persistido disponible.</p>}
        {view.error ? <p className="gex-warning">Código del resultado: {/^[A-Z0-9_]{1,80}$/.test(view.error.code) ? view.error.code : 'ERROR'}</p> : null}
      </article>
      <article><h3>Traza durable</h3>{view.events.length ? <ol>{view.events.map(e => <li key={`${e.seq}-${e.event_id}`}><strong>{e.seq} · {e.kind}</strong> · {e.timestamp}<details><summary>{e.event_id}</summary><pre>{json(e)}</pre></details></li>)}</ol> : <p>No hay eventos recuperados.</p>}</article>
    </>}
  </section>
}
