// @vitest-environment jsdom
import React from 'react'
import {afterEach,beforeEach,expect,it,vi} from 'vitest'
import {act,cleanup,fireEvent,render,screen,waitFor} from '@testing-library/react'
import {resetLocaleForTests,setLocale,t} from '../../src/i18n'
import AgentServiceReview from '../../src/components/AgentServiceReview'

const proposal={proposal_id:'fsproposal_'+'a'.repeat(32),owner_id:'producer',conversation_id:'conv',root:'C:/synthetic',plan_sha256:'b'.repeat(64),status:'PROPOSED'}
const value={...proposal,conversation_revision:7,review_token:'host-review-token',plan:{operation:'write',source:null,target:'report.txt',content:'Synthetic report',sha256:proposal.plan_sha256}}
const response=(data:any,status=200)=>({ok:status<400,status,json:async()=>data})
beforeEach(()=>{localStorage.clear();resetLocaleForTests()})
afterEach(()=>{cleanup();vi.unstubAllGlobals()})

it('executes only after a separate human review and exact token/hash confirmation',async()=>{
 const calls:any[]=[]
 vi.stubGlobal('fetch',vi.fn(async(path:string,init:RequestInit)=>{
   const body=JSON.parse(String(init.body));calls.push({path,body})
   return response(path.endsWith('/execute')?{...value,status:'VERIFIED',review_token:null,receipt:{status:'VERIFIED'}}:value)
 }))
 render(<AgentServiceReview proposal={proposal} ownerId="producer" conversationId="conv" revision={7}/>)
 await screen.findByDisplayValue('Synthetic report')
 expect(calls).toHaveLength(1)
 expect((screen.getByRole('button',{name:t('agentTools.confirmExecute')}) as HTMLButtonElement).disabled).toBe(true)
 fireEvent.click(screen.getByLabelText(t('agentTools.approvePlan')))
 fireEvent.click(screen.getByRole('button',{name:t('agentTools.confirmExecute')}))
 await screen.findByText('VERIFIED')
 expect(calls[1].body).toEqual({owner_id:'producer',conversation_id:'conv',revision:7,review_token:value.review_token,plan_sha256:proposal.plan_sha256,confirmed:true})
 expect(calls.filter(c=>c.path.endsWith('/execute'))).toHaveLength(1)
})

it.each([{ownerId:'foreign',conversationId:'conv'},{ownerId:'producer',conversationId:'foreign'}])('rejects a foreign proposal before requesting any review: %s',async binding=>{
 const fetch=vi.fn();vi.stubGlobal('fetch',fetch)
 render(<AgentServiceReview proposal={proposal} {...binding} revision={7}/>)
 expect(screen.getByRole('alert').textContent).toContain(t('agentTools.reviewMismatch'))
 expect(fetch).not.toHaveBeenCalled()
})

it('drops a stale in-flight review when the conversation revision changes',async()=>{
 let release:(value:any)=>void=()=>{}
 let count=0
 vi.stubGlobal('fetch',vi.fn(async()=>++count===1?await new Promise(resolve=>{release=resolve}):response({...value,conversation_revision:8,review_token:'new-token'})))
 const view=render(<AgentServiceReview proposal={proposal} ownerId="producer" conversationId="conv" revision={7}/>)
 await waitFor(()=>expect(count).toBe(1))
 view.rerender(<AgentServiceReview proposal={proposal} ownerId="producer" conversationId="conv" revision={8}/>)
 await screen.findByDisplayValue('Synthetic report')
 await act(async()=>{release(response({...value,plan:{...value.plan,content:'stale text'}}))})
 expect(screen.queryByDisplayValue('stale text')).toBeNull()
 expect((screen.getByRole('button',{name:t('agentTools.confirmExecute')}) as HTMLButtonElement).disabled).toBe(true)
})

it('rejects an altered plan fingerprint and never retries a failed execution',async()=>{
 const fetch=vi.fn(async()=>response({...value,plan_sha256:'c'.repeat(64)}));vi.stubGlobal('fetch',fetch)
 render(<AgentServiceReview proposal={proposal} ownerId="producer" conversationId="conv" revision={7}/>)
 await screen.findByRole('alert')
 expect(screen.queryByRole('button',{name:t('agentTools.confirmExecute')})).toBeNull()
 expect(fetch).toHaveBeenCalledTimes(1)
})

it('keeps the same review controls available in English',async()=>{
 setLocale('en');vi.stubGlobal('fetch',vi.fn(async()=>response(value)))
 render(<AgentServiceReview proposal={proposal} ownerId="producer" conversationId="conv" revision={7}/>)
 await screen.findByDisplayValue('Synthetic report')
 expect(screen.getByRole('button',{name:'Confirm and execute this operation'})).toBeTruthy()
 expect(screen.getByLabelText('I reviewed the folder, operation and content.')).toBeTruthy()
})

it('does not retry when confirmation fails or the result is uncertain',async()=>{
 const calls:string[]=[]
 vi.stubGlobal('fetch',vi.fn(async(path:string)=>{calls.push(path);return path.endsWith('/execute')?response({error:'changed'},409):response(value)}))
 render(<AgentServiceReview proposal={proposal} ownerId="producer" conversationId="conv" revision={7}/>)
 await screen.findByDisplayValue('Synthetic report')
 fireEvent.click(screen.getByLabelText(t('agentTools.approvePlan')))
 fireEvent.click(screen.getByRole('button',{name:t('agentTools.confirmExecute')}))
 await screen.findByRole('alert')
 expect(calls.filter(path=>path.endsWith('/execute'))).toHaveLength(1)
 expect(calls).toHaveLength(2)
 expect(screen.queryByRole('button',{name:t('agentTools.confirmExecute')})).toBeNull()
})
