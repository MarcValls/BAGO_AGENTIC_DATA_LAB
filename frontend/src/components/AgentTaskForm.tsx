import { useId } from 'react'
import './AgentTaskForm.css'

export interface TaskDate { key: string; label: string; value: string }
export interface TaskDefinition { prompt: string; dates: TaskDate[] }

export function taskError(task: TaskDefinition): string {
  if (!task.prompt.trim() || task.prompt.trim().length > 8000) return 'Escribe una tarea de hasta 8000 caracteres.'
  if (task.dates.length > 8) return 'Máximo 8 fechas.'
  const keys = new Set<string>()
  for (const date of task.dates) {
    if (!/^[a-z][a-z0-9_]{0,39}$/.test(date.key) || keys.has(date.key)) return 'Cada fecha necesita una clave única: letras minúsculas, números o _.'
    keys.add(date.key)
    if (!date.label.trim() || date.label.length > 80) return 'Pon un nombre a cada fecha (máximo 80 caracteres).'
    const parsed = new Date(`${date.value}T00:00:00Z`)
    if (!/^\d{4}-\d{2}-\d{2}$/.test(date.value) || Number(date.value.slice(0, 4)) < 1 || Number.isNaN(parsed.getTime()) || parsed.toISOString().slice(0, 10) !== date.value) return 'Revisa las fechas.'
  }
  return ''
}

export default function AgentTaskForm({ value, onChange, disabled = false }: { value: TaskDefinition; onChange: (task: TaskDefinition) => void; disabled?: boolean }) {
  const id = useId()
  const updateDate = (index: number, changes: Partial<TaskDate>) => onChange({ ...value, dates: value.dates.map((date, position) => position === index ? { ...date, ...changes } : date) })
  return <div className="agent-task-form">
    <label htmlFor={`${id}-prompt`}>Tarea *</label>
    <textarea id={`${id}-prompt`} required maxLength={8000} rows={4} value={value.prompt} disabled={disabled} onChange={event => onChange({ ...value, prompt: event.target.value })} />
    <details className="agent-task-dates" open={value.dates.length ? true : undefined}>
      <summary>Fechas <span>{value.dates.length}/8</span></summary>
      {value.dates.map((date, index) => <div className="agent-task-date" key={index}>
        <label>Nombre<input aria-label={`Nombre de fecha ${index + 1}`} maxLength={80} value={date.label} disabled={disabled} onChange={event => updateDate(index, { label: event.target.value })} /></label>
        <label>Clave<input aria-label={`Clave de fecha ${index + 1}`} maxLength={40} value={date.key} disabled={disabled} onChange={event => updateDate(index, { key: event.target.value })} /></label>
        <label>Fecha<input aria-label={`Fecha ${index + 1}`} type="date" required value={date.value} disabled={disabled} onChange={event => updateDate(index, { value: event.target.value })} /></label>
        <button type="button" aria-label={`Eliminar fecha ${index + 1}`} disabled={disabled} onClick={() => onChange({ ...value, dates: value.dates.filter((_, position) => position !== index) })}>×</button>
      </div>)}
      <div className="agent-task-dates-actions"><button type="button" disabled={disabled || value.dates.length >= 8} onClick={() => {
        let next = 1
        while (value.dates.some(date => date.key === `fecha_${next}`)) next++
        onChange({ ...value, dates: [...value.dates, { key: `fecha_${next}`, label: `Fecha ${next}`, value: '' }] })
      }}>Añadir fecha</button><small>En la tarea: {'{{clave}}'}</small></div>
    </details>
  </div>
}
