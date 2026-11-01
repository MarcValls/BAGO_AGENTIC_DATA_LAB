import {apiError} from '../i18n'
export type Schedule = { kind: 'now' | 'once' | 'daily' | 'weekly'; timezone: string; at: string | null; time: string | null; weekdays: number[] }
export type Contact = { id: string; name: string; phone: string }
export type Draft = { id: string; revision: string; contact_id: string; recipient: Contact; text: string; attachments: Array<{ path: string; name: string; sha256: string; size: number }>; schedule: Schedule; state: string; next_run_at: string | null; created_at: string; updated_at: string; conversation_id: string | null; last_error: string | null }
export type Run = { id: string; draft_id: string; occurrence_at: string; started_at: string; finished_at: string | null; state: string; receipt: unknown; error: string | null }
export type WhatsAppStatus = { state: string; configured: boolean; label: string; checked_at: string | null; reason: string | null; browser_available: boolean; persistent_profile: boolean }
export type WhatsAppAuthorization = { available: boolean; enabled: boolean; revision: string; grant_id: string | null; project: {project_id: string; root: string; binding: string}; session_identity: string | null; validity: 'until_revoked'; granted_at: string | null; revoked_at: string | null }
export async function communicationRequest<T>(url: string, init?: RequestInit): Promise<T> {
  const response = await fetch(url, init)
  const body = await response.json()
  if (!response.ok) {
    throw apiError(body,response.status,'communications')
  }
  return body as T
}
