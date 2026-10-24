import {useI18n,t,localMessage,errorMessage,apiError,formatDate,formatNumber} from '../i18n'
import './DirectoryScanRun.css'
import { FormEvent, useState } from 'react'

export type ScanLocation = { path: string; start_line: number; end_line: number; name?: string }
export type DuplicateFinding = { kind: 'exact_block' | 'similar_python_function_structure'; similarity: number | string; left: ScanLocation; right: ScanLocation }
export type ScanReport = {
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
  error?: string
}
export type ScanManifestFile = { path: string; sha256: string; bytes: number }
export type ScanReceipt = { path: string; files_scanned: number; finding_count: number; manifest_sha256: string; duration_ms: number; truncated: boolean; files: ScanManifestFile[] }
export type ScanTrace = { trace_id: string; trace_state: string }
export type ScanOutcome = { result: ScanReport; receipt: ScanReceipt; trace: ScanTrace; conversation_id: string }

type DirectoryScanRunProps = {
  conversationId: string
  revision: number
  disabled?: boolean
  showForm: boolean
  initialOutcome?: ScanOutcome
  onConversationUpdate: (conversation: { id: string; revision: number; status: string; [key: string]: unknown }) => void
}

async function responseError(response: Response): Promise<Error> {
  return apiError(await response.json().catch(() => null), response.status, 'agents')
}

function locationLabel(location: ScanLocation): string {
  return `${location.path}:${location.start_line}-${location.end_line}`
}

export default function DirectoryScanRun({ conversationId, revision, disabled = false, showForm, initialOutcome, onConversationUpdate }: DirectoryScanRunProps) {
  useI18n()

  const [directory, setDirectory] = useState('.')
  const [authorized, setAuthorized] = useState(false)
  const [scanning, setScanning] = useState(false)
  const [error, setError] = useState<any>('')

  const runScan = async (event: FormEvent) => {
    event.preventDefault()
    const target = directory.trim().replace(/\\/g, '/')
    if (!target) { setError("core.DirectoryScanRun.enter_a_project_relative_directory_a580a4"); return }
    if (!authorized) { setError("core.DirectoryScanRun.authorize_this_directory_before_scanning_6dd4a8"); return }
    setAuthorized(false)
    setScanning(true)
    setError('')
    try {
      const authorizationResponse = await fetch('/api/workspace-scan/authorizations', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ owner_kind: 'assistant', owner_id: 'app-assistant', conversation_id: conversationId, revision, directories: [target] }),
      })
      if (!authorizationResponse.ok) throw await responseError(authorizationResponse)
      const authorization = await authorizationResponse.json()
      const scanResponse = await fetch('/api/workspace-scan/run', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ conversation_id: conversationId, revision, authorization_id: authorization.authorization_id, directory: target }),
      })
      if (!scanResponse.ok) throw await responseError(scanResponse)
      const data = await scanResponse.json() as ScanOutcome & { conversation?: { id: string; revision: number; status: string; [key: string]: unknown } }
      if (data.conversation) onConversationUpdate(data.conversation)
      if (!data.result?.ok) { setError(data.result?.error ? apiError({detail:{message:data.result.error}},0,'agents') : localMessage('agents.aux.DirectoryScanRun.the_authorized_directory_could_not_be_scanned')); return }
      if (typeof data.result.finding_count !== 'number' || !data.receipt?.manifest_sha256) throw localMessage("core.DirectoryScanRun.the_scanner_returned_an_incomplete_report_60b525")
    } catch (cause) {
      setError(cause instanceof Error ? cause : localMessage('agents.aux.DirectoryScanRun.the_directory_scan_failed'))
    } finally {
      setScanning(false)
    }
  }

  return (
    <section className="directory-scan-run">
      {showForm && <form className="code-scan-form" onSubmit={(event) => void runScan(event)}>
        <label htmlFor="code-scan-directory">{t("core.DirectoryScanRun.project_relative_directory_d5bd1c")}</label>
        <input id="code-scan-directory" value={directory} maxLength={512} onChange={(event) => { setDirectory(event.target.value); setAuthorized(false) }} disabled={scanning || disabled} autoComplete="off" />
        <label className="code-scan-consent">
          <input type="checkbox" checked={authorized} onChange={(event) => setAuthorized(event.target.checked)} disabled={scanning || disabled} />
          <span>{t("core.DirectoryScanRun.authorize_one_read_only_scan_of_this_68c104")}</span>
        </label>
        <button type="submit" className="code-scan-submit" disabled={scanning || disabled || !directory.trim() || !authorized}>
          {scanning ? t("core.DirectoryScanRun.scanning_38d96d") : t("core.DirectoryScanRun.scan_duplicates_bb7da0")}
        </button>
      </form>}
      {showForm && error && <p className="code-scan-error" role="alert">{errorMessage(error)}</p>}
      {initialOutcome && <section className="code-scan-results" aria-label={t("core.DirectoryScanRun.duplicate_code_scan_results_857711")}>
        <div className="code-scan-result-heading">
          <div><p className="code-scan-eyebrow">{t("core.DirectoryScanRun.read_only_scan_3d3df9")}</p><h3>{initialOutcome.result.directory}</h3></div>
          <span className="code-scan-count">{t('agents.aux.findingsCount',{count:formatNumber(initialOutcome.result.finding_count)})}</span>
        </div>
        {initialOutcome.result.truncated && <p className="code-scan-warning" role="status">{t("core.DirectoryScanRun.the_report_reached_a_scan_limit_review_9a60cd")}</p>}
        {initialOutcome.result.findings.length ? <ol className="code-scan-findings">{initialOutcome.result.findings.map((finding, index) => <li key={`${finding.kind}:${finding.left.path}:${finding.left.start_line}:${finding.right.path}:${finding.right.start_line}:${index}`}>
          <strong>{finding.kind === 'exact_block' ? t("core.DirectoryScanRun.exact_repeated_block_e2a808") : t("core.DirectoryScanRun.similar_python_function_structure_de9bae")}</strong>
          <code>{locationLabel(finding.left)} ↔ {locationLabel(finding.right)}</code>
          {finding.left.name && finding.right.name && <small>{finding.left.name} ↔ {finding.right.name}</small>}
        </li>)}</ol> : <p className="code-scan-empty">{t("core.DirectoryScanRun.no_matching_code_was_found_in_this_fcf63c")}</p>}
      </section>}
    </section>
  )
}
