import type {CSSProperties} from 'react'
import type {ProjectTreeEntry} from '../types/projectPermissions'

type Props = {
  entriesByDirectory: Record<string, ProjectTreeEntry[]>
  loadingDirectories: string[]
  truncatedDirectories: string[]
  expandedDirectories: string[]
  readDirectories: string[]
  writeDirectories: string[]
  onToggleDirectory: (path: string) => void
  onToggle: (kind: 'read' | 'write', path: string, enabled: boolean) => void
}

function inherited(paths: string[], path: string) {
  return paths.some(scope => scope !== path && (scope === '.' || path.startsWith(`${scope}/`)))
}

export default function ProjectPermissionTree({entriesByDirectory, loadingDirectories, truncatedDirectories, expandedDirectories, readDirectories, writeDirectories, onToggleDirectory, onToggle}: Props) {
  const renderRows = (entries: ProjectTreeEntry[], level: number) => entries.map(entry => {
    const readParent = inherited(readDirectories, entry.path)
    const writeParent = inherited(writeDirectories, entry.path)
    const expanded = expandedDirectories.includes(entry.path)
    const loading = loadingDirectories.includes(entry.path)
    const children = entriesByDirectory[entry.path]
    const truncated = truncatedDirectories.includes(entry.path)
    return <li key={entry.path} data-kind={entry.kind}>
      <div className="project-permission-tree__row" style={{'--tree-level': level - 1} as CSSProperties}>
        {entry.kind === 'directory'
          ? <button type="button" className="project-permission-tree__open" aria-expanded={expanded} onClick={() => onToggleDirectory(entry.path)} aria-label={`${expanded ? 'Contraer' : 'Expandir'} carpeta ${entry.name}`}><span className="project-permission-tree__chevron" aria-hidden="true">{expanded ? '▾' : '▸'}</span><span className="project-permission-tree__icon" aria-hidden="true">▰</span>{entry.name}</button>
          : <span className="project-permission-tree__name"><span className="project-permission-tree__icon" aria-hidden="true">▤</span>{entry.name}</span>}
        <label><input type="checkbox" aria-label={`Permitir lectura en ${entry.path}`} checked={readDirectories.includes(entry.path) || readParent} disabled={readParent} onChange={event => onToggle('read', entry.path, event.target.checked)}/><span>Leer</span></label>
        <label><input type="checkbox" aria-label={`Permitir escritura en ${entry.path}`} checked={writeDirectories.includes(entry.path) || writeParent} disabled={writeParent} onChange={event => onToggle('write', entry.path, event.target.checked)}/><span>Escribir</span></label>
      </div>
      {entry.kind === 'directory' && expanded && <>
        {loading && <p className="project-permission-tree__node-status" role="status">Cargando…</p>}
        {!loading && children?.length ? <ul className="project-permission-tree__children">{renderRows(children, level + 1)}</ul> : null}
        {!loading && children && children.length === 0 && <p className="project-permission-tree__node-status">Carpeta vacía</p>}
        {truncated && <p className="project-permission-tree__node-status" role="status">Contenido limitado por seguridad.</p>}
      </>}
    </li>
  })

  const readRoot = readDirectories.includes('.')
  const writeRoot = writeDirectories.includes('.')
  return <section className="project-permission-tree" aria-label="Árbol de archivos y permisos">
    <div className="project-permission-tree__heading"><div><strong>Archivos y carpetas del proyecto</strong><p>Expande carpetas y marca lectura o escritura por elemento.</p></div><code>.</code></div>
    <div className="project-permission-tree__column-headings" aria-hidden="true"><span>Elemento</span><span>Lectura</span><span>Escritura</span></div>
    {loadingDirectories.includes('.') && <p role="status">Cargando archivos del proyecto.</p>}
    {!loadingDirectories.includes('.') && <ul className="project-permission-tree__root-list" aria-label="Archivos y carpetas">{renderRows(entriesByDirectory['.'] ?? [], 1)}</ul>}
    {!loadingDirectories.includes('.') && entriesByDirectory['.']?.length === 0 && <p>El proyecto no contiene archivos ni subcarpetas visibles.</p>}
    <div className="project-permission-tree__current"><strong>Todo el proyecto</strong><label><input type="checkbox" aria-label="Permitir lectura en ." checked={readRoot} onChange={event => onToggle('read', '.', event.target.checked)}/>Leer</label><label><input type="checkbox" aria-label="Permitir escritura en ." checked={writeRoot} onChange={event => onToggle('write', '.', event.target.checked)}/>Escribir</label></div>
    {truncatedDirectories.includes('.') && <p role="status">La lista supera el límite de seguridad. Expande una carpeta para ver sus elementos.</p>}
  </section>
}
