import {useI18n,t,localMessage,errorMessage,apiError,formatDate,formatNumber} from '../i18n'
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
const verifiedLabel = (v: unknown) => v === true ? t('agents.aux.GovernedFixtureRunner.valido_backend') : v === false ? t('agents.aux.GovernedFixtureRunner.no_valido') : t('agents.aux.GovernedFixtureRunner.no_comprobado')

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
  useI18n()

  const base = `${apiBase.replace(/\/$/, '')}/api/gex`
  const [selectedAgent, setSelectedAgent] = useState(agentId || '')
  const [apiKey, setApiKey] = useState('')
  const [session, setSession] = useState<Session | null>(null)
  const sessionRef = useRef<Session | null>(null)
  const [task, setTask] = useState('Lee el resumen de cliente de la fixture sintética registrada.')
  const [requestId, setRequestId] = useState('')
  const [view, setView] = useState<GexRequestView | null>(null)
  const [status, setStatus] = useState<any>(localMessage('agents.aux.GovernedFixtureRunner.consultando_disponibilidad'))
  const [ready, setReady] = useState(false)
  const [busy, setBusy] = useState(false)
  const busyRef = useRef(false)
  const [error, setError] = useState<any>('')
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
        } else { setStatus(localMessage('agents.aux.GovernedFixtureRunner.respuesta_de_disponibilidad_no_valida')); setReady(false) }
      }).catch(() => { if (mounted.current && !c.signal.aborted) setStatus(localMessage('agents.aux.GovernedFixtureRunner.no_se_pudo_consultar_el_servicio')) })
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
        setError(localMessage(detail.persisted === false ? 'agents.aux.gexPersistenceUnconfirmed' : 'agents.aux.gexOperationUnconfirmed',{code:String(code)}))
        return
      }
      if (kind === 'session') {
        setApiKey('')
        if (!object(data) || !['session_id', 'session_token', 'principal_id', 'workspace_id', 'agent_id', 'issued_at', 'expires_at'].every(k => text(data[k])) || data.agent_id !== selectedAgent.trim() || !Number.isFinite(Date.parse(String(data.expires_at)))) throw new Error('invalid')
        const s = data as unknown as Session; sessionRef.current = s; setSession(s); setView(null); setUncertain(false)
      } else if (kind === 'revoke') {
        clearAuth(); setView(null)
        if (!object(data) || data.status !== 'REVOKED') setError("core.GovernedFixtureRunner.revocation_was_not_confirmed_by_the_service_f191a9")
      } else {
        const next = readGexView(data)
        const expected = kind === 'reload' ? requestId.trim() : kind === 'propose' ? null : view?.request_id
        if (!next || (expected && expected !== next.request_id)) throw new Error('invalid')
        setView(next); setRequestId(next.request_id); setUncertain(false)
      }
    } catch {
      if (mounted.current) { setError("core.GovernedFixtureRunner.unconfirmed_response_or_timeout_reload_by_id_0d1a01"); setUncertain(true); if (kind === 'session' || kind === 'revoke') clearAuth() }
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
    <header><h2 id="gex-title">{t("core.GovernedFixtureRunner.governed_action_fixture_read_3bc8a4")}</h2>
      <p>{t("core.GovernedFixtureRunner.real_provider_configured_in_your_agent_proposal_6f599b")}</p>
      <p className="gex-scope">{t("core.GovernedFixtureRunner.synthetic_data_ee56a3")}{' '}{fixtureId}{t("core.GovernedFixtureRunner.recorded_read_only_with_no_network_or_7a7714")}</p>
      <p role="status">{t("core.GovernedFixtureRunner.availability_7f3549")}{' '}{typeof status === 'string' ? observedStateLabel(status) : errorMessage(status)}</p></header>
    <fieldset disabled={busy}><legend>{t("core.GovernedFixtureRunner.1_authenticate_the_operator_d2c36e")}</legend>
      <label>{t("core.GovernedFixtureRunner.saved_agent_id_b33b6d")}<input value={selectedAgent} disabled={!!session} onChange={e => setSelectedAgent(e.target.value)} autoComplete="off" spellCheck={false} /></label>
      {!session ? <><label>{t("core.GovernedFixtureRunner.operator_key_6d4c8e")}<input type="password" value={apiKey} onChange={e => setApiKey(e.target.value)} autoComplete="off" /></label>
        <button disabled={!ready || !apiKey || !selectedAgent.trim()} onClick={() => void action('session')}>{t("core.GovernedFixtureRunner.create_session_1ba8d2")}</button></> : <>
        <p>{t("core.GovernedFixtureRunner.operator_92aa31")}{' '}{session.principal_id}{' '}{t("core.GovernedFixtureRunner.workspace_e32785")}{' '}{session.workspace_id}</p><p>{t("core.GovernedFixtureRunner.session_88efb2")}{' '}{session.session_id}{' '}{t("core.GovernedFixtureRunner.expires_910d30")}{' '}{session.expires_at}{!sessionActive ? t("core.GovernedFixtureRunner.expired_2cca72") : ''}</p>
        <button onClick={() => void action('revoke')}>{t("core.GovernedFixtureRunner.revoke_and_clear_session_20dc9e")}</button></>}
      <p>{t("core.GovernedFixtureRunner.the_key_and_token_remain_in_this_e9f849")}</p>
    </fieldset>
    <fieldset disabled={busy || !sessionActive}><legend>{t("core.GovernedFixtureRunner.2_ask_the_agent_for_a_proposal_a1ff17")}</legend>
      <label>{t("core.GovernedFixtureRunner.task_981fc1")}<textarea maxLength={4000} value={task} onChange={e => setTask(e.target.value)} /></label>
      <button disabled={!ready || !task.trim()} onClick={() => void action('propose')}>{t("core.GovernedFixtureRunner.request_proposal_55f373")}</button>
      <label>{t("core.GovernedFixtureRunner.request_id_to_recover_0fcbd4")}<input value={requestId} maxLength={256} onChange={e => setRequestId(e.target.value)} autoComplete="off" spellCheck={false} /></label>
      <button disabled={!requestId.trim()} onClick={() => void action('reload')}>{t("core.GovernedFixtureRunner.reload_durable_state_a27bb6")}</button>
    </fieldset>
    {busy ? <p role="status">{t("core.GovernedFixtureRunner.waiting_for_the_service_ffebe2")}</p> : null}
    {error ? <p role="alert" className="gex-warning">{errorMessage(error)}</p> : null}
    {!view ? <p>{t("core.GovernedFixtureRunner.no_request_has_been_recovered_yet_370186")}</p> : <>
      <article><h3>{t("core.GovernedFixtureRunner.3_review_the_exact_request_b47ccf")}</h3>
        <dl><dt>{t("core.GovernedFixtureRunner.durable_state_74f5f0")}</dt><dd>{observedStateLabel(view.state)}</dd><dt>{t("core.GovernedFixtureRunner.request_213b02")}</dt><dd>{view.request_id}</dd><dt>{t("core.GovernedFixtureRunner.run_proposal_0cfca2")}</dt><dd>{view.run_id} / {view.proposal_id}</dd>
          <dt>{t("core.GovernedFixtureRunner.provider_model_68cd92")}</dt><dd>{view.provider.provider_id} / {view.provider.model_id}</dd><dt>{t("core.GovernedFixtureRunner.task_981fc1")}</dt><dd>{view.task}</dd><dt>{t("core.GovernedFixtureRunner.complete_request_digest_16bdbe")}</dt><dd>{view.request_digest || t('agents.aux.GovernedFixtureRunner.no_registrado')}</dd>
          <dt>{t("core.GovernedFixtureRunner.model_proposal_48adef")}</dt><dd><pre>{json(view.proposal)}</pre></dd><dt>{t("core.GovernedFixtureRunner.capability_version_b4774c")}</dt><dd><pre>{json(child(r, 'capability'))}</pre></dd>
          <dt>{t("core.GovernedFixtureRunner.bound_workspace_7fe82d")}</dt><dd><pre>{json(child(r, 'workspace'))}</pre></dd><dt>{t("core.GovernedFixtureRunner.exact_arguments_and_scope_1cff28")}</dt><dd><pre>{json(child(r, 'operation'))}</pre></dd>
          <dt>{t("core.GovernedFixtureRunner.effective_constraints_fa36cd")}</dt><dd><pre>{json(child(r, 'constraints'))}</pre></dd><dt>{t("core.GovernedFixtureRunner.policy_and_decision_11cd1b")}</dt><dd><pre>{json({ policy: child(r, 'policy'), decision: view.policy_decision })}</pre></dd><dt>{t("core.GovernedFixtureRunner.expiry_1deb57")}</dt><dd>{String(r?.expires_at || t('agents.aux.GovernedFixtureRunner.no_registrada'))}</dd></dl>
        <details><summary>{t("core.GovernedFixtureRunner.complete_immutable_object_1574e8")}</summary><pre>{json(r)}</pre></details>
        {!reviewable ? <p className="gex-warning">{t("core.GovernedFixtureRunner.the_request_is_incomplete_or_its_integrity_b1cb33")}</p> : null}
        {uncertain ? <p className="gex-warning">{t("core.GovernedFixtureRunner.uncertain_state_recover_the_record_before_deciding_b2e222")}</p> : null}
        <div className="gex-actions"><button disabled={busy || !pending} onClick={() => void action('APPROVED')}>{t("core.GovernedFixtureRunner.approve_the_exact_request_and_execute_now_2ba732")}</button>
          <button disabled={busy || !pending} onClick={() => void action('REJECTED')}>{t("core.GovernedFixtureRunner.reject_2a0515")}</button><button disabled={busy || !pending} onClick={() => void action('CANCELLED')}>{t("core.GovernedFixtureRunner.cancel_request_c9d980")}</button></div>
      </article>
      <article><h3>{t("core.GovernedFixtureRunner.4_receipt_and_verification_b35599")}</h3>
        <p className={success ? 'gex-success' : 'gex-warning'} role="status">{success ? t("core.GovernedFixtureRunner.fixture_result_verified_by_the_backend_with_8faff0") : t("core.GovernedFixtureRunner.no_verified_execution_result_08f253")}</p>
        <dl>{Object.entries(view.integrity).map(([key, value]) => <div key={key}><dt>{integrityLabel(key)} <code>{key}</code></dt><dd>{verifiedLabel(value)}</dd></div>)}</dl>
        <p>{t("core.GovernedFixtureRunner.the_backend_verifies_signatures_and_the_chain_41fee3")}</p>
        <details><summary>{t("core.GovernedFixtureRunner.signed_approval_6cdf72")}</summary><pre>{json(view.approval)}</pre></details><details><summary>{t("core.GovernedFixtureRunner.signed_permit_0c55a4")}</summary><pre>{json(view.permit)}</pre></details>
        {view.receipt ? <><dl><dt>{t("core.GovernedFixtureRunner.receipt_id_ffda10")}</dt><dd>{view.receipt.receipt_id}</dd><dt>{t("core.GovernedFixtureRunner.attempt_permit_f7f7c0")}</dt><dd>{view.receipt.attempt_id || t('agents.aux.GovernedFixtureRunner.no_registrado')} / {view.receipt.permit_id || t('agents.aux.GovernedFixtureRunner.no_registrado')}</dd>
          <dt>{t("core.GovernedFixtureRunner.expected_fixture_hash_a430c7")}</dt><dd>{fixtureSha}</dd><dt>{t("core.GovernedFixtureRunner.executor_hash_736253")}</dt><dd>{view.receipt.executor_output_sha256 || t('agents.aux.GovernedFixtureRunner.no_registrado')}</dd><dt>{t("core.GovernedFixtureRunner.independent_observer_hash_f4b007")}</dt><dd>{view.receipt.observed_sha256 || t('agents.aux.GovernedFixtureRunner.no_registrado')}</dd><dt>{t("core.GovernedFixtureRunner.persisted_afc7e5")}</dt><dd>{view.receipt.persisted_at}</dd></dl>
          <details><summary>{t("core.GovernedFixtureRunner.complete_receipt_and_synthetic_output_a1df4d")}</summary><pre>{json(view.receipt)}</pre></details></> : <p>{t("core.GovernedFixtureRunner.no_persisted_receipt_is_available_36bb53")}</p>}
        {view.error ? <p className="gex-warning">{t("core.GovernedFixtureRunner.result_code_648154")}{' '}{/^[A-Z0-9_]{1,80}$/.test(view.error.code) ? view.error.code : 'ERROR'}</p> : null}
      </article>
      <article><h3>{t("core.GovernedFixtureRunner.durable_trace_a3cb91")}</h3>{view.events.length ? <ol>{view.events.map(e => <li key={`${e.seq}-${e.event_id}`}><strong>{e.seq} · {e.kind}</strong> · {e.timestamp}<details><summary>{e.event_id}</summary><pre>{json(e)}</pre></details></li>)}</ol> : <p>{t("core.GovernedFixtureRunner.no_events_were_recovered_605d0c")}</p>}</article>
    </>}
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

function integrityLabel(key: string): string {
  switch(key) {
    case 'request_digest_valid': return t('agents.aux.gex.integrity.request_digest_valid')
    case 'event_chain_valid': return t('agents.aux.gex.integrity.event_chain_valid')
    case 'approval_signature_valid': return t('agents.aux.gex.integrity.approval_signature_valid')
    case 'permit_signature_valid': return t('agents.aux.gex.integrity.permit_signature_valid')
    case 'receipt_verified': return t('agents.aux.gex.integrity.receipt_verified')
    default: return t('agents.aux.context.technical')
  }
}
