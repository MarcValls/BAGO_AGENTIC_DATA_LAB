import {t, useI18n, formatDate, errorMessage} from '../i18n'
import {useCallback, useEffect, useRef, useState} from 'react'
import {communicationRequest, type WhatsAppAuthorization, type WhatsAppStatus} from '../types/communications'
import './WhatsAppSettings.css'

const labels: Record<string, string> = { get not_configured(){return t('commerce.not_configured')}, get disconnected(){return t('commerce.disconnected')}, get linking(){return t('commerce.awaiting_qr_linking')}, get connected(){return t('commerce.connected')}, get unavailable(){return t('commerce.unavailable')}, get unknown(){return t('commerce.unknown_state')} }
const authorizationUrl = '/api/communications/whatsapp-authorization'
const jsonRequest = (method: string, body: unknown): RequestInit => ({method, headers: {'Content-Type':'application/json'}, body: JSON.stringify(body)})
function authorizationRecord(value: unknown): WhatsAppAuthorization {
  const record = value as Partial<WhatsAppAuthorization>|null
  const text = (item: unknown): item is string => typeof item === 'string' && item.trim().length > 0
  const nullableText = (item: unknown) => item === null || text(item)
  const identity = (item: unknown) => typeof item === 'string' && /^[a-f0-9]{64}$/.test(item)
  if (!record || typeof record !== 'object' || typeof record.available !== 'boolean' || typeof record.enabled !== 'boolean'
      || !record.project || !text(record.project.project_id) || !text(record.project.root) || !text(record.project.binding)
      || !(record.revision === 'none' || identity(record.revision)) || !nullableText(record.grant_id)
      || !(record.session_identity === null || identity(record.session_identity)) || record.validity !== 'until_revoked'
      || !nullableText(record.granted_at) || !nullableText(record.revoked_at)
      || (record.enabled && (!record.session_identity || !record.grant_id || record.revision === 'none'))) {
    throw new Error(t('whatsappSettings.invalidAuthorization'))
  }
  return record as WhatsAppAuthorization
}
const readAuthorization = async () => authorizationRecord(await communicationRequest<unknown>(authorizationUrl))
export default function WhatsAppSettings() {
  useI18n()
  const [status, setStatus] = useState<WhatsAppStatus | null>(null)
  const [authorization, setAuthorization] = useState<WhatsAppAuthorization|null>(null)
  const [label, setLabel] = useState('')
  const [busy, setBusy] = useState(false)
  const [saved, setSaved] = useState(false)
  const [error, setError] = useState<string|Error>('')
  const generation = useRef(0)
  const mutating = useRef(false)
  const savedLabel = useRef('')
  const attemptedLabel = useRef('')
  const initialized = useRef(false)
  const refresh = useCallback(async (initial = false) => {
    const id = ++generation.current
    const results = await Promise.allSettled([
      communicationRequest<WhatsAppStatus>('/api/whatsapp/session'),
      readAuthorization(),
    ])
    if (id !== generation.current) return
    if (results[0].status === 'fulfilled') {
      setStatus(results[0].value)
      if (initial) {savedLabel.current = results[0].value.label; setLabel(results[0].value.label)}
      initialized.current = true
    } else {setStatus(null); setError(results[0].reason)}
    if (results[1].status === 'fulfilled') setAuthorization(results[1].value)
    else {setAuthorization(null); setError(results[1].reason)}
  }, [])
  useEffect(() => {
    void refresh(true)
    const timer = window.setInterval(() => {if (!mutating.current && document.visibilityState === 'visible') void refresh()}, 15000)
    return () => { ++generation.current; window.clearInterval(timer) }
  }, [refresh])
  const saveConnection = async (name: string, enabled: boolean) => {
    const result = await communicationRequest<WhatsAppStatus>('/api/whatsapp/session', jsonRequest('PUT', {label:name, enabled}))
    savedLabel.current = name; setLabel(name); setStatus(result); setSaved(true)
    return result
  }
  useEffect(() => {
    const name = label.trim()
    if (!initialized.current || busy || !status || !authorization?.available || !name || name === savedLabel.current || name === attemptedLabel.current) return
    const timer = window.setTimeout(() => {
      mutating.current = true; ++generation.current; setBusy(true); setError('')
      attemptedLabel.current = name
      void saveConnection(name, status.configured).then(() => refresh()).catch(setError).finally(() => {mutating.current = false; setBusy(false)})
    }, 450)
    return () => window.clearTimeout(timer)
  }, [label, busy, status?.configured, authorization?.available, refresh])
  const authorize = async (enabled: boolean) => {
    if (!authorization || mutating.current) return
    mutating.current = true; ++generation.current; setBusy(true); setError(''); setSaved(false)
    try {
      // Only this deliberate checkbox grants authority; inherited enabled and
      // saving a label never call the channel-authorization PUT.
      if (enabled) await saveConnection(label.trim() || t('whatsappSettings.defaultLabel'), true)
      const current = enabled ? await readAuthorization() : authorization
      if (!current.session_identity) throw new Error(t('whatsappSettings.authorityUnavailable'))
      const next = authorizationRecord(await communicationRequest<unknown>(authorizationUrl, jsonRequest('PUT', {
        enabled, expected_project_id:current.project.project_id, expected_binding:current.project.binding,
        expected_session_identity:current.session_identity, expected_authorization_revision:current.revision,
      })))
      setAuthorization(next)
      if (!enabled) await saveConnection(label.trim() || t('whatsappSettings.defaultLabel'), false)
      await refresh(); setSaved(true)
    } catch (cause) {setError(cause instanceof Error ? cause : t('commerce.could_not_complete_the_operation'))}
    finally {mutating.current = false; setBusy(false)}
  }
  const browserAction = async (action: 'open'|'close') => {
    if (mutating.current) return
    mutating.current = true; ++generation.current; setBusy(true); setStatus(null); setError('')
    try {
      if (action === 'open' && !status?.configured) await saveConnection(label.trim() || t('whatsappSettings.defaultLabel'), true)
      await communicationRequest('/api/whatsapp/session/'+action, jsonRequest('POST', {confirmed:true}))
      await refresh()
    } catch (cause) {setError(cause instanceof Error ? cause : t('commerce.could_not_complete_the_operation'))}
    finally {mutating.current = false; setBusy(false)}
  }
  const needsLink = status && status.state !== 'connected' && status.browser_available
  return <section className="whatsapp-settings" aria-labelledby="whatsapp-title">
    <p className="app-kicker">{t('commerce.bago_connections')}</p><h2 id="whatsapp-title">{t('whatsappSettings.title')}</h2>
    <p>{t('whatsappSettings.description')}</p>
    <div className={`whatsapp-session-state ${!busy && status?.state === 'connected' ? 'is-connected' : ''}`} role="status"><strong>{busy ? t('whatsappSettings.saving') : status ? labels[status.state] ?? t('commerce.unrecognized_state') : t('commerce.unknown_state')}</strong><span>{!busy && status?.checked_at ? t('commerce.last_probe',{date:formatDate(status.checked_at)}) : t('commerce.no_current_check')}</span></div>
    {error && <p role="alert">{errorMessage(error)}</p>}
    <label className="whatsapp-enabled"><input type="checkbox" checked={authorization?.enabled ?? false} onChange={event => void authorize(event.target.checked)} disabled={busy || !authorization?.available} /> {t('whatsappSettings.autoSend')}</label>
    <p className="whatsapp-note">{t('whatsappSettings.autoSendHelp')}</p>
    <p className="whatsapp-authorization-state">{t(authorization?.enabled ? 'whatsappSettings.enabled' : 'whatsappSettings.disabled')}</p>
    {authorization && <p className="whatsapp-note">{t('whatsappSettings.project')}: <code>{authorization.project.root}</code></p>}
    {!authorization && <p className="whatsapp-note">{t('whatsappSettings.authorityUnavailable')}</p>}
    {needsLink && <div className="whatsapp-link"><p>{t(status.state === 'linking' ? 'whatsappSettings.linking' : 'whatsappSettings.initialLink')}</p>
      <button disabled={busy || !authorization?.available} onClick={() => void browserAction('open')}>{t('whatsappSettings.link')}</button></div>}
    <details className="whatsapp-advanced"><summary>{t('whatsappSettings.advanced')}</summary>
      <label>{t('whatsappSettings.label')}<input value={label} maxLength={100} placeholder={t('whatsappSettings.defaultLabel')} onChange={event => {attemptedLabel.current = ''; setLabel(event.target.value); setSaved(false)}} disabled={busy || !status || !authorization?.available} /></label>
      <p className="whatsapp-note">{saved ? t('whatsappSettings.saved') : t('whatsappSettings.inFlight')}</p>
      <div className="whatsapp-actions"><button disabled={busy} onClick={() => {setError(''); void refresh()}}>{t('whatsappSettings.check')}</button><button disabled={busy || !status?.configured} onClick={() => void browserAction('close')}>{t('whatsappSettings.close')}</button></div>
      {status?.reason && <details><summary>{t('commerce.technical_detail')}</summary><pre>{status.reason}</pre></details>}
    </details>
  </section>
}
