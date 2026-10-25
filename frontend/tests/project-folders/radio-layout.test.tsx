// @vitest-environment jsdom
import React from 'react'
import {afterEach,beforeEach,expect,it,vi} from 'vitest'
import {cleanup,render,screen,waitFor} from '@testing-library/react'
import {readFileSync} from 'node:fs'
import WorkspaceManager from '../../src/components/WorkspaceManager'
import {resetLocaleForTests,setLocale} from '../../src/i18n'
import {folderFixture} from './fixtures'
beforeEach(()=>{localStorage.clear();resetLocaleForTests();setLocale('es')})
afterEach(()=>{cleanup();vi.unstubAllGlobals()})
it('keeps actual mode radios intrinsic and labels at least 44px without changing the text input rule or causing effects',async()=>{
 const style=document.createElement('style');style.textContent=readFileSync('src/components/WorkspaceManager.css','utf8');document.head.append(style)
 try{
  const f=folderFixture();render(<WorkspaceManager/>);await waitFor(()=>expect((screen.getByRole('button',{name:'Usar carpeta'}) as HTMLButtonElement).disabled).toBe(false))
  for(const label of ['Usar esta carpeta existente','Crear una carpeta hija']){
   const radio=screen.getByRole('radio',{name:label}),computed=getComputedStyle(radio)
   expect(computed.width).toBe('auto');expect(computed.display).toBe('inline-block');expect(computed.flex).toBe('0 0 auto');expect(computed.margin).toBe('0px')
   expect(getComputedStyle(radio.closest('label')!).getPropertyValue('min-block-size')).toBe('44px')
  }
  expect(getComputedStyle(screen.getByLabelText('Nombre de carpeta')).width).toBe('100%')
  expect(f.mutations()).toEqual([])
 }finally{style.remove()}
})
