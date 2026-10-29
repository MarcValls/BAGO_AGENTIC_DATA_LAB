import { useCallback, useEffect, useRef, useState } from 'react'
import type { FormEvent } from 'react'
import { apiError, errorMessage, t, useI18n } from '../i18n'
import './FreelancerSettings.css'

type FreelancerConnection = {
  id: string; name: string; kind: 'freelancer_readonly'; environment: 'sandbox' | 'production'
  state: 'configured_unverified' | 'connected' | 'error'; has_credential: boolean
  account_id: number | null; username: string | null; display_name: string | null
  last_checked_at: string | null; last_error: { code: string; message: string } | null; revision: string
}

async function request(url: string, init?: RequestInit): Promise<any> {
  const response = await fetch(url, { cache: 'no-store', ...init })
  const body = await response.json()
  if (!response.ok) throw apiError(body, response.status, 'agents')
  return body
}
const post = (body?: unknown): RequestInit => ({ method: 'POST', headers: { 'Content-Type': 'application/json' }, ...(body === undefined ? {} : { body: JSON.stringify(body) }) })

export default function FreelancerSettings() {
  useI18n()
  const tokenRef = useRef<HTMLInputElement>(null)
  const [connections, setConnections] = useState<FreelancerConnection[]>([])
  const [loading, setLoading] = useState(false)
  const [expanded, setExpanded] = useState(false)
  const [busy, setBusy] = useState('')
  const [error, setError] = useState<unknown>('')
  const [notice, setNotice] = useState('')

  const refresh = useCallback(async () => {
    setLoading(true)
    try {
      const data = await request('/api/connections/freelancer')
      setConnections(Array.isArray(data.connections) ? data.connections : [])
      setError('')
    } catch (cause) { setError(cause) }
    finally { setLoading(false) }
  }, [])
  useEffect(() => {
    if (expanded) void refresh()
  }, [expanded, refresh])

  const submit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    const form = new FormData(event.currentTarget)
    const credential = String(form.get('credential') || '')
    if (tokenRef.current) tokenRef.current.value = ''
    setBusy('link'); setError(''); setNotice('')
    try {
      const saved = await request('/api/connections/freelancer', post({
        name: String(form.get('name') || ''), environment: String(form.get('environment') || 'sandbox'), credential,
      })) as FreelancerConnection
      setNotice(t('commerce.freelancer_saved_verifying'))
      try {
        await request(`/api/connections/freelancer/${encodeURIComponent(saved.id)}/verify`, post())
        setNotice(t('commerce.freelancer_verified'))
      } catch (cause) { setError(cause) }
      await refresh()
    } catch (cause) { setError(cause) }
    finally { setBusy('') }
  }

  const verify = async (id: string) => {
    setBusy(id); setError(''); setNotice('')
    try { await request(`/api/connections/freelancer/${encodeURIComponent(id)}/verify`, post()); setNotice(t('commerce.freelancer_verified')); await refresh() }
    catch (cause) { setError(cause); await refresh() }
    finally { setBusy('') }
  }
  const disconnect = async (id: string) => {
    setBusy(id); setError(''); setNotice('')
    try { await request(`/api/connections/freelancer/${encodeURIComponent(id)}`, { method: 'DELETE' }); setNotice(t('commerce.freelancer_disconnected_local')); await refresh() }
    catch (cause) { setError(cause) }
    finally { setBusy('') }
  }

  return <details className="freelancer-settings" onToggle={event => setExpanded(event.currentTarget.open)}>
    <summary><span className="app-kicker">{t('commerce.read_only_connection')}</span><strong id="freelancer-settings-title">Freelancer</strong></summary>
    <section aria-labelledby="freelancer-settings-title">
    <header>
      <p>{t('commerce.freelancer_settings_intro')}</p></header>
    <p className="freelancer-settings-note">{t('commerce.freelancer_token_note')}</p>
    {error && <p role="alert" className="freelancer-error">{errorMessage(error)}</p>}
    {notice && <p role="status">{notice}</p>}
    <form onSubmit={event => void submit(event)} aria-label={t('commerce.freelancer_link_account')}>
      <label>{t('commerce.connection_name')}<input name="name" required maxLength={100} defaultValue="Freelancer" /></label>
      <label>{t('commerce.environment')}<select name="environment" defaultValue="sandbox"><option value="sandbox">Sandbox</option><option value="production">Production</option></select></label>
      <label>{t('commerce.freelancer_oauth_token')}<input ref={tokenRef} name="credential" type="password" autoComplete="new-password" required maxLength={8192} /></label>
      <button type="submit" disabled={!!busy}>{busy === 'link' ? t('commerce.freelancer_saving') : t('commerce.freelancer_save_and_verify')}</button>
    </form>
    <div className="freelancer-connections" aria-live="polite">
      <h4>{t('commerce.freelancer_saved_accounts')}</h4>
      {loading ? <p role="status">{t('commerce.loading')}</p> : connections.length === 0
        ? <p>{t('commerce.freelancer_no_accounts')}</p>
        : connections.map(connection => <article key={connection.id} className="freelancer-connection">
          <div><strong>{connection.name}</strong><span>{connection.environment === 'sandbox' ? 'Sandbox' : 'Production'} · {connection.state === 'connected' ? t('commerce.freelancer_verified_state') : connection.state === 'error' ? t('commerce.freelancer_error_state') : t('commerce.freelancer_unverified_state')}</span>
            {connection.account_id && <span>{connection.display_name || connection.username || `Account ${connection.account_id}`} · ID {connection.account_id}</span>}
            {connection.last_error && <span role="alert" className="freelancer-error">{connection.last_error.message}</span>}
          </div>
          <div className="freelancer-actions"><button type="button" disabled={!!busy} onClick={() => void verify(connection.id)}>{busy === connection.id ? t('commerce.freelancer_checking') : t('commerce.check_connection')}</button><button type="button" disabled={!!busy} onClick={() => void disconnect(connection.id)}>{t('commerce.freelancer_disconnect')}</button></div>
        </article>)}
    </div>
    <p className="freelancer-settings-note">{t('commerce.freelancer_revoke_note')}</p>
    </section>
  </details>
}
