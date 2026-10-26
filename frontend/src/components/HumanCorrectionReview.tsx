import {useEffect, useId, useRef, useState} from 'react'
import './HumanCorrectionReview.css'

export type HumanCorrectionSource = {
  ownerKind: 'assistant' | 'agent'; ownerId: string; conversationId: string; revision: number
  messageId: string; content: string; traceId?: string
}
export type PreparedHumanCorrection = {source: HumanCorrectionSource; sourceSha256: string; content: string}
export function humanCorrectionMessage(source: HumanCorrectionSource, text: string, hash: string) {
  return `Corrección humana de intención.\nReferencia a la respuesta visible ${source.messageId}, conversación ${source.conversationId}, revisión ${source.revision}.\nSHA-256 de la respuesta visible: ${hash}\n\nMi intención corregida:\n${text.trim()}\n\nRehaz la respuesta teniendo en cuenta esta corrección. Conserva la respuesta original. Esta corrección no concede permisos ni autoriza acciones adicionales.`
}
export default function HumanCorrectionReview({source, current, busy, permissions, permissionIdentity = permissions, onSend, onCancel}: {
  source: HumanCorrectionSource; current: boolean; busy: boolean; permissions: string; permissionIdentity?: string
  onSend: (prepared: PreparedHumanCorrection) => void; onCancel: () => void
}) {
  const [text,setText] = useState('')
  const [prepared,setPrepared] = useState<PreparedHumanCorrection|null>(null)
  const [preparing,setPreparing] = useState(false)
  const [error,setError] = useState('')
  const editor = useRef<HTMLTextAreaElement>(null)
  const request = useRef(0)
  const editorId = useId()
  useEffect(()=>{editor.current?.focus(); return()=>{request.current++}},[])
  useEffect(()=>{setPrepared(null); request.current++; setPreparing(false)},[source,current,permissionIdentity])
  async function prepare() {
    if (!text.trim() || !current || busy || preparing) return
    const version=++request.current
    setPreparing(true);setError('')
    try {
      const bytes = new TextEncoder().encode(source.content)
      const hash = Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256',bytes)), b=>b.toString(16).padStart(2,'0')).join('')
      if(version!==request.current)return
      setPrepared({source,sourceSha256:hash,content:humanCorrectionMessage(source,text,hash)})
    } catch {if(version===request.current)setError('No se pudo preparar la identidad de la respuesta. No se enviará la corrección.')}
    finally {if(version===request.current)setPreparing(false)}
  }
  return <section className="human-correction-review" aria-label="Corrección humana de intención" onKeyDown={event=>{
    if(event.key==='Escape'&&!busy){event.preventDefault();event.stopPropagation();onCancel()}
  }}>
    <header><h3>Corregir interpretación</h3><button type="button" onClick={onCancel} disabled={busy}>Cancelar corrección</button></header>
    <p className="human-correction-reference">Respuesta <code>{source.messageId}</code> · conversación <code>{source.conversationId}</code> · revisión {source.revision}</p>
    <details><summary>Respuesta original visible</summary><pre>{source.content}</pre></details>
    <p>No se aportó una interpretación separada. Corrige aquí la intención que quieres expresar; el original y tu borrador del chat se conservan.</p>
    <label htmlFor={editorId}>Mi intención corregida</label>
    <textarea ref={editor} id={editorId} value={text} maxLength={8000} rows={3} disabled={busy} onChange={event=>{
      request.current++;setPreparing(false);setPrepared(null);setText(event.target.value);setError('')
    }}/>
    {!current&&<p role="alert">El contexto de la respuesta cambió o ya no está disponible. No se enviará esta corrección. Tu texto sigue aquí para recuperarlo.</p>}
    {error&&<p role="alert">{error}</p>}
    <button type="button" onClick={()=>void prepare()} disabled={!current||busy||preparing||!text.trim()}>{preparing?'Preparando…':'Preparar corrección'}</button>
    {prepared&&<div className="human-correction-proposal">
      <h4>Mensaje nuevo propuesto</h4><pre>{prepared.content}</pre>
      <p>Se enviará como un mensaje nuevo; la referencia al original es informativa.</p>
      <p>Permisos actuales: {permissions}. Se aplican los controles habituales del chat.</p>
      <button type="button" disabled={!current||busy||preparing} onClick={()=>onSend(prepared)}>{busy?'Enviando corrección…':'Rehacer con esta corrección'}</button>
    </div>}
  </section>
}
