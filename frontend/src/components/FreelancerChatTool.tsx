import { useEffect, useState } from 'react'
import type { FormEvent } from 'react'
import { apiError, errorMessage, t, useI18n } from '../i18n'
import './FreelancerChatTool.css'

type Connection = { id: string; name: string; environment: 'sandbox' | 'production'; state: string; account_id: number | null; username: string | null }
type Operation = 'projects.search' | 'project.read' | 'threads.list' | 'messages.read'
type Challenge = { challenge_id: string; operation: Operation; arguments: Record<string, unknown>; account_id: number; environment: string; expires_in_seconds: number; request_fingerprint: string }

async function request(url: string, init?: RequestInit): Promise<any> {
  const response = await fetch(url, { cache: 'no-store', ...init })
  const body = await response.json()
  if (!response.ok) throw apiError(body, response.status, 'agents')
  return body
}
const post = (body: unknown): RequestInit => ({ method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) })

export default function FreelancerChatTool({ conversationId, conversationRevision, enabled }: { conversationId?: string; conversationRevision?: number; enabled: boolean }) {
  useI18n()
  const [connections, setConnections] = useState<Connection[]>([])
  const [connectionId, setConnectionId] = useState('')
  const [loading, setLoading] = useState(false)
  const [busy, setBusy] = useState(false)
  const [operation, setOperation] = useState<Operation>('projects.search')
  const [query, setQuery] = useState('')
  const [targetId, setTargetId] = useState('')
  const [challenge, setChallenge] = useState<Challenge | null>(null)
  const [result, setResult] = useState<any>(null)
  const [error, setError] = useState<unknown>('')

  useEffect(() => {
    setChallenge(null); setResult(null); setError('')
  }, [conversationId, conversationRevision])

  useEffect(() => {
    if (!enabled || !conversationId || conversationRevision === undefined) { setConnections([]); setConnectionId(''); return }
    let current = true
    setLoading(true)
    request('/api/connections/freelancer').then(data => {
      if (!current) return
      const rows = Array.isArray(data.connections) ? data.connections.filter((row: any) => row?.state === 'connected' && typeof row.id === 'string') : []
      setConnections(rows)
      setConnectionId(previous => rows.some((row: Connection) => row.id === previous) ? previous : rows[0]?.id ?? '')
    }).catch(cause => { if (current) setError(cause) }).finally(() => { if (current) setLoading(false) })
    return () => { current = false }
  }, [enabled, conversationId, conversationRevision])

  const argumentsForOperation = (): Record<string, unknown> | null => {
    if (operation === 'projects.search') return query.trim() ? { query: query.trim(), limit: 10, offset: 0 } : null
    if (operation === 'threads.list') return { count: 10 }
    const id = Number(targetId)
    if (!Number.isSafeInteger(id) || id < 1) return null
    return operation === 'project.read' ? { project_id: id } : { thread_id: id, limit: 10, offset: 0 }
  }

  const prepare = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    if (!enabled || !conversationId || conversationRevision === undefined || !connectionId) return
    const args = argumentsForOperation()
    if (!args) { setError(t('commerce.freelancer_invalid_input')); return }
    setBusy(true); setError(''); setChallenge(null); setResult(null)
    try {
      const value = await request(`/api/connections/freelancer/${encodeURIComponent(connectionId)}/challenge`, post({
        conversation_id: conversationId, conversation_revision: conversationRevision,
        operation, arguments: args,
      })) as Challenge
      setChallenge(value)
    } catch (cause) { setError(cause) }
    finally { setBusy(false) }
  }

  const authorizeAndRead = async () => {
    if (!challenge || !conversationId || conversationRevision === undefined || !connectionId) return
    setBusy(true); setError(''); setResult(null)
    try {
      const value = await request(`/api/connections/freelancer/${encodeURIComponent(connectionId)}/read`, post({
        challenge_id: challenge.challenge_id, conversation_id: conversationId,
        conversation_revision: conversationRevision,
      }))
      setResult(value)
      setChallenge(null)
    } catch (cause) { setError(cause); setChallenge(null) }
    finally { setBusy(false) }
  }

  return <section className="freelancer-chat-tool" aria-labelledby="freelancer-chat-title">
    <header><p className="app-kicker">{t('commerce.freelancer_untrusted_remote')}</p><h2 id="freelancer-chat-title">Freelancer · {t('commerce.freelancer_read_only')}</h2>
      <p>{t('commerce.freelancer_chat_intro')}</p></header>
    {!enabled || !conversationId || conversationRevision === undefined
      ? <p role="status">{t('commerce.freelancer_assistant_chat_only')}</p>
      : <>
        {error && <p className="freelancer-chat-error" role="alert">{errorMessage(error)}</p>}
        {loading ? <p role="status">{t('commerce.loading')}</p> : connections.length === 0
          ? <p>{t('commerce.freelancer_no_verified_accounts')}</p>
          : <>
            <form onSubmit={event => void prepare(event)}>
              <label>{t('commerce.freelancer_account')}<select value={connectionId} onChange={event => { setConnectionId(event.target.value); setChallenge(null); setResult(null) }}>
                {connections.map(connection => <option key={connection.id} value={connection.id}>{connection.name} · {connection.environment} · {connection.username || `ID ${connection.account_id}`}</option>)}
              </select></label>
              <label>{t('commerce.freelancer_read_type')}<select value={operation} onChange={event => { setOperation(event.target.value as Operation); setChallenge(null); setResult(null) }}>
                <option value="projects.search">{t('commerce.freelancer_project_search')}</option>
                <option value="project.read">{t('commerce.freelancer_project_detail')}</option>
                <option value="threads.list">{t('commerce.freelancer_thread_list')}</option>
                <option value="messages.read">{t('commerce.freelancer_thread_messages')}</option>
              </select></label>
              {operation === 'projects.search' && <label>{t('commerce.freelancer_search_query')}<input required maxLength={200} value={query} onChange={event => setQuery(event.target.value)} /></label>}
              {(operation === 'project.read' || operation === 'messages.read') && <label>{operation === 'project.read' ? t('commerce.freelancer_project_id') : t('commerce.freelancer_thread_id')}<input required inputMode="numeric" pattern="[0-9]+" value={targetId} onChange={event => setTargetId(event.target.value)} /></label>}
              <button type="submit" disabled={busy || !connectionId}>{busy ? t('commerce.freelancer_preparing') : t('commerce.freelancer_review_read')}</button>
            </form>
            {challenge && <section className="freelancer-read-review" aria-label={t('commerce.freelancer_read_review')}>
              <h3>{t('commerce.freelancer_explicit_approval')}</h3>
              <p>{t('commerce.freelancer_review_summary', { operation: challenge.operation, account: String(challenge.account_id), environment: challenge.environment })}</p>
              <p>{t('commerce.freelancer_review_exact_arguments')}</p>
              <pre>{JSON.stringify(challenge.arguments, null, 2)}</pre>
              <p>{t('commerce.freelancer_challenge_expiry', { seconds: challenge.expires_in_seconds })}</p>
              <button type="button" className="primary-action" disabled={busy} onClick={() => void authorizeAndRead()}>{busy ? t('commerce.freelancer_reading') : t('commerce.freelancer_authorize_read')}</button>
              <button type="button" disabled={busy} onClick={() => setChallenge(null)}>{t('commerce.cancel')}</button>
            </section>}
          </>}
        {result && <section className="freelancer-read-result" aria-label={t('commerce.freelancer_remote_result')}>
          <h3>{t('commerce.freelancer_remote_result')}</h3>
          <p>{t('commerce.freelancer_untrusted_result_note')}</p>
          <p>{t('commerce.freelancer_read_receipt')}: <code>{result.receipt?.receipt_id}</code></p>
          <pre>{JSON.stringify(result.data, null, 2)}</pre>
        </section>}
      </>}
  </section>
}
