import type {ProjectTreeEntry} from '../types/projectPermissions'

type Props = {
  directory: string
  entries: ProjectTreeEntry[]
  readDirectories: string[]
  writeDirectories: string[]
  loading: boolean
  truncated: boolean
  onOpen: (path: string) => void
  onToggle: (kind: 'read' | 'write', path: string, enabled: boolean) => void
}

function inherited(paths: string[], path: string) {
  return paths.some(scope => scope !== path && (scope === '.' || path.startsWith(`${scope}/`)))
}

export default function ProjectPermissionTree({directory, entries, readDirectories, writeDirectories, loading, truncated, onOpen, onToggle}: Props) {
  const current = directory || '.'
  const explicit = (paths: string[], path: string) => paths.includes(path)
  const row = (entry: ProjectTreeEntry) => {
    const readParent = inherited(readDirectories, entry.path)
    const writeParent = inherited(writeDirectories, entry.path)
    return <li key={entry.path} data-kind={entry.kind}>
      {entry.kind === 'directory'
        ? <button type="button" className="project-permission-tree__open" onClick={() => onOpen(entry.path)} aria-label={`Abrir carpeta ${entry.name}`}><span aria-hidden="true">▸</span>{entry.name}</button>
        : <span className="project-permission-tree__name"><span aria-hidden="true">▤</span>{entry.name}</span>}
      <label><input type="checkbox" aria-label={`Permitir lectura en ${entry.path}`} checked={explicit(readDirectories, entry.path) || readParent} disabled={readParent} onChange={event => onToggle('read', entry.path, event.target.checked)}/><span>Leer</span></label>
      <label><input type="checkbox" aria-label={`Permitir escritura en ${entry.path}`} checked={explicit(writeDirectories, entry.path) || writeParent} disabled={writeParent} onChange={event => onToggle('write', entry.path, event.target.checked)}/><span>Escribir</span></label>
    </li>
  }
  const readInherited = inherited(readDirectories, current)
  const writeInherited = inherited(writeDirectories, current)
  return <section className="project-permission-tree" aria-label="Árbol de archivos y permisos">
    <div className="project-permission-tree__heading"><div><strong>Archivos y carpetas</strong><p>La selección de una carpeta cubre todo su contenido.</p></div><code>{current}</code></div>
    <div className="project-permission-tree__column-headings" aria-hidden="true"><span>Elemento</span><span>Lectura</span><span>Escritura</span></div>
    {current !== '.' && <button type="button" className="project-permission-tree__parent" onClick={() => onOpen(current.includes('/') ? current.slice(0, current.lastIndexOf('/')) : '.')}>↑ Carpeta superior</button>}
    {loading && <p role="status">Cargando contenido de la carpeta.</p>}
    {!loading && <ul>{entries.map(row)}</ul>}
    {!loading && entries.length === 0 && <p>Esta carpeta no contiene archivos ni subcarpetas visibles.</p>}
    {!loading && <div className="project-permission-tree__current"><strong>Aplicar a esta carpeta</strong><label><input type="checkbox" aria-label={`Permitir lectura en ${current}`} checked={explicit(readDirectories, current) || readInherited} disabled={readInherited} onChange={event => onToggle('read', current, event.target.checked)}/>Leer</label><label><input type="checkbox" aria-label={`Permitir escritura en ${current}`} checked={explicit(writeDirectories, current) || writeInherited} disabled={writeInherited} onChange={event => onToggle('write', current, event.target.checked)}/>Escribir</label></div>}
    {truncated && <p role="status">La lista supera el límite de seguridad. Abre una carpeta para ver sus elementos.</p>}
  </section>
}
