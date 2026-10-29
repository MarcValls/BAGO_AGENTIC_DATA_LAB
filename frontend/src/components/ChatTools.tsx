import {t, useI18n} from '../i18n'
import { useEffect, useRef, useState } from 'react'
import { createPortal } from 'react-dom'
import KnowledgeIngest from './KnowledgeIngest'
import OntologyReview from './OntologyReview'
import CatalogQuality from './CatalogQuality'
import './ChatTools.css'
import Contacts from './Contacts'
import Communications from './Communications'
import type { AddressContact } from '../types/contacts'

const tools = [
  { id: 'contacts', get label(){return t('commerce.contacts')} },
  { id: 'source', get label(){return t('commerce.consult_file')} },
  { id: 'relations', get label(){return t('commerce.knowledge_relationships')} },
  { id: 'catalog', get label(){return t('commerce.local_catalog')} },
] as const
type ToolId = typeof tools[number]['id']

export default function ChatTools({conversationId, onOpenCommunication}: {conversationId?: string; onOpenCommunication?: (id: string) => void}) {
  useI18n()

  const [selectedContact, setSelectedContact] = useState<AddressContact | null>(null)
  useEffect(() => {setSelectedContact(null)}, [conversationId])
  const [activeTool, setActiveTool] = useState<ToolId | null>(null)
  const menuRef = useRef<HTMLDetailsElement>(null)
  const launcherRef = useRef<HTMLElement>(null)
  const dialogRef = useRef<HTMLDialogElement>(null)
  const selectedTool = tools.find(tool => tool.id === activeTool)

  useEffect(() => {
    const dismissMenu = (event: PointerEvent) => {
      const menu = menuRef.current
      if (menu?.open && !menu.contains(event.target as Node)) menu.open = false
    }
    document.addEventListener('pointerdown', dismissMenu)
    return () => document.removeEventListener('pointerdown', dismissMenu)
  }, [])

  useEffect(() => {
    const dialog = dialogRef.current
    if (!dialog) return
    if (activeTool && !dialog.open) dialog.showModal()
    else if (!activeTool && dialog.open) dialog.close()
  }, [activeTool])

  const openTool = (tool: ToolId) => {
    if (menuRef.current) menuRef.current.open = false
    setActiveTool(tool)
  }

  return <>
    <details className="chat-tools-menu" ref={menuRef} onKeyDown={event => {
      if (event.key === 'Escape' && menuRef.current?.open) {
        event.preventDefault()
        menuRef.current.open = false
        launcherRef.current?.focus()
      }
    }}>
      <summary ref={launcherRef} aria-controls="chat-tools-options">{t('commerce.chat_resources')}</summary>
      <div className="chat-tools-options" id="chat-tools-options" role="group" aria-label={t('commerce.chat_resources_group')}>
        {tools.map(tool => <button key={tool.id} type="button" onClick={() => openTool(tool.id)}>{tool.label}</button>)}
      </div>
    </details>
    {/* Resource forms live outside the composer; portal events still need isolation. */}
    {typeof document !== 'undefined' && createPortal(<dialog ref={dialogRef} className="chat-tool-dialog" aria-label={selectedTool?.label ?? t('commerce.chat_resources_group')}
      onSubmit={event => event.stopPropagation()}
      onCancel={() => setActiveTool(null)} onClose={() => { setActiveTool(null); launcherRef.current?.focus() }}>
      <header className="chat-tool-dialog-heading"><strong>{selectedTool?.label}</strong><button type="button" onClick={() => setActiveTool(null)} aria-label={t('commerce.close_tool')}>{t('commerce.close')} <span aria-hidden="true">×</span></button></header>
      <div className="chat-tool-dialog-body">
        {activeTool === 'contacts' && <><Contacts inline onUseContact={setSelectedContact} />{selectedContact && <Communications key={selectedContact.id} inline initialContact={selectedContact} conversationId={conversationId} onOpenFull={onOpenCommunication} />}</>}
        {activeTool === 'source' && <KnowledgeIngest />}
        {activeTool === 'relations' && <OntologyReview />}
        {activeTool === 'catalog' && <CatalogQuality />}
      </div>
    </dialog>, menuRef.current?.closest('.control-chat') ?? document.body)}
  </>
}
