import './OntologyReview.css'
import { useState } from 'react'

type Relation = { proposal_id: string; type?: string; subject?: string; predicate?: string; object?: string; source?: string; target?: string; source_id?: string; target_id?: string; evidence_line?: string | number; evidence?: { line?: string | number; line_number?: number; text?: string; excerpt?: string; source_path?: string; source_sha256?: string }; validator?: { valid?: boolean; status?: string; errors?: string[]; reason?: string | null } | string; validation?: { valid?: boolean; status?: string; errors?: string[]; reason?: string | null } }
type Proposal = { proposal_id: string; source?: { path?: string; sha256?: string }; entities?: Array<{ id?: string; name?: string; type?: string }>; relations?: Relation[]; proposed_relations?: Relation[]; receipt?: { receipt_id?: string }; proposal_receipt?: { receipt_id?: string }; trace?: { trace_id?: string }; trace_id?: string }
type Approval = { accepted_ids?: string[]; accepted_proposal_ids?: string[]; graph_fingerprint?: string; receipt?: { receipt_id?: string }; approval_receipt?: { receipt_id?: string }; trace?: { trace_id?: string }; trace_id?: string }
type QueryResult = { explicit_paths?: unknown[]; inferred_paths?: unknown[]; paths?: unknown[]; inferred?: unknown[]; inferences?: unknown[]; contradictions?: unknown[]; violations?: unknown[]; evidence_refs?: unknown[]; source_refs?: unknown[]; graph_fingerprint?: string; receipt?: { receipt_id?: string }; trace?: { trace_id?: string }; receipt_id?: string; trace_id?: string }

async function errorMessage(response: Response) {
  if (response.status === 404 || response.status === 405) return 'Ontology review is not supported by this backend.'
  try { const body = await response.json(); if (typeof body?.detail === 'string') return body.detail; if (typeof body?.detail?.message === 'string') return body.detail.message } catch { /* use status */ }
  return `Request failed (${response.status}).`
}
function identity(obj: { receipt?: { receipt_id?: string }; proposal_receipt?: { receipt_id?: string }; approval_receipt?: { receipt_id?: string }; trace?: { trace_id?: string }; trace_id?: string; receipt_id?: string }) {
  return { receipt: obj.receipt?.receipt_id || obj.proposal_receipt?.receipt_id || obj.approval_receipt?.receipt_id || obj.receipt_id, trace: obj.trace?.trace_id || obj.trace_id }
}
function dump(value: unknown) { return typeof value === 'string' ? value : JSON.stringify(value, null, 2) }

export default function OntologyReview() {
  const [path, setPath] = useState('')
  const [question, setQuestion] = useState('')
  const [proposal, setProposal] = useState<Proposal | null>(null)
  const [selected, setSelected] = useState<string[]>([])
  const [approval, setApproval] = useState<Approval | null>(null)
  const [queryResult, setQueryResult] = useState<QueryResult | null>(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [queryError, setQueryError] = useState('')
  const relations = proposal?.relations || proposal?.proposed_relations || []

  const propose = async (event: React.FormEvent) => {
    event.preventDefault(); if (!path.trim() || busy) return
    setBusy(true); setError(''); setProposal(null); setSelected([]); setApproval(null); setQueryResult(null)
    try {
      const response = await fetch('/api/ontology/proposals', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ path: path.trim() }) })
      if (!response.ok) throw new Error(await errorMessage(response))
      const body = await response.json() as Proposal
      if (!body || typeof body.proposal_id !== 'string' || !body.source || typeof body.source.path !== 'string' || typeof body.source.sha256 !== 'string' || !Array.isArray(body.relations || body.proposed_relations)) throw new Error('The backend returned an incomplete proposal record. No approval is available.')
      setProposal(body)
    } catch (cause) { setError(cause instanceof Error ? cause.message : 'Proposal request failed.') }
    finally { setBusy(false) }
  }
  const approve = async () => {
    if (!proposal || !selected.length || busy) return
    setBusy(true); setError(''); setApproval(null); setQueryResult(null)
    try {
      const response = await fetch(`/api/ontology/proposals/${encodeURIComponent(proposal.proposal_id)}/approve`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ proposal_ids: selected }) })
      if (!response.ok) throw new Error(await errorMessage(response))
      const body = await response.json() as Approval
      const accepted = body.accepted_ids || body.accepted_proposal_ids
      if (!Array.isArray(accepted) || accepted.length === 0 || typeof body.graph_fingerprint !== 'string') throw new Error('The backend returned an incomplete approval record. No accepted state is shown.')
      if (accepted.length !== selected.length || selected.some(id => !accepted.includes(id))) throw new Error('The backend approval IDs did not match the exact IDs selected. No accepted state is shown.')
      setApproval(body)
    } catch (cause) { setError(cause instanceof Error ? cause.message : 'Approval request failed.') }
    finally { setBusy(false) }
  }
  const query = async (event: React.FormEvent) => {
    event.preventDefault(); if (!question.trim() || busy) return
    setBusy(true); setQueryError(''); setQueryResult(null)
    try {
      const response = await fetch('/api/ontology/query', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ query: question.trim() }) })
      if (!response.ok) throw new Error(await errorMessage(response))
      const body = await response.json() as QueryResult
      if (!body || typeof body.graph_fingerprint !== 'string' || !Array.isArray(body.explicit_paths || body.paths) || !Array.isArray(body.inferred_paths || body.inferred || body.inferences) || !Array.isArray(body.contradictions || body.violations)) throw new Error('The backend returned an incomplete graph query record.')
      setQueryResult(body)
    } catch (cause) { setQueryError(cause instanceof Error ? cause.message : 'Graph query failed.') }
    finally { setBusy(false) }
  }

  return <section className="ontology-review" aria-labelledby="ontology-review-title">
    <header><p className="section-eyebrow">Knowledge graph · local rules</p><h2 id="ontology-review-title">Review relations and query evidence</h2><p>Choose one project-relative Markdown or text file. Proposals stay unaccepted until you select passing IDs and approve them.</p></header>
    <p className="ontology-limit"><strong>Scope:</strong> deterministic relation extraction and bounded reasoning; approval does not independently establish that a relation is true. The accepted graph is local to this checkout.</p>
    <form onSubmit={(event) => void propose(event)} aria-label="Propose relations from a local source">
      <label>Project-relative file path<input aria-label="Relation source file path" required value={path} onChange={event => setPath(event.target.value)} placeholder="docs/knowledge.md" disabled={busy} /></label>
      <button type="submit" disabled={busy || !path.trim()}>{busy ? 'Reading source…' : 'Read source and propose relations'}</button>
    </form>
    {busy && <p role="status">Processing the requested local graph operation…</p>}{error && <p role="alert">{error}</p>}
    {proposal && <section className="ontology-card" aria-label="Relation proposal review"><h3>Proposal review</h3><dl><div><dt>Proposal ID</dt><dd><code>{proposal.proposal_id}</code></dd></div><div><dt>Source</dt><dd>{proposal.source?.path}</dd></div><div><dt>Source SHA-256</dt><dd><code>{proposal.source?.sha256}</code></dd></div><div><dt>Proposal receipt</dt><dd>{identity(proposal).receipt || 'Unavailable in backend response'}</dd></div><div><dt>Trace</dt><dd>{identity(proposal).trace || 'Unavailable in backend response'}</dd></div></dl>
      {relations.length === 0 ? <p role="status">The backend returned no relation proposals. Nothing can be approved.</p> : <ul className="ontology-relations">{relations.map((relation) => { const validation = relation.validator || relation.validation; const valid = typeof validation === 'string' ? validation.toLowerCase() === 'valid' || validation.toLowerCase() === 'pass' : validation?.valid === true || ['valid', 'pass'].includes(validation?.status?.toLowerCase() || ''); const line = relation.evidence_line ?? relation.evidence?.line_number ?? relation.evidence?.line; const quote = typeof relation.evidence?.line === 'string' ? relation.evidence.line : relation.evidence?.text ?? relation.evidence?.excerpt; const validationReason = typeof validation === 'object' ? validation?.reason : undefined; return <li key={relation.proposal_id}><label><input type="checkbox" checked={selected.includes(relation.proposal_id)} disabled={busy || !valid} onChange={event => setSelected(current => event.target.checked ? [...current, relation.proposal_id] : current.filter(id => id !== relation.proposal_id))} />Select proposal {relation.proposal_id}</label><p><strong>{relation.subject || relation.source || relation.source_id || 'Endpoint unavailable'}</strong> — {relation.type || relation.predicate || 'Relation type unavailable'} → <strong>{relation.object || relation.target || relation.target_id || 'Endpoint unavailable'}</strong></p><p>Validator: <strong>{valid ? 'PASS' : (typeof validation === 'string' ? validation : validation?.status || 'Unavailable')}</strong>{validationReason ? ` · ${validationReason}` : ''}</p><p>Evidence {relation.evidence?.source_path ? `from ${relation.evidence.source_path}, ` : ''}line {line ?? 'unavailable'}{quote ? `: ${quote}` : ''}{relation.evidence?.source_sha256 ? ` · SHA-256 ${relation.evidence.source_sha256}` : ''}</p>{typeof validation === 'object' && validation?.errors?.length ? <ul>{validation.errors.map((item, i) => <li key={i}>{item}</li>)}</ul> : null}</li> })}</ul>}
      <button type="button" onClick={() => void approve()} disabled={busy || !selected.length}>{busy ? 'Saving approval…' : 'Approve selected exact proposal IDs'}</button>
      {approval && <section className="ontology-accepted" aria-label="Accepted graph state"><h4>Accepted state returned by backend</h4><p>Accepted IDs: {(approval.accepted_ids || approval.accepted_proposal_ids || []).join(', ')}</p><p>Graph fingerprint: <code>{approval.graph_fingerprint}</code></p><p>Approval receipt: {identity(approval).receipt || 'Unavailable in backend response'}</p><p>Trace: {identity(approval).trace || 'Unavailable in backend response'}</p></section>}
    </section>}
    <form className="ontology-query" onSubmit={event => void query(event)} aria-label="Query the accepted local graph"><h3>Query accepted graph</h3><label>Graph question<textarea required value={question} onChange={event => setQuestion(event.target.value)} rows={2} disabled={busy} placeholder="What relations connect these entities?" /></label><button type="submit" disabled={busy || !question.trim()}>{busy ? 'Querying…' : 'Query graph'}</button></form>
    {queryError && <p role="alert">{queryError}</p>}
    {queryResult && <section className="ontology-card" aria-label="Graph query result"><h3>Graph query result</h3><p>Graph fingerprint: <code>{queryResult.graph_fingerprint}</code></p><p>Receipt: {identity(queryResult).receipt || 'Unavailable in backend response'} · Trace: {identity(queryResult).trace || 'Unavailable in backend response'}</p><h4>Explicit paths</h4><pre>{dump(queryResult.explicit_paths || queryResult.paths)}</pre><h4>Inferred paths</h4><pre>{dump(queryResult.inferred_paths || queryResult.inferred || queryResult.inferences)}</pre><h4>Contradictions</h4><pre>{dump(queryResult.contradictions || queryResult.violations)}</pre><h4>Source evidence references</h4><pre>{dump(queryResult.evidence_refs || queryResult.source_refs || 'Unavailable in backend response')}</pre></section>}
  </section>
}
