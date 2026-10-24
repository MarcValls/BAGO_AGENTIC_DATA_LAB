import {useI18n,t,localMessage,errorMessage,apiError,formatDate,formatNumber} from '../i18n'
import './KnowledgeIngest.css'
import { useState } from 'react'

type Authority = 'PROPOSED' | 'VERIFIED'
type EvidenceHit = {
  rank?: number
  chunk_id?: string
  document_id?: string
  score?: number
  evidence?: { chunk_id?: string; document_id?: string; source_uri?: string; revision?: string; citation?: string }
}
type GroundedRun = {
  run_id?: string
  status?: 'answered' | 'no_evidence' | 'failed'
  ingestion?: { receipt_id?: string; source_id?: string; source_path?: string; source_sha256?: string; source_revision?: string; source_authority?: Authority; minimum_authority?: Authority; index_fingerprint?: string; chunk_count?: number; idempotent?: boolean }
  retrieval?: { query?: string; index_fingerprint?: string; eligible_count?: number; filtered_count?: number; hits?: EvidenceHit[]; citations?: unknown[] }
  generation?: { provider_id?: string; model_id?: string; answer?: string } | null
  trace?: { trace_id?: string; path?: string; sha256?: string }
  error?: unknown
}

async function responseError(response: Response): Promise<Error> {
  const body = await response.json().catch(() => null)
  if ((response.status === 404 || response.status === 405) && !(typeof body?.detail === 'string' || typeof body?.detail?.message === 'string')) return localMessage('core.KnowledgeIngest.grounded_local_retrieval_is_not_supported_by_c2f17c')
  return apiError(body,response.status,'agents')
}

function sha(value: string | undefined): string {
  return value || t('agents.aux.KnowledgeIngest.unavailable_in_backend_response')
}

export default function KnowledgeIngest() {
  useI18n()

  const [path, setPath] = useState('')
  const [question, setQuestion] = useState('')
  const [sourceAuthority, setSourceAuthority] = useState<Authority>('PROPOSED')
  const [minimumAuthority, setMinimumAuthority] = useState<Authority>('PROPOSED')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<any>('')
  const [result, setResult] = useState<GroundedRun | null>(null)

  const submit = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    if (!path.trim() || !question.trim() || loading) return
    setLoading(true)
    setError('')
    setResult(null)
    try {
      const response = await fetch('/api/knowledge/ingest-and-answer', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ path: path.trim(), question: question.trim(), source_authority: sourceAuthority, minimum_authority: minimumAuthority }),
      })
      if (!response.ok) throw await responseError(response)
      const body = await response.json() as GroundedRun
      if (!body || !['answered', 'no_evidence', 'failed'].includes(body.status ?? '') || typeof body.run_id !== 'string'
        || typeof body.trace?.trace_id !== 'string' || typeof body.ingestion?.receipt_id !== 'string') {
        throw localMessage("core.KnowledgeIngest.the_backend_returned_an_incomplete_run_record_70b3e4")
      }
      if (body.status === 'answered' && (typeof body.generation?.answer !== 'string' || !Array.isArray(body.retrieval?.hits) || body.retrieval.hits.length === 0)) {
        throw localMessage("core.KnowledgeIngest.the_backend_returned_an_answer_without_linked_fd0021")
      }
      setResult(body)
      if (body.status === 'failed') setError(typeof body.error === 'string' ? apiError({detail:{message:body.error}},0,'agents') : localMessage('agents.aux.KnowledgeIngest.the_backend_recorded_a_failed_run'))
    } catch (cause) {
      setError(cause instanceof Error ? cause : localMessage('agents.aux.KnowledgeIngest.the_knowledge_request_could_not_be_completed'))
    } finally { setLoading(false) }
  }

  return <section className="knowledge-ingest" aria-labelledby="knowledge-ingest-title">
    <header><p className="section-eyebrow">{t("core.KnowledgeIngest.local_knowledge_one_file_6960f1")}</p><h2 id="knowledge-ingest-title">{t("core.KnowledgeIngest.index_a_source_and_ask_with_citations_e86734")}</h2>
      <p>{t("core.KnowledgeIngest.choose_one_project_relative_text_or_markdown_e4d7b4")}</p>
    </header>
    <p className="knowledge-authority-note"><strong>{t("core.KnowledgeIngest.authority_is_user_declared_c7f2ff")}</strong>{' '}{t("core.KnowledgeIngest.these_labels_are_not_independently_checked_the_262693")}</p>
    <form onSubmit={(event) => void submit(event)} aria-label={t("core.KnowledgeIngest.index_local_source_and_ask_d0c6d1")}>
      <label>{t("core.KnowledgeIngest.project_relative_file_path_8c345b")}<input required value={path} onChange={(event) => setPath(event.target.value)} placeholder="docs/guide.md" disabled={loading} autoComplete="off" /></label>
      <label>{t("core.KnowledgeIngest.question_289aff")}<textarea required rows={3} value={question} onChange={(event) => setQuestion(event.target.value)} placeholder={t("core.KnowledgeIngest.what_does_this_source_say_cd7190")} disabled={loading} /></label>
      <div className="knowledge-authority-fields">
        <label>{t("core.KnowledgeIngest.declared_source_authority_40eded")}<select value={sourceAuthority} onChange={(event) => setSourceAuthority(event.target.value as Authority)} disabled={loading}><option value="PROPOSED">{observedStateLabel('PROPOSED')}</option><option value="VERIFIED">{observedStateLabel('VERIFIED')}</option></select></label>
        <label>{t("core.KnowledgeIngest.minimum_retrieval_authority_c637a8")}<select value={minimumAuthority} onChange={(event) => setMinimumAuthority(event.target.value as Authority)} disabled={loading}><option value="PROPOSED">{observedStateLabel('PROPOSED')}</option><option value="VERIFIED">{observedStateLabel('VERIFIED')}</option></select></label>
      </div>
      <button type="submit" className="primary-action" disabled={loading || !path.trim() || !question.trim()}>{loading ? t("core.KnowledgeIngest.indexing_and_retrieving_06f2a7") : t("core.KnowledgeIngest.index_source_and_answer_281cef")}</button>
    </form>
    {loading && <p role="status" className="knowledge-state">{t("core.KnowledgeIngest.reading_the_selected_file_updating_the_local_24f0c4")}</p>}
    {error && <p role="alert" className="knowledge-error">{errorMessage(error)}</p>}
    {result?.status === 'no_evidence' && <section className="knowledge-result" aria-label={t("core.KnowledgeIngest.grounded_retrieval_result_d7b871")}><h3>{t("core.KnowledgeIngest.no_eligible_evidence_a379a8")}</h3><p>{t("core.KnowledgeIngest.the_backend_reported_no_eligible_evidence_no_be17c1")}</p></section>}
    {result?.status === 'answered' && result.generation?.answer && <section className="knowledge-result" aria-label={t("core.KnowledgeIngest.grounded_retrieval_result_d7b871")}>
      <h3>{t("core.KnowledgeIngest.answer_from_retrieved_evidence_3ca044")}</h3><p className="knowledge-model">{result.generation.provider_id || t('agents.aux.KnowledgeIngest.provider_unavailable')} · {result.generation.model_id || t('agents.aux.KnowledgeIngest.model_unavailable')}</p>
      <div className="knowledge-answer">{result.generation.answer}</div>
      <dl className="knowledge-run-facts"><div><dt>{t("core.KnowledgeIngest.source_0e570c")}</dt><dd>{result.ingestion?.source_path || t('agents.aux.KnowledgeIngest.unavailable')}</dd></div><div><dt>{t("core.KnowledgeIngest.declared_source_authority_40eded")}</dt><dd>{result.ingestion?.source_authority ? observedStateLabel(result.ingestion.source_authority) : t('agents.aux.KnowledgeIngest.unavailable')}</dd></div><div><dt>{t("core.KnowledgeIngest.minimum_retrieval_authority_c637a8")}</dt><dd>{result.ingestion?.minimum_authority ? observedStateLabel(result.ingestion.minimum_authority) : t('agents.aux.KnowledgeIngest.unavailable')}</dd></div><div><dt>{t("core.KnowledgeIngest.revision_2e516d")}</dt><dd>{sha(result.ingestion?.source_revision)}</dd></div><div><dt>{t("core.KnowledgeIngest.source_sha_256_982334")}</dt><dd>{sha(result.ingestion?.source_sha256)}</dd></div><div><dt>{t("core.KnowledgeIngest.index_fingerprint_190d47")}</dt><dd>{sha(result.ingestion?.index_fingerprint || result.retrieval?.index_fingerprint)}</dd></div><div><dt>{t("core.KnowledgeIngest.ingest_receipt_b2eafc")}</dt><dd>{sha(result.ingestion?.receipt_id)}</dd></div><div><dt>{t("core.KnowledgeIngest.eligible_excluded_by_filter_290982")}</dt><dd>{result.retrieval?.eligible_count ?? t('agents.aux.KnowledgeIngest.unavailable')} / {result.retrieval?.filtered_count ?? t('agents.aux.KnowledgeIngest.unavailable')}</dd></div><div><dt>{t("core.KnowledgeIngest.run_00d60e")}</dt><dd>{result.run_id}</dd></div></dl>
      <section className="knowledge-citations" aria-label={t("core.KnowledgeIngest.retrieved_citations_7eaa62")}><h4>{t("core.KnowledgeIngest.retrieved_citations_7eaa62")}</h4>{result.retrieval?.hits?.length ? <ol>{result.retrieval.hits.map((hit, index) => <li key={hit.chunk_id || hit.evidence?.chunk_id || index}><p>{hit.evidence?.citation || t('agents.aux.KnowledgeIngest.citation_text_unavailable_in_backend_response')}</p><code>{hit.evidence?.source_uri || t('agents.aux.KnowledgeIngest.source_uri_unavailable')}{' '}{t("core.KnowledgeIngest.revision_c281c6")}{' '}{hit.evidence?.revision || t('agents.aux.KnowledgeIngest.unavailable')}</code><small>{t("core.KnowledgeIngest.chunk_1617de")}{' '}{hit.evidence?.chunk_id || hit.chunk_id || t('agents.aux.KnowledgeIngest.unavailable')}{' '}{t("core.KnowledgeIngest.document_54eb3e")}{' '}{hit.evidence?.document_id || hit.document_id || t('agents.aux.KnowledgeIngest.unavailable')}{' '}{t("core.KnowledgeIngest.rank_401b56")}{' '}{hit.rank ?? t('agents.aux.KnowledgeIngest.unavailable')}</small></li>)}</ol> : <p role="status">{t("core.KnowledgeIngest.the_backend_returned_no_citation_hits_for_abc390")}</p>}</section>
    </section>}
    {result && <section className="knowledge-receipt" aria-label={t("core.KnowledgeIngest.ingestion_receipt_and_trace_124171")}><h3>{t("core.KnowledgeIngest.run_receipt_and_trace_60152e")}</h3><dl><div><dt>{t("core.KnowledgeIngest.source_0e570c")}</dt><dd>{result.ingestion?.source_path || t('agents.aux.KnowledgeIngest.unavailable')}</dd></div><div><dt>{t("core.KnowledgeIngest.declared_source_authority_40eded")}</dt><dd>{result.ingestion?.source_authority ? observedStateLabel(result.ingestion.source_authority) : t('agents.aux.KnowledgeIngest.unavailable')}</dd></div><div><dt>{t("core.KnowledgeIngest.minimum_retrieval_authority_c637a8")}</dt><dd>{result.ingestion?.minimum_authority ? observedStateLabel(result.ingestion.minimum_authority) : t('agents.aux.KnowledgeIngest.unavailable')}</dd></div><div><dt>{t("core.KnowledgeIngest.source_revision_49114e")}</dt><dd>{sha(result.ingestion?.source_revision)}</dd></div><div><dt>{t("core.KnowledgeIngest.source_sha_256_982334")}</dt><dd>{sha(result.ingestion?.source_sha256)}</dd></div><div><dt>{t("core.KnowledgeIngest.index_fingerprint_190d47")}</dt><dd>{sha(result.ingestion?.index_fingerprint || result.retrieval?.index_fingerprint)}</dd></div><div><dt>{t("core.KnowledgeIngest.eligible_excluded_by_filter_290982")}</dt><dd>{result.retrieval?.eligible_count ?? t('agents.aux.KnowledgeIngest.unavailable')} / {result.retrieval?.filtered_count ?? t('agents.aux.KnowledgeIngest.unavailable')}</dd></div><div><dt>{t("core.KnowledgeIngest.run_id_26d3e7")}</dt><dd>{result.run_id}</dd></div><div><dt>{t("core.KnowledgeIngest.trace_id_c4cbbc")}</dt><dd>{sha(result.trace?.trace_id)}</dd></div><div><dt>{t("core.KnowledgeIngest.trace_file_9df31b")}</dt><dd>{sha(result.trace?.path)}</dd></div><div><dt>{t("core.KnowledgeIngest.trace_sha_256_636762")}</dt><dd>{sha(result.trace?.sha256)}</dd></div><div><dt>{t("core.KnowledgeIngest.ingestion_receipt_274a66")}</dt><dd>{sha(result.ingestion?.receipt_id)}</dd></div></dl></section>}
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
