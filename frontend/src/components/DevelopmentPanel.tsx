import {useCallback, useEffect, useId, useRef, useState, type ReactNode} from 'react'
import {createPortal} from 'react-dom'
import {t, useI18n} from '../i18n'
import './DevelopmentPanel.css'

type Check = {check_id: string; status: string; returncode?: number}
type Review = {reviewer_id: string; approved: boolean; reason: string}
export type DevelopmentChange = {
  change_id: string; patch_sha256: string; status: string; author: {owner_id: string; conversation_id: string}
  diff: string; checks: Check[]; reviews: Review[]; apply_eligible?: boolean; rollback_eligible?: boolean
}

function supported(value: unknown): value is DevelopmentChange {
  const c = value as DevelopmentChange | null
  return Boolean(c && typeof c.change_id === 'string' && /^[a-f0-9]{64}$/.test(c.patch_sha256) &&
    typeof c.author?.owner_id === 'string' && typeof c.author.conversation_id === 'string' && typeof c.status === 'string' && typeof c.diff === 'string' &&
    Array.isArray(c.checks) && c.checks.every(v => typeof v.check_id === 'string' && typeof v.status === 'string') &&
    Array.isArray(c.reviews) && c.reviews.every(v => typeof v.reviewer_id === 'string' && typeof v.approved === 'boolean' && typeof v.reason === 'string'))
}

async function readResponse(response: Response) {
  const data = await response.json()
  if (!response.ok) throw new Error(typeof data?.detail === 'string' ? data.detail : data?.detail?.message || data?.error?.message || 'No se pudo completar la operación.')
  return data
}

export default function DevelopmentPanel({ownerId, projectRoot = null, portalTarget = null, disabled = false, workspaceContent, historyContent, onExpandedChange, showChanges = true, initialOpen = true}: {ownerId: string; projectRoot?: string | null; portalTarget?: HTMLElement | null; disabled?: boolean; workspaceContent?: ReactNode; historyContent?: ReactNode; onExpandedChange?: (expanded: boolean) => void; showChanges?: boolean; initialOpen?: boolean}) {
  useI18n()
  const [open, setOpen] = useState(() => initialOpen && !(typeof window !== 'undefined' && typeof window.matchMedia === 'function' && window.matchMedia('(max-width: 760px)').matches))
  const [expanded, setExpanded] = useState(false)
  useEffect(() => {onExpandedChange?.(expanded)}, [expanded, onExpandedChange])
  const panelId = useId()
  const toggleRef = useRef<HTMLButtonElement>(null)
  const closeRef = useRef<HTMLButtonElement>(null)
  const firstRender = useRef(true)
  useEffect(() => {
    if (firstRender.current) {firstRender.current = false; return}
    if (open) closeRef.current?.focus()
    else toggleRef.current?.focus()
  }, [open])
  useEffect(() => {
    if (!open) return
    const escape = (event: KeyboardEvent) => {
      if (event.key !== 'Escape' || event.defaultPrevented || document.querySelector('dialog[open], [role="dialog"][aria-modal="true"], .chat-tools-menu[open], .conversation-context-menu, .chat-agent-panel[open]')) return
      event.preventDefault()
      setOpen(false)
    }
    document.addEventListener('keydown', escape)
    return () => document.removeEventListener('keydown', escape)
  }, [open])
  const [changes, setChanges] = useState<DevelopmentChange[]>([])
  const [candidate, setCandidate] = useState<DevelopmentChange | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [confirmed, setConfirmed] = useState(false)
  const [busy, setBusy] = useState(false)
  const [notice, setNotice] = useState('')
  const lock = useRef(false)
  const generation = useRef(0)
  const base = '/api/development/changes'
  const refresh = useCallback(async () => {
    const version = ++generation.current
    setLoading(true); setError(''); setCandidate(null); setConfirmed(false); setNotice('')
    try {
      const data = await readResponse(await fetch(base))
      if (version !== generation.current) return
      if (!Array.isArray(data.changes) || !data.changes.every((v: unknown) => supported(v))) throw new Error('La lista de cambios tiene un formato no compatible.')
      setChanges(data.changes)
    } catch (cause) { if (version === generation.current) {setChanges([]); setError(cause instanceof Error ? cause.message : 'No se pudieron cargar los cambios.')} }
    finally {if (version === generation.current) setLoading(false)}
  }, [ownerId])
  useEffect(() => {if (showChanges) void refresh(); else setLoading(false); return () => {generation.current++}}, [refresh, showChanges])
  async function inspect(id: string) {
    if (lock.current) return
    const version = ++generation.current
    setCandidate(null); setConfirmed(false); setError(''); setNotice(''); setLoading(true)
    try {
      const data = await readResponse(await fetch(base + '/' + encodeURIComponent(id)))
      if (version !== generation.current) return
      if (!supported(data) || data.change_id !== id) throw new Error('El cambio recibido tiene una identidad o formato no compatible.')
      setCandidate(data)
    } catch (cause) {if (version === generation.current) setError(cause instanceof Error ? cause.message : 'No se pudo revisar el cambio.')}
    finally {if (version === generation.current) setLoading(false)}
  }
  const checked = Boolean(candidate?.checks.length && candidate.checks.every(c => c.status === 'PASS'))
  const reviewed = Boolean(candidate?.reviews.length && candidate.reviews.every(r => r.approved === true))
  async function act(operation: 'apply' | 'rollback') {
    if (lock.current || !candidate || !confirmed || disabled || (operation === 'apply' ? candidate.apply_eligible !== true || !checked || !reviewed : candidate.status !== 'APPLIED' || candidate.rollback_eligible !== true)) return
    lock.current = true; setBusy(true); setError(''); setNotice('')
    const version = generation.current
    try {
      const data = await readResponse(await fetch(base + '/' + encodeURIComponent(candidate.change_id) + '/' + operation, {
        method: 'POST', headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({expected_sha256: candidate.patch_sha256, confirmed: true}),
      }))
      if (version !== generation.current) return
      if (!supported(data) || data.change_id !== candidate.change_id || data.patch_sha256 !== candidate.patch_sha256) throw new Error('No se pudo verificar el resultado de la operación. Actualiza los cambios.')
      setCandidate(data); setConfirmed(false)
      setChanges(previous => previous.map(c => c.change_id === data.change_id ? data : c))
      setNotice('Resultado recibido: ' + data.status)
    } catch (cause) {if (version === generation.current) {setError(cause instanceof Error ? cause.message : 'No se pudo completar la operación.'); setConfirmed(false); setCandidate(null)}}
    finally {lock.current = false; setBusy(false)}
  }
  const drawer = <div className="development-drawer-anchor" data-open={open} data-expanded={expanded}>
    <button ref={toggleRef} type="button" className="development-drawer-tab"
      aria-expanded={open} aria-controls={panelId} aria-label={t('commerce.project_panel_title')} onClick={() => setOpen(value => !value)}>
      <span className="project-sidebar-tab-label">{t('commerce.project_panel_title')}</span>
      <code title={projectRoot || undefined}>{projectRoot || t('commerce.project_not_registered')}</code>
      <span className="development-drawer-tab-state" aria-hidden="true">⌄</span>
    </button>
    <section id={panelId} aria-label={t('commerce.project_context_label')} className="development-drawer" data-expanded={expanded} hidden={!open}>
    <header className="development-drawer-header"><h3>{t('commerce.project_panel_title')}</h3>
      <div className="development-drawer-header-actions">
        <button type="button" className="development-drawer-size" aria-pressed={expanded} aria-label={expanded ? t('commerce.restore_project_panel') : t('commerce.expand_project_panel')} onClick={() => setExpanded(value => !value)}>{expanded ? t('commerce.restore_project_panel') : t('commerce.expand_project_panel')}</button>
        <button ref={closeRef} type="button" className="development-drawer-close" aria-label={t('commerce.close_project_panel')} onClick={() => setOpen(false)}>{t('commerce.close')} <span aria-hidden="true">×</span></button>
      </div>
    </header>
    <div className="project-sidebar-sections">
    {workspaceContent}
    {historyContent && <details className="project-sidebar-section project-sidebar-history" open><summary>Historial de conversaciones</summary><div className="project-sidebar-section-body" style={{display: 'flex', flexDirection: 'column'}}>{historyContent}</div></details>}
    {showChanges && <details className="project-sidebar-section project-sidebar-history" open><summary>Historial de cambios</summary>
    <div className="development-drawer-body project-sidebar-section-body">
    <button type="button" onClick={() => void refresh()} disabled={loading || busy || disabled}>Actualizar cambios</button>
    {loading && <p role="status">Cargando cambios…</p>}
    {error && <p role="alert">{error}</p>}
    {!loading && !error && changes.length === 0 && <p>Todavía no hay cambios preparados en este proyecto.</p>}
    <ul>{changes.map(c => <li key={c.change_id} data-status={c.status}><button type="button" disabled={busy || loading || disabled} onClick={() => void inspect(c.change_id)}>{c.change_id} · {c.status}</button></li>)}</ul>
    {candidate && <div>
      <p>Estado: {candidate.status} · Autor: {candidate.author.owner_id}</p>
      <details><summary>Identidad del cambio</summary><code>{candidate.change_id}</code><br/><code>{candidate.patch_sha256}</code></details>
      <details open><summary>Revisar diferencias</summary><pre className="development-drawer-diff">{candidate.diff}</pre></details>
      <h4>Pruebas</h4>{candidate.checks.length ? <ul>{candidate.checks.map((c, i) => <li key={i}>{c.check_id}: {c.status}</li>)}</ul> : <p>Faltan pruebas.</p>}
      <h4>Revisión</h4>{candidate.reviews.length ? <ul>{candidate.reviews.map((r, i) => <li key={i}>{r.reviewer_id}: {r.approved ? "Aprobada" : "Rechazada"} · {r.reason}</li>)}</ul> : <p>Falta la revisión.</p>}
      {!checked || !reviewed ? <p>La aplicación requiere pruebas y revisión aprobadas.</p> : null}
      <label><input type="checkbox" checked={confirmed} disabled={busy || disabled} onChange={e => setConfirmed(e.target.checked)}/>He revisado las diferencias y confirmo esta operación</label>
      <div className="project-sidebar-actions"><button type="button" disabled={busy || disabled || !confirmed || candidate.apply_eligible !== true || !checked || !reviewed} onClick={() => void act('apply')}>Aplicar cambio</button>
      <button type="button" disabled={busy || disabled || !confirmed || candidate.status !== 'APPLIED' || candidate.rollback_eligible !== true} onClick={() => void act('rollback')}>Revertir cambio</button></div>
    </div>}
    {busy && <p role="status">Procesando la operación…</p>}
    {notice && <p role="status">{notice}</p>}
    </div>
    </details>}
    </div>
    </section>
  </div>
  return portalTarget ? createPortal(drawer, portalTarget) : drawer
}

