import type {ProjectDirectory} from '../types/projectPermissions'

type Props = {
  directory: string
  directories: ProjectDirectory[]
  readCurrent: boolean
  writeCurrent: boolean
  readDirectories: string[]
  writeDirectories: string[]
  loading: boolean
  truncated: boolean
  onOpen: (path: string) => void
  onToggle: (kind: 'read' | 'write', path: string, enabled: boolean) => void
}

export default function ProjectPermissionTree({directory, directories, readCurrent, writeCurrent, readDirectories, writeDirectories, loading, truncated, onOpen, onToggle}: Props) {
  const isAllowed = (paths: string[], path: string) => paths.includes(path)
  return <section className="project-permission-tree" aria-label="Carpetas del proyecto">
    <p>Carpeta: <code>{directory || '.'}</code></p>
    {!loading && <div className="project-permission-tree__current"><strong>Permisos de esta carpeta</strong><label><input type="checkbox" aria-label={`Permitir lectura en ${directory || '.'}`} checked={readCurrent} onChange={event => onToggle('read', directory || '.', event.target.checked)}/>Leer</label><label><input type="checkbox" aria-label={`Permitir escritura en ${directory || '.'}`} checked={writeCurrent} onChange={event => onToggle('write', directory || '.', event.target.checked)}/>Escribir</label></div>}
    {!loading && directory && <button type="button" onClick={() => onOpen(directory.includes('/') ? directory.slice(0, directory.lastIndexOf('/')) : '.')}>↑ Carpeta superior</button>}
    {loading && <p role="status">Cargando carpetas…</p>}
    {!loading && <ul>{directories.map(item => <li key={item.path}>
      <button type="button" className="project-permission-tree__open" onClick={() => onOpen(item.path)} aria-label={`Abrir carpeta ${item.name}`}>📁 {item.name}</button>
      <label><input type="checkbox" aria-label={`Permitir lectura en ${item.path}`} checked={isAllowed(readDirectories, item.path)} onChange={event => onToggle('read', item.path, event.target.checked)}/>Leer</label>
      <label><input type="checkbox" aria-label={`Permitir escritura en ${item.path}`} checked={isAllowed(writeDirectories, item.path)} onChange={event => onToggle('write', item.path, event.target.checked)}/>Escribir</label>
    </li>)}</ul>}
    {!loading && directories.length === 0 && <p>No hay subcarpetas en esta ubicación.</p>}
    {truncated && <p role="status">La lista está limitada. Abre una carpeta para consultar su contenido.</p>}
  </section>
}
