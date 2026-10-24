import {useI18n, t, formatDate, formatNumber, apiError, errorMessage} from '../i18n'
import { useId } from 'react'
import './AgentTaskForm.css'

export interface TaskDate { key: string; label: string; value: string }
export interface TaskDefinition { prompt: string; dates: TaskDate[] }

export function taskError(task: TaskDefinition): string {
  if (!task.prompt.trim() || task.prompt.trim().length > 8000) return t('agents.AgentTaskForm.escribe_una_tarea_de_hasta_8000_caracteres')
  if (task.dates.length > 8) return t('agents.AgentTaskForm.maximo_8_fechas')
  const keys = new Set<string>()
  for (const date of task.dates) {
    if (!/^[a-z][a-z0-9_]{0,39}$/.test(date.key) || keys.has(date.key)) return t('agents.AgentTaskForm.cada_fecha_necesita_una_clave_unica_letras_minusculas_numeros_o')
    keys.add(date.key)
    if (!date.label.trim() || date.label.length > 80) return t('agents.AgentTaskForm.pon_un_nombre_a_cada_fecha_maximo_80_caracteres')
    const parsed = new Date(`${date.value}T00:00:00Z`)
    if (!/^\d{4}-\d{2}-\d{2}$/.test(date.value) || Number(date.value.slice(0, 4)) < 1 || Number.isNaN(parsed.getTime()) || parsed.toISOString().slice(0, 10) !== date.value) return t('agents.AgentTaskForm.revisa_las_fechas')
  }
  return ''
}

export default function AgentTaskForm({ value, onChange, disabled = false }: { value: TaskDefinition; onChange: (task: TaskDefinition) => void; disabled?: boolean }) {
  useI18n()
  const id = useId()
  const updateDate = (index: number, changes: Partial<TaskDate>) => onChange({ ...value, dates: value.dates.map((date, position) => position === index ? { ...date, ...changes } : date) })
  return <div className="agent-task-form">
    <label htmlFor={`${id}-prompt`}>{t('agents.AgentTaskForm.tarea')}</label>
    <textarea id={`${id}-prompt`} required maxLength={8000} rows={4} value={value.prompt} disabled={disabled} onChange={event => onChange({ ...value, prompt: event.target.value })} />
    <details className="agent-task-dates" open={value.dates.length ? true : undefined}>
      <summary>{t('agents.AgentTaskForm.fechas')} <span>{value.dates.length}/8</span></summary>
      {value.dates.map((date, index) => <div className="agent-task-date" key={index}>
        <label>{t('agents.AgentTaskForm.nombre')}<input aria-label={t('agents.AgentTaskForm.nombre_de_fecha_p0', {p0: index + 1})} maxLength={80} value={date.label} disabled={disabled} onChange={event => updateDate(index, { label: event.target.value })} /></label>
        <label>{t('agents.AgentTaskForm.clave')}<input aria-label={t('agents.AgentTaskForm.clave_de_fecha_p0', {p0: index + 1})} maxLength={40} value={date.key} disabled={disabled} onChange={event => updateDate(index, { key: event.target.value })} /></label>
        <label>{t('agents.AgentTaskForm.fecha')}<input aria-label={t('agents.AgentTaskForm.fecha_p0', {p0: index + 1})} type="date" required value={date.value} disabled={disabled} onChange={event => updateDate(index, { value: event.target.value })} /></label>
        <button type="button" aria-label={t('agents.AgentTaskForm.eliminar_fecha_p0', {p0: index + 1})} disabled={disabled} onClick={() => onChange({ ...value, dates: value.dates.filter((_, position) => position !== index) })}>×</button>
      </div>)}
      <div className="agent-task-dates-actions"><button type="button" disabled={disabled || value.dates.length >= 8} onClick={() => {
        let next = 1
        while (value.dates.some(date => date.key === `fecha_${next}`)) next++
        onChange({ ...value, dates: [...value.dates, { key: `fecha_${next}`, label: `Fecha ${next}`, value: '' }] })
      }}>{t('agents.AgentTaskForm.anadir_fecha')}</button><small>{t('agents.AgentTaskForm.en_la_tarea')} {'{{clave}}'}</small></div>
    </details>
  </div>
}

/** Local UI messages resolve at presentation time; no payload or evidence is rewritten. */
export class AgentPresentationError extends Error {
  constructor(private readonly presentation: () => string) { super(); this.name = 'AgentPresentationError' }
  get message() { return this.presentation() }
}

/** Human label plus the original protocol value. Never used for comparison or payloads. */
export function agentStateLabel(value: string): string {
  const labels: Record<string, () => string> = {
"available": () => t('agents.state.available'),
"unavailable": () => t('agents.state.unavailable'),
"unknown": () => t('agents.state.unknown'),
"eligible": () => t('agents.state.eligible'),
"ineligible": () => t('agents.state.ineligible'),
"authorized": () => t('agents.state.authorized'),
"rejected": () => t('agents.state.rejected'),
"requires_approval": () => t('agents.state.requires_approval'),
"expired": () => t('agents.state.expired'),
"revoked": () => t('agents.state.revoked'),
"valid": () => t('agents.state.valid'),
"not_yet_valid": () => t('agents.state.not_yet_valid'),
"not_started": () => t('agents.state.not_started'),
"succeeded": () => t('agents.state.succeeded'),
"unverified": () => t('agents.state.unverified'),
"failed": () => t('agents.state.failed'),
"partial": () => t('agents.state.partial'),
"read_only": () => t('agents.state.read_only'),
"mutating": () => t('agents.state.mutating'),
"external": () => t('agents.state.external'),
"supports": () => t('agents.state.supports'),
"contradicts": () => t('agents.state.contradicts'),
"context_only": () => t('agents.state.context_only'),
"insufficient": () => t('agents.state.insufficient'),
"rag": () => t('agents.state.rag'),
"tool": () => t('agents.state.tool'),
"multi-agent": () => t('agents.state.multi-agent'),
"PASS": () => t('agents.state.PASS'),
"FAIL": () => t('agents.state.FAIL'),
"ERROR": () => t('agents.state.ERROR'),
"PARTIAL": () => t('agents.state.PARTIAL'),
"approve": () => t('agents.state.approve'),
"reject": () => t('agents.state.reject'),
"cancel": () => t('agents.state.cancel'),
"sequence_gap": () => t('agents.state.sequence_gap'),
"missing_parent": () => t('agents.state.missing_parent'),
"duplicate_event_id": () => t('agents.state.duplicate_event_id'),
"trace_id_mismatch": () => t('agents.state.trace_id_mismatch'),
"invalid_sequence": () => t('agents.state.invalid_sequence')
  }
  return Object.prototype.hasOwnProperty.call(labels, value) ? `${labels[value]()} (${value})` : t('agents.state.unrecognized', {value})
}

export function presentAgentError(error: unknown): string {
  if (error instanceof AgentPresentationError || (error instanceof Error && error.name === 'PresentationError')) return errorMessage(error)
  return errorMessage(apiError({detail: {message: error instanceof Error ? error.message : String(error ?? '')}}, 0, 'agents'))
}

