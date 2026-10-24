import {es as statesEs,en as statesEn} from './domains/states'
import {useSyncExternalStore} from 'react'
import {es as commonEs,en as commonEn} from './domains/common'
import {es as coreEs,en as coreEn} from './domains/core'
import {es as commerceEs,en as commerceEn} from './domains/commerce'
import {es as agentsEs,en as agentsEn} from './domains/agents'
export const catalogs={es:{...commonEs,...statesEs,...coreEs,...commerceEs,...agentsEs},en:{...commonEn,...statesEn,...coreEn,...commerceEn,...agentsEn}}
export type Locale='es'|'en'
export type TranslationKey=keyof typeof catalogs.es
export type MessageParameters=Record<string,string|number>
type Placeholder<S extends string>=S extends `${string}{${infer P}}${infer R}`?P|Placeholder<R>:never
export type ParametersFor<K extends TranslationKey>=Record<Placeholder<(typeof catalogs.es)[K]>,string|number>
const storageKey='bago.ui.locale'
let locale:Locale='es',loaded=false,version=0,storageUnavailable=false
const listeners=new Set<()=>void>()
const notify=()=>{version++;listeners.forEach(listener=>listener())}
function initialize(){
 if(loaded)return
 loaded=true
 try{const saved=globalThis.localStorage?.getItem(storageKey);locale=saved==='en'?'en':'es'}catch{locale='es';storageUnavailable=true}
}
export function getLocale():Locale{initialize();return locale}
export function setLocale(next:Locale){
 if(next!=='es'&&next!=='en')return
 initialize();locale=next
 try{globalThis.localStorage?.setItem(storageKey,next);storageUnavailable=false}catch{storageUnavailable=true}
 if(typeof document!=='undefined'){document.documentElement.lang=next;document.title=t('common.applicationTitle')}
 notify()
}
type TranslationArgs<K extends TranslationKey> = K extends TranslationKey ? keyof ParametersFor<K> extends never ? [params?:MessageParameters] : [params:ParametersFor<K>] : never
export function t<K extends TranslationKey>(key:K,...args:TranslationArgs<K>):string
export function t(key:TranslationKey,params?:MessageParameters):string{
 const template=catalogs[getLocale()][key]
 if(typeof template!=='string')return `[${key}]`
 return template.replace(/\{([A-Za-z][\w]*)\}/g,(_all,name:string)=>params&&Object.prototype.hasOwnProperty.call(params,name)?String(params[name]):`{${name}}`)
}
export function formatDate(value:string|number|Date,options:Intl.DateTimeFormatOptions={}){
 const date=value instanceof Date?value:new Date(value)
 if(Number.isNaN(date.getTime()))return String(value)
 const explicitParts=['year','month','day','hour','minute','second','weekday'].some(key=>key in options)
 return new Intl.DateTimeFormat(getLocale()==='es'?'es-ES':'en-GB',{...(explicitParts?{}:{dateStyle:'medium',timeStyle:'short'}),timeZone:'UTC',...options}).format(date)
}
export function formatNumber(value:number,options:Intl.NumberFormatOptions={}){return new Intl.NumberFormat(getLocale()==='es'?'es-ES':'en-GB',options).format(value)}
export function useI18n(){
 initialize()
 useSyncExternalStore(listener=>{listeners.add(listener);return()=>listeners.delete(listener)},()=>version,()=>0)
 return {t,locale:getLocale(),setLocale,formatDate,formatNumber,storageUnavailable}
}
export class PresentationError extends Error{
 readonly originalDetail:string;readonly code:string;readonly status:number
 constructor(code:string,originalDetail:string,status=0){super();this.name='PresentationError';this.code=code;this.originalDetail=originalDetail;this.status=status}
 get message(){
  const key=`common.error.${this.code}` as TranslationKey
  const explanation=key in catalogs.es?t(key):t('common.requestFailed')
  return this.originalDetail?`${explanation}\n${t('common.originalDiagnostic')}: ${this.originalDetail}`:explanation
 }
}
export function apiError(body:unknown,status=0,_domain?:string):PresentationError{
 const payload=body&&typeof body==='object'?body as Record<string,any>:{}
 const detail=payload.error??payload.detail??payload
 const code=typeof detail==='string'&&/^\w+$/.test(detail)?detail:typeof detail?.reason_code==='string'?detail.reason_code:typeof detail?.code==='string'?detail.code:'unknown'
 const original=typeof detail==='string'?detail:typeof detail?.message==='string'?detail.message:''
 return new PresentationError(code,original,status)
}
export function errorMessage(error:unknown,fallbackKey:TranslationKey='common.requestFailed'){
 const value=error instanceof Error?error.message:typeof error==='string'?error:''
 if(value in catalogs.es)return t(value as TranslationKey)
 if(error instanceof Error && !(error instanceof PresentationError) && error.name!=='AgentPresentationError' && !Object.getOwnPropertyDescriptor(error,'message')?.get)return apiError({detail:{message:value}}).message
 return value||t(fallbackKey)
}
export function localMessage<K extends TranslationKey>(key:K,...args:TranslationArgs<K>):Error
export function localMessage(key:TranslationKey,params?:MessageParameters):Error{
 const error=new Error();Object.defineProperty(error,'message',{get:()=>t(key,params),configurable:true});return error
}
/** Test-only preference reset. No application state, permissions or data are touched. */
export function resetLocaleForTests(){locale='es';loaded=false;storageUnavailable=false;notify()}

export function stateLabel(value:unknown){
 const raw=String(value??''),key=`common.state.${raw}` as TranslationKey
 return key in catalogs.es?`${t(key)} · ${raw}`:`${t('common.unknownState')} · ${raw||t('common.notRecorded')}`
}
