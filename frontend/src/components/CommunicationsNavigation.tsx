import {t,useI18n} from '../i18n'
import {useEffect,useRef,useState} from 'react'
import './CommunicationsNavigation.css'
export const COMMUNICATION_SECTIONS=[
 {id:'communications',get label(){return t('core.CommunicationsNavigation.messages')},icon:'✉'},
 {id:'communications_history',get label(){return t('core.CommunicationsNavigation.history')},icon:'◷'},
 {id:'contacts',get label(){return t('core.App.contacts_baf2c1')},icon:'▤'},
] as const
export type CommunicationSection=typeof COMMUNICATION_SECTIONS[number]['id']
export function isCommunicationSection(view:string):view is CommunicationSection{return COMMUNICATION_SECTIONS.some(section=>section.id===view)}
type Props={activeView:string;collapsed:boolean;onExpandSidebar:()=>void;onNavigate:(view:CommunicationSection)=>void}
/** Native disclosure navigation; expanding never activates a destination. */
export default function CommunicationsNavigation({activeView,collapsed,onExpandSidebar,onNavigate}:Props){
 useI18n()
 const active=isCommunicationSection(activeView),[expanded,setExpanded]=useState(active)
 const trigger=useRef<HTMLButtonElement>(null),children=useRef<HTMLDivElement>(null),visible=expanded&&!collapsed
 useEffect(()=>{if(isCommunicationSection(activeView))setExpanded(true)},[activeView])
 const open=()=>{if(collapsed)onExpandSidebar();setExpanded(true)}
 return <div className={`communications-navigation${active?' has-active-child':''}`} onKeyDown={event=>{
  if(event.key==='Escape'&&visible){event.preventDefault();setExpanded(false);trigger.current?.focus()}
 }}>
  <button ref={trigger} type="button" className={`navigation-item communications-navigation-toggle${active&&!visible?' active':''}`}
   aria-label={t('core.App.communications_85090d')} aria-expanded={visible} aria-controls="communications-navigation-items" title={collapsed?t('core.App.communications_85090d'):undefined}
   onClick={()=>{if(collapsed)open();else setExpanded(value=>!value)}} onKeyDown={event=>{
    if(event.key!=='ArrowDown')return
    event.preventDefault();open();window.requestAnimationFrame(()=>children.current?.querySelector<HTMLButtonElement>('button')?.focus())
   }}>
   <span className="navigation-item-icon" aria-hidden="true">✉</span><span>{t('core.App.communications_85090d')}</span><span className="communications-navigation-chevron" aria-hidden="true">{visible?'⌃':'⌄'}</span>
  </button>
  <div ref={children} id="communications-navigation-items" role="group" aria-label={t('core.App.communications_85090d')} className="communications-navigation-children" hidden={!visible}>
   {COMMUNICATION_SECTIONS.map(section=><button key={section.id} type="button" className={`navigation-item${activeView===section.id?' active':''}`} aria-current={activeView===section.id?'page':undefined} onClick={()=>onNavigate(section.id)}><span className="navigation-item-icon" aria-hidden="true">{section.icon}</span><span>{section.label}</span></button>)}
  </div>
 </div>
}
