import {t, useI18n, formatNumber, errorMessage} from '../i18n'
import { useEffect, useId, useRef, useState } from 'react'
import { communicationRequest as request, type Contact, type Draft, type Run, type Schedule } from '../types/communications'
import './Communications.css'

const emptySchedule: Schedule = { kind: 'now', timezone: 'Europe/Madrid', at: null, time: null, weekdays: [] }
const stateNames: Record<string, string> = { get draft(){return t('commerce.draft')}, get scheduled(){return t('commerce.scheduled')}, get sending(){return t('commerce.sending_297')}, get sent(){return t('commerce.sent')}, get failed(){return t('commerce.failed')}, get uncertain(){return t('commerce.uncertain_outcome')}, get cancelled(){return t('commerce.cancelled')}, get needs_review(){return t('commerce.needs_review')} }
interface Props { activeSection?: 'message' | 'history'; initialContact?: Contact; inline?: boolean; initialDraft?: Draft; draftId?: string; conversationId?: string; onOpenFull?: (id: string) => void }
export default function Communications({ activeSection = 'message', initialContact, inline = false, initialDraft, draftId, conversationId, onOpenFull }: Props) {
  useI18n()

  const prefix = useId()
  const section = activeSection
  const contactRequest = useRef(initialContact)
  const pendingInitialContact = useRef(initialContact)
  const dirtyRef = useRef(false)
  const [contacts, setContacts] = useState<Contact[]>([])
  const [drafts, setDrafts] = useState<Draft[]>([])
  const [runs, setRuns] = useState<Run[]>([])
  const [draft, setDraft] = useState<Draft | null>(null)
  const [contactId, setContactId] = useState('')
  const [text, setText] = useState('')
  const [attachments, setAttachments] = useState('')
  const [schedule, setSchedule] = useState<Schedule>(emptySchedule)
  const [loading, setLoading] = useState(true)
  const [busy, setBusy] = useState(false)
  const [dirty, setDirty] = useState(false)
  const [reviewed, setReviewed] = useState(false)
  const [conflict, setConflict] = useState<Draft | null>(null)
  const [error, setError] = useState<string|Error>('')
  const loadDraft = (item: Draft | null) => {
    dirtyRef.current = false
    setDraft(item); setContactId(item?.contact_id ?? ''); setText(item?.text ?? '')
    setAttachments(item?.attachments.map(file => file.path).join('\n') ?? '')
    setSchedule(item?.schedule ?? emptySchedule); setDirty(false); setReviewed(false); setConflict(null)
  }
  const reloadLists = async () => {
    const [a, b] = await Promise.all([request<{ drafts: Draft[] }>('/api/communications/drafts'), request<{ runs: Run[] }>('/api/communications/runs')])
    setDrafts(a.drafts); setRuns(b.runs)
  }
  useEffect(() => {
    let active = true
    setLoading(true); setError('')
    const id = draftId ?? initialDraft?.id
    void Promise.all([
      request<{ contacts: Contact[] }>('/api/communications/contacts'),
      request<{ drafts: Draft[] }>('/api/communications/drafts'),
      request<{ runs: Run[] }>('/api/communications/runs'),
      id ? request<Draft>(`/api/communications/drafts/${encodeURIComponent(id)}`) : Promise.resolve(null),
    ]).then(([a, b, c, selected]) => { if (active) { setContacts(a.contacts); setDrafts(b.drafts); setRuns(c.runs); if (dirtyRef.current && selected) { setConflict(selected); setReviewed(false) } else loadDraft(selected)
      const requestedContact = pendingInitialContact.current
      pendingInitialContact.current = undefined
      if (requestedContact) {
        if (selected && ['sending','sent','cancelled','uncertain'].includes(selected.state)) setError('commerce.this_draft_does_not_allow_changing_the_recipient')
        else {
          setContacts(current => current.some(item => item.id === requestedContact.id) ? current.map(item => item.id === requestedContact.id ? requestedContact : item) : [...current, requestedContact])
          setContactId(requestedContact.id); dirtyRef.current = true; setDirty(true); setReviewed(false)
        }
      } } })
      .catch(cause => { if (active) setError(cause instanceof Error ? cause : "commerce.could_not_load_communications") })
      .finally(() => { if (active) setLoading(false) })
    return () => { active = false }
  }, [draftId, initialDraft?.id, initialDraft?.revision])
  const change = (action: () => void) => { dirtyRef.current = true; action(); setDirty(true); setReviewed(false); setError('') }
  const json = (method: string, body: unknown) => ({ method, headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) })
  const fail = async (cause: unknown) => {
    setError(cause instanceof Error ? cause : "commerce.could_not_complete_the_operation")
    if ((cause as { status?: number })?.status === 409 && draft) {
      try { setConflict(await request<Draft>(`/api/communications/drafts/${encodeURIComponent(draft.id)}`)) }
      catch { setError("commerce.revision_conflict_could_not_recover_the_current_version_your_text_remains_in_the_editor") }
    }
  }
  const save = async () => {
    setBusy(true); setError('')
    try {
      const payload = { contact_id: contactId, text, attachments: attachments.split(/\r?\n/).map(path => path.trim()).filter(Boolean), schedule, conversation_id: conversationId ?? draft?.conversation_id ?? null }
      const saved = await request<Draft>(draft ? `/api/communications/drafts/${encodeURIComponent(draft.id)}` : '/api/communications/drafts', json(draft ? 'PATCH' : 'POST', { ...payload, ...(draft ? { expected_revision: draft.revision } : {}) }))
      loadDraft(saved); await reloadLists()
    } catch (cause) { await fail(cause) } finally { setBusy(false) }
  }
  const action = async (name: 'confirm' | 'cancel') => {
    if (!draft) return
    setBusy(true); setError(''); setReviewed(false)
    try {
      loadDraft(await request<Draft>(`/api/communications/drafts/${encodeURIComponent(draft.id)}/${name}`, json('POST', { expected_revision: draft.revision, confirmed: true })))
      await reloadLists()
    } catch (cause) { await fail(cause) } finally { setBusy(false) }
  }
  const recipient = contacts.find(item => item.id === contactId)
  const knownState = draft ? stateNames[draft.state] : t('commerce.unsaved')
  const readonly = draft?.state === 'sending' || draft?.state === 'sent' || draft?.state === 'cancelled' || draft?.state === 'uncertain'
  useEffect(() => {
    if (contactRequest.current === initialContact) return
    contactRequest.current = initialContact
    pendingInitialContact.current = undefined
    if (!initialContact) return
    if (loading || busy || readonly) { setError('commerce.this_draft_does_not_allow_changing_the_recipient'); return }
    setContacts(current => current.some(item => item.id === initialContact.id) ? current.map(item => item.id === initialContact.id ? initialContact : item) : [...current, initialContact])
    change(() => setContactId(initialContact.id))
    // A rejected request is consumed here, never retried when busy/readonly changes.
  }, [initialContact])
  const confirmable = draft && ['draft', 'needs_review', 'failed'].includes(draft.state) && !dirty && !conflict
  return <section className={`communications ${inline ? 'communications--inline' : ''}`} aria-labelledby={`${prefix}-title`}>
    <header className="communications-heading"><div><p className="app-kicker">{t('commerce.bago_customer_communications')}</p><h2 id={`${prefix}-title`}>{inline ? t('commerce.review_communication') : t('commerce.communications')}</h2></div>{inline && draft && onOpenFull && <button onClick={() => onOpenFull(draft.id)}>{t('commerce.open_full_screen')}</button>}</header>
    {loading && <p role="status">{t('commerce.loading_communications')}</p>}{error && <p className="communications-error" role="alert">{errorMessage(error)}</p>}
    {!loading && <div className="communications-layout" data-section={section}>
      {!inline && section === 'message' && <aside className="communications-library" aria-label={t('commerce.drafts')}><h3>{t('commerce.drafts_and_scheduling')}</h3><button disabled={busy || dirty} onClick={() => loadDraft(null)}>{t('commerce.new_draft')}</button>{dirty && <small>{t('commerce.save_your_changes_before_switching_drafts')}</small>}{drafts.length === 0 && <p>{t('commerce.no_drafts_yet')}</p>}<ul>{drafts.map(item => <li key={item.id}><button disabled={busy || dirty} aria-current={draft?.id === item.id ? 'true' : undefined} onClick={() => { setBusy(true); void request<Draft>(`/api/communications/drafts/${encodeURIComponent(item.id)}`).then(loadDraft).catch(fail).finally(() => setBusy(false)) }}>{item.recipient.name} · {stateNames[item.state] ?? t('commerce.unrecognized_state')}</button></li>)}</ul>
      </aside>}
      <div className="communications-editor"><div className="communications-state" role="status">{knownState ?? t('commerce.unrecognized_state')}{dirty ? t('commerce.unsaved_changes') : ''}</div>
        {draft && <details className="communications-identity"><summary>{t('commerce.draft_identity_and_revision')}</summary><code>{draft.id}</code><code>{draft.revision}</code></details>}
        {conflict && <section className="communications-conflict" role="alert"><h3>{t('commerce.the_draft_changed_in_another_session')}</h3><p>{t('commerce.your_text_is_preserved_load_the_current_version_or_keep_your_changes_over_that_revision_and_save_again')}</p><blockquote>{conflict.text}</blockquote><button onClick={() => loadDraft(conflict)}>{t('commerce.load_server_version')}</button><button onClick={() => { setDraft(conflict); setConflict(null); dirtyRef.current = true; setDirty(true); setReviewed(false) }}>{t('commerce.keep_my_changes_for_review')}</button></section>}
        <section role="region" tabIndex={0} id={`${prefix}-panel-message`} aria-label={t('commerce.message')} hidden={section !== 'message'}>
        <fieldset disabled={loading || busy || Boolean(readonly)}><legend>{t('commerce.content_and_recipient')}</legend>
          <label>{t('commerce.recipient')}<select value={contactId} onChange={event => change(() => setContactId(event.target.value))}><option value="">{t('commerce.select_a_contact')}</option>{contacts.map(item => <option key={item.id} value={item.id} disabled={!item.phone}>{item.name} · {item.phone}</option>)}</select></label>
          <label>{t('commerce.message')}<textarea rows={6} value={text} onChange={event => change(() => setText(event.target.value))} /></label>
          <label>{t('commerce.workspace_attachments_one_exact_relative_path_per_line')}<textarea rows={2} value={attachments} onChange={event => change(() => setAttachments(event.target.value))} placeholder="resultados/informe.pdf" /></label><small>{t('commerce.pdf_text_csv_or_images_up_to_5_files_of_10_mib')}</small>
          <label>{t('commerce.when')}<select value={schedule.kind} onChange={event => change(() => setSchedule({ ...emptySchedule, timezone: schedule.timezone, kind: event.target.value as Schedule['kind'] }))}><option value="now">{t('commerce.send_now')}</option><option value="once">{t('commerce.a_specific_date')}</option><option value="daily">{t('commerce.every_day')}</option><option value="weekly">{t('commerce.every_week')}</option></select></label>
          <label>{t('commerce.iana_time_zone')}<input value={schedule.timezone} onChange={event => change(() => setSchedule({ ...schedule, timezone: event.target.value }))} /></label>
          {schedule.kind === 'once' && <label>{t('commerce.iso_8601_date_with_explicit_zone_or_offset')}<input value={schedule.at ?? ''} placeholder="2026-10-30T10:00:00+01:00" onChange={event => change(() => setSchedule({ ...schedule, at: event.target.value || null }))} /></label>}
          {['daily', 'weekly'].includes(schedule.kind) && <label>{t('commerce.local_time')}<input type="time" value={schedule.time ?? ''} onChange={event => change(() => setSchedule({ ...schedule, time: event.target.value || null }))} /></label>}
          {schedule.kind === 'weekly' && <fieldset><legend>{t('commerce.days_of_the_week')}</legend>{[t('commerce.monday'), t('commerce.tuesday'), t('commerce.wednesday'), t('commerce.thursday'), t('commerce.friday'), t('commerce.saturday'), t('commerce.sunday')].map((day, index) => <label className="communications-check" key={index+1}><input type="checkbox" checked={schedule.weekdays.includes(index + 1)} onChange={event => change(() => setSchedule({ ...schedule, weekdays: event.target.checked ? [...schedule.weekdays, index + 1].sort() : schedule.weekdays.filter(value => value !== index + 1) }))} />{day}</label>)}</fieldset>}
        </fieldset>
        <button disabled={busy || Boolean(readonly) || !contactId || !text.trim() || Boolean(conflict)} onClick={() => void save()}>{t('commerce.save_and_prepare_review')}</button>
        {draft && <section className="communications-review" aria-label={t('commerce.review_before_authorizing')}><h3>{t('commerce.saved_content_review')}</h3><p><strong>{draft.recipient.name}</strong> · {draft.recipient.phone}</p><p className="communications-message">{draft.text}</p><ul>{draft.attachments.map(file => <li key={file.path}>{file.name} · {formatNumber(file.size)} bytes<details><summary>{t('commerce.attachment_fingerprint')}</summary><code>{file.sha256}</code></details></li>)}</ul><p>{t('commerce.schedule')} {{now:t('commerce.schedule_now'),once:t('commerce.schedule_once'),daily:t('commerce.schedule_daily'),weekly:t('commerce.schedule_weekly')}[draft.schedule.kind]??t('commerce.unrecognized_state')} · {draft.schedule.timezone}{draft.schedule.at ? ` · ${draft.schedule.at}` : ''}{draft.schedule.time ? ` · ${draft.schedule.time}` : ''}{draft.schedule.weekdays.length ? t('commerce.iso_days',{days:draft.schedule.weekdays.join(', ')}) : ''}</p><p>{t('commerce.next_run')} {draft.next_run_at ? `${draft.next_run_at} (UTC)` : draft.schedule.kind === 'now' ? t('commerce.immediately_on_confirmation') : t('commerce.the_server_has_not_calculated_a_date_yet')}</p>{draft.last_error && <div role="alert"><details><summary>{t('commerce.technical_detail')}</summary><pre>{draft.last_error}</pre></details></div>}
          {confirmable && <><label className="communications-check"><input type="checkbox" checked={reviewed} onChange={event => setReviewed(event.target.checked)} />{t('commerce.i_reviewed_the_exact_recipient_text_attachments_and_schedule')}</label><button className="communications-confirm" disabled={busy || !reviewed} onClick={() => void action('confirm')}>{draft.schedule.kind === 'now' ? t('commerce.confirm_and_send_now') : t('commerce.confirm_schedule')}</button></>}
          {!['sent', 'cancelled', 'sending', 'uncertain'].includes(draft.state) && <button disabled={busy || dirty || Boolean(conflict)} onClick={() => void action('cancel')}>{t('commerce.cancel_draft_or_future_runs')}</button>}
          {draft.state === 'uncertain' && <p>{t('commerce.no_automatic_retry_check_the_result_before_preparing_another_operation')}</p>}
        </section>}
        {recipient && !draft && <p>{t('commerce.selected_recipient')} {recipient.name} · {recipient.phone}</p>}
        </section>
        <section role="region" tabIndex={0} id={`${prefix}-panel-history`} aria-label={t('commerce.history')} hidden={section !== 'history'}><h3>{t('commerce.history')}</h3><button disabled={busy} onClick={() => { setBusy(true); void reloadLists().catch(fail).finally(() => setBusy(false)) }}>{t('commerce.refresh_history')}</button>{runs.length === 0 ? <p>{t('commerce.no_runs_recorded')}</p> : <ul className="communications-runs">{runs.map(run => <li key={run.id}><strong>{stateNames[run.state] ?? t('commerce.unrecognized_state')}</strong><span>{run.occurrence_at} · {run.draft_id}</span>{run.error && <details><summary>{t('commerce.technical_detail')}</summary><pre>{run.error}</pre></details>}<details><summary>{t('commerce.execution_receipt')}</summary><pre>{JSON.stringify(run.receipt, null, 2) ?? t('commerce.no_receipt')}</pre></details></li>)}</ul>}</section>
      </div>
    </div>}
  </section>
}
