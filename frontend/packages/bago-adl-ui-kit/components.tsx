import type { ButtonHTMLAttributes, HTMLAttributes, KeyboardEvent, ReactNode } from 'react'

export type ButtonVariant = 'primary' | 'secondary' | 'ghost' | 'danger'
export function BagoButton({ variant = 'secondary', className = '', ...props }: ButtonHTMLAttributes<HTMLButtonElement> & { variant?: ButtonVariant }) {
  return <button {...props} className={`bago-ui-button bago-ui-button--${variant} ${className}`.trim()} />
}

export function BagoPanel({ className = '', ...props }: HTMLAttributes<HTMLElement>) {
  return <section {...props} className={`bago-ui-panel ${className}`.trim()} />
}

export function BagoPageHeader({ kicker, title, description, actions }: { kicker?: string; title: string; description?: string; actions?: ReactNode }) {
  return <header className="bago-ui-page-header"><div className="bago-ui-page-header__copy">{kicker && <p className="bago-ui-kicker">{kicker}</p>}<h1 className="bago-ui-title">{title}</h1>{description && <p className="bago-ui-description">{description}</p>}</div>{actions && <div className="bago-ui-page-header__actions">{actions}</div>}</header>
}

export function BagoMetric({ label, value, hint }: { label: string; value: ReactNode; hint?: ReactNode }) {
  return <div className="bago-ui-panel bago-ui-metric"><span className="bago-ui-metric__label">{label}</span><strong className="bago-ui-metric__value">{value}</strong>{hint && <span className="bago-ui-metric__hint">{hint}</span>}</div>
}

export type StatusTone = 'success' | 'warning' | 'danger' | 'info' | 'neutral'
export function BagoStatus({ tone = 'neutral', children }: { tone?: StatusTone; children: ReactNode }) {
  return <span className={`bago-ui-status bago-ui-status--${tone}`}>{children}</span>
}

export function BagoEmptyState({ title, description, action }: { title: string; description?: string; action?: ReactNode }) {
  return <div className="bago-ui-empty"><h2 className="bago-ui-empty__title">{title}</h2>{description && <p className="bago-ui-empty__description">{description}</p>}{action}</div>
}

export interface BagoTabItem<T extends string> { id: T; label: ReactNode }
export function BagoTabStrip<T extends string>({ label, items, value, onChange }: { label: string; items: BagoTabItem<T>[]; value: T; onChange: (value: T) => void }) {
  return <div className="bago-ui-tabs" role="group" aria-label={label}>{items.map((item) => <button key={item.id} type="button" className="bago-ui-tab" aria-pressed={value === item.id} onClick={() => onChange(item.id)}>{item.label}</button>)}</div>
}

export interface BagoGridRow { id: string; cells: ReactNode[] }
export function BagoDataGrid({ label, columns, rows, selectedId, onSelect }: { label: string; columns: string[]; rows: BagoGridRow[]; selectedId?: string; onSelect?: (id: string) => void }) {
  const activate = (event: KeyboardEvent<HTMLTableRowElement>, id: string) => { if ((event.key === 'Enter' || event.key === ' ') && onSelect) { event.preventDefault(); onSelect(id) } }
  return <div className="bago-ui-grid-scroll" role="region" aria-label={label} tabIndex={0}><table className="bago-ui-grid"><thead><tr>{columns.map((column) => <th key={column} scope="col">{column}</th>)}</tr></thead><tbody>{rows.map((row) => <tr key={row.id} aria-selected={onSelect ? selectedId === row.id : undefined} tabIndex={onSelect ? 0 : undefined} onClick={onSelect ? () => onSelect(row.id) : undefined} onKeyDown={onSelect ? (event) => activate(event, row.id) : undefined}>{row.cells.map((cell, index) => <td key={`${row.id}:${index}`}>{cell}</td>)}</tr>)}</tbody></table></div>
}
