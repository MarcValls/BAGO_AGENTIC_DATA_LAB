import {presentAgentError} from './AgentTaskForm'
import {AgentPresentationError} from './AgentTaskForm'
import {useI18n, t, formatDate, formatNumber, apiError, errorMessage} from '../i18n'
import {useEffect, useRef, useState} from 'react'
import {isConversationInspection, type ConversationInspection, type InspectionSelection} from '../types/inspection'
import './ChatInspection.css'
import './ChatInspectionOverrides.css'

type InspectionView='inspector'|'summary'|'retrieval'|'authorization'|'trace'|'evaluation'
const viewTitles:Record<InspectionView,string>={get inspector() { return t('agents.ChatInspection.conversacion_actual_inspect') },get summary() { return t('agents.ChatInspection.resumen_de_la_ejecucion') },get retrieval() { return t('agents.ChatInspection.evidencias_de_la_ejecucion') },get authorization() { return t('agents.ChatInspection.autorizacion_de_la_ejecucion') },get trace() { return t('agents.ChatInspection.traza_de_la_ejecucion') },get evaluation() { return t('agents.ChatInspection.evaluacion_de_la_ejecucion') }}
export default function ChatInspection({selection, onSelect,view='inspector',embedded=false,onViewChange}: {selection: InspectionSelection | null; onSelect: (selection: InspectionSelection) => void;view?:InspectionView;embedded?:boolean;onViewChange?:(view:InspectionView)=>void}) {
  useI18n()
  if (!selection) return <section role="status">{!embedded&&<h2>{t('agents.ChatInspection.inspeccion_de_la_conversacion')}</h2>}<p>{t('agents.ChatInspection.selecciona_una_conversacion_en_chat_no_se_han_cargado_artefactos_de_ot')}</p></section>
  return <InspectionContent key={`${selection.conversationId}:${selection.revision ?? ''}:${selection.traceId ?? ''}:${selection.executionId ?? ''}`} selection={selection} onSelect={onSelect} view={view} embedded={embedded} onViewChange={onViewChange} />
}
function InspectionContent({selection, onSelect,view,embedded,onViewChange}: {selection: InspectionSelection; onSelect: (selection: InspectionSelection) => void;view:InspectionView;embedded:boolean;onViewChange?:(view:InspectionView)=>void}) {
  useI18n()
  const [data,setData]=useState<ConversationInspection | null>(null)
  const [loading,setLoading]=useState(true)
  const [error,setError]=useState<string | Error>('')
  const [offset,setOffset]=useState(0)
  const [copyState,setCopyState]=useState<{identity:string;status:'copied'|'failed'}|null>(null)
  const copyRequest=useRef(0)
  const mounted=useRef(true)
  useEffect(()=>{mounted.current=true;return()=>{mounted.current=false;copyRequest.current++}},[])
  async function copyIdentity(identity:string,value:string){
    const request=++copyRequest.current
    setCopyState(null)
    try {
      await navigator.clipboard.writeText(value)
      if(mounted.current&&request===copyRequest.current)setCopyState({identity,status:'copied'})
    } catch {
      if(mounted.current&&request===copyRequest.current)setCopyState({identity,status:'failed'})
    }
  }
  useEffect(()=>{
    const controller=new AbortController();let current=true
    setLoading(true);setData(null);setError('')
    const query=new URLSearchParams({offset:String(offset),limit:'20'})
    if(selection.traceId)query.set('trace_id',selection.traceId)
    if(selection.executionId)query.set('execution_id',selection.executionId)
    void fetch(`/api/conversations/${encodeURIComponent(selection.conversationId)}/inspection?${query}`,{signal:controller.signal})
      .then(async response=>{const body=await response.json();if(!response.ok)throw apiError(body,response.status,'agents');return body as ConversationInspection})
      .then(body=>{
        if(!current)return
        if(!isConversationInspection(body,selection))throw new AgentPresentationError(() => t('agents.ChatInspection.la_respuesta_no_corresponde_a_la_seleccion_o_contiene_datos_invalidos_'))
        setData(body)
      }).catch(cause=>{if(current)setError(cause instanceof Error ? cause : new AgentPresentationError(() => t('agents.ChatInspection.error_de_inspeccion')))}).finally(()=>{if(current)setLoading(false)})
    return()=>{current=false;controller.abort()}
  },[selection.conversationId,selection.revision,selection.traceId,selection.executionId,offset])
  const selected=data?.selected
  const trace=selected?.state==='available'?selected.trace:null
  const integrityLabel=selected?.integrity==='hash_verified'?t('agents.hierarchy.integrityHashVerified'):selected?.integrity==='legacy_unverified'?t('agents.hierarchy.integrityLegacyUnverified'):selected?.integrity==='not_available'?t('agents.hierarchy.integrityUnavailable'):t('agents.hierarchy.integrityUnknown')
  const identity = (
    <footer className="chat-inspection-context" role="group" aria-label={t('agents.hierarchy.conversationIdentity')}>
      <div className="chat-inspection-context-row" role="group" aria-label={t('agents.ChatInspection.conversacion')}>
        <span className="chat-inspection-context-label">{t('agents.ChatInspection.conversacion')}</span>
        <code>{selection.conversationId}</code>
        <button type="button" aria-label={t('agents.hierarchy.copyConversationId')} onClick={()=>void copyIdentity('conversation',selection.conversationId)}>{t('agents.hierarchy.copyShort')}</button>
        {copyState&&copyState.identity==='conversation'&&<span role="status">{t(copyState.status==='copied'?'agents.hierarchy.copiedConversationId':'agents.hierarchy.copyConversationFailed')}</span>}
      </div>
      {selected&&<div className="chat-inspection-context-row" role="group" aria-label={t('agents.hierarchy.executionIdentity')}>
        <span className="chat-inspection-context-label">{t('agents.ChatInspection.ejecucion')}</span>
        {selected.execution_id?<><code>{selected.execution_id}</code><button type="button" aria-label={t('agents.hierarchy.copyIdentity',{label:t('agents.ChatInspection.ejecucion')})} onClick={()=>void copyIdentity('execution',selected.execution_id!)}>{t('agents.hierarchy.copyShort')}</button>{copyState&&copyState.identity==='execution'&&<span role="status">{t(copyState.status==='copied'?'agents.hierarchy.identityCopied':'agents.hierarchy.copyIdentityFailed')}</span>}</>:<span>{t('agents.ChatInspection.no_registrada')}</span>}
        <span className="chat-inspection-context-label">{t('agents.ChatInspection.traza')}</span>
        <code>{selected.trace_id}</code>
        <button type="button" aria-label={t('agents.hierarchy.copyIdentity',{label:t('agents.ChatInspection.traza')})} onClick={()=>void copyIdentity('trace',selected.trace_id)}>{t('agents.hierarchy.copyShort')}</button>
        {copyState&&copyState.identity==='trace'&&<span role="status">{t(copyState.status==='copied'?'agents.hierarchy.identityCopied':'agents.hierarchy.copyIdentityFailed')}</span>}
        <span className={`chat-inspection-integrity chat-inspection-integrity--${selected.integrity==='hash_verified'?'checked':selected.integrity==='legacy_unverified'?'unverified':'unavailable'}`}>{integrityLabel}</span>
      </div>}
    </footer>
  )
  const technicalFields = selected && <>
          <dl><dt>{t('agents.hierarchy.originalIntegrity')}</dt><dd><code>{selected.integrity}</code></dd>
            {selected.sha256&&<><dt>{t('agents.hierarchy.traceHash')}</dt><dd><code>{selected.sha256}</code></dd></>}
            {selected.reason&&<><dt>{t('agents.hierarchy.originalReason')}</dt><dd>{selected.reason}</dd></>}
          </dl>
          {selected.limitations.length>0&&<ul>{selected.limitations.map((item,index)=><li key={index}>{item}</li>)}</ul>}
        </>
  const technicalDetails = selected && <details className="chat-inspection-technical"><summary>{t('agents.aux.context.technical')}</summary>{technicalFields}</details>
  const commonContext = <details className="chat-inspection-technical chat-inspection-common"><summary>{t('agents.aux.context.technical')}</summary>{identity}{technicalFields}</details>
  return <section className="chat-inspection" aria-label={t('agents.ChatInspection.inspeccion_de_la_conversacion_actual')}>
    <header className="chat-inspection-heading">
      {!embedded&&<h2>{viewTitles[view]}</h2>}
    </header>
    {loading&&<p role="status">{t('agents.ChatInspection.cargando_inspeccion_de_esta_conversacion')}</p>}
    {error&&<p role="alert">{typeof error === 'string' ? error : presentAgentError(error)}</p>}
    {embedded&&commonContext}
    {data&&<>
      {data.total>0&&<div className="chat-inspection-run-control">
        <label className="chat-inspection-execution-select">{t('agents.ChatInspection.ejecucion_de_esta_conversacion')}<select value={selected?.trace_id ?? ''} onChange={event=>{if(event.target.value)onSelect({...selection,traceId:event.target.value,executionId:undefined})}}>{!selected&&<option value="">{t('agents.ChatInspection.ejecucion_no_disponible')}</option>}{selected&&!data.executions.some(item=>item.trace_id===selected.trace_id)&&<option value={selected.trace_id}>{t('agents.hierarchy.selectedExecution')}</option>}{data.executions.map((item,index)=><option key={item.trace_id} value={item.trace_id}>{t('agents.hierarchy.executionOrdinal',{current:data.offset+index+1,total:data.total})}</option>)}</select></label>
        {(data.total>20||data.offset>0)&&<div className="chat-inspection-run-pagination"><span>{t('agents.inspection.traceCount', {count: formatNumber(data.total), start: formatNumber(data.offset+1)})}</span>{data.offset>0&&<button onClick={()=>setOffset(Math.max(0,offset-20))}>{t('agents.ChatInspection.ejecuciones_anteriores')}</button>}{data.next_offset!==null&&<button onClick={()=>setOffset(data.next_offset!)}>{t('agents.ChatInspection.mas_ejecuciones')}</button>}</div>}
      </div>}
      {data.state==='no_artifacts'&&<p role="status">{t('agents.ChatInspection.esta_conversacion_no_tiene_artefactos_de_ejecucion_asociados_no_se_uti')}</p>}
      {data.state==='selection_required'&&<p role="status">{t('agents.ChatInspection.hay_varias_ejecuciones_selecciona_la_que_quieres_inspeccionar')}</p>}
      {data.total===0&&<h3>{t('agents.ChatInspection.sin_ejecucion_registrada')}</h3>}
      {(view==='summary'||(!embedded&&view==='inspector'))&&<dl className="chat-inspection-counters" aria-label={t('agents.ChatInspection.registros_de_la_conversacion_y_ejecucion_actual')}>
        <div><dt>{t('agents.ChatInspection.ejecuciones')}</dt><dd>{formatNumber(data.total)}</dd></div>
        <div><dt>{t('agents.ChatInspection.eventos')}</dt><dd>{formatNumber(trace?.events.length??0)}</dd></div>
        <div><dt>{t('agents.ChatInspection.referencias')}</dt><dd>{formatNumber(new Set(trace?.events.flatMap(event=>event.evidence_refs)??[]).size)}</dd></div>
        <div><dt>{t('agents.ChatInspection.registros_de_autorizacion')}</dt><dd>{formatNumber(trace?.events.filter(event=>event.kind==='authorization').length??0)}</dd></div>
      </dl>}
      {selected&&<>
        {selected.state!=='available'&&<p role="alert">{selected.state==='invalid'?t('agents.hierarchy.traceRejected'):t('agents.hierarchy.traceUnavailable')}</p>}
        {!embedded&&technicalDetails}
        {selected.state==='available'&&selected.trace&&<>
          {embedded&&view==='inspector'&&<section className="chat-inspection-overview"><p>{t('agents.ChatInspection.estos_datos_describen_el_registro_de_ejecucion_no_certifican_el_result')}</p>{onViewChange&&<nav aria-label={viewTitles.inspector}><button type="button" onClick={()=>onViewChange('summary')}>{viewTitles.summary}</button><button type="button" onClick={()=>onViewChange('trace')}>{viewTitles.trace}</button></nav>}</section>}
          {view==='summary'&&<section aria-label={t('agents.ChatInspection.resumen_observado')}><p>{t('agents.ChatInspection.estos_datos_describen_el_registro_de_ejecucion_no_certifican_el_result')}</p><p>{t('agents.ChatInspection.datos_de_traza_local_no_equivalen_a_una_evaluacion_pass_ni_a_un_paquet')}</p></section>}
          {view==='authorization'&&<section role="status"><h3>{t('agents.ChatInspection.sin_paquete_de_autorizacion')}</h3><p>{t('agents.ChatInspection.esta_traza_no_aporta_una_autorizacion_gobernada_un_estado_allow_de_una')}</p></section>}
          {view==='evaluation'&&<section role="status"><h3>{t('agents.ChatInspection.sin_evaluacion_registrada')}</h3><p>{t('agents.ChatInspection.esta_traza_no_aporta_resultados_de_evaluacion_no_se_asigna_pass_a_part')}</p></section>}
          {view==='retrieval'&&<section aria-label={t('agents.ChatInspection.referencias_de_evidencia')}><h3>{t('agents.ChatInspection.referencias_registradas')}</h3>{selected.trace.events.some(event=>event.evidence_refs.length>0)?<ul>{selected.trace.events.filter(event=>event.evidence_refs.length>0).map(event=><li key={event.event_id}><strong>{event.name}</strong><ul>{event.evidence_refs.map((ref,index)=><li key={index}><code>{ref}</code></li>)}</ul></li>)}</ul>:<p>{t('agents.ChatInspection.no_hay_referencias_de_evidencia_en_los_eventos_de_esta_traza')}</p>}<p>{t('agents.ChatInspection.una_referencia_registrada_no_demuestra_por_si_sola_que_su_contenido_es')}</p></section>}
          {(view==='trace'||(!embedded&&view==='inspector'))&&<div className="chat-inspection-table" role="region" aria-label={t('agents.ChatInspection.eventos_de_la_ejecucion')} tabIndex={0}>
          <table><caption>{t('agents.ChatInspection.eventos_de_la_ejecucion_seleccionada')}</caption><thead><tr><th>{t('agents.ChatInspection.orden')}</th><th>{t('agents.ChatInspection.evento')}</th><th>{t('agents.ChatInspection.estado_observado')}</th><th>{t('agents.ChatInspection.evidencia')}</th></tr></thead><tbody>{[...selected.trace.events].sort((a,b)=>a.sequence-b.sequence).map(event=><tr key={event.event_id}><td>{event.sequence}</td><td><code>{event.event_id}</code> {event.name}<br/>{t('agents.ChatInspection.padre')} {event.parent_event_id ?? t('agents.ChatInspection.sin_padre')}</td><td>{event.status}</td><td><details><summary>{t('agents.ChatInspection.ver_datos_registrados')}</summary><pre>{JSON.stringify({attributes:event.attributes,evidence_refs:event.evidence_refs},null,2)}</pre></details></td></tr>)}</tbody></table>
          </div>}
        </>}
      </>}
    </>}
    {!embedded&&identity}

  </section>
}


