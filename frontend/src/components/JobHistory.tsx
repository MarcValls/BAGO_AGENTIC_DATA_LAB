import {useEffect, useId, useRef, useState} from 'react'
import {formatDate, formatNumber, useI18n} from '../i18n'
import './JobHistory.css'
import './WindowsSurface.css'

const kinds = ['legacy_job', 'task_run', 'delegation', 'agent_turn', 'evaluation'] as const
type WorkKind = typeof kinds[number]
type HistoryFilter = 'all' | WorkKind
type SourceState = 'available' | 'absent' | 'partial' | 'unavailable'
export interface WorkHistoryItem {
  key: string
  kind: WorkKind
  id: string
  status: string | null
  agent_id: string | null
  agent_name: string | null
  parent_conversation_id: string | null
  conversation_id: string | null
  message_id: string | null
  trace_id: string | null
  receipt_id: string | null
  receipt_sha256: string | null
  created_at: string | null
  started_at: string | null
  completed_at: string | null
  activity_at: string | null
  duration_ms: number | null
  cost_usd: number | null
  tools_executed: boolean | null
  target_written: boolean | null
  tool_receipt_count: number | null
  related_key: string | null
}
interface HistorySource {kind: WorkKind; state: SourceState; error_code: string | null; truncated: boolean}
interface HistoryPage {
  schema: 'work-history.v1'
  items: WorkHistoryItem[]
  total: number
  limit: number
  offset: number
  has_more: boolean
  next_offset: number | null
  sources: HistorySource[]
}
interface JobHistoryProps {
  /** Historical prop name retained; selection exposes only the metadata index contract. */
  onJobSelect?: (job: WorkHistoryItem) => void
  inline?: boolean
}
const strings = ['status', 'agent_id', 'agent_name', 'parent_conversation_id', 'conversation_id', 'message_id', 'trace_id', 'receipt_id', 'receipt_sha256', 'created_at', 'started_at', 'completed_at', 'activity_at', 'related_key'] as const
const numbers = ['duration_ms', 'cost_usd', 'tool_receipt_count'] as const
const booleans = ['tools_executed', 'target_written'] as const
const object = (value: unknown): value is Record<string, unknown> => value !== null && typeof value === 'object' && !Array.isArray(value)
const integer = (value: unknown): value is number => typeof value === 'number' && Number.isInteger(value) && value >= 0
const isKind = (value: unknown): value is WorkKind => kinds.includes(value as WorkKind)

// Project a whitelist instead of retaining unknown fields in the selection/callback.
function readPage(value: unknown, kind: HistoryFilter, offset: number): HistoryPage {
  if (!object(value) || value.schema !== 'work-history.v1' || !Array.isArray(value.items) || !Array.isArray(value.sources)
      || !integer(value.total) || value.limit !== 50 || value.offset !== offset || typeof value.has_more !== 'boolean'
      || value.items.length > 50 || value.total < value.items.length
      || (value.has_more ? !integer(value.next_offset) || value.next_offset <= offset || value.next_offset > 10000 : value.next_offset !== null)) throw new Error('invalid_history_contract')
  const seen = new Set<string>()
  const items = value.items.map(raw => {
    if (!object(raw) || !isKind(raw.kind) || typeof raw.id !== 'string' || !raw.id || raw.key !== `${raw.kind}:${raw.id}`
        || (kind !== 'all' && raw.kind !== kind) || seen.has(raw.key as string)
        || strings.some(field => raw[field] !== null && typeof raw[field] !== 'string')
        || numbers.some(field => raw[field] !== null && (typeof raw[field] !== 'number' || !Number.isFinite(raw[field]) || (raw[field] as number) < 0))
        || (raw.tool_receipt_count !== null && !integer(raw.tool_receipt_count))
        || booleans.some(field => raw[field] !== null && typeof raw[field] !== 'boolean')) throw new Error('invalid_history_contract')
    seen.add(raw.key as string)
    return Object.fromEntries(['key', 'kind', 'id', ...strings, ...numbers, ...booleans].map(field => [field, raw[field]])) as unknown as WorkHistoryItem
  })
  const sourceKinds = new Set<string>()
  const sources = value.sources.map(raw => {
    if (!object(raw) || !isKind(raw.kind) || sourceKinds.has(raw.kind) || !['available', 'absent', 'partial', 'unavailable'].includes(raw.state as string)
        || (raw.error_code !== null && typeof raw.error_code !== 'string') || typeof raw.truncated !== 'boolean') throw new Error('invalid_history_contract')
    sourceKinds.add(raw.kind)
    return {kind: raw.kind, state: raw.state as SourceState, error_code: raw.error_code as string | null, truncated: raw.truncated}
  })
  if (sourceKinds.size !== kinds.length) throw new Error('invalid_history_contract')
  return {schema: 'work-history.v1', items, sources, total: value.total, limit: 50, offset, has_more: value.has_more, next_offset: value.next_offset as number | null}
}

export default function JobHistory({onJobSelect, inline = false}: JobHistoryProps) {
  const {locale} = useI18n()
  const say = (es: string, en: string) => locale === 'en' ? en : es
  const [query, setQuery] = useState<{kind: HistoryFilter; offset: number}>({kind: 'all', offset: 0})
  const [refresh, setRefresh] = useState(0)
  const [loaded, setLoaded] = useState<{kind: HistoryFilter; page: HistoryPage} | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<{kind: 'http' | 'network' | 'contract'; status?: number} | null>(null)
  const [selectedKey, setSelectedKey] = useState<string | null>(null)
  const generation = useRef(0)
  const selectedButton = useRef<HTMLButtonElement | null>(null)
  const detailId = useId()
  useEffect(() => {
    const controller = new AbortController()
    const currentGeneration = ++generation.current
    const current = () => !controller.signal.aborted && generation.current === currentGeneration
    setLoading(true)
    setError(null)
    void (async () => {
      try {
        const params = new URLSearchParams({limit: '50', offset: String(query.offset), kind: query.kind})
        const response = await fetch(`/api/work-history?${params}`, {signal: controller.signal})
        if (!current()) return
        if (!response.ok) {setError({kind: 'http', status: response.status}); return}
        let raw: unknown
        try {raw = await response.json()} catch {if (current()) setError({kind: 'contract'}); return}
        if (!current()) return
        let page: HistoryPage
        try {page = readPage(raw, query.kind, query.offset)} catch {setError({kind: 'contract'}); return}
        setLoaded({kind: query.kind, page})
      } catch {
        if (current()) setError({kind: 'network'})
      } finally {
        if (current()) setLoading(false)
      }
    })()
    return () => controller.abort()
  }, [query.kind, query.offset, refresh])
  const page = loaded?.kind === query.kind && loaded.page.offset === query.offset ? loaded.page : null
  const selected = page?.items.find(item => item.key === selectedKey)
  const incomplete = page?.sources.some(source => source.state === 'partial' || source.state === 'unavailable' || source.truncated)
  const sourceName = (kind: WorkKind) => ({legacy_job: say('Trabajo legacy', 'Legacy job'), task_run: say('Ejecución de tarea', 'Task run'), delegation: say('Delegación', 'Delegation'), agent_turn: say('Turno de agente', 'Agent turn'), evaluation: say('Evaluación', 'Evaluation')})[kind]
  const sourceState = (state: SourceState) => ({available: say('Disponible', 'Available'), absent: say('Ausente', 'Absent'), partial: say('Parcial', 'Partial'), unavailable: say('No disponible', 'Unavailable')})[state]
  const missing = say('No registrado', 'Not recorded')
  const statusLabel = (status: string | null) => {
    if (status === null) return say('Estado no registrado', 'Status not recorded')
    const labels: Record<string, string> = {
      PASSED: say('Respuesta recibida', 'Response received'), answered: say('Respuesta recibida', 'Response received'),
      failed: say('Fallida', 'Failed'), FAILED: say('Fallida', 'Failed'), FAIL: say('Fallo registrado', 'Recorded failure'),
      running: say('En curso', 'Running'), RUNNING: say('En curso', 'Running'),
      success: say('Éxito registrado', 'Recorded success'), SUCCEEDED: say('Éxito registrado', 'Recorded success'),
      CANCELLED: say('Cancelada', 'Cancelled'), cancelled: say('Cancelada', 'Cancelled'),
      timeout: say('Tiempo agotado', 'Timed out'), INCONCLUSIVE: say('No concluyente', 'Inconclusive'),
      NEEDS_AUTHORIZATION: say('Necesita autorización', 'Needs authorization'), NEEDS_REVIEW: say('Necesita revisión', 'Needs review'),
      OUT_OF_SCOPE: say('Fuera de alcance', 'Out of scope'), pending: say('Pendiente', 'Pending'),
    }
    return Object.prototype.hasOwnProperty.call(labels, status) ? labels[status] : say('Estado observado', 'Observed status')
  }
  const stateTone = (status: string | null) => status !== null && ['failed', 'FAILED', 'FAIL', 'ERROR', 'timeout'].includes(status) ? 'failure' : status !== null && ['running', 'RUNNING', 'pending', 'NEEDS_AUTHORIZATION', 'NEEDS_REVIEW'].includes(status) ? 'pending' : 'neutral'
  const date = (value: string | null) => value && /(?:Z|[+-]\d{2}:\d{2})$/.test(value) && Number.isFinite(Date.parse(value)) ? <time dateTime={value}>{formatDate(value)} UTC</time> : <span>{say('Fecha no disponible', 'Date unavailable')}</span>
  const duration = (value: number | null) => value === null ? missing : value < 1000 ? `${formatNumber(value)} ms` : `${formatNumber(value / 1000, {minimumFractionDigits: 2, maximumFractionDigits: 2})} s`
  const cost = (value: number | null) => value === null ? missing : `$${formatNumber(value, {minimumFractionDigits: 4, maximumFractionDigits: 4})}`
  const bool = (value: boolean | null) => value === null ? missing : value ? say('Sí', 'Yes') : say('No', 'No')
  const metadata: Array<[string, string | null]> = selected ? [
    ['Key', selected.key], ['ID', selected.id], [say('ID de agente', 'Agent ID'), selected.agent_id], [say('Nombre histórico', 'Historical name'), selected.agent_name],
    [say('Conversación padre', 'Parent conversation'), selected.parent_conversation_id], [say('Conversación', 'Conversation'), selected.conversation_id], [say('Mensaje', 'Message'), selected.message_id],
    [say('ID de traza', 'Trace ID'), selected.trace_id], [say('ID de recibo', 'Receipt ID'), selected.receipt_id], ['SHA-256', selected.receipt_sha256], [say('Registro relacionado', 'Related record'), selected.related_key],
  ] : []
  return <section className={`job-history${inline ? ' job-history-inline' : ''}`} aria-label={say('Historial de trabajos', 'Work history')}>
    <div className="history-header"><h2>{say('Historial de trabajos', 'Work history')}</h2><button type="button" aria-disabled={loading} onClick={() => {if (!loading) setRefresh(value => value + 1)}}>{say('Actualizar', 'Refresh')}</button></div>
    <p className="work-history-explanation">{say('El estado pertenece a su fuente. Una respuesta recibida no acredita la finalización del encargo.', 'Each status belongs to its source. A received response does not establish completion of the task.')}</p>
    <label className="work-history-filter">{say('Filtrar por fuente', 'Filter by source')}<select value={query.kind} onChange={event => setQuery({kind: event.target.value as HistoryFilter, offset: 0})}><option value="all">{say('Todas las fuentes', 'All sources')}</option>{kinds.map(kind => <option key={kind} value={kind}>{sourceName(kind)}</option>)}</select></label>
    {loading && <p role="status">{say('Cargando historial…', 'Loading history…')}</p>}
    {error && <p role="alert">{error.kind === 'contract' ? say('El servidor no devolvió un índice de historial compatible.', 'The server did not return a compatible history index.') : error.kind === 'http' ? `${say('No se pudo cargar el historial.', 'History could not be loaded.')} HTTP ${error.status}` : say('No se pudo conectar para cargar el historial.', 'Could not connect to load history.')} {say('Pulsa Actualizar para reintentarlo.', 'Choose Refresh to retry.')}</p>}
    {page && (loading || error) && <p className="work-history-stale" role="status">{say('Mostrando la última carga válida; estos datos no se han actualizado.', 'Showing the last valid load; these records have not been refreshed.')}</p>}
    {page && <>
      <details className="work-history-sources" open={incomplete || undefined}><summary>{say('Fuentes del historial', 'History sources')}{incomplete ? ` · ${say('Cobertura incompleta', 'Incomplete coverage')}` : ''}</summary>
        <ul>{page.sources.map(source => <li key={source.kind}><span>{sourceName(source.kind)}</span><code>{source.kind}</code><span className={`work-history-source-state source-${source.state}`}>{sourceState(source.state)} ({source.state})</span>{source.truncated && <span>{say('Límite alcanzado', 'Limit reached')}</span>}{source.error_code !== null && <code>{source.error_code}</code>}</li>)}</ul>
      </details>
      {incomplete && <p className="work-history-warning" role="status">{say('Alguna fuente no está disponible o sólo se ha enumerado parcialmente. El total corresponde a los registros enumerados.', 'A source is unavailable or only partially enumerated. The total covers enumerated records.')}</p>}
      {!page.items.length && <p className="work-history-empty">{incomplete ? say('No hay registros enumerados en esta selección; la cobertura es incompleta.', 'No records are enumerated in this selection; coverage is incomplete.') : say('No hay registros en esta selección.', 'There are no records in this selection.')}</p>}
      <div className={`work-history-content${selected ? ' has-selection' : ''}`} aria-busy={loading}>
        <ul className="work-history-list" aria-label={say('Registros de trabajo', 'Work records')}>
          {page.items.map(item => <li key={item.key}><button type="button" className="work-history-row" aria-expanded={selectedKey === item.key} aria-controls={detailId} onClick={event => {selectedButton.current = event.currentTarget; setSelectedKey(item.key); onJobSelect?.(item)}}>
            <span className="work-history-row-state"><span className="work-history-kind">{sourceName(item.kind)} · {item.kind}</span><span className={`work-history-status status-${stateTone(item.status)}`}>{statusLabel(item.status)}{item.status !== null && <> · <code>{item.status}</code></>}</span></span>
            <span className="work-history-agent">{item.agent_name ?? say('Nombre de agente no registrado', 'Agent name not recorded')}{item.agent_id !== null && <code>{item.agent_id}</code>}</span>
            <span className="work-history-activity"><span>{say('Última actividad', 'Last activity')}</span>{date(item.activity_at)}</span><code className="work-history-key">{item.key}</code>
          </button></li>)}
        </ul>
        {selected && <section id={detailId} className="work-history-detail" aria-label={say('Metadatos del registro', 'Record metadata')}>
          <div className="work-history-detail-heading"><h3>{say('Metadatos del registro', 'Record metadata')}</h3><button type="button" onClick={() => {setSelectedKey(null); if (selectedButton.current?.isConnected) selectedButton.current.focus()}}>{say('Cerrar detalles', 'Close details')}</button></div>
          <p>{sourceName(selected.kind)} · <code>{selected.kind}</code> · {statusLabel(selected.status)}{selected.status !== null && <> · <code>{selected.status}</code></>}</p>
          <dl>{metadata.map(([label, value]) => <div key={label}><dt>{label}</dt><dd>{value === null ? missing : <code>{value}</code>}</dd></div>)}
            {([['created_at', say('Creación', 'Created')], ['started_at', say('Inicio', 'Started')], ['completed_at', say('Finalización registrada', 'Recorded finish')], ['activity_at', say('Última actividad', 'Last activity')]] as const).map(([field, label]) => <div key={field}><dt>{label}</dt><dd>{date(selected[field])}</dd></div>)}
            <div><dt>{say('Duración', 'Duration')}</dt><dd>{duration(selected.duration_ms)}</dd></div><div><dt>{say('Coste', 'Cost')}</dt><dd>{cost(selected.cost_usd)}</dd></div>
            <div><dt>{say('Herramientas ejecutadas', 'Tools executed')}</dt><dd>{bool(selected.tools_executed)}</dd></div><div><dt>{say('Escritura registrada', 'Write recorded')}</dt><dd>{bool(selected.target_written)}</dd></div><div><dt>{say('Recibos de herramienta', 'Tool receipts')}</dt><dd>{selected.tool_receipt_count === null ? missing : formatNumber(selected.tool_receipt_count)}</dd></div>
          </dl>
        </section>}
        {!selected && selectedKey !== null && <p className="work-history-selection-note">{say('El registro seleccionado no está en esta página. No se muestran detalles de una carga anterior.', 'The selected record is not on this page. Details from an earlier load are not displayed.')}</p>}
      </div>
    </>}
    <nav className="work-history-paging" aria-label={say('Paginación del historial', 'History pagination')}>
      <button type="button" aria-disabled={loading || query.offset === 0} onClick={() => {if (!loading && query.offset > 0) setQuery({...query, offset: Math.max(0, query.offset - 50)})}}>{say('Anterior', 'Previous')}</button>
      <span>{page ? `${formatNumber(page.items.length ? page.offset + 1 : 0)}–${formatNumber(page.items.length ? page.offset + page.items.length : 0)} ${say('de', 'of')} ${formatNumber(page.total)} ${say('enumerados', 'enumerated')}` : say('Sin página cargada', 'No page loaded')}</span>
      <button type="button" aria-disabled={loading || !page?.has_more} onClick={() => {if (!loading && page?.has_more && page.next_offset !== null) setQuery({...query, offset: page.next_offset})}}>{say('Siguiente', 'Next')}</button>
      {query.offset > 0 && <button type="button" aria-disabled={loading} onClick={() => {if (!loading) setQuery({...query, offset: 0})}}>{say('Primera página', 'First page')}</button>}
    </nav>
  </section>
}
