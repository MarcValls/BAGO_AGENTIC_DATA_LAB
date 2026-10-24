import {useI18n,t,localMessage,errorMessage,apiError,formatDate,formatNumber} from '../i18n'
import './OntologyReview.css'
import { useState } from 'react'

type Relation = { proposal_id: string; type?: string; subject?: string; predicate?: string; object?: string; source?: string; target?: string; source_id?: string; target_id?: string; evidence_line?: string | number; evidence?: { line?: string | number; line_number?: number; text?: string; excerpt?: string; source_path?: string; source_sha256?: string }; validator?: { valid?: boolean; status?: string; errors?: string[]; reason?: string | null } | string; validation?: { valid?: boolean; status?: string; errors?: string[]; reason?: string | null } }
type Proposal = { proposal_id: string; source?: { path?: string; sha256?: string }; entities?: Array<{ id?: string; name?: string; type?: string }>; relations?: Relation[]; proposed_relations?: Relation[]; receipt?: { receipt_id?: string }; proposal_receipt?: { receipt_id?: string }; trace?: { trace_id?: string }; trace_id?: string }
type Approval = { accepted_ids?: string[]; accepted_proposal_ids?: string[]; graph_fingerprint?: string; receipt?: { receipt_id?: string }; approval_receipt?: { receipt_id?: string }; trace?: { trace_id?: string }; trace_id?: string }
type QueryResult = { explicit_paths?: unknown[]; inferred_paths?: unknown[]; paths?: unknown[]; inferred?: unknown[]; inferences?: unknown[]; contradictions?: unknown[]; violations?: unknown[]; evidence_refs?: unknown[]; source_refs?: unknown[]; graph_fingerprint?: string; receipt?: { receipt_id?: string }; trace?: { trace_id?: string }; receipt_id?: string; trace_id?: string }

async function requestError(response: Response): Promise<Error> {
  if (response.status === 404 || response.status === 405) return localMessage('core.OntologyReview.ontology_review_is_not_supported_by_this_fc0e8c')
  const body = await response.json().catch(() => null)
  return apiError(body,response.status,'agents')
}

function identity(obj: { receipt?: { receipt_id?: string }; proposal_receipt?: { receipt_id?: string }; approval_receipt?: { receipt_id?: string }; trace?: { trace_id?: string }; trace_id?: string; receipt_id?: string }) {
  return { receipt: obj.receipt?.receipt_id || obj.proposal_receipt?.receipt_id || obj.approval_receipt?.receipt_id || obj.receipt_id, trace: obj.trace?.trace_id || obj.trace_id }
}
function dump(value: unknown) { return typeof value === 'string' ? value : JSON.stringify(value, null, 2) }

export default function OntologyReview() {
  useI18n()

  const [path, setPath] = useState('')
  const [question, setQuestion] = useState('')
  const [proposal, setProposal] = useState<Proposal | null>(null)
  const [selected, setSelected] = useState<string[]>([])
  const [approval, setApproval] = useState<Approval | null>(null)
  const [queryResult, setQueryResult] = useState<QueryResult | null>(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<any>('')
  const [queryError, setQueryError] = useState<any>('')
  const relations = proposal?.relations || proposal?.proposed_relations || []

  const propose = async (event: React.FormEvent) => {
    event.preventDefault(); if (!path.trim() || busy) return
    setBusy(true); setError(''); setProposal(null); setSelected([]); setApproval(null); setQueryResult(null)
    try {
      const response = await fetch('/api/ontology/proposals', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ path: path.trim() }) })
      if (!response.ok) throw await requestError(response)
      const body = await response.json() as Proposal
      if (!body || typeof body.proposal_id !== 'string' || !body.source || typeof body.source.path !== 'string' || typeof body.source.sha256 !== 'string' || !Array.isArray(body.relations || body.proposed_relations)) throw localMessage("core.OntologyReview.the_backend_returned_an_incomplete_proposal_record_81375e")
      setProposal(body)
    } catch (cause) { setError(cause instanceof Error ? cause : localMessage('agents.aux.OntologyReview.proposal_request_failed')) }
    finally { setBusy(false) }
  }
  const approve = async () => {
    if (!proposal || !selected.length || busy) return
    setBusy(true); setError(''); setApproval(null); setQueryResult(null)
    try {
      const response = await fetch(`/api/ontology/proposals/${encodeURIComponent(proposal.proposal_id)}/approve`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ proposal_ids: selected }) })
      if (!response.ok) throw await requestError(response)
      const body = await response.json() as Approval
      const accepted = body.accepted_ids || body.accepted_proposal_ids
      if (!Array.isArray(accepted) || accepted.length === 0 || typeof body.graph_fingerprint !== 'string') throw localMessage("core.OntologyReview.the_backend_returned_an_incomplete_approval_record_4d304f")
      if (accepted.length !== selected.length || selected.some(id => !accepted.includes(id))) throw localMessage("core.OntologyReview.the_backend_approval_ids_did_not_match_3befd0")
      setApproval(body)
    } catch (cause) { setError(cause instanceof Error ? cause : localMessage('agents.aux.OntologyReview.approval_request_failed')) }
    finally { setBusy(false) }
  }
  const query = async (event: React.FormEvent) => {
    event.preventDefault(); if (!question.trim() || busy) return
    setBusy(true); setQueryError(''); setQueryResult(null)
    try {
      const response = await fetch('/api/ontology/query', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ query: question.trim() }) })
      if (!response.ok) throw await requestError(response)
      const body = await response.json() as QueryResult
      if (!body || typeof body.graph_fingerprint !== 'string' || !Array.isArray(body.explicit_paths || body.paths) || !Array.isArray(body.inferred_paths || body.inferred || body.inferences) || !Array.isArray(body.contradictions || body.violations)) throw localMessage("core.OntologyReview.the_backend_returned_an_incomplete_graph_query_4d7857")
      setQueryResult(body)
    } catch (cause) { setQueryError(cause instanceof Error ? cause : localMessage('agents.aux.OntologyReview.graph_query_failed')) }
    finally { setBusy(false) }
  }

  return <section className="ontology-review" aria-labelledby="ontology-review-title">
    <header><p className="section-eyebrow">{t("core.OntologyReview.knowledge_graph_local_rules_78f2b3")}</p><h2 id="ontology-review-title">{t("core.OntologyReview.review_relations_and_query_evidence_4e1ac6")}</h2><p>{t("core.OntologyReview.choose_one_project_relative_markdown_or_text_92b317")}</p></header>
    <p className="ontology-limit"><strong>{t("core.OntologyReview.scope_f0038a")}</strong>{' '}{t("core.OntologyReview.deterministic_relation_extraction_and_bounded_reasoning_approval_da2559")}</p>
    <form onSubmit={(event) => void propose(event)} aria-label={t("core.OntologyReview.propose_relations_from_a_local_source_7a92be")}>
      <label>{t("core.OntologyReview.project_relative_file_path_8c345b")}<input aria-label={t("core.OntologyReview.relation_source_file_path_84d4d8")} required value={path} onChange={event => setPath(event.target.value)} placeholder="docs/knowledge.md" disabled={busy} /></label>
      <button type="submit" disabled={busy || !path.trim()}>{busy ? t("core.OntologyReview.reading_source_8e9e4d") : t("core.OntologyReview.read_source_and_propose_relations_36e8e0")}</button>
    </form>
    {busy && <p role="status">{t("core.OntologyReview.processing_the_requested_local_graph_operation_23fdcc")}</p>}{error && <p role="alert">{errorMessage(error)}</p>}
    {proposal && <section className="ontology-card" aria-label={t("core.OntologyReview.relation_proposal_review_7f0963")}><h3>{t("core.OntologyReview.proposal_review_07ad08")}</h3><dl><div><dt>{t("core.OntologyReview.proposal_id_40bb3a")}</dt><dd><code>{proposal.proposal_id}</code></dd></div><div><dt>{t("core.OntologyReview.source_0e570c")}</dt><dd>{proposal.source?.path}</dd></div><div><dt>{t("core.OntologyReview.source_sha_256_982334")}</dt><dd><code>{proposal.source?.sha256}</code></dd></div><div><dt>{t("core.OntologyReview.proposal_receipt_849868")}</dt><dd>{identity(proposal).receipt || t('agents.aux.KnowledgeIngest.unavailable_in_backend_response')}</dd></div><div><dt>{t("core.OntologyReview.trace_7e14c3")}</dt><dd>{identity(proposal).trace || t('agents.aux.KnowledgeIngest.unavailable_in_backend_response')}</dd></div></dl>
      {relations.length === 0 ? <p role="status">{t("core.OntologyReview.the_backend_returned_no_relation_proposals_nothing_e7f9e4")}</p> : <ul className="ontology-relations">{relations.map((relation) => { const validation = relation.validator || relation.validation; const valid = typeof validation === 'string' ? validation.toLowerCase() === 'valid' || validation.toLowerCase() === 'pass' : validation?.valid === true || ['valid', 'pass'].includes(validation?.status?.toLowerCase() || ''); const line = relation.evidence_line ?? relation.evidence?.line_number ?? relation.evidence?.line; const quote = typeof relation.evidence?.line === 'string' ? relation.evidence.line : relation.evidence?.text ?? relation.evidence?.excerpt; const validationReason = typeof validation === 'object' ? validation?.reason : undefined; return <li key={relation.proposal_id}><label><input type="checkbox" checked={selected.includes(relation.proposal_id)} disabled={busy || !valid} onChange={event => setSelected(current => event.target.checked ? [...current, relation.proposal_id] : current.filter(id => id !== relation.proposal_id))} />{t("core.OntologyReview.select_proposal_9fe60c")}{' '}{relation.proposal_id}</label><p><strong>{relation.subject || relation.source || relation.source_id || t('agents.aux.OntologyReview.endpoint_unavailable')}</strong> — {relation.type || relation.predicate || t('agents.aux.OntologyReview.relation_type_unavailable')} → <strong>{relation.object || relation.target || relation.target_id || t('agents.aux.OntologyReview.endpoint_unavailable')}</strong></p><p>{t("core.OntologyReview.validator_8920ae")}{' '}<strong>{valid ? 'PASS' : (typeof validation === 'string' ? validation : validation?.status || t('agents.aux.KnowledgeIngest.unavailable'))}</strong>{validationReason ? ` · ${validationReason}` : ''}</p><p>{t("core.OntologyReview.evidence_03867a")}{' '}{relation.evidence?.source_path ? t('agents.aux.OntologyReview.from_p0',{p0:relation.evidence.source_path}) : ''}{t("core.OntologyReview.line_38a9c1")}{' '}{line ?? t('agents.aux.KnowledgeIngest.unavailable')}{quote ? `: ${quote}` : ''}{relation.evidence?.source_sha256 ? ` · SHA-256 ${relation.evidence.source_sha256}` : ''}</p>{typeof validation === 'object' && validation?.errors?.length ? <ul>{validation.errors.map((item, i) => <li key={i}>{item}</li>)}</ul> : null}</li> })}</ul>}
      <button type="button" onClick={() => void approve()} disabled={busy || !selected.length}>{busy ? t("core.OntologyReview.saving_approval_c74cd4") : t("core.OntologyReview.approve_selected_exact_proposal_ids_ee8cdd")}</button>
      {approval && <section className="ontology-accepted" aria-label={t("core.OntologyReview.accepted_graph_state_7eaa72")}><h4>{t("core.OntologyReview.accepted_state_returned_by_backend_f64cf6")}</h4><p>{t("core.OntologyReview.accepted_ids_c4ba4d")}{' '}{(approval.accepted_ids || approval.accepted_proposal_ids || []).join(', ')}</p><p>{t("core.OntologyReview.graph_fingerprint_2b1426")}{' '}<code>{approval.graph_fingerprint}</code></p><p>{t("core.OntologyReview.approval_receipt_4d50c3")}{' '}{identity(approval).receipt || t('agents.aux.KnowledgeIngest.unavailable_in_backend_response')}</p><p>{t("core.OntologyReview.trace_8f1f10")}{' '}{identity(approval).trace || t('agents.aux.KnowledgeIngest.unavailable_in_backend_response')}</p></section>}
    </section>}
    <form className="ontology-query" onSubmit={event => void query(event)} aria-label={t("core.OntologyReview.query_the_accepted_local_graph_ae6f04")}><h3>{t("core.OntologyReview.query_accepted_graph_2b4051")}</h3><label>{t("core.OntologyReview.graph_question_72b973")}<textarea required value={question} onChange={event => setQuestion(event.target.value)} rows={2} disabled={busy} placeholder={t("core.OntologyReview.what_relations_connect_these_entities_2bdc68")} /></label><button type="submit" disabled={busy || !question.trim()}>{busy ? t("core.OntologyReview.querying_419dc4") : t("core.OntologyReview.query_graph_121c4a")}</button></form>
    {queryError && <p role="alert">{errorMessage(queryError)}</p>}
    {queryResult && <section className="ontology-card" aria-label={t("core.OntologyReview.graph_query_result_2b7121")}><h3>{t("core.OntologyReview.graph_query_result_2b7121")}</h3><p>{t("core.OntologyReview.graph_fingerprint_2b1426")}{' '}<code>{queryResult.graph_fingerprint}</code></p><p>{t("core.OntologyReview.receipt_3783ba")}{' '}{identity(queryResult).receipt || t('agents.aux.KnowledgeIngest.unavailable_in_backend_response')}{' '}{t("core.OntologyReview.trace_68b8dd")}{' '}{identity(queryResult).trace || t('agents.aux.KnowledgeIngest.unavailable_in_backend_response')}</p><h4>{t("core.OntologyReview.explicit_paths_cffd9d")}</h4><pre>{dump(queryResult.explicit_paths || queryResult.paths)}</pre><h4>{t("core.OntologyReview.inferred_paths_d482b6")}</h4><pre>{dump(queryResult.inferred_paths || queryResult.inferred || queryResult.inferences)}</pre><h4>{t("core.OntologyReview.contradictions_c1c93b")}</h4><pre>{dump(queryResult.contradictions || queryResult.violations)}</pre><h4>{t("core.OntologyReview.source_evidence_references_98efc9")}</h4><pre>{dump(queryResult.evidence_refs || queryResult.source_refs || t('agents.aux.KnowledgeIngest.unavailable_in_backend_response'))}</pre></section>}
  </section>
}
