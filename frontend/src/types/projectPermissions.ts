export type ProjectPermissionState = 'active' | 'revoked' | 'unknown' | string

export type ProjectPermissionSnapshot = {
  project_id: string | null
  root: string | null
  binding: unknown
  revision: number | null
  state: ProjectPermissionState
  read_directories: string[]
  write_directories: string[]
}

export type ProjectDirectory = {name: string; path: string}

export function isProjectPermissionSnapshot(value: unknown): value is ProjectPermissionSnapshot {
  if (!value || typeof value !== 'object') return false
  const item = value as Record<string, unknown>
  return (typeof item.project_id === 'string' || item.project_id === null)
    && (typeof item.root === 'string' || item.root === null)
    && 'binding' in item
    && (typeof item.revision === 'number' || item.revision === null)
    && typeof item.state === 'string'
    && Array.isArray(item.read_directories) && item.read_directories.every(path => typeof path === 'string')
    && Array.isArray(item.write_directories) && item.write_directories.every(path => typeof path === 'string')
}

export function isDirectoryListing(value: unknown): value is {project_id: string; root: string; binding: unknown; revision: number; directory: string; directories: ProjectDirectory[]; truncated: boolean} {
  if (!value || typeof value !== 'object') return false
  const item = value as Record<string, unknown>
  return typeof item.project_id === 'string' && typeof item.root === 'string' && 'binding' in item
    && typeof item.revision === 'number' && typeof item.directory === 'string'
    && Array.isArray(item.directories) && item.directories.every((entry: unknown) => Boolean(entry && typeof entry === 'object' && typeof (entry as ProjectDirectory).name === 'string' && typeof (entry as ProjectDirectory).path === 'string'))
    && typeof item.truncated === 'boolean'
}
