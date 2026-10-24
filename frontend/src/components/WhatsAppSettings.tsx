import {t, useI18n, formatDate, errorMessage} from '../i18n'
import { useCallback, useEffect, useRef, useState } from 'react'
import { communicationRequest, type WhatsAppStatus } from '../types/communications'
import './WhatsAppSettings.css'

const labels: Record<string, string> = { get not_configured(){return t('commerce.not_configured')}, get disconnected(){return t('commerce.disconnected')}, get linking(){return t('commerce.awaiting_qr_linking')}, get connected(){return t('commerce.connected')}, get unavailable(){return t('commerce.unavailable')}, get unknown(){return t('commerce.unknown_state')} }
export default function WhatsAppSettings() {
  useI18n()

  const [status, setStatus] = useState<WhatsAppStatus | null>(null)
  const [label, setLabel] = useState('')
  const [enabled, setEnabled] = useState(false)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string|Error>('')
  const generation = useRef(0)
  const refresh = useCallback(async (initial = false) => {
    const id = ++generation.current
    try {
      const result = await communicationRequest<WhatsAppStatus>('/api/whatsapp/session')
      if (id !== generation.current) return
      setStatus(result); setError('')
      if (initial) { setLabel(result.label); setEnabled(result.configured) }
    } catch (cause) {
      if (id !== generation.current) return
      setStatus(null); setError(cause instanceof Error ? cause : "commerce.could_not_check_the_session")
    }
  }, [])
  useEffect(() => {
    void refresh(true)
    const timer = window.setInterval(() => { if (document.visibilityState === 'visible') void refresh() }, 15000)
    return () => { ++generation.current; window.clearInterval(timer) }
  }, [refresh])
  const act = async (action: 'save' | 'open' | 'close') => {
    ++generation.current; setBusy(true); setStatus(null); setError('')
    try {
      await communicationRequest('/api/whatsapp/session' + (action === 'save' ? '' : `/${action}`), {
        method: action === 'save' ? 'PUT' : 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(action === 'save' ? { label, enabled } : { confirmed: true }),
      })
      await refresh()
    } catch (cause) { setError(cause instanceof Error ? cause : "commerce.could_not_complete_the_operation") }
    finally { setBusy(false) }
  }
  return <section className="whatsapp-settings" aria-labelledby="whatsapp-title">
    <p className="app-kicker">{t('commerce.bago_connections')}</p><h2 id="whatsapp-title">WhatsApp</h2>
    <p>{t('commerce.own_session_qr_linking')}</p>
    <div className={`whatsapp-session-state ${status?.state === 'connected' ? 'is-connected' : ''}`} role="status"><strong>{busy ? t('commerce.checking_session') : status ? labels[status.state] ?? t('commerce.unrecognized_state') : t('commerce.unknown_state')}</strong><span>{status?.checked_at ? t('commerce.last_probe',{date:formatDate(status.checked_at)}) : t('commerce.no_current_check')}</span></div>
    {status?.reason && <details><summary>{t('commerce.technical_detail')}</summary><pre>{status.reason}</pre></details>}{error && <p role="alert">{errorMessage(error)}</p>}
    <label>{t('commerce.session_name')}<input value={label} maxLength={100} onChange={event => setLabel(event.target.value)} disabled={busy} /></label>
    <label className="whatsapp-enabled"><input type="checkbox" checked={enabled} onChange={event => setEnabled(event.target.checked)} disabled={busy} /> {t('commerce.enable_whatsapp_for_bago')}</label>
    <div className="whatsapp-actions"><button disabled={busy} onClick={() => void act('save')}>{t('commerce.save_configuration')}</button><button disabled={busy} onClick={() => void act('open')}>{t('commerce.open_browser_and_link_qr')}</button><button disabled={busy} onClick={() => void refresh()}>{t('commerce.check_connection')}</button><button disabled={busy} onClick={() => void act('close')}>{t('commerce.close_browser_keeping_session')}</button></div>
    
  </section>
}
