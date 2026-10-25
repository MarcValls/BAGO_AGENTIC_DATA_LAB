import { useEffect, useRef, useState } from 'react'
import { t, useI18n } from '../i18n'

export const CHAT_SECTIONS = [
  { id: 'chat', get label(){return t('core.App.chat_460b3a')}, icon: '◉' },
  { id: 'capabilities', get label(){return t('commerce.capabilities')}, icon: '◇' },
] as const
export type ChatSection = typeof CHAT_SECTIONS[number]['id']
export function isChatSection(view: string): view is ChatSection { return CHAT_SECTIONS.some(section => section.id === view) }

type Props = { activeView: string; collapsed: boolean; onExpandSidebar: () => void; onNavigate: (view: ChatSection) => void }

export default function ChatNavigation({ activeView, collapsed, onExpandSidebar, onNavigate }: Props) {
  useI18n()
  const selected = isChatSection(activeView) ? activeView : ''
  const active = selected !== ''
  const [expanded, setExpanded] = useState(active)
  const button = useRef<HTMLButtonElement>(null)
  const children = useRef<HTMLDivElement>(null)
  const visible = expanded && !collapsed
  useEffect(() => { if (isChatSection(activeView)) setExpanded(true) }, [activeView])
  const open = () => { if (collapsed) onExpandSidebar(); setExpanded(true) }

  return <div className={`chat-navigation${active ? ' has-active-child' : ''}`} onKeyDown={event => {
    if (event.key === 'Escape' && visible) { event.preventDefault(); setExpanded(false); button.current?.focus() }
  }}>
    <button ref={button} type="button" className={`navigation-item agent-navigation-toggle${active && !visible ? ' active' : ''}`}
      aria-label="BAGO5" aria-expanded={visible} aria-controls="chat-navigation-items"
      title={collapsed ? 'BAGO5' : undefined}
      onClick={() => { if (collapsed) open(); else setExpanded(current => !current) }}
      onKeyDown={event => {
        if (event.key !== 'ArrowDown') return
        event.preventDefault(); open()
        window.requestAnimationFrame(() => children.current?.querySelector<HTMLButtonElement>('button')?.focus())
      }}>
      <span className="navigation-item-icon" aria-hidden="true">◉</span><span>BAGO5</span>
      <span className="agent-navigation-chevron" aria-hidden="true">{visible ? '⌄' : '›'}</span>
    </button>
    <div ref={children} id="chat-navigation-items" role="group" aria-label={t('core.App.chat_460b3a')} className="agent-navigation-children" hidden={!visible}>
      {CHAT_SECTIONS.map(section => <button key={section.id} type="button" className={`navigation-item${selected === section.id ? ' active' : ''}`}
        aria-current={selected === section.id ? 'page' : undefined} onClick={() => onNavigate(section.id)}>
        <span className="navigation-item-icon" aria-hidden="true">{section.icon}</span><span>{section.label}</span>
      </button>)}
    </div>
  </div>
}
