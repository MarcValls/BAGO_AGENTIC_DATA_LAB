// @vitest-environment jsdom
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { act, cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import GovernedFixtureRunner, { type GexRequestView, readGexView, reviewableGex, verifiedGexSuccess } from '../../../src/components/GovernedFixtureRunner'

const h = 'a'.repeat(64)
const fixture = 'adl.synthetic.customer-summary.v1'
const expectedSha = '1ae8dee0e30cde63635ef7696020d1d8ff731346660ff8b1be8bca4ad82cdb7d'
const expires = () => new Date(Date.now() + 240000).toISOString()
function pending(): GexRequestView {
  return {
    contract_version: 'gex-runtime/v1', request_id: 'request-1', run_id: 'run-1', proposal_id: 'proposal-1', state: 'AWAITING_APPROVAL', task: 'Lee fixture',
    provider: { provider_id: 'ollama', model_id: 'real-model-configured' },
    proposal: { tool_name: 'fixture.read', arguments: { fixture_id: fixture }, proposal_digest: h },
    request: { contract_version: 'gex-request/v1', request_id: 'request-1', run_id: 'run-1', proposal_id: 'proposal-1',
      principal: { subject: 'principal_demo', issuer: 'local', auth_strength: 'verified', session_binding: h }, agent: { agent_id: 'agent_demo', config_digest: h, revision: h },
      workspace: { workspace_id: 'workspace_demo', binding_fingerprint: h, repository_identity: 'controlled-local', branch: 'main', commit_sha: 'f'.repeat(40), context_revision: h, root_identity: h },
      capability: { id: 'fixture.read', version: '1', registry_digest: h, schema_digest: h, executor_kind: 'local', effect: 'READ' },
      operation: { arguments: { fixture_id: fixture }, target: 'registered-immutable-fixture', effect_scope: 'read:fixture:sample' },
      constraints: { network: 'deny', write_scope: 'none', sandbox_profile: 'read_only_agent', timeout_ms: 1000, max_output_bytes: 65536, egress_allowlist: [] },
      policy: { revision: 'gex-fixture-human-v1', policy_digest: h }, context_revision: h, proposed_at: new Date().toISOString(), expires_at: expires(), nonce: 'random'
    }, request_digest: h,
    policy_decision: { result: 'REQUIRE_HUMAN', request_digest: h, decision_id: 'decision-1' }, approval: null, permit: null, receipt: null,
    events: [{ event_id: 'event-proposed', seq: 1, kind: 'PROPOSED', request_id: 'request-1', request_digest: h, timestamp: new Date().toISOString(), prev_hash: null, event_digest: h, attempt_id: null, permit_id: null, payload_ref: 'proposal-1' }],
    integrity: { request_digest_valid: true, event_chain_valid: true, approval_signature_valid: null, permit_signature_valid: null, receipt_verified: false }, error: null, synthetic: true
  }
}
function complete(): GexRequestView {
  const v = pending(); v.state = 'SUCCEEDED'
  v.approval = { contract_version: 'gex-approval/v1', approval_id: 'approval-1', request_digest: h, decision: 'APPROVED', signature_algorithm: 'Ed25519', signature: 'a'.repeat(86), workspace_binding_fingerprint: h, decision_id: 'decision-1', principal_subject: 'principal_demo', actor: 'principal_demo', operation_summary_digest: h, auth_context_ref: h, evidence_ref: 'decision-1', key_id: 'key-1' }
  v.permit = { contract_version: 'gex-permit/v1', permit_id: 'permit-1', request_digest: h, authorization_source: { approval_id: 'approval-1', decision_id: 'decision-1', auto_rule_id: null }, signature_algorithm: 'Ed25519', signature: 'a'.repeat(86), agent_id: 'agent_demo', workspace_binding_fingerprint: h, agent_config_digest: h, principal_subject: 'principal_demo', session_binding: h, capability_id: 'fixture.read', capability_version: '1', max_uses: 1, registry_digest: h }
  v.receipt = { receipt_id: 'receipt-1', request_digest: h, attempt_id: 'attempt-1', permit_id: 'permit-1', status: 'SUCCESS', verification_state: 'VERIFIED_SUCCESS', verification_result_id: 'verification-1', observed_sha256: expectedSha, executor_output_sha256: expectedSha, fixture_id: fixture, synthetic: true, output: '{"customer_id":"fixture-customer-001","status":"synthetic","open_invoice_count":2}\n', sandbox_receipt: { receipt_id: 'sandbox-1' }, persisted_at: new Date().toISOString(), evidence_refs: ['receipt-1'], error_code: null }
  v.integrity = { request_digest_valid: true, event_chain_valid: true, approval_signature_valid: true, permit_signature_valid: true, receipt_verified: true }
  for (const kind of ['DISPATCH_INTENT', 'RECEIPT_PERSISTED']) v.events.push({ ...v.events[0], kind, seq: v.events.length + 1, event_id: `event-${kind}`, attempt_id: 'attempt-1', permit_id: 'permit-1' })
  return v
}
const response = (data: unknown, status = 200) => Promise.resolve(new Response(JSON.stringify(data), { status, headers: { 'Content-Type': 'application/json' } }))
let fetcher: ReturnType<typeof vi.fn>
let calls: Array<{ url: string; init?: RequestInit }>
beforeEach(() => {
  calls = []
  fetcher = vi.fn((url: string, init?: RequestInit) => { calls.push({ url, init });
    if (url.endsWith('/status')) return response({ state: 'READY', synthetic: true, capability_id: 'fixture.read', contract_version: 'gex-runtime/v1' })
    if (url.endsWith('/sessions') && init?.method === 'POST') return response({ session_id: 'session-1', session_token: 'secret-session', principal_id: 'principal_demo', workspace_id: 'workspace_demo', agent_id: 'agent_demo', issued_at: new Date().toISOString(), expires_at: expires() }, 201)
    if (url.endsWith('/sessions/current')) return response({ status: 'REVOKED', session_id: 'session-1' })
    if (url.endsWith('/decision')) return response(complete())
    if (url.endsWith('/requests')) return response(pending(), 201)
    return response(pending())
  })
  vi.stubGlobal('fetch', fetcher)
})
afterEach(() => { cleanup(); vi.useRealTimers(); vi.restoreAllMocks(); vi.unstubAllGlobals() })
async function login() {
  render(<GovernedFixtureRunner apiBase="http://localhost:8081" agentId="agent_demo" />)
  await waitFor(() => expect(screen.getByRole('button', { name: 'Crear sesión' }).hasAttribute('disabled')).toBe(true))
  await screen.findByText('Disponibilidad: READY')
  fireEvent.change(screen.getByLabelText('Clave de operador'), { target: { value: 'secret-operator' } })
  fireEvent.click(screen.getByRole('button', { name: 'Crear sesión' }))
  await screen.findByRole('button', { name: 'Revocar y borrar sesión' })
}
async function propose() { await login(); fireEvent.click(screen.getByRole('button', { name: 'Solicitar propuesta' })); await screen.findByText('AWAITING_APPROVAL') }

describe('GEX UI consistency guards (deterministic simulated API)', () => {
  it('requires exact request envelope and backend-verified full authority/receipt binding', () => {
    expect(reviewableGex(pending(), 'agent_demo')).toBe(true)
    expect(verifiedGexSuccess(complete(), 'agent_demo')).toBe(true)
    const mutations: Array<(v: GexRequestView) => void> = [
      v => { v.receipt = null }, v => { v.receipt!.attempt_id = 'foreign' }, v => { v.receipt!.permit_id = 'foreign' },
      v => { v.receipt!.request_digest = 'b'.repeat(64) }, v => { v.receipt!.observed_sha256 = 'b'.repeat(64) }, v => { v.receipt!.executor_output_sha256 = 'b'.repeat(64) },
      v => { v.receipt!.output = 'forged' }, v => { v.integrity.approval_signature_valid = null }, v => { v.integrity.permit_signature_valid = false },
      v => { v.integrity.event_chain_valid = false }, v => { v.integrity.receipt_verified = false }, v => { v.integrity.request_digest_valid = null },
      v => { v.approval!.request_digest = 'b'.repeat(64) }, v => { v.permit!.request_digest = 'b'.repeat(64) }, v => { v.permit!.agent_id = 'other' },
      v => { v.permit!.workspace_binding_fingerprint = 'b'.repeat(64) }, v => { v.permit!.authorization_source = {} },
      v => { v.request!.constraints = { network: 'allow', write_scope: 'any' } }, v => { v.events = [] }, v => { delete v.request!.nonce }
    ]
    for (const mutate of mutations) { const v = complete(); mutate(v); expect(verifiedGexSuccess(v, 'agent_demo')).toBe(false) }
    expect(readGexView({ state: 'SUCCEEDED' })).toBeNull()
  })
  it('sends auth only in headers, exact task/decision bodies and displays review and durable verified receipt', async () => {
    const storage = vi.spyOn(Storage.prototype, 'setItem')
    await propose()
    expect(screen.queryByDisplayValue('secret-operator')).toBeNull()
    for (const label of ['Workspace vinculado', 'Restricciones efectivas', 'Caducidad', 'Argumentos y alcance exactos', 'Digest de solicitud completa', 'Política y decisión']) expect(screen.getByText(label)).toBeTruthy()
    const create = calls.find(c => c.url.endsWith('/sessions'))!
    expect(JSON.parse(String(create.init?.body))).toEqual({ agent_id: 'agent_demo' })
    expect((create.init?.headers as Record<string, string>).Authorization).toBe('Bearer secret-operator')
    const p = calls.find(c => c.url.endsWith('/requests'))!
    expect((p.init?.headers as Record<string, string>)['X-GEX-Agent-ID']).toBe('agent_demo')
    expect((p.init?.headers as Record<string, string>).Authorization).toBe('Bearer secret-session')
    expect(Object.keys(JSON.parse(String(p.init?.body)))).toEqual(['task'])
    fireEvent.click(screen.getByRole('button', { name: 'Aprobar solicitud exacta y ejecutar ahora' }))
    await screen.findByText('Resultado de fixture VERIFICADO por el backend y vinculaciones comprobadas en esta vista.')
    const d = calls.find(c => c.url.endsWith('/decision'))!
    expect(JSON.parse(String(d.init?.body))).toEqual({ request_digest: h, decision: 'APPROVED', reason: 'Apruebo la solicitud exacta mostrada y su ejecución ahora.' })
    expect(screen.getByText('receipt-1')).toBeTruthy()
    expect(storage).not.toHaveBeenCalled()
    for (const c of calls) { expect(c.url).not.toContain('secret'); expect(c.init?.body || '').not.toContain('secret') }
    expect(window.location.href).not.toContain('secret')
  })
  it.each(['REJECTED', 'CANCELLED'] as const)('persists explicit %s decision without a success claim', async decision => {
    await propose(); fetcher.mockImplementationOnce((_url: string, init: RequestInit) => { const v = pending(); v.state = decision; expect(JSON.parse(String(init.body)).decision).toBe(decision); return response(v) })
    fireEvent.click(screen.getByRole('button', { name: decision === 'REJECTED' ? 'Rechazar' : 'Cancelar solicitud' }))
    await screen.findByText(decision)
    expect(screen.getByText('Sin resultado de ejecución verificado.')).toBeTruthy()
  })
  it('blocks duplicate decisions while awaiting the server and blocks retry after timeout/transport failure', async () => {
    await propose(); let reject!: (e: Error) => void
    fetcher.mockImplementationOnce(() => new Promise((_resolve, r) => { reject = r }))
    const button = screen.getByRole('button', { name: 'Aprobar solicitud exacta y ejecutar ahora' })
    fireEvent.click(button); fireEvent.click(button)
    expect(calls.filter(c => c.url.endsWith('/decision'))).toHaveLength(0) // override records separately below
    expect(fetcher.mock.calls.filter(c => String(c[0]).endsWith('/decision'))).toHaveLength(1)
    reject(new TypeError('transport failure containing secret-session'))
    await screen.findByRole('alert')
    expect(button.hasAttribute('disabled')).toBe(true)
    expect(screen.getByRole('alert').textContent).not.toContain('secret')
    fireEvent.click(screen.getByRole('button', { name: 'Recargar estado durable' }))
    await waitFor(() => expect(button.hasAttribute('disabled')).toBe(false))
    const read = calls.find(c => c.url.endsWith('/requests/request-1'))!
    expect(read.init?.method).toBe('GET')
    expect(fetcher.mock.calls.filter(c => String(c[0]).endsWith('/decision'))).toHaveLength(1)
  })
  it('treats a real abort timeout as uncertain and never retries approval automatically', async () => {
    await propose(); vi.useFakeTimers()
    fetcher.mockImplementationOnce((_url: string, init: RequestInit) => new Promise((_resolve, reject) => {
      init.signal!.addEventListener('abort', () => reject(new DOMException('aborted', 'AbortError')))
    }))
    fireEvent.click(screen.getByRole('button', { name: 'Aprobar solicitud exacta y ejecutar ahora' }))
    expect(screen.getByText('Esperando al servicio…')).toBeTruthy()
    await act(async () => { await vi.advanceTimersByTimeAsync(30001) })
    expect(screen.getByRole('alert').textContent).toContain('tiempo agotado')
    expect(screen.getByRole('button', { name: 'Aprobar solicitud exacta y ejecutar ahora' }).hasAttribute('disabled')).toBe(true)
    expect(fetcher.mock.calls.filter(c => String(c[0]).endsWith('/decision'))).toHaveLength(1)
  })
  it.each(['expired', 'foreign', 'unsupported'] as const)('blocks approval for %s requests', async reason => {
    await login()
    fetcher.mockImplementationOnce(() => { const v = pending();
      if (reason === 'expired') v.request!.expires_at = new Date(Date.now() - 1000).toISOString()
      if (reason === 'foreign') v.request!.principal = { subject: 'foreign', issuer: 'local', auth_strength: 'verified', session_binding: h }
      if (reason === 'unsupported') v.request!.operation = { arguments: { fixture_id: 'arbitrary-file' }, target: 'registered-immutable-fixture', effect_scope: 'read:fixture:sample' }
      return response(v, 201)
    })
    fireEvent.click(screen.getByRole('button', { name: 'Solicitar propuesta' }))
    await screen.findByText('AWAITING_APPROVAL')
    expect(screen.getByRole('button', { name: 'Aprobar solicitud exacta y ejecutar ahora' }).hasAttribute('disabled')).toBe(true)
  })
  it.each([401, 409, 503])('renders HTTP %s without synthesizing persistence or success', async code => {
    await propose()
    fetcher.mockImplementationOnce(() => response({ detail: { code: code === 401 ? 'AUTH_INVALID' : code === 409 ? 'PERMIT_REPLAY' : 'STORE_UNAVAILABLE_FAIL_CLOSED', message: 'secret-session', persisted: false } }, code))
    fireEvent.click(screen.getByRole('button', { name: 'Aprobar solicitud exacta y ejecutar ahora' }))
    await screen.findByRole('alert')
    expect(screen.getByRole('alert').textContent).toContain('Sin persistencia confirmada')
    expect(screen.getByRole('alert').textContent).not.toContain('secret-session')
    if (code === 401) expect(screen.getByLabelText('Clave de operador')).toBeTruthy()
    expect(screen.getByRole('button', { name: 'Aprobar solicitud exacta y ejecutar ahora' }).hasAttribute('disabled')).toBe(true)
  })
  it.each(['missing', 'mismatch', 'integrity'] as const)('renders an unverified result for %s receipt evidence', async failure => {
    await propose()
    fetcher.mockImplementationOnce(() => { const v = complete(); if (failure === 'missing') v.receipt = null; if (failure === 'mismatch') v.receipt!.observed_sha256 = h; if (failure === 'integrity') v.integrity.permit_signature_valid = null; return response(v) })
    fireEvent.click(screen.getByRole('button', { name: 'Aprobar solicitud exacta y ejecutar ahora' }))
    await screen.findByText('SUCCEEDED')
    expect(screen.getByText('Sin resultado de ejecución verificado.')).toBeTruthy()
    expect(screen.queryByText(/^Resultado de fixture VERIFICADO/)).toBeNull()
  })
  it('clears session locally even when revoke fails and attempts revoke on unmount', async () => {
    await login(); fetcher.mockImplementationOnce(() => response({ detail: { code: 'STORE_UNAVAILABLE_FAIL_CLOSED', persisted: false } }, 503))
    fireEvent.click(screen.getByRole('button', { name: 'Revocar y borrar sesión' }))
    await screen.findByLabelText('Clave de operador')
    expect((screen.getByLabelText('Clave de operador') as HTMLInputElement).value).toBe('')
    cleanup(); await login(); cleanup()
    expect(calls.some(c => c.url.endsWith('/sessions/current') && c.init?.keepalive === true)).toBe(true)
  })
  it('keeps unavailable and malformed responses closed and rejects mismatched recovered ID', async () => {
    await propose()
    fireEvent.change(screen.getByLabelText('ID de solicitud para recuperar'), { target: { value: 'different' } })
    fireEvent.click(screen.getByRole('button', { name: 'Recargar estado durable' }))
    await screen.findByRole('alert')
    expect(screen.getByRole('button', { name: 'Aprobar solicitud exacta y ejecutar ahora' }).hasAttribute('disabled')).toBe(true)
    cleanup()
    fetcher.mockImplementationOnce(() => response({ state: 'READY' }))
    render(<GovernedFixtureRunner />)
    await screen.findByText('Disponibilidad: Respuesta de disponibilidad no válida')
    expect(screen.getByRole('button', { name: 'Crear sesión' }).hasAttribute('disabled')).toBe(true)
  })
})
