// @vitest-environment jsdom
import React from 'react'
import {afterEach,beforeEach,expect,it,vi} from 'vitest'
import {act,cleanup,fireEvent,render,screen,waitFor} from '@testing-library/react'
import {readFileSync} from 'node:fs'
import postcss from 'postcss'
import CognitionSettings from '../../../src/components/CognitionSettings'
import ProjectContextDocument from '../../../src/components/ProjectContextDocument'
import {resetLocaleForTests,setLocale,t} from '../../../src/i18n'
const root='C:/SYNTHETIC/'+('long-folder/'.repeat(20))
const ids=['project-context','project-state','active-handoff','conversations','cognition-traces']
const paths=ids.map(id=>({id,label:'ORIGINAL '+id,path:root+id,state:'present' as const,purpose:'ORIGINAL PURPOSE '+id}))
const metadata={workspace_root:root,cognition:{profile:'EXACT_PROFILE',capacity:16,max_hops:3,max_expansions:4},paths,memory:{kind:'conversation_history',state:'present',description:'ORIGINAL MEMORY'}}
const response=(body:unknown,status=200)=>({ok:status<400,status,json:async()=>body})
beforeEach(()=>{localStorage.clear();resetLocaleForTests()})
afterEach(()=>{cleanup();vi.unstubAllGlobals()})
it('opts in only Settings long paths and retains every metadata/source value with no document read until expansion',async()=>{
 const fetch=vi.fn(async()=>response(metadata));vi.stubGlobal('fetch',fetch)
 const view=render(<CognitionSettings mode="baseline" onModeChange={vi.fn()}/>);await screen.findByText('EXACT_PROFILE')
 const scope=view.container.querySelector('.cognition-context')!
 expect(scope.querySelectorAll('.cognition-context-summary > div')).toHaveLength(1)
 expect(scope.querySelectorAll('.cognition-detail-summary > div')).toHaveLength(3)
 expect(scope.querySelectorAll('.context-source-grid > .workspace-source')).toHaveLength(5)
 const code=scope.querySelector('.cognition-context-summary code') as HTMLElement
 expect(code.textContent).toBe(root);expect(code.title).toBe(root);expect(code.tabIndex).toBe(0)
 code.focus();expect(document.activeElement).toBe(code)
 for(const path of paths){const el=Array.from(scope.querySelectorAll('code.context-location-path')).find(el=>el.textContent===path.path) as HTMLElement;expect(el.title).toBe(path.path);expect(el.tabIndex).toBe(0);expect(el.classList.contains('context-location-path')).toBe(true)}
 expect(fetch).toHaveBeenCalledExactlyOnceWith('/api/chat/context',expect.objectContaining({signal:expect.any(AbortSignal)}))
})
it('leaves WorkspaceOnly without new classes or path focus stops and preserves its input',async()=>{
 vi.stubGlobal('fetch',vi.fn(async()=>response(metadata)))
 const view=render(<CognitionSettings mode="baseline" onModeChange={vi.fn()} workspaceOnly/>);await screen.findByDisplayValue(root)
 expect(view.container.querySelector('.cognition-context')).toBeNull()
 expect(view.container.querySelector('.context-location-path')).toBeNull()
 expect(view.container.querySelector('code[tabindex]')).toBeNull()
 expect(view.container.querySelector('.project-document-path')?.getAttribute('class')).toBe('project-document-path')
 const input=screen.getByDisplayValue(root) as HTMLInputElement;fireEvent.change(input,{target:{value:'UNSAVED_WORKSPACE'}});expect(input.value).toBe('UNSAVED_WORKSPACE')
})
it('retains loading and empty metadata without fabricating sources',async()=>{
 let finish!:(value:unknown)=>void;vi.stubGlobal('fetch',vi.fn(()=>new Promise(resolve=>{finish=resolve})))
 const view=render(<CognitionSettings mode="baseline" onModeChange={vi.fn()}/>)
 expect(screen.getByText(t('core.CognitionSettings.loading_context_sources_4b187f'))).toBeTruthy()
 finish(response({...metadata,paths:[]}));await screen.findByText('EXACT_PROFILE')
 expect(view.container.querySelectorAll('.context-source-grid > *')).toHaveLength(0)
})
it('retains metadata failure and retry without claiming a populated layout',async()=>{
 const fetch=vi.fn(async()=>response({detail:{message:'ORIGINAL_CONTEXT_FAILURE'}},503));vi.stubGlobal('fetch',fetch)
 const view=render(<CognitionSettings mode="baseline" onModeChange={vi.fn()}/>)
 await screen.findByRole('alert');expect(view.container.querySelector('.context-summary')).toBeNull()
 fireEvent.click(screen.getByRole('button',{name:t('core.CognitionSettings.retry_942087')}))
 await waitFor(()=>expect(fetch).toHaveBeenCalledTimes(2))
})
it.each(['markdown','json'] as const)('retains exact %s document data when opening an opted-in path',async format=>{
 const content=format==='markdown'?'# USER TITLE\nUser prose with several words and `original_code`':'{"long_key_original":"Exact user value with spaces","rows":[1,2]}'
 const fetch=vi.fn(async()=>response({id:paths[0].id,workspace_root:root,path:paths[0].path,format,content,size_bytes:content.length,sha256:'a'.repeat(64)}));vi.stubGlobal('fetch',fetch)
 const view=render(<ProjectContextDocument item={paths[0]} workspaceRoot={root} compactPath/>)
 const details=view.container.querySelector('details')!;expect(fetch).not.toHaveBeenCalled()
 details.open=true;fireEvent(details,new Event('toggle',{bubbles:true}))
 await waitFor(()=>expect(view.container.querySelector('.project-document-raw pre')?.textContent).toBe(content))
 expect(fetch).toHaveBeenCalledTimes(1);expect(view.container.querySelector('.project-document-path')?.textContent).toBe(paths[0].path)
})
it('keeps foreign document rejection and default opt-out for other consumers',async()=>{
 vi.stubGlobal('fetch',vi.fn(async()=>response({id:'FOREIGN',workspace_root:'other',format:'markdown',content:'FOREIGN PRIVATE CONTENT'})))
 const view=render(<ProjectContextDocument item={paths[0]} workspaceRoot={root}/>),details=view.container.querySelector('details')!
 expect(view.container.querySelector('code[tabindex]')).toBeNull()
 details.open=true;fireEvent(details,new Event('toggle',{bubbles:true}))
 await screen.findByRole('alert');expect(screen.queryByText('FOREIGN PRIVATE CONTENT')).toBeNull()
})
it('scopes compact layout to Settings, preserves native details and prose, and adapts by effective container width',()=>{
 const css=readFileSync('src/components/ContextReadability.css','utf8'),ast=postcss.parse(css)
 ast.walkRules(rule=>{expect(rule.selector.split(',').every(selector=>selector.trim().startsWith('#root .app-shell .cognition-context'))).toBe(true)})
 ast.walkDecls(decl=>{
  expect(decl.important).not.toBe(true)
  expect(['font-size','height','min-height','max-height']).not.toContain(decl.prop)
  if(decl.prop==='white-space')expect((decl.parent as postcss.Rule).selector).toContain('code.context-location-path')
  if(decl.prop==='display'&&decl.value==='grid')expect((decl.parent as postcss.Rule).selector).toContain(':not(.project-document)')
 })
 expect(css).toContain('@container context-readability (max-width: 760px)')
 expect(css).toContain('align-items: start')
 expect(css).toContain('overflow-x: auto');expect(css).toContain('text-overflow: clip')
 expect(css).not.toMatch(/project-document-content|project-json|\.workspace-settings|\.workspace-sources/)
})

it('defaults secondary metadata/prose to one closed native Details, retains disclosure state across ES/EN without refetch',async()=>{
 const fetch=vi.fn(async()=>response(metadata));vi.stubGlobal('fetch',fetch)
 const view=render(<CognitionSettings mode="baseline" onModeChange={vi.fn()}/>);await screen.findByText('EXACT_PROFILE')
 const details=view.container.querySelector('.cognition-context-details') as HTMLDetailsElement
 expect(details.open).toBe(false);expect(details.querySelector(':scope > summary')?.textContent).toBe('Detalles')
 expect(screen.getByText('EXACT_PROFILE').closest('details')).toBe(details)
 expect(view.container.querySelector('.context-source-grid p')).toBeNull()
 expect(view.container.querySelector('.context-sources-heading span')).toBeNull()
 expect(view.container.querySelector('.cognition-context-intro')).toBeNull()
 expect(details.querySelectorAll('.context-source-descriptions > div')).toHaveLength(5)
 details.open=true;fireEvent(details,new Event('toggle',{bubbles:true}))
 act(()=>setLocale('en'));expect(details.querySelector(':scope > summary')?.textContent).toBe('Details');expect(details.open).toBe(true)
 act(()=>setLocale('es'));expect(details.open).toBe(true);expect(fetch).toHaveBeenCalledTimes(1)
})
it('keeps absent source and non-present/unknown memory state visible outside secondary Details',async()=>{
 vi.stubGlobal('fetch',vi.fn(async()=>response({...metadata,paths:paths.map(p=>({...p,state:'absent'})),memory:{...metadata.memory,state:'UNEXPECTED_MEMORY_STATE'}})))
 const view=render(<CognitionSettings mode="baseline" onModeChange={vi.fn()}/>);await screen.findByText('EXACT_PROFILE')
 const critical=view.container.querySelector('.cognition-memory-state')!
 expect(critical.textContent).toContain('UNEXPECTED_MEMORY_STATE');expect(critical.getAttribute('role')).toBe('status')
 expect(critical.closest('.cognition-context-details')).toBeNull()
 expect(view.container.querySelectorAll('.context-source-grid .absent')).toHaveLength(5)
 for(const source of view.container.querySelectorAll('.context-source-grid .absent'))expect(source.closest('.cognition-context-details')).toBeNull()
})
