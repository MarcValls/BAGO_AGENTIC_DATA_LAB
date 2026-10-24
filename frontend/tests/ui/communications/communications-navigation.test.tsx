// @vitest-environment jsdom
import React,{useEffect,useState} from 'react'
import {afterEach,beforeEach,expect,it,vi} from 'vitest'
import {act,cleanup,fireEvent,render,screen,waitFor,within} from '@testing-library/react'
import {readFileSync} from 'node:fs'
import postcss from 'postcss'
import CommunicationsNavigation from '../../../src/components/CommunicationsNavigation'
import {resetLocaleForTests,setLocale,t} from '../../../src/i18n'
const fixture=vi.hoisted(()=>({messagesMounts:0,contactsMounts:0,latestContact:null as any,contact:{id:'contact-fixture',name:'Synthetic recipient',phone:''}}))
vi.mock('axios',()=>({default:{get:vi.fn(()=>new Promise(()=>{}))}}))
vi.mock('../../../src/components/AgentChat',()=>({default:({onNavigate,onOpenCommunication}:any)=><div>Chat fixture<button onClick={()=>onNavigate('communications')}>Open messages from chat</button><button onClick={()=>onOpenCommunication('draft-fixture')}>Open existing draft from chat</button></div>}))
vi.mock('../../../src/components/Communications',()=>({default:({activeSection='message',initialContact,draftId,inline}:any)=>{
 const [body,setBody]=useState(''),[calendar,setCalendar]=useState(''),[contact,setContact]=useState('')
 useEffect(()=>{fixture.messagesMounts++},[]);useEffect(()=>{fixture.latestContact=initialContact;if(initialContact)setContact(initialContact.id)},[initialContact])
 return <section aria-label="Existing messages fixture" data-section={activeSection} data-draft={draftId??''} data-inline={String(Boolean(inline))}><p>Current section {activeSection}</p><input aria-label="Preserved message fixture" value={body} onChange={e=>setBody(e.target.value)}/><input aria-label="Preserved schedule fixture" value={calendar} onChange={e=>setCalendar(e.target.value)}/><p>Recipient {contact}</p></section>
}}))
vi.mock('../../../src/components/Contacts',()=>({default:({onUseContact,inline}:any)=>{
 const [edit,setEdit]=useState('');useEffect(()=>{fixture.contactsMounts++},[])
 return <section aria-label="Full existing Contacts fixture" data-inline={String(Boolean(inline))}><input aria-label="Preserved contact editor fixture" value={edit} onChange={e=>setEdit(e.target.value)}/><button onClick={()=>onUseContact(fixture.contact)}>Use synthetic recipient</button></section>
}}))
vi.mock('../../../src/components/CognitionSettings',()=>({default:()=> <p>Settings fixture</p>,readCognitiveMode:()=> 'baseline'}))
import App from '../../../src/App'
beforeEach(()=>{localStorage.clear();resetLocaleForTests();fixture.messagesMounts=0;fixture.contactsMounts=0;fixture.latestContact=null;vi.stubGlobal('fetch',vi.fn(async()=>({ok:true,status:200,json:async()=>({agents:[],models:[]})})));HTMLDialogElement.prototype.showModal=function(){this.open=true};HTMLDialogElement.prototype.close=function(){this.open=false}})
afterEach(()=>{cleanup();vi.unstubAllGlobals();vi.restoreAllMocks()})
const props=()=>({activeView:'chat',collapsed:false,onExpandSidebar:vi.fn(),onNavigate:vi.fn()})
it('parent disclosure opens exactly three native children without navigating or activating a destination',()=>{
 const options=props();render(<CommunicationsNavigation {...options}/>);const parent=screen.getByRole('button',{name:'Comunicaciones'})
 expect(parent.getAttribute('aria-expanded')).toBe('false');expect(screen.queryByRole('button',{name:'Mensajes'})).toBeNull()
 fireEvent.click(parent);expect(options.onNavigate).not.toHaveBeenCalled();expect(parent.getAttribute('aria-expanded')).toBe('true')
 const group=screen.getByRole('group',{name:'Comunicaciones'});expect(within(group).getAllByRole('button').map(button=>button.textContent!.slice(1))).toEqual(['Mensajes','Historial','Contactos'])
 for(const [label,id] of [['Mensajes','communications'],['Historial','communications_history'],['Contactos','contacts']]){fireEvent.click(within(group).getByRole('button',{name:label}));expect(options.onNavigate).toHaveBeenLastCalledWith(id)}
})
it('active child, Escape focus and ArrowDown match the existing Agents disclosure pattern',async()=>{
 vi.spyOn(window,'requestAnimationFrame').mockImplementation(callback=>{setTimeout(()=>callback(0),0);return 1})
 const options={...props(),activeView:'communications_history'};render(<CommunicationsNavigation {...options}/>)
 const history=screen.getByRole('button',{name:'Historial'});expect(history.getAttribute('aria-current')).toBe('page');history.focus();fireEvent.keyDown(history,{key:'Escape'})
 const parent=screen.getByRole('button',{name:'Comunicaciones'});expect(document.activeElement).toBe(parent);expect(parent.getAttribute('aria-expanded')).toBe('false');expect(options.onNavigate).not.toHaveBeenCalled()
 fireEvent.keyDown(parent,{key:'ArrowDown'});await waitFor(()=>expect(document.activeElement).toBe(screen.getByRole('button',{name:'Mensajes'})))
})
it('expands a compact sidebar and translates all three children in place',()=>{
 const options={...props(),collapsed:true};const view=render(<CommunicationsNavigation {...options}/>)
 fireEvent.click(screen.getByRole('button',{name:'Comunicaciones'}));expect(options.onExpandSidebar).toHaveBeenCalledOnce();expect(options.onNavigate).not.toHaveBeenCalled()
 view.rerender(<CommunicationsNavigation {...options} collapsed={false} activeView="contacts"/>);expect(screen.getByRole('button',{name:'Contactos'}).getAttribute('aria-current')).toBe('page')
 act(()=>setLocale('en'));for(const label of ['Communications','Messages','History','Contacts'])expect(screen.getByRole('button',{name:label})).toBeTruthy()
 expect(screen.getByRole('button',{name:'Contacts'}).getAttribute('aria-current')).toBe('page')
})
it('App removes flat duplicates, avoids mounting screens on disclosure, and preserves both mounted editors across its three routes',()=>{
 render(<App/>);const sidebar=screen.getByRole('complementary',{name:t('core.App.workspace_sidebar_bc2716')})
 expect(screen.queryByRole('button',{name:'Contactos'})).toBeNull();fireEvent.click(within(sidebar).getByRole('button',{name:'Comunicaciones'}))
 expect(fixture.messagesMounts).toBe(0);expect(fixture.contactsMounts).toBe(0);expect(screen.getByText('Chat fixture')).toBeTruthy()
 expect(within(sidebar).getAllByRole('button',{name:'Contactos'})).toHaveLength(1)
 fireEvent.click(within(sidebar).getByRole('button',{name:'Mensajes'}));const body=screen.getByLabelText('Preserved message fixture') as HTMLInputElement,calendar=screen.getByLabelText('Preserved schedule fixture') as HTMLInputElement
 fireEvent.change(body,{target:{value:'UNSENT_BODY'}});fireEvent.change(calendar,{target:{value:'2030-01-01'}})
 fireEvent.click(within(sidebar).getByRole('button',{name:'Historial'}));expect(screen.getByText('Current section history')).toBeTruthy()
 fireEvent.click(within(sidebar).getByRole('button',{name:'Contactos'}));expect(screen.queryByRole('region',{name:'Existing messages fixture'})).toBeNull()
 const edit=screen.getByLabelText('Preserved contact editor fixture') as HTMLInputElement;fireEvent.change(edit,{target:{value:'UNSAVED_CONTACT_EDIT'}})
 expect(screen.getByRole('region',{name:'Full existing Contacts fixture'}).getAttribute('data-inline')).toBe('false')
 fireEvent.click(within(sidebar).getByRole('button',{name:'Mensajes'}));expect(body.isConnected).toBe(true);expect(body.value).toBe('UNSENT_BODY');expect(calendar.value).toBe('2030-01-01')
 fireEvent.click(within(sidebar).getByRole('button',{name:'Contactos'}));expect(edit.isConnected).toBe(true);expect(edit.value).toBe('UNSAVED_CONTACT_EDIT');expect(fixture.messagesMounts).toBe(1);expect(fixture.contactsMounts).toBe(1)
 expect((fetch as any).mock.calls.every((call:any[])=>!call[1]?.method||call[1].method==='GET')).toBe(true)
})
it('reuses chat links and passes a fresh explicit contact request without clearing an existing draft identity or message',()=>{
 render(<App/>);fireEvent.click(screen.getByText('Open existing draft from chat'))
 const body=screen.getByLabelText('Preserved message fixture') as HTMLInputElement;fireEvent.change(body,{target:{value:'KEEP_EXISTING_DRAFT'}})
 expect(screen.getByRole('region',{name:'Existing messages fixture'}).getAttribute('data-draft')).toBe('draft-fixture')
 fireEvent.click(screen.getByRole('button',{name:'Contactos'}));fireEvent.click(screen.getByText('Use synthetic recipient'))
 expect(screen.getByRole('button',{name:'Mensajes'}).getAttribute('aria-current')).toBe('page');expect(body.value).toBe('KEEP_EXISTING_DRAFT')
 expect(screen.getByRole('region',{name:'Existing messages fixture'}).getAttribute('data-draft')).toBe('draft-fixture');expect(fixture.latestContact).toEqual(fixture.contact);expect(fixture.latestContact).not.toBe(fixture.contact)
 fireEvent.click(screen.getByRole('button',{name:'Chat'}));expect(screen.queryByRole('region',{name:'Existing messages fixture',hidden:true})).toBeNull()
 fireEvent.click(screen.getByText('Open messages from chat'));expect(screen.getByText('Current section message')).toBeTruthy()
})
it('has effective hidden panels, full-width consumers and a scoped 320px-compatible horizontal navigation pattern',()=>{
 const css=readFileSync('src/components/CommunicationsNavigation.css','utf8'),ast=postcss.parse(css);const hidden:string[]=[]
 ast.walkRules(rule=>{rule.walkDecls(d=>{expect(d.important).not.toBe(true);if(d.prop==='display'&&d.value==='none')hidden.push(rule.selector)});expect(rule.selector.includes('.communications-')).toBe(true)})
 expect(hidden.some(selector=>selector.includes('.communications-section-panel[hidden]'))).toBe(true);expect(hidden.some(selector=>selector.includes('.communications-navigation-children[hidden]'))).toBe(true)
 expect(css).toContain('.communications-section-panel > :is(.communications, .contacts-page)');expect(css).toContain('var(--vs-header)');expect(css).toContain("[role='region']:not([hidden])")
 const mobile:string[]=[];ast.walkAtRules('media',media=>{expect(media.params).toBe('(max-width: 760px)');media.walkDecls(d=>mobile.push(d.prop+':'+d.value))});expect(mobile).toContain('flex-direction:row');expect(mobile).not.toContain('min-width:320px')
})
