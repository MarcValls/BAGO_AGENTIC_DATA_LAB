import {useEffect, useRef, useState, type FormEvent} from 'react'
import {apiError, errorMessage, localMessage, t, useI18n} from '../i18n'
import {isDirectoryListing, isProjectPermissionSnapshot, type ProjectPermissionSnapshot, type ProjectTreeEntry} from '../types/projectPermissions'
import {isProjectCsvPath, type CsvChatContext, type CsvReadSelection} from '../types/csvChat'
import './CsvChatQuery.css'

export default function CsvChatQuery({projectId, projectRoot, contextKey, disabled, notice, onSubmit, onSent}: CsvChatContext & {onSent: () => void}) {
  useI18n()
  const [snapshot, setSnapshot] = useState<ProjectPermissionSnapshot | null>(null)
  const [entries, setEntries] = useState<ProjectTreeEntry[]>([])
  const [directory, setDirectory] = useState('.')
  const [truncated, setTruncated] = useState(false)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<Error | null>(null)
  const [path, setPath] = useState('')
  const [question, setQuestion] = useState('')
  const [delimiter, setDelimiter] = useState<CsvReadSelection['delimiter']>('auto')
  const [decimalSeparator, setDecimalSeparator] = useState<CsvReadSelection['decimal_separator']>('.')
  const [consent, setConsent] = useState(false)
  const [busy, setBusy] = useState(false)
  const [cancelling, setCancelling] = useState(false)
  const [refresh, setRefresh] = useState(0)
  const generation = useRef(0)
  const submission = useRef<AbortController | null>(null)
  const metadata = useRef<AbortController | null>(null)
  const mounted = useRef(true)

  useEffect(() => {
    mounted.current = true
    return () => {mounted.current = false; submission.current?.abort(); metadata.current?.abort(); generation.current++}
  }, [])

  async function listDirectory(target: string, policy: ProjectPermissionSnapshot, request: number, signal: AbortSignal) {
    const response = await fetch('/api/project-permissions/directories', {
      method: 'POST', headers: {'Content-Type': 'application/json'}, signal,
      body: JSON.stringify({expected_project_id: policy.project_id, expected_binding: policy.binding, expected_revision: policy.revision, directory: target}),
    })
    if (!response.ok) throw apiError(await response.json().catch(() => null), response.status)
    const value: unknown = await response.json()
    if (signal.aborted || request !== generation.current) return
    if (!isDirectoryListing(value) || value.project_id !== projectId || value.root !== projectRoot
      || value.revision !== policy.revision || value.directory !== target || JSON.stringify(value.binding) !== JSON.stringify(policy.binding)) {
      throw localMessage('csvChat.contextChanged')
    }
    setEntries(value.entries ?? [...value.directories.map(item => ({...item, kind: 'directory' as const})), ...(value.files ?? []).map(item => ({...item, kind: 'file' as const}))])
    setDirectory(target); setTruncated(value.truncated)
  }

  useEffect(() => {
    const request = ++generation.current
    const controller = new AbortController(); metadata.current?.abort(); metadata.current = controller
    submission.current?.abort()
    setSnapshot(null); setEntries([]); setDirectory('.'); setTruncated(false); setPath(''); setQuestion(''); setConsent(false); setError(null)
    setDelimiter('auto'); setDecimalSeparator('.'); setBusy(false); setCancelling(false)
    if (!projectId || !projectRoot) {setLoading(false); setError(localMessage('csvChat.noProject')); return () => controller.abort()}
    setLoading(true)
    void (async () => {
      try {
        const response = await fetch('/api/project-permissions', {signal: controller.signal})
        if (!response.ok) throw apiError(await response.json().catch(() => null), response.status)
        const value: unknown = await response.json()
        if (controller.signal.aborted || request !== generation.current) return
        if (!isProjectPermissionSnapshot(value) || value.project_id !== projectId || value.root !== projectRoot || value.revision === null) throw localMessage('csvChat.contextChanged')
        setSnapshot(value)
        await listDirectory('.', value, request, controller.signal)
      } catch (cause) {
        if (!controller.signal.aborted && request === generation.current) {setSnapshot(null); setEntries([]); setError(cause instanceof Error ? cause : localMessage('csvChat.permissionsError'))}
      } finally {if (!controller.signal.aborted && request === generation.current) setLoading(false)}
    })()
    return () => {controller.abort(); submission.current?.abort()}
  }, [projectId, projectRoot, contextKey, refresh])

  async function browse(target: string) {
    if (!snapshot || loading || busy) return
    const request = ++generation.current
    const controller = new AbortController(); metadata.current?.abort(); metadata.current = controller
    setLoading(true); setError(null); setConsent(false)
    try {await listDirectory(target, snapshot, request, controller.signal)}
    catch (cause) {if (!controller.signal.aborted && request === generation.current) {setSnapshot(null); setEntries([]); setError(cause instanceof Error ? cause : localMessage('csvChat.directoryError'))}}
    finally {if (!controller.signal.aborted && request === generation.current) setLoading(false)}
  }

  const selectedPath = path.trim()
  const validPath = isProjectCsvPath(selectedPath)
  const readAllowed = Boolean(snapshot && ['active', 'configured'].includes(snapshot.state) && snapshot.read_directories.some(scope => scope === '.' || scope === selectedPath || selectedPath.startsWith(`${scope}/`)))
  const unavailable = disabled || busy || loading

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (unavailable || submission.current || !consent || !validPath || !readAllowed || !question.trim() || !snapshot || !projectRoot) return
    const controller = new AbortController(); submission.current = controller
    const request = generation.current
    setBusy(true); setCancelling(false); setError(null); setConsent(false)
    try {
      const sent = await onSubmit({message: question.trim(), csv_read: {path: selectedPath, delimiter, decimal_separator: decimalSeparator},
        expected_project: {project_id: snapshot.project_id, binding: snapshot.binding, revision: snapshot.revision}, projectRoot, contextKey}, controller.signal)
      if (mounted.current && sent) onSent()
      else if (mounted.current && request === generation.current && !controller.signal.aborted) setError(localMessage('csvChat.unsent'))
    } catch (cause) {if (mounted.current && request === generation.current) setError(cause instanceof Error ? cause : localMessage('csvChat.unsent'))}
    finally {
      if (submission.current === controller) submission.current = null
      if (mounted.current && request === generation.current) {setBusy(false); setCancelling(false)}
    }
  }

  return <section className="csv-chat-query" aria-labelledby="csv-chat-query-title">
    <header><h2 id="csv-chat-query-title">{t('csvChat.title')}</h2><p>{t('csvChat.intro')}</p></header>
    <p className="csv-chat-note">{t('csvChat.metadataOnly')}</p>
    <div className="csv-chat-browser" aria-label={t('csvChat.files')}>
      <div className="csv-chat-browser-heading"><strong>{t('csvChat.directory')}: <code>{directory}</code></strong>
        <button type="button" disabled={unavailable} onClick={() => setRefresh(value => value + 1)}>{t('csvChat.refresh')}</button>
      </div>
      {directory !== '.' && <button type="button" disabled={unavailable} onClick={() => void browse(directory.includes('/') ? directory.slice(0, directory.lastIndexOf('/')) : '.')}>{t('csvChat.parent')}</button>}
      {loading && <p role="status">{t('csvChat.loading')}</p>}
      {!loading && <ul>{entries.filter(entry => entry.kind === 'directory' || /\.csv$/i.test(entry.name)).map(entry => <li key={entry.path}>
        {entry.kind === 'directory'
          ? <button type="button" disabled={unavailable} onClick={() => void browse(entry.path)} aria-label={t('csvChat.openDirectory', {name: entry.name})}>▰ {entry.name}</button>
          : <button type="button" disabled={unavailable} aria-pressed={selectedPath === entry.path} onClick={() => {setPath(entry.path); setConsent(false)}} aria-label={t('csvChat.chooseFile', {path: entry.path})}>▤ {entry.name}</button>}
      </li>)}</ul>}
      {!loading && !entries.some(entry => entry.kind === 'file' && /\.csv$/i.test(entry.name)) && <p>{t('csvChat.empty')}</p>}
      {truncated && <p role="status">{t('csvChat.truncated')}</p>}
    </div>
    <form onSubmit={event => void submit(event)} aria-label={t('csvChat.title')}>
      <label>{t('csvChat.path')}<input required value={path} onChange={event => {setPath(event.target.value); setConsent(false)}} maxLength={512} disabled={unavailable} placeholder="datos/pedidos.csv" autoComplete="off"/></label>
      {path && !validPath && <p role="alert">{t('csvChat.invalidPath')}</p>}
      {validPath && !readAllowed && <p role="status">{t('csvChat.readRequired')}</p>}
      <label>{t('csvChat.question')}<textarea required rows={3} maxLength={8000} value={question} onChange={event => {setQuestion(event.target.value); setConsent(false)}} disabled={unavailable} placeholder={t('csvChat.questionPlaceholder')}/></label>
      <div className="csv-chat-options">
        <label>{t('csvChat.delimiter')}<select value={delimiter} onChange={event => {setDelimiter(event.target.value as CsvReadSelection['delimiter']); setConsent(false)}} disabled={unavailable}>
          <option value="auto">{t('csvChat.auto')}</option><option value=",">{t('csvChat.comma')}</option><option value=";">{t('csvChat.semicolon')}</option><option value={'\t'}>{t('csvChat.tab')}</option><option value="|">{t('csvChat.pipe')}</option>
        </select></label>
        <label>{t('csvChat.decimal')}<select value={decimalSeparator} onChange={event => {setDecimalSeparator(event.target.value as CsvReadSelection['decimal_separator']); setConsent(false)}} disabled={unavailable}>
          <option value=".">{t('csvChat.dot')}</option><option value=",">{t('csvChat.decimalComma')}</option>
        </select></label>
      </div>
      <label className="csv-chat-consent"><input type="checkbox" checked={consent} onChange={event => setConsent(event.target.checked)} disabled={unavailable || !validPath || !readAllowed || !question.trim()}/><span>{t('csvChat.consent')}</span></label>
      <p className="csv-chat-note">{t('csvChat.limits')}</p>
      <div className="csv-chat-actions"><button type="submit" className="primary-action" disabled={unavailable || !consent || !validPath || !readAllowed || !question.trim()}>{t('csvChat.submit')}</button>
        {busy && <button type="button" disabled={cancelling} onClick={() => {setCancelling(true); submission.current?.abort()}}>{t('csvChat.cancel')}</button>}
      </div>
    </form>
    {busy && <p role="status">{t(cancelling ? 'csvChat.cancelling' : 'csvChat.running')}</p>}
    {(error || notice) && <p role="alert" className="csv-chat-error">{errorMessage(error || notice!)}</p>}
  </section>
}
