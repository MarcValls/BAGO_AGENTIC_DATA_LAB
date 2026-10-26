import {t, useI18n} from '../i18n'
import { useEffect, useRef, useState } from 'react'

export const AGENT_SECTIONS = [
  { id: 'agents', get label(){return t('commerce.my_agents')}, icon: '◈' },
  { id: 'tools', get label(){return t('agentTools.agentTools')}, icon: '⚒' },
  { id: 'builder', get label(){return t('commerce.create_agent')}, icon: '⊞' },
  { id: 'runner', get label(){return t('commerce.run_test')}, icon: '▷' },
  { id: 'evaluation_lab', get label(){return t('commerce.evaluation_454')}, icon: '▦' },
] as const
export type AgentSection = typeof AGENT_SECTIONS[number]['id']
export function isAgentSection(view: string): view is AgentSection {
  return AGENT_SECTIONS.some(section => section.id === view)
}

type Props = { activeView: string; collapsed: boolean; onExpandSidebar: () => void; onNavigate: (view: AgentSection) => void }

/** Disclosure navigation: native buttons retain Tab/Enter/Space behavior. */
export default function AgentNavigation({ activeView, collapsed, onExpandSidebar, onNavigate }: Props) {
  useI18n()

  const selected = activeView === 'control' ? 'runner' : activeView
  const active = isAgentSection(selected)
  const [expanded, setExpanded] = useState(active)
  const button = useRef<HTMLButtonElement>(null)
  const children = useRef<HTMLDivElement>(null)
  const visible = expanded && !collapsed

  useEffect(() => { if (isAgentSection(activeView) || activeView === 'control') setExpanded(true) }, [activeView])

  const open = () => { if (collapsed) onExpandSidebar(); setExpanded(true) }
  return <div className={`agent-navigation${active ? ' has-active-child' : ''}`} onKeyDown={event => {
    if (event.key === 'Escape' && visible) { event.preventDefault(); setExpanded(false); button.current?.focus() }
  }}>
    <button ref={button} type="button" className={`navigation-item agent-navigation-toggle${active && !visible ? ' active' : ''}`}
      aria-label={t('commerce.agents_455')} aria-expanded={visible} aria-controls="agent-navigation-items" title={collapsed ? t('commerce.agents_455') : undefined}
      onClick={() => { if (collapsed) open(); else setExpanded(current => !current) }}
      onKeyDown={event => {
        if (event.key !== 'ArrowDown') return
        event.preventDefault(); open()
        window.requestAnimationFrame(() => children.current?.querySelector<HTMLButtonElement>('button')?.focus())
      }}>
      <span className="navigation-item-icon" aria-hidden="true">◈</span><span>{t('commerce.agents_455')}</span>
      <span className="agent-navigation-chevron" aria-hidden="true">{visible ? '⌃' : '⌄'}</span>
    </button>
    <div ref={children} id="agent-navigation-items" role="group" aria-label={t('commerce.agent_management_and_work')} className="agent-navigation-children" hidden={!visible}>
      {AGENT_SECTIONS.map(section => <button key={section.id} type="button" className={`navigation-item${selected === section.id ? ' active' : ''}`}
        aria-current={selected === section.id ? 'page' : undefined} onClick={() => onNavigate(section.id)}>
        <span className="navigation-item-icon" aria-hidden="true">{section.icon}</span><span>{section.label}</span>
      </button>)}
    </div>
  </div>
}
