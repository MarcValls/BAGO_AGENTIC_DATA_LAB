// @vitest-environment jsdom
import React from 'react'
import {afterEach, beforeEach, expect, it, vi} from 'vitest'
import {cleanup, fireEvent, render, screen} from '@testing-library/react'
import FreelancerSettings from '../../../src/components/FreelancerSettings'
import {resetLocaleForTests, setLocale} from '../../../src/i18n'

beforeEach(() => { resetLocaleForTests(); setLocale('en') })
afterEach(() => { cleanup(); vi.unstubAllGlobals() })

it('stores a write-only token through the API, verifies identity and never retains it in browser storage', async () => {
  const calls: Array<{url:string; init?:RequestInit}> = []
  let listCount = 0
  vi.stubGlobal('fetch', vi.fn(async (url:string, init?:RequestInit) => {
    calls.push({url,init})
    if (url === '/api/connections/freelancer' && !init?.method) {
      listCount += 1
      return {ok:true,status:200,json:async()=>({connections:listCount === 1 ? [] : [{id:'conn-1',name:'Freelancer',kind:'freelancer_readonly',environment:'sandbox',state:'connected',has_credential:true,account_id:42,username:'ada',display_name:null,last_checked_at:'now',last_error:null,revision:'rev-2'}]})}
    }
    const body = url.endsWith('/verify')
      ? {id:'conn-1',name:'Freelancer',kind:'freelancer_readonly',environment:'sandbox',state:'connected',has_credential:true,account_id:42,username:'ada',display_name:null,last_checked_at:'now',last_error:null,revision:'rev-2'}
      : url === '/api/connections/freelancer' && init?.method === 'POST'
        ? {id:'conn-1',name:'Freelancer',kind:'freelancer_readonly',environment:'sandbox',state:'configured_unverified',has_credential:true,account_id:null,username:null,display_name:null,last_checked_at:null,last_error:null,revision:'rev-1'}
        : {connections:[{id:'conn-1',name:'Freelancer',kind:'freelancer_readonly',environment:'sandbox',state:'connected',has_credential:true,account_id:42,username:'ada',display_name:null,last_checked_at:'now',last_error:null,revision:'rev-2'}]}
    return {ok:true,status:200,json:async()=>body}
  }))
  render(<FreelancerSettings />)
  fireEvent.click(screen.getByText('Freelancer',{exact:true}))
  await screen.findByText('No Freelancer accounts are saved.')
  fireEvent.change(screen.getByLabelText('Freelancer OAuth token'),{target:{value:'LOCAL_SECRET_SENTINEL'}})
  fireEvent.click(screen.getByRole('button',{name:'Save and verify'}))
  await screen.findByText((_, element) => element?.tagName === 'SPAN' && Boolean(element.textContent?.includes('ID 42')))
  expect(calls.map(call=>call.url)).toEqual(['/api/connections/freelancer','/api/connections/freelancer','/api/connections/freelancer/conn-1/verify','/api/connections/freelancer'])
  expect(JSON.parse(String(calls[1].init?.body)).credential).toBe('LOCAL_SECRET_SENTINEL')
  expect((screen.getByLabelText('Freelancer OAuth token') as HTMLInputElement).value).toBe('')
  expect(JSON.stringify(localStorage)).not.toContain('LOCAL_SECRET_SENTINEL')
  expect(document.body.textContent).not.toContain('LOCAL_SECRET_SENTINEL')
  expect(screen.getByText((_, element) => element?.tagName === 'SPAN' && Boolean(element.textContent?.includes('verified')))).toBeTruthy()
})
