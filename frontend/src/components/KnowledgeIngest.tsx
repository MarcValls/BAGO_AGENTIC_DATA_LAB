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

async function responseError(response: Response): Promise<string> {
  try {
    const body = await response.json()
    if (typeof body?.detail === 'string') return body.detail
    if (typeof body?.detail?.message === 'string') return body.detail.message
  } catch { /* use the status below */ }
  if (response.status === 404 || response.status === 405) return 'Grounded local retrieval is not supported by this backend.'
  return `Knowledge request failed (${response.status}).`
}

function sha(value: string | undefined): string {
  return value || 'Unavailable in backend response'
}

export default function KnowledgeIngest() {
  const [path, setPath] = useState('')
  const [question, setQuestion] = useState('')
  const [sourceAuthority, setSourceAuthority] = useState<Authority>('PROPOSED')
  const [minimumAuthority, setMinimumAuthority] = useState<Authority>('PROPOSED')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
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
      if (!response.ok) throw new Error(await responseError(response))
      const body = await response.json() as GroundedRun
      if (!body || !['answered', 'no_evidence', 'failed'].includes(body.status ?? '') || typeof body.run_id !== 'string'
        || typeof body.trace?.trace_id !== 'string' || typeof body.ingestion?.receipt_id !== 'string') {
        throw new Error('The backend returned an incomplete run record. No answer was accepted.')
      }
      if (body.status === 'answered' && (typeof body.generation?.answer !== 'string' || !Array.isArray(body.retrieval?.hits) || body.retrieval.hits.length === 0)) {
        throw new Error('The backend returned an answer without linked retrieval evidence. No answer was accepted.')
      }
      setResult(body)
      if (body.status === 'failed') setError(typeof body.error === 'string' ? body.error : 'The backend recorded a failed run.')
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : 'The knowledge request could not be completed.')
    } finally { setLoading(false) }
  }

  return <section className="knowledge-ingest" aria-labelledby="knowledge-ingest-title">
    <header><p className="section-eyebrow">Local knowledge · one file</p><h2 id="knowledge-ingest-title">Index a source and ask with citations</h2>
      <p>Choose one project-relative text or Markdown file. Submitting authorizes local indexing and sends the question with eligible retrieved passages to the selected model.</p>
    </header>
    <p className="knowledge-authority-note"><strong>Authority is user-declared.</strong> These labels are not independently checked. The local hash-embedding index is a reproducible prototype, not evidence of hosted embedding quality or production search relevance.</p>
    <form onSubmit={(event) => void submit(event)} aria-label="Index local source and ask">
      <label>Project-relative file path<input required value={path} onChange={(event) => setPath(event.target.value)} placeholder="docs/guide.md" disabled={loading} autoComplete="off" /></label>
      <label>Question<textarea required rows={3} value={question} onChange={(event) => setQuestion(event.target.value)} placeholder="What does this source say?" disabled={loading} /></label>
      <div className="knowledge-authority-fields">
        <label>Declared source authority<select value={sourceAuthority} onChange={(event) => setSourceAuthority(event.target.value as Authority)} disabled={loading}><option value="PROPOSED">PROPOSED</option><option value="VERIFIED">VERIFIED</option></select></label>
        <label>Minimum retrieval authority<select value={minimumAuthority} onChange={(event) => setMinimumAuthority(event.target.value as Authority)} disabled={loading}><option value="PROPOSED">PROPOSED</option><option value="VERIFIED">VERIFIED</option></select></label>
      </div>
      <button type="submit" className="primary-action" disabled={loading || !path.trim() || !question.trim()}>{loading ? 'Indexing and retrieving…' : 'Index source and answer'}</button>
    </form>
    {loading && <p role="status" className="knowledge-state">Reading the selected file, updating the local index and retrieving eligible evidence…</p>}
    {error && <p role="alert" className="knowledge-error">{error}</p>}
    {result?.status === 'no_evidence' && <section className="knowledge-result" aria-label="Grounded retrieval result"><h3>No eligible evidence</h3><p>The backend reported no eligible evidence. No model answer is shown.</p></section>}
    {result?.status === 'answered' && result.generation?.answer && <section className="knowledge-result" aria-label="Grounded retrieval result">
      <h3>Answer from retrieved evidence</h3><p className="knowledge-model">{result.generation.provider_id || 'Provider unavailable'} · {result.generation.model_id || 'Model unavailable'}</p>
      <div className="knowledge-answer">{result.generation.answer}</div>
      <dl className="knowledge-run-facts"><div><dt>Source</dt><dd>{result.ingestion?.source_path || 'Unavailable'}</dd></div><div><dt>Declared source authority</dt><dd>{result.ingestion?.source_authority || 'Unavailable'}</dd></div><div><dt>Minimum retrieval authority</dt><dd>{result.ingestion?.minimum_authority || 'Unavailable'}</dd></div><div><dt>Revision</dt><dd>{sha(result.ingestion?.source_revision)}</dd></div><div><dt>Source SHA-256</dt><dd>{sha(result.ingestion?.source_sha256)}</dd></div><div><dt>Index fingerprint</dt><dd>{sha(result.ingestion?.index_fingerprint || result.retrieval?.index_fingerprint)}</dd></div><div><dt>Ingest receipt</dt><dd>{sha(result.ingestion?.receipt_id)}</dd></div><div><dt>Eligible / excluded by filter</dt><dd>{result.retrieval?.eligible_count ?? 'Unavailable'} / {result.retrieval?.filtered_count ?? 'Unavailable'}</dd></div><div><dt>Run</dt><dd>{result.run_id}</dd></div></dl>
      <section className="knowledge-citations" aria-label="Retrieved citations"><h4>Retrieved citations</h4>{result.retrieval?.hits?.length ? <ol>{result.retrieval.hits.map((hit, index) => <li key={hit.chunk_id || hit.evidence?.chunk_id || index}><p>{hit.evidence?.citation || 'Citation text unavailable in backend response'}</p><code>{hit.evidence?.source_uri || 'Source URI unavailable'} · revision {hit.evidence?.revision || 'unavailable'}</code><small>Chunk {hit.evidence?.chunk_id || hit.chunk_id || 'unavailable'} · document {hit.evidence?.document_id || hit.document_id || 'unavailable'} · rank {hit.rank ?? 'unavailable'}</small></li>)}</ol> : <p role="status">The backend returned no citation hits for this answer.</p>}</section>
    </section>}
    {result && <section className="knowledge-receipt" aria-label="Ingestion receipt and trace"><h3>Run receipt and trace</h3><dl><div><dt>Source</dt><dd>{result.ingestion?.source_path || 'Unavailable'}</dd></div><div><dt>Declared source authority</dt><dd>{result.ingestion?.source_authority || 'Unavailable'}</dd></div><div><dt>Minimum retrieval authority</dt><dd>{result.ingestion?.minimum_authority || 'Unavailable'}</dd></div><div><dt>Source revision</dt><dd>{sha(result.ingestion?.source_revision)}</dd></div><div><dt>Source SHA-256</dt><dd>{sha(result.ingestion?.source_sha256)}</dd></div><div><dt>Index fingerprint</dt><dd>{sha(result.ingestion?.index_fingerprint || result.retrieval?.index_fingerprint)}</dd></div><div><dt>Eligible / excluded by filter</dt><dd>{result.retrieval?.eligible_count ?? 'Unavailable'} / {result.retrieval?.filtered_count ?? 'Unavailable'}</dd></div><div><dt>Run ID</dt><dd>{result.run_id}</dd></div><div><dt>Trace ID</dt><dd>{sha(result.trace?.trace_id)}</dd></div><div><dt>Trace file</dt><dd>{sha(result.trace?.path)}</dd></div><div><dt>Trace SHA-256</dt><dd>{sha(result.trace?.sha256)}</dd></div><div><dt>Ingestion receipt</dt><dd>{sha(result.ingestion?.receipt_id)}</dd></div></dl></section>}
  </section>
}
