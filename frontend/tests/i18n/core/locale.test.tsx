// @vitest-environment jsdom
import React,{useState} from 'react'
import {afterEach,beforeEach,expect,it,vi} from 'vitest'
import {act,cleanup,fireEvent,render,screen} from '@testing-library/react'
import {catalogs,t,setLocale,getLocale,resetLocaleForTests,formatDate,formatNumber,apiError,errorMessage,localMessage,useI18n} from '../../../src/i18n'
import LanguageSelector from '../../../src/i18n/LanguageSelector'
const placeholder=(text:string)=>[...text.matchAll(/\{([A-Za-z][\w]*)\}/g)].map(m=>m[1]).sort()
beforeEach(()=>{localStorage.clear();resetLocaleForTests()})
afterEach(()=>{cleanup();vi.restoreAllMocks();localStorage.clear();resetLocaleForTests()})
it('has exact key and placeholder parity across the complete ES/EN catalogs',()=>{
 expect(Object.keys(catalogs.es).sort()).toEqual(Object.keys(catalogs.en).sort())
 for(const key of Object.keys(catalogs.es) as Array<keyof typeof catalogs.es>){
  expect(catalogs.es[key].trim(),key).not.toBe('');expect(catalogs.en[key].trim(),key).not.toBe('')
  expect(placeholder(catalogs.es[key]),key).toEqual(placeholder(catalogs.en[key]))
 }
})
it('starts in Spanish regardless of English browser settings and rejects invalid persisted choices',()=>{
 vi.spyOn(navigator,'language','get').mockReturnValue('en-US')
 expect(getLocale()).toBe('es');expect(t('common.close')).toBe('Cerrar')
 localStorage.setItem('bago.ui.locale','fr');resetLocaleForTests();expect(getLocale()).toBe('es')
})
it('persists English and restores it without relying on browser language',()=>{
 setLocale('en');expect(localStorage.getItem('bago.ui.locale')).toBe('en')
 resetLocaleForTests();expect(getLocale()).toBe('en');expect(t('common.close')).toBe('Close')
})
it('switches in place without losing form text or consent and never submits a form',()=>{
 const submit=vi.fn()
 function Fixture(){useI18n();const[text,setText]=useState('Original user text'),[checked,setChecked]=useState(false);return <form onSubmit={event=>{event.preventDefault();submit()}}><LanguageSelector/><label>Fixture<input aria-label="Fixture input" value={text} onChange={event=>setText(event.target.value)}/></label><input aria-label="Fixture consent" type="checkbox" checked={checked} onChange={event=>setChecked(event.target.checked)}/><button type="submit">Fixture submit</button></form>}
 render(<Fixture/>);fireEvent.change(screen.getByLabelText('Fixture input'),{target:{value:'Do not translate USER_123'}});fireEvent.click(screen.getByLabelText('Fixture consent'))
 fireEvent.change(screen.getByLabelText('Idioma de la interfaz'),{target:{value:'en'}})
 expect(screen.getByLabelText('Interface language')).toBeTruthy();expect((screen.getByLabelText('Fixture input') as HTMLInputElement).value).toBe('Do not translate USER_123');expect((screen.getByLabelText('Fixture consent') as HTMLInputElement).checked).toBe(true)
 fireEvent.change(screen.getByLabelText('Interface language'),{target:{value:'es'}});expect(screen.getByLabelText('Idioma de la interfaz')).toBeTruthy();expect(submit).not.toHaveBeenCalled()
 expect(document.documentElement.lang).toBe('es');expect(document.title).toBe('BAGO · Espacio de trabajo')
})
it('keeps the preference in memory and reports unavailable storage',()=>{
 vi.spyOn(Storage.prototype,'getItem').mockImplementation(()=>{throw new Error('blocked')})
 vi.spyOn(Storage.prototype,'setItem').mockImplementation(()=>{throw new Error('blocked')})
 resetLocaleForTests();render(<LanguageSelector/>);fireEvent.change(screen.getByLabelText('Idioma de la interfaz'),{target:{value:'en'}})
 expect(getLocale()).toBe('en');expect(screen.getByRole('status').textContent).toContain('kept for this session')
})
it('formats dates in explicit UTC and numbers according to the selected locale',()=>{
 expect(formatNumber(1234.5,{minimumFractionDigits:2})).toBe(new Intl.NumberFormat('es-ES',{minimumFractionDigits:2}).format(1234.5))
 const value='2026-10-23T12:34:00Z';expect(formatDate(value,{year:'numeric',month:'2-digit',day:'2-digit'})).toBe(new Intl.DateTimeFormat('es-ES',{year:'numeric',month:'2-digit',day:'2-digit',timeZone:'UTC'}).format(new Date(value)))
 setLocale('en');expect(formatNumber(1234.5)).toBe(new Intl.NumberFormat('en-GB').format(1234.5));expect(formatDate(value)).toContain('23 Oct 2026')
})
it('localizes known errors and preserves unknown diagnostics as technical data without mutating payloads',()=>{
 const body={error:{code:'busy',message:'ORIGINAL_PERMISSION_DIAGNOSTIC'}};const original=JSON.stringify(body),error=apiError(body,409,'workspace')
 expect(errorMessage(error)).toContain('Otra operación');expect(errorMessage(error)).toContain('Detalle técnico original: ORIGINAL_PERMISSION_DIAGNOSTIC');setLocale('en')
 expect(errorMessage(error)).toContain('Another operation');expect(JSON.stringify(body)).toBe(original);expect(error.code).toBe('busy');expect(error.status).toBe(409)
 const unknown=apiError({detail:{code:'UNKNOWN_RAW_CODE',message:'DO_NOT_TRANSLATE_123'}})
 expect(errorMessage(unknown)).toContain('The request could not be completed');expect(errorMessage(unknown)).toContain('Original technical detail: DO_NOT_TRANSLATE_123')
})
it('keeps local error and notice descriptors reactive after they were created',()=>{
 const message=localMessage('common.requestFailed');expect(errorMessage(message)).toBe('No se pudo completar la solicitud.');setLocale('en');expect(errorMessage(message)).toBe('The request could not be completed.')
 expect(errorMessage('common.close')).toBe('Close');expect(errorMessage(new Error('common.close'))).toBe('Close')
})
