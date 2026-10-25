import {t, useI18n, formatDate, formatNumber, errorMessage, localMessage} from '../i18n'
import {useEffect, useId, useRef, useState, type ChangeEvent} from 'react'
import {contactsRequest as request, type AddressContact, type ContactPreview, type GoogleContactStatus} from '../types/contacts'
import './Contacts.css'
import ServiceTabs from './ServiceTabs'

interface Props {inline?: boolean; onUseContact?: (contact: AddressContact) => void}
const blank = {name: '', phone: '', email: ''}
export default function Contacts({inline = false, onUseContact}: Props) {
  useI18n()

  const uid = useId()
  const [section,setSection] = useState<'agenda'|'google'>('agenda')
  const searchEpoch = useRef(0)
  const [contacts, setContacts] = useState<AddressContact[]>([])
  const [query, setQuery] = useState('')
  const [loading, setLoading] = useState(true)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string|Error>('')
  const [notice, setNotice] = useState<string|Error>('')
  const [editing, setEditing] = useState<AddressContact | null>(null)
  const [fields, setFields] = useState(blank)
  const [deleteTarget, setDeleteTarget] = useState<AddressContact | null>(null)
  const [deleteReviewed, setDeleteReviewed] = useState(false)
  const [google, setGoogle] = useState<GoogleContactStatus | null>(null)
  const [clientPath, setClientPath] = useState('')
  const [clientFileName, setClientFileName] = useState('')
  const [authorization, setAuthorization] = useState('')
  const [preview, setPreview] = useState<ContactPreview | null>(null)
  const [selected, setSelected] = useState<Set<string>>(new Set())
  const [previewQuery, setPreviewQuery] = useState('')
  const [importReviewed, setImportReviewed] = useState(false)
  const fail = (cause: unknown) => setError(cause instanceof Error ? cause : "commerce.could_not_complete_the_operation")
  const reload = async () => {
    const result = await request<{contacts: AddressContact[]}>(`/contacts?q=${encodeURIComponent(query)}`)
    setContacts(result.contacts)
  }
  useEffect(() => {
    const epoch = ++searchEpoch.current
    setLoading(true)
    const timer = window.setTimeout(() => {
      void request<{contacts: AddressContact[]}>(`/contacts?q=${encodeURIComponent(query)}`)
        .then(value => {if (searchEpoch.current === epoch) setContacts(value.contacts)})
        .catch(cause => {if (searchEpoch.current === epoch) fail(cause)})
        .finally(() => {if (searchEpoch.current === epoch) setLoading(false)})
    }, 180)
    return () => {window.clearTimeout(timer); searchEpoch.current++}
  }, [query])
  useEffect(() => {
    let active = true
    void request<GoogleContactStatus>('/google/status').then(value => {if (active) setGoogle(value)})
      .catch(cause => {if (active) fail(cause)})
    return () => {active = false}
  }, [])
  const run = async (action: () => Promise<void>) => {
    setBusy(true); setError(''); setNotice('')
    try {await action()} catch (cause) {fail(cause)} finally {setBusy(false)}
  }
  const choose = (contact: AddressContact | null) => {
    setEditing(contact); setFields(contact ? {name: contact.name, phone: contact.phone, email: contact.email} : blank)
    setDeleteTarget(null); setDeleteReviewed(false); setError('')
  }
  const save = () => run(async () => {
    const contact = await request<AddressContact>(editing ? `/contacts/${encodeURIComponent(editing.id)}` : '/contacts',
      editing ? 'PUT' : 'POST', {...fields, ...(editing ? {expected_revision: editing.revision} : {})})
    choose(contact); await reload(); setNotice("commerce.contact_saved_to_the_local_address_book")
  })
  const remove = () => run(async () => {
    if (!deleteTarget || !deleteReviewed) return
    await request(`/contacts/${encodeURIComponent(deleteTarget.id)}`, 'DELETE',
      {expected_revision: deleteTarget.revision, confirmed: true})
    choose(null); await reload(); setNotice("commerce.contact_deleted_from_the_local_address_book_google_was_not_modified")
  })
  const refreshGoogle = () => run(async () => {setGoogle(await request<GoogleContactStatus>('/google/status'))})
  const configureGoogleFile = (event: ChangeEvent<HTMLInputElement>) => {
    const input = event.currentTarget
    const file = input.files?.[0]
    if (!file) return
    void run(async () => {
      try {
        if (!file.name.toLocaleLowerCase().endsWith('.json') || file.size > 65536) throw new Error('commerce.invalid_google_oauth_file')
        const client_json: unknown = JSON.parse(await file.text())
        if (!client_json || typeof client_json !== 'object' || Array.isArray(client_json)) throw new Error('commerce.invalid_google_oauth_file')
        setGoogle(await request<GoogleContactStatus>('/google/configure-file', 'POST', {client_json}))
        setClientFileName(file.name); setClientPath(''); setAuthorization('')
        setNotice('commerce.google_oauth_file_saved_locally')
      } catch (cause) {
        const code = cause && typeof cause === 'object' && 'code' in cause ? cause.code : undefined
        throw cause instanceof SyntaxError || code === 'invalid_oauth_client' ? new Error('commerce.invalid_google_oauth_file') : cause
      } finally {
        input.value = ''
      }
    })
  }
  const connect = () => run(async () => {
    const result = await request<{authorization_url: string}>('/google/connect', 'POST', {})
    const url = new URL(result.authorization_url)
    if (url.protocol !== 'https:' || url.hostname !== 'accounts.google.com') throw new Error("commerce.the_authorization_address_does_not_belong_to_google")
    setAuthorization(url.href)
  })
  const loadPreview = () => run(async () => {
    setPreview(null); setSelected(new Set()); setImportReviewed(false)
    const result = await request<ContactPreview>('/google/preview', 'POST', {})
    setPreview(result); setGoogle(await request<GoogleContactStatus>('/google/status'))
  })
  const importSelection = () => run(async () => {
    if (!preview || !selected.size || !importReviewed) return
    const result = await request<{imported: AddressContact[]; skipped: Array<{selection_id: string; reason: string}>}>(
      '/imports/selected', 'POST', {preview_id: preview.preview_id, expected_revision: preview.revision,
        selected_ids: [...selected], duplicate_policy: 'skip'})
    setPreview(null); setSelected(new Set()); setImportReviewed(false); await reload()
    setNotice(localMessage('commerce.import_notice',{imported:result.imported.length,skipped:result.skipped.length}))
  })
  const shown = preview?.contacts.filter(contact => `${contact.name} ${contact.phone} ${contact.email}`.toLocaleLowerCase().includes(previewQuery.toLocaleLowerCase())) ?? []
  return <section className={`contacts-page ${inline ? 'contacts-page--inline' : ''}`} aria-labelledby={`${uid}-title`}>
    <header className="contacts-heading"><div><p className="app-kicker">{t('commerce.bago_relationships_and_communications')}</p>
      <h2 id={`${uid}-title`}>{t('commerce.contacts')}</h2></div>
      <button onClick={() => {setSection('agenda');choose(null)}} disabled={busy}>{t('commerce.new_contact')}</button></header>
    <ServiceTabs<'agenda'|'google'> id={uid} label={t('commerce.contacts_sections')} value={section} onChange={setSection} items={[{id:'agenda',label:t('commerce.address_book')},{id:'google',label:'Google'}]} />
    {error && <p className="contacts-alert" role="alert">{errorMessage(error)}</p>}
    {notice && <p className="contacts-notice" role="status">{errorMessage(notice)}</p>}
    <div className="contacts-workspace" role="tabpanel" tabIndex={0} id={`${uid}-panel-agenda`} aria-labelledby={`${uid}-tab-agenda`} hidden={section !== 'agenda'}>
      <section className="contacts-card" aria-label={t('commerce.local_address_book')}>
        <div className="contacts-card-heading"><h3>{t('commerce.local_address_book')}</h3><span>{t('commerce.search_count',{count:formatNumber(contacts.length)})}</span></div>
        <label>{t('commerce.search_contacts')}<input type="search" value={query} onChange={event => setQuery(event.target.value)} placeholder={t('commerce.name_phone_or_email')} /></label>
        {loading ? <p role="status">{t('commerce.searching_contacts')}</p> : contacts.length === 0 ? <p>{t('commerce.no_contacts_match_this_search')}</p> :
          <ul className="contacts-list">{contacts.map(contact => <li key={contact.id}>
            <div><strong>{contact.name}</strong><span>{contact.phone || contact.email}</span><small>{contact.source === 'google' ? t('commerce.imported_from_google') : contact.source === 'fixture' ? t('commerce.test_data') : t('commerce.local_address_book')}</small></div>
            <div className="contacts-row-actions"><button disabled={busy} onClick={() => choose(contact)} aria-label={t('commerce.edit_contact_named',{name:contact.name})}>{t('commerce.edit_380')}</button>
              {onUseContact && <><button disabled={busy || !contact.phone} title={!contact.phone ? t('commerce.add_a_valid_international_phone_number_for_whatsapp') : undefined} onClick={() => onUseContact(contact)}>{t('commerce.prepare_message')}</button>{!contact.phone && <small>{t('commerce.no_phone_number_unavailable_for_whatsapp')}</small>}</>}</div>
          </li>)}</ul>}
      </section>
      <section className="contacts-card" aria-label={t('commerce.contact_editor')}><h3>{editing ? t('commerce.edit_contact') : t('commerce.new_contact')}</h3>
        <form onSubmit={event => {event.preventDefault(); void save()}}>
          <label>{t('commerce.name')}<input required maxLength={200} value={fields.name} onChange={event => setFields({...fields, name: event.target.value})} /></label>
          <label>{t('commerce.international_phone')}<input type="tel" value={fields.phone} onChange={event => setFields({...fields, phone: event.target.value})} placeholder={t('commerce.country_code_and_number')} /></label>
          <label>{t('commerce.email')}<input type="email" value={fields.email} onChange={event => setFields({...fields, email: event.target.value})} /></label>
          <p className="contacts-hint">{t('commerce.phone_or_email_saved_to_your_local_address_book')}</p>
          <button disabled={busy || !fields.name.trim() || (!fields.phone.trim() && !fields.email.trim())} type="submit">{editing ? t('commerce.save_changes') : t('commerce.save_contact')}</button>
          {editing && <button type="button" disabled={busy} onClick={() => {setDeleteTarget(editing); setDeleteReviewed(false)}}>{t('commerce.delete_from_local_address_book')}</button>}
        </form>
        {deleteTarget && <section className="contacts-delete" aria-label={t('commerce.confirm_local_deletion')}><h4>{t('commerce.delete_contact_named',{name:deleteTarget.name})}</h4>
          <p>{t('commerce.this_action_deletes_the_local_record_it_does_not_delete_the_google_contact_or_sent_messages')}</p>
          <label className="contacts-check"><input type="checkbox" checked={deleteReviewed} onChange={event => setDeleteReviewed(event.target.checked)} />{t('commerce.i_confirm_deletion_of_this_local_contact')}</label>
          <button disabled={busy || !deleteReviewed} onClick={() => void remove()}>{t('commerce.delete_local_contact')}</button><button onClick={() => setDeleteTarget(null)} disabled={busy}>{t('commerce.keep_contact')}</button>
        </section>}
      </section>
    </div>
    <section className="contacts-card contacts-google" role="tabpanel" tabIndex={0} id={`${uid}-panel-google`} aria-labelledby={`${uid}-tab-google`} hidden={section !== 'google'}><div className="contacts-card-heading"><div><p className="app-kicker">{t('commerce.read_only_connection')}</p><h3>{t('commerce.google_contacts')}</h3></div>
      <span className="contacts-connection">{google === null ? t('commerce.not_checked') : !google.configured ? t('commerce.not_configured') : google.live_verified ? t('commerce.live_reading_verified') : google.connected ? t('commerce.authorization_saved_reading_not_verified') : t('commerce.disconnected')}</span></div>
      <p>{t('commerce.choose_contacts_to_import_duplicates_are_skipped')}</p>
      {google?.last_error && <div role="alert"><details><summary>{t('commerce.technical_detail')}</summary><pre>{google.last_error}</pre></details></div>}
      <section className="contacts-google-setup" aria-label={t('commerce.configure_google_connection')}>
        <h4>{t('commerce.google_setup_title')}</h4>
        <p>{t('commerce.google_setup_steps')}</p>
        <label>{t('commerce.select_google_oauth_file')}<input type="file" accept=".json,application/json" disabled={busy} onChange={configureGoogleFile} /></label>
        {clientFileName && <p role="status">{t('commerce.google_oauth_file_ready',{name:clientFileName})}</p>}
        <p className="contacts-hint">{t('commerce.google_oauth_file_privacy')}</p>
        <details><summary>{t('commerce.advanced_manual_google_setup')}</summary>
          <p>{t('commerce.read_only_permission_see_the_manual_for_file_preparation')}</p>
          <label>{t('commerce.local_desktop_oauth_file_path')}<input value={clientPath} onChange={event => setClientPath(event.target.value)} placeholder={t('commerce.absolute_path_to_google_json')} /></label>
          <button disabled={busy || !clientPath.trim()} onClick={() => void run(async () => {setGoogle(await request<GoogleContactStatus>('/google/configure', 'POST', {client_json_path: clientPath})); setClientFileName(''); setClientPath(''); setAuthorization('')})}>{t('commerce.save_google_configuration')}</button>
        </details>
      </section>
      <div className="contacts-actions"><button disabled={busy || !google?.configured} onClick={() => void connect()}>{t('commerce.connect_to_google')}</button>
        <button disabled={busy} onClick={() => void refreshGoogle()}>{t('commerce.check_connection')}</button>
        <button disabled={busy || !google?.connected} onClick={() => void loadPreview()}>{t('commerce.view_contacts_to_select')}</button>
        <button disabled={busy || !google?.connected} onClick={() => void run(async () => {setGoogle(await request<GoogleContactStatus>('/google/disconnect', 'POST', {confirmed: true})); setPreview(null); setSelected(new Set()); setAuthorization('')})}>{t('commerce.disconnect_local_authorization')}</button>
      </div>
      {authorization && <p><a href={authorization} target="_blank" rel="noopener noreferrer">{t('commerce.continue_authorization_at_google')}</a> {t('commerce.when_finished_select_check_connection')}</p>}
      {preview && <section aria-label={t('commerce.google_contacts_selection')} className="contacts-import">
        <h4>{preview.source === 'fixture' ? t('commerce.test_preview_not_a_google_connection') : t('commerce.google_preview')}</h4>
        <p>{t('commerce.selected_preview',{selected:formatNumber(selected.size),total:formatNumber(preview.contacts.length),expires:formatDate(preview.expires_at)})}</p>
        <label>{t('commerce.filter_preview')}<input value={previewQuery} onChange={event => setPreviewQuery(event.target.value)} /></label>
        <div><button disabled={busy} onClick={() => {setSelected(new Set([...selected, ...shown.filter(item => !item.duplicates.length && !item.warnings.length).map(item => item.selection_id)])); setImportReviewed(false)}}>{t('commerce.select_visible_rows_without_warnings')}</button>
          <button disabled={busy} onClick={() => {setSelected(new Set()); setImportReviewed(false)}}>{t('commerce.clear_selection')}</button></div>
        <ul className="contacts-list">{shown.map(item => <li key={item.selection_id}><label className="contacts-check"><input type="checkbox" disabled={busy} checked={selected.has(item.selection_id)} onChange={event => {const next = new Set(selected); if (event.target.checked) next.add(item.selection_id); else next.delete(item.selection_id); setSelected(next); setImportReviewed(false)}} />
          <span><strong>{item.name}</strong><span>{item.phone || item.email}</span>{item.duplicates.length > 0 && <small>{t('commerce.duplicate_skipped_without_overwriting')}</small>}{item.warnings.map(warning => <small key={warning}><>{t('commerce.technical_detail')}: {warning}</></small>)}</span></label></li>)}</ul>
        <label className="contacts-check"><input type="checkbox" disabled={busy || !selected.size} checked={importReviewed} onChange={event => setImportReviewed(event.target.checked)} />{t('commerce.reviewed_selection',{count:formatNumber(selected.size)})}</label>
        <button className="contacts-primary" disabled={busy || !selected.size || !importReviewed} onClick={() => void importSelection()}>{t('commerce.import_selection',{count:formatNumber(selected.size)})}</button>
      </section>}
    </section>
  </section>
}
