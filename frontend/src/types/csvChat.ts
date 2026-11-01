import type {ProjectPermissionSnapshot} from './projectPermissions'

export type CsvReadSelection = {
  path: string
  delimiter: 'auto' | ',' | ';' | '\t' | '|'
  decimal_separator: '.' | ','
}

export type CsvChatSubmission = {
  message: string
  csv_read: CsvReadSelection
  expected_project: Pick<ProjectPermissionSnapshot, 'project_id' | 'binding' | 'revision'>
  projectRoot: string
  contextKey: string
}

export type CsvChatContext = {
  projectId: string | null
  projectRoot: string | null
  contextKey: string
  disabled: boolean
  notice?: string | Error | null
  onSubmit: (request: CsvChatSubmission, signal: AbortSignal) => Promise<boolean>
}

export function isProjectCsvPath(path: string): boolean {
  return path.length > 0 && path.length <= 512 && /\.csv$/i.test(path)
    && !path.startsWith('/') && !path.includes('\\') && !/[\x00-\x1f:*?"<>|]/.test(path)
    && path.split('/').every(part => Boolean(part) && part !== '.' && part !== '..' && part === part.trim())
}

/** The host uses sorted keys, UTF-8 and compact JSON for this exact request. */
export async function csvRequestFingerprint(message: string, selection: CsvReadSelection): Promise<string> {
  const canonical = JSON.stringify({csv_read: {decimal_separator: selection.decimal_separator, delimiter: selection.delimiter, path: selection.path}, message})
  const digest = await globalThis.crypto.subtle.digest('SHA-256', new TextEncoder().encode(canonical))
  return Array.from(new Uint8Array(digest), byte => byte.toString(16).padStart(2, '0')).join('')
}
