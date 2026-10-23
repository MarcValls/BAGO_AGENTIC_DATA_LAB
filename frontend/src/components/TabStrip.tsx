import {useI18n,t,localMessage,errorMessage,apiError,formatDate,formatNumber} from '../i18n'
import type { ReactNode } from 'react'

export interface TabStripItem<T extends string> {
  id: T
  label: ReactNode
}

interface TabStripProps<T extends string> {
  label: string
  items: TabStripItem<T>[]
  value: T
  onChange: (value: T) => void
}

/** A compact, controlled filter strip. It intentionally uses group semantics, not ARIA tabs. */
export default function TabStrip<T extends string>({ label, items, value, onChange }: TabStripProps<T>) {
  useI18n()

  return (
    <div className="tab-strip" role="group" aria-label={label}>
      {items.map((item) => (
        <button
          key={item.id}
          type="button"
          className={`tab-strip-item ${value === item.id ? 'is-selected' : ''}`}
          aria-pressed={value === item.id}
          onClick={() => onChange(item.id)}
        >
          {item.label}
        </button>
      ))}
    </div>
  )
}
