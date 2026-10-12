import type { ReactNode } from 'react'

interface WindowPanelProps {
  title: string
  description?: string
  actions?: ReactNode
  children: ReactNode
  className?: string
  hideTitlebar?: boolean
}

export default function WindowPanel({ title, description, actions, children, className = '', hideTitlebar = false }: WindowPanelProps) {
  return (
    <section className={`window-panel ${className}`.trim()} aria-label={title}>
      {!hideTitlebar && <header className="window-panel-titlebar">
        <div className="window-panel-heading">
          <h2>{title}</h2>
          {description && <p>{description}</p>}
        </div>
        {actions && <div className="window-panel-actions">{actions}</div>}
      </header>}
      <div className="window-panel-content">{children}</div>
    </section>
  )
}
