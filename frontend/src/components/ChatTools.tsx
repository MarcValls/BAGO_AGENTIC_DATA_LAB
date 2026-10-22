import { useEffect, useRef, useState } from 'react'
import KnowledgeIngest from './KnowledgeIngest'
import OntologyReview from './OntologyReview'
import CatalogQuality from './CatalogQuality'
import './ChatTools.css'

const tools = [
  { id: 'source', label: 'Consultar archivo' },
  { id: 'relations', label: 'Relaciones de conocimiento' },
  { id: 'catalog', label: 'Catálogo local' },
] as const
type ToolId = typeof tools[number]['id']

export default function ChatTools() {
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
      <summary ref={launcherRef} aria-controls="chat-tools-options">Herramientas</summary>
      <div className="chat-tools-options" id="chat-tools-options" role="group" aria-label="Herramientas del chat">
        {tools.map(tool => <button key={tool.id} type="button" onClick={() => openTool(tool.id)}>{tool.label}</button>)}
      </div>
    </details>
    <dialog ref={dialogRef} className="chat-tool-dialog" aria-label={selectedTool?.label ?? 'Herramientas del chat'}
      onCancel={() => setActiveTool(null)} onClose={() => { setActiveTool(null); launcherRef.current?.focus() }}>
      <header className="chat-tool-dialog-heading"><strong>{selectedTool?.label}</strong><button type="button" onClick={() => setActiveTool(null)} aria-label="Cerrar herramienta">Cerrar <span aria-hidden="true">×</span></button></header>
      <div className="chat-tool-dialog-body">
        {activeTool === 'source' && <KnowledgeIngest />}
        {activeTool === 'relations' && <OntologyReview />}
        {activeTool === 'catalog' && <CatalogQuality />}
      </div>
    </dialog>
  </>
}
