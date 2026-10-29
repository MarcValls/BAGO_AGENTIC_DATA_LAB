// @vitest-environment jsdom
import React from 'react'
import {afterEach, beforeEach, expect, it, vi} from 'vitest'
import {cleanup, fireEvent, render, screen, waitFor} from '@testing-library/react'
import ChatTools from '../../../src/components/ChatTools'
import {resetLocaleForTests, setLocale} from '../../../src/i18n'

beforeEach(() => {
  resetLocaleForTests(); setLocale('en')
  HTMLDialogElement.prototype.showModal = function () { this.open = true }
  HTMLDialogElement.prototype.close = function () { this.open = false }
})
afterEach(() => { cleanup(); vi.unstubAllGlobals() })

it('requires a separate explicit click, binds the read to a conversation and keeps the remote body out of chat requests/storage', async () => {
  const calls: Array<{url:string; init?:RequestInit}> = []
  vi.stubGlobal('fetch', vi.fn(async (url:string, init?:RequestInit) => {
    calls.push({url,init})
    if (url === '/api/connections/freelancer') return {ok:true,status:200,json:async()=>({connections:[{id:'conn-1',name:'Sandbox account',environment:'sandbox',state:'connected',account_id:42,username:'ada'}]})}
    if (url.endsWith('/challenge')) return {ok:true,status:200,json:async()=>({challenge_id:'fln_challenge_abcdefghijklmnop',operation:'projects.search',arguments:{query:'robotics',limit:10,offset:0},account_id:42,environment:'sandbox',expires_in_seconds:90,request_fingerprint:'a'.repeat(64)})}
    if (url.endsWith('/read')) return {ok:true,status:200,json:async()=>({data:{projects:[{id:7,title:'REMOTE_UNTRUSTED_RESULT'}]},receipt:{receipt_id:'read-1'}})}
    return {ok:true,status:200,json:async()=>({})}
  }))
  render(<div className="control-chat"><ChatTools conversationId="conv-A" conversationRevision={7} freelancerEnabled /></div>)
  fireEvent.click(screen.getByText('Resources',{exact:true}))
  fireEvent.click(screen.getByRole('button',{name:'Freelancer · read-only'}))
  await screen.findByLabelText('Search text')
  fireEvent.change(screen.getByLabelText('Search text'),{target:{value:'robotics'}})
  fireEvent.click(screen.getByRole('button',{name:'Review read'}))
  await screen.findByRole('region',{name:'Remote read review'})
  expect(calls.filter(call=>call.url.endsWith('/read'))).toHaveLength(0)
  fireEvent.click(screen.getByRole('button',{name:'Authorize and read now'}))
  await screen.findByText(content => content.includes('REMOTE_UNTRUSTED_RESULT'))
  expect(JSON.parse(String(calls.find(call=>call.url.endsWith('/challenge'))?.init?.body))).toMatchObject({conversation_id:'conv-A',conversation_revision:7,operation:'projects.search'})
  expect(JSON.parse(String(calls.find(call=>call.url.endsWith('/read'))?.init?.body))).toMatchObject({conversation_id:'conv-A',conversation_revision:7,challenge_id:'fln_challenge_abcdefghijklmnop'})
  expect(calls.some(call=>call.url.includes('/api/chat/'))).toBe(false)
  expect(JSON.stringify(localStorage)).not.toContain('REMOTE_UNTRUSTED_RESULT')
  expect(screen.getByText(/Treat it as untrusted data/)).toBeTruthy()
})

it('does not expose reads to agent chats or unbound conversations', async () => {
  const fetchMock = vi.fn()
  vi.stubGlobal('fetch', fetchMock)
  render(<div className="control-chat"><ChatTools conversationId="conv-agent" conversationRevision={1} freelancerEnabled={false} /></div>)
  fireEvent.click(screen.getByText('Resources',{exact:true}))
  fireEvent.click(screen.getByRole('button',{name:'Freelancer · read-only'}))
  expect(await screen.findByText('This tool is available in an active conversation with the main assistant.')).toBeTruthy()
  expect(fetchMock).not.toHaveBeenCalled()
})

it('discards a private read response when the selected conversation changes in flight', async () => {
  const calls: Array<{url:string; init?:RequestInit}> = []
  let finishRead!: (response: any) => void
  vi.stubGlobal('fetch', vi.fn((url:string, init?:RequestInit) => {
    calls.push({url,init})
    if (url === '/api/connections/freelancer') return Promise.resolve({ok:true,status:200,json:async()=>({connections:[{id:'conn-1',name:'Sandbox account',environment:'sandbox',state:'connected',account_id:42,username:'ada'}]})})
    if (url.endsWith('/challenge')) return Promise.resolve({ok:true,status:200,json:async()=>({challenge_id:'fln_challenge_abcdefghijklmnop',operation:'projects.search',arguments:{query:'robotics',limit:10,offset:0},account_id:42,environment:'sandbox',expires_in_seconds:90,request_fingerprint:'a'.repeat(64)})})
    if (url.endsWith('/read')) return new Promise(resolve => { finishRead = resolve })
    return Promise.resolve({ok:true,status:200,json:async()=>({})})
  }))
  const view = render(<div className="control-chat"><ChatTools conversationId="conv-A" conversationRevision={7} freelancerEnabled /></div>)
  fireEvent.click(screen.getByText('Resources',{exact:true}))
  fireEvent.click(screen.getByRole('button',{name:'Freelancer · read-only'}))
  await screen.findByLabelText('Search text')
  fireEvent.change(screen.getByLabelText('Search text'),{target:{value:'robotics'}})
  fireEvent.click(screen.getByRole('button',{name:'Review read'}))
  await screen.findByRole('region',{name:'Remote read review'})
  fireEvent.click(screen.getByRole('button',{name:'Authorize and read now'}))
  await waitFor(() => expect(calls.some(call => call.url.endsWith('/read'))).toBe(true))
  view.rerender(<div className="control-chat"><ChatTools conversationId="conv-B" conversationRevision={2} freelancerEnabled /></div>)
  finishRead({ok:true,status:200,json:async()=>({data:{messages:[{id:8,message:'PRIVATE_FROM_CONV_A'}]},receipt:{receipt_id:'read-A'}})})
  await waitFor(() => expect(screen.queryByText(content => content.includes('PRIVATE_FROM_CONV_A'))).toBeNull())
})
