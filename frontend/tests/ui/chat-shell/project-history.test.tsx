// @vitest-environment jsdom
import React from 'react'
import {afterEach,beforeEach,expect,it,vi} from 'vitest'
import {cleanup,fireEvent,render,screen,waitFor} from '@testing-library/react'
import {readFileSync} from 'node:fs'
import postcss from 'postcss'
import AgentChat from '../../../src/components/AgentChat'
import {resetLocaleForTests,setLocale} from '../../../src/i18n'

const records = [
  {id:'conv-zulu',owner_kind:'assistant',owner_id:'app-assistant',title:'Zulu long synthetic conversation',status:'active',labels:['Zeta','Urgent'],created_at:'2026-10-01T07:30:00Z',updated_at:'2026-10-28T10:15:00Z',revision:3},
  {id:'conv-alpha',owner_kind:'assistant',owner_id:'app-assistant',title:'Alpha synthetic conversation',status:'active',labels:['Docs'],created_at:'2026-10-02T08:45:00Z',updated_at:'2026-10-26T12:00:00Z',revision:1},
  {id:'conv-gamma',owner_kind:'assistant',owner_id:'app-assistant',title:'Gamma with unavailable creation date',status:'active',labels:[],created_at:'bad-timestamp',updated_at:'2026-10-27T09:05:00Z',revision:2},
] as const
const project={project_id:'project-synthetic',title:'Synthetic project',scope:'project',root:'C:\\Synthetic\\Project'}
const permissions={project_id:project.project_id,root:project.root,binding:{kind:'synthetic'},revision:1,state:'active',read_directories:['.'],write_directories:[]}
let calls:Array<{url:string;method:string}>=[]
let conversations=records.map(record=>({...record,labels:[...record.labels]}))

beforeEach(()=>{
  localStorage.clear();resetLocaleForTests();setLocale('en');calls=[];conversations=records.map(record=>({...record,labels:[...record.labels]}))
  HTMLElement.prototype.scrollIntoView=vi.fn()
  vi.stubGlobal('fetch',vi.fn(async(input:string,init?:RequestInit)=>{
    const url=String(input),method=init?.method??'GET';calls.push({url,method})
    let body:unknown=null
    if(url==='/api/agents/list')body={agents:[]}
    else if(url==='/api/providers/chat-models')body={models:[]}
    else if(url==='/api/providers/selection')body=null
    else if(url==='/api/project-folders/v1/active')body=project
    else if(url==='/api/project-permissions'&&method==='GET')body=permissions
    else if(url.startsWith('/api/conversations/')&&url.endsWith('/labels')&&method==='PATCH'){
      const id=url.split('/')[3],payload=JSON.parse(String(init?.body)) as {labels:string[];revision:number}
      const current=conversations.find(item=>item.id===id)
      if(!current||current.revision!==payload.revision)return {ok:false,status:409,json:async()=>({detail:'changed elsewhere'})}
      current.labels=[...payload.labels];current.revision+=1;body=current
    }
    else if(url.startsWith('/api/conversations?'))body={conversations}
    else if(url==='/api/conversations/conv-alpha')body={...conversations[1],messages:[{id:'msg-preserved',role:'assistant',content:'Synthetic conversation content remains visible.'}]}
    else if(url.startsWith('/api/capabilities/proposals?'))body={proposals:[]}
    else return {ok:false,status:404,json:async()=>({detail:'not found'})}
    return {ok:true,status:200,json:async()=>body}
  }))
})
afterEach(()=>{cleanup();vi.unstubAllGlobals();vi.restoreAllMocks()})

async function renderChat(){
  const view=render(<AgentChat cognitiveMode="baseline" onNavigate={()=>{}} onOpenProviderSettings={()=>{}} onOpenCognitionSettings={()=>{}} />)
  await waitFor(()=>expect(calls.some(call=>call.url.startsWith('/api/conversations?'))).toBe(true))
  return view
}
function openProject(){
  const button=screen.getByRole('button',{name:'Project'})
  if(button.getAttribute('aria-expanded')!=='true')fireEvent.click(button)
  return button
}

it('keeps Resources, Cognition and model in one DOM group in the required order',async()=>{
  const {container}=await renderChat()
  const group=container.querySelector('.chat-context-controls')!
  const resources=group.querySelector('.chat-tools-menu > summary')!
  const cognition=group.querySelector('button[aria-label="Open cognition and context settings"]')!
  const model=group.querySelector('select[aria-label="Orchestrator model"]')!
  expect(resources.compareDocumentPosition(cognition)&Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy()
  expect(cognition.compareDocumentPosition(model)&Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy()
  expect(model.parentElement?.parentElement).toBe(group)
})

it('shows source-backed UTC dates and sorts the expanded table by labels, name and creation time',async()=>{
  const {container}=await renderChat()
  openProject()
  await waitFor(()=>expect(container.querySelector('.conversation-compact-row[data-conversation-id="conv-alpha"]')).not.toBeNull())
  const compact=container.querySelector('.conversation-library-list')!
  expect(compact.querySelectorAll('.conversation-compact-row')).toHaveLength(3)
  expect(compact.querySelector('[data-conversation-id="conv-zulu"] time')?.getAttribute('datetime')).toBe('2026-10-28T10:15:00Z')
  expect(compact.querySelectorAll('.conversation-row-actions-button')).toHaveLength(3)
  expect(container.querySelector('.development-drawer-tab code')?.textContent).toBe(project.root)

  fireEvent.click(screen.getByRole('button',{name:'Expand Project panel'}))
  const region=await screen.findByRole('region',{name:'Loaded conversations'})
  const rows=()=>Array.from(region.querySelectorAll('tbody tr')).map(row=>row.getAttribute('data-conversation-id'))
  expect(rows()).toEqual(['conv-zulu','conv-gamma','conv-alpha'])
  expect(region.querySelector('tbody tr[data-conversation-id="conv-gamma"] td:nth-child(3)')?.textContent).toBe('Unavailable')
  expect(region.querySelector('tbody tr[data-conversation-id="conv-alpha"] td:nth-child(3) time')?.getAttribute('datetime')).toBe('2026-10-02T08:45:00Z')
  expect(region.querySelectorAll('.conversation-row-actions-button')).toHaveLength(3)
  expect(screen.getByRole('button',{name:'Actions for Alpha synthetic conversation'})).toBeTruthy()

  fireEvent.click(screen.getByRole('button',{name:'Labels'}))
  expect(rows()).toEqual(['conv-gamma','conv-alpha','conv-zulu'])
  expect(region.querySelector('th[aria-sort="ascending"]')).not.toBeNull()
  fireEvent.click(region.querySelector('thead button')!)
  expect(rows()).toEqual(['conv-alpha','conv-gamma','conv-zulu'])
  expect(region.querySelector('th[aria-sort="ascending"]')).not.toBeNull()
  fireEvent.click(screen.getByRole('button',{name:/Created/}))
  expect(rows()).toEqual(['conv-zulu','conv-alpha','conv-gamma'])
  expect(region.querySelectorAll('.conversation-label-chip')).toHaveLength(3)
})

it('edits conversation labels through the scoped API and renders the saved tags',async()=>{
  await renderChat()
  openProject()
  fireEvent.click(screen.getByRole('button',{name:'Expand Project panel'}))
  const region=await screen.findByRole('region',{name:'Loaded conversations'})
  vi.spyOn(window,'prompt').mockReturnValue('Release, QA')
  fireEvent.click(screen.getByRole('button',{name:'Actions for Alpha synthetic conversation'}))
  fireEvent.click(screen.getByRole('menuitem',{name:'Edit labels'}))
  await waitFor(()=>expect(calls.some(call=>call.url==='/api/conversations/conv-alpha/labels'&&call.method==='PATCH')).toBe(true))
  const labels=Array.from(region.querySelectorAll('tbody tr[data-conversation-id="conv-alpha"] .conversation-label-chip')).map(node=>node.textContent)
  expect(labels).toEqual(['Release','QA'])
  const request=vi.mocked(fetch).mock.calls.find(([url,init])=>String(url)==='/api/conversations/conv-alpha/labels'&&init?.method==='PATCH')
  expect(JSON.parse(String(request?.[1]?.body))).toEqual({revision:1,labels:['Release','QA']})
})

it('closes Project with Escape and its button without losing the selected conversation, draft or content',async()=>{
  const {container}=await renderChat()
  openProject()
  const alpha=container.querySelector('.conversation-compact-row[data-conversation-id="conv-alpha"] .conversation-library-item') as HTMLButtonElement
  fireEvent.click(alpha)
  await screen.findByText('Synthetic conversation content remains visible.')
  const composer=screen.getByRole('textbox',{name:'Message the assistant or selected agent'}) as HTMLTextAreaElement
  fireEvent.change(composer,{target:{value:'UNSENT_SYNTHETIC_DRAFT'}})
  const mutationCount=()=>calls.filter(call=>call.method!=='GET').length
  const before=mutationCount()

  const bar=screen.getByRole('button',{name:'Project'})
  fireEvent.keyDown(document.activeElement??bar,{key:'Escape'})
  await waitFor(()=>expect(bar.getAttribute('aria-expanded')).toBe('false'))
  expect(document.activeElement).toBe(bar)
  fireEvent.click(bar)
  await screen.findByText('Synthetic conversation content remains visible.')
  expect(composer.value).toBe('UNSENT_SYNTHETIC_DRAFT')
  expect(container.querySelector('.conversation-compact-row[data-conversation-id="conv-alpha"] .conversation-library-item.selected')).not.toBeNull()
  fireEvent.click(screen.getByRole('button',{name:'Close Project panel'}))
  await waitFor(()=>expect(bar.getAttribute('aria-expanded')).toBe('false'))
  expect(mutationCount()).toBe(before)
  expect(composer.value).toBe('UNSENT_SYNTHETIC_DRAFT')
  expect(screen.getByText('Synthetic conversation content remains visible.')).toBeTruthy()
})

it('provides an explicit close button and Escape return for the conversations and agents panel',async()=>{
  const {container}=await renderChat()
  const details=container.querySelector('details.chat-agent-panel') as HTMLDetailsElement
  const summary=details.querySelector('summary') as HTMLElement
  fireEvent.click(summary)
  await waitFor(()=>expect(details.open).toBe(true))
  expect(summary.getAttribute('aria-expanded')).toBe('true')
  const close=screen.getByRole('button',{name:'Close conversations and agents panel'})
  fireEvent.click(close)
  await waitFor(()=>expect(details.open).toBe(false))
  expect(document.activeElement).toBe(summary)
  fireEvent.click(summary)
  await waitFor(()=>expect(details.open).toBe(true))
  fireEvent.keyDown(summary,{key:'Escape'})
  await waitFor(()=>expect(details.open).toBe(false))
  expect(document.activeElement).toBe(summary)
})

it('defines full-width Project bar, expand/restore drawer, internal table scrolling and responsive chat controls',()=>{
  const development=postcss.parse(readFileSync('src/components/DevelopmentPanel.css','utf8'))
  const rules=new Map<string,Record<string,string>>()
  development.walkRules(rule=>{const values=rules.get(rule.selector)??{};rule.walkDecls(decl=>{values[decl.prop]=decl.value});rules.set(rule.selector,values)})
  expect(rules.get('.development-panel-portal')?.inset).toBe('0')
  expect(rules.get('.development-drawer-tab')?.width).toBe('100%')
  expect(rules.get('.development-drawer[data-expanded="true"]')?.width).toBe('100%')
  const chat=postcss.parse(readFileSync('src/components/AgentChatOverrides.css','utf8'))
  const table=chat.nodes.find(node=>node.type==='rule'&&node.selector==='.conversation-library-table-scroll')
  expect(table?.nodes?.some(node=>node.type==='decl'&&node.prop==='overflow'&&node.value==='auto')).toBe(true)
  const source=readFileSync('src/components/AgentChat.tsx','utf8')
  expect(source).toContain('conversationSort')
  expect(source).toContain("sortHeader('created_at'")
  expect(source).toContain("sortHeader('updated_at'")
})
