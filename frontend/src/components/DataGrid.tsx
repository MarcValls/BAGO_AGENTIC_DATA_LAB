import type { ReactNode, KeyboardEvent } from 'react'

export interface DataGridRow {
  id: string
  cells: ReactNode[]
}

interface DataGridProps {
  label: string
  columns: string[]
  rows: DataGridRow[]
  selectedId?: string
  onSelect?: (id: string) => void
}

export default function DataGrid({ label, columns, rows, selectedId, onSelect }: DataGridProps) {
  const activateOnEnter = (event: KeyboardEvent<HTMLTableRowElement>, id: string) => {
    if ((event.key === 'Enter' || event.key === ' ') && onSelect) {
      event.preventDefault()
      onSelect(id)
    }
  }

  return (
    <div className="data-grid-scroll" role="region" aria-label={label} tabIndex={0}>
      <table className="data-grid">
        <thead><tr>{columns.map((column) => <th key={column} scope="col">{column}</th>)}</tr></thead>
        <tbody>
          {rows.map((row) => (
            <tr
              key={row.id}
              className={selectedId === row.id ? 'is-selected' : ''}
              aria-selected={onSelect ? selectedId === row.id : undefined}
              tabIndex={onSelect ? 0 : undefined}
              onClick={onSelect ? () => onSelect(row.id) : undefined}
              onKeyDown={onSelect ? (event) => activateOnEnter(event, row.id) : undefined}
            >
              {row.cells.map((cell, index) => <td key={`${row.id}:${index}`}>{cell}</td>)}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
