import './Control.css'
import './WindowsSurface.css'
import { FormEvent, useState } from 'react'
import WindowPanel from './WindowPanel'

type ScanLocation = { path: string; start_line: number; end_line: number; name?: string }
type DuplicateFinding = { kind: 'exact_block' | 'similar_python_function_structure'; similarity: number | string; left: ScanLocation; right: ScanLocation }
type ScanReport = {
  ok: boolean
  directory: string
  files_scanned: number
  files_skipped: number
  lines_scanned: number
  bytes_scanned: number
  finding_count: number
  truncated: boolean
  manifest_sha256: string
  supported_extensions: string[]
  method: { exact: string; similar: string }
  limitations: string[]
  findings: DuplicateFinding[]
}
type ScanReceipt = { path: string; files_scanned: number; finding_count: number; manifest_sha256: string; duration_ms: number; truncated: boolean }
type ScanOutcome = { result: ScanReport; receipt: ScanReceipt; trace: { trace_id: string; trace_state: string }; conversation_id: string }

async function responseError(response: Response): Promise<string> {
  try {
    const body = await response.json()
    if (typeof body?.detail?.message === 'string') return body.detail.message
    if (typeof body?.detail === 'string') return body.detail
  } catch { /* keep a safe generic error */ }
  return `Request failed (${response.status}).`
}

function locationLabel(location: ScanLocation): string {
  return `${location.path}:${location.start_line}-${location.end_line}`
}

export default function Control() {
  const [directory, setDirectory] = useState('')
  const [authorized, setAuthorized] = useState(false)
  const [scanning, setScanning] = useState(false)
  const [error, setError] = useState('')
  const [outcome, setOutcome] = useState<ScanOutcome | null>(null)

  const runScan = async (event: FormEvent) => {
    event.preventDefault()
    const target = directory.trim().replace(/\\/g, '/')
    if (!target) { setError('Enter one exact project-relative directory.'); return }
    if (!authorized) { setError('Authorize one read-only scan of this directory before running it.'); return }
    setScanning(true)
    setError('')
    setOutcome(null)
    try {
      const conversationResponse = await fetch('/api/conversations', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ owner_kind: 'assistant', owner_id: 'app-assistant', title: `Code duplicate scan: ${target}`.slice(0, 160) }),
      })
      if (!conversationResponse.ok) throw new Error(await responseError(conversationResponse))
      const conversation = await conversationResponse.json()
      const authorizationResponse = await fetch('/api/workspace-scan/authorizations', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ owner_kind: 'assistant', owner_id: 'app-assistant', conversation_id: conversation.id, revision: conversation.revision, directories: [target] }),
      })
      if (!authorizationResponse.ok) throw new Error(await responseError(authorizationResponse))
      const authorization = await authorizationResponse.json()
      const scanResponse = await fetch('/api/workspace-scan/run', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ conversation_id: conversation.id, revision: conversation.revision, authorization_id: authorization.authorization_id, directory: target }),
      })
      if (!scanResponse.ok) throw new Error(await responseError(scanResponse))
      const data = await scanResponse.json() as ScanOutcome
      if (!data.result?.ok) { setError((data.result as ScanReport & { error?: string })?.error ?? 'The authorized directory could not be scanned.'); return }
      if (!data.result || typeof data.result.finding_count !== 'number' || !data.receipt?.manifest_sha256) throw new Error('The scanner returned an incomplete report.')
      setOutcome(data)
      setAuthorized(false)
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : 'The directory scan failed.')
    } finally {
      setScanning(false)
    }
  }

  return (
    <div className="control-container">
      <WindowPanel title="Code duplicate scanner" description="Inspect one project directory with a bounded, read-only local analysis." className="control-panel">
        <form className="code-scan-form" onSubmit={(event) => void runScan(event)}>
          <label htmlFor="code-scan-directory">Project-relative source directory</label>
          <input id="code-scan-directory" value={directory} maxLength={512} onChange={(event) => setDirectory(event.target.value)} placeholder="src" disabled={scanning} autoComplete="off" />
          <label className="code-scan-consent">
            <input type="checkbox" checked={authorized} onChange={(event) => setAuthorized(event.target.checked)} disabled={scanning} />
            <span>Authorize one read-only scan of this exact directory for this run.</span>
          </label>
          <p className="code-scan-privacy">The analyzer runs locally. Source contents stay in the workspace; no code is sent to a model, modified, or executed.</p>
          <button type="submit" className="code-scan-submit" disabled={scanning || !directory.trim() || !authorized}>
            {scanning ? 'Scanning directory…' : 'Scan for duplicate code'}
          </button>
        </form>
        {error && <p className="code-scan-error" role="alert">{error}</p>}
        {outcome && <section className="code-scan-results" aria-labelledby="code-scan-results-title">
          <div className="code-scan-result-heading">
            <div><p className="code-scan-eyebrow">Read-only scan complete</p><h2 id="code-scan-results-title">{outcome.result.directory}</h2></div>
            <span className="code-scan-count">{outcome.result.finding_count} findings</span>
          </div>
          {outcome.result.truncated && <p className="code-scan-warning" role="status">The report reached a scan limit. Review the counts and run a narrower directory scan for complete coverage.</p>}
          <dl className="code-scan-metrics">
            <div><dt>Files scanned</dt><dd>{outcome.result.files_scanned}</dd></div>
            <div><dt>Files skipped</dt><dd>{outcome.result.files_skipped}</dd></div>
            <div><dt>Lines scanned</dt><dd>{outcome.result.lines_scanned.toLocaleString()}</dd></div>
            <div><dt>Duration</dt><dd>{outcome.receipt.duration_ms} ms</dd></div>
          </dl>
          <div className="code-scan-manifest"><strong>Manifest SHA-256</strong><code>{outcome.result.manifest_sha256}</code><small>Trace {outcome.trace.trace_id} · {outcome.trace.trace_state} · Conversation {outcome.conversation_id}</small></div>
          {outcome.result.findings.length ? <ol className="code-scan-findings">{outcome.result.findings.map((finding, index) => <li key={`${finding.kind}:${finding.left.path}:${finding.left.start_line}:${finding.right.path}:${finding.right.start_line}:${index}`}>
            <strong>{finding.kind === 'exact_block' ? 'Exact repeated block' : 'Similar Python function structure'}</strong>
            <code>{locationLabel(finding.left)} ↔ {locationLabel(finding.right)}</code>
            {finding.left.name && finding.right.name && <small>{finding.left.name} ↔ {finding.right.name}</small>}
          </li>)}</ol> : <p className="code-scan-empty">No matching blocks or function structures were found in the scanned files.</p>}
          <details className="code-scan-method"><summary>Detection method and limits</summary><p>{outcome.result.method.exact}.</p><p>{outcome.result.method.similar}.</p><ul>{outcome.result.limitations.map((limitation) => <li key={limitation}>{limitation}</li>)}</ul></details>
        </section>}
      </WindowPanel>

      <aside className="control-sidebar" aria-label="Scanner limits">
        <section className="card"><h2>Scan boundaries</h2><ul>
          <li>One exact authorized project-relative directory per run</li>
          <li>Read-only; no source contents sent to a model</li>
          <li>Up to 300 files, 10 MiB and 150,000 lines</li>
          <li>Up to 200 reported finding pairs</li>
          <li>Python structural matches; exact blocks for the listed source types</li>
        </ul></section>
        <section className="card"><h2>Evidence</h2><p>Each run stores a single-use authorization, a file-hash manifest, line-based findings, a conversation receipt and a local trace.</p></section>
      </aside>
    </div>
  )
}
