import {apiError,localMessage} from '../i18n'
export interface AddressContact {
  id: string; name: string; phone: string; email: string; source: string; source_id: string
  revision: string; created_at: string; updated_at: string
}
export interface GoogleContactStatus {
  configured: boolean; connected: boolean; state: string; scope: string
  live_verified: boolean; last_error: string | null
}
export interface ContactPreview {
  preview_id: string; revision: string; source: string; created_at: string; expires_at: string
  contacts: Array<{selection_id: string; name: string; phone: string; email: string; source_id: string;
    duplicates: Array<{id: string; name: string}>; warnings: string[]}>
}
export const contactsBase = '/api/contacts/v1'
export async function contactsRequest<T>(path: string, method = 'GET', body?: unknown): Promise<T> {
  const response = await fetch(contactsBase + path, {method,
    headers: body === undefined ? undefined : {'Content-Type': 'application/json'},
    body: body === undefined ? undefined : JSON.stringify(body)})
  const result = await response.json().catch(() => null)
  if (!response.ok) {
    throw apiError(result,response.status,'contacts')
  }
  if (!result || typeof result !== 'object') throw localMessage('common.requestFailed')
  return result as T
}
