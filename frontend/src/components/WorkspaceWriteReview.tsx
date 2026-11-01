import {t, useI18n, apiError, errorMessage, localMessage} from '../i18n'
import {useEffect,useId,useRef,useState} from 'react'
import ServiceTabs from './ServiceTabs'

type Context={owner_kind:'agent';owner_id:string;conversation_id:string;conversation_revision:number}
export type WriteProposalSummary={proposal_id:string;revision:string;workspace_id:string;path:string;mode:'create'|'modify';status:'PROPOSED'|'APPLIED'|'CONFLICT'|'UNCERTAIN';context:Context;proposed_sha256:string}
type Review=WriteProposalSummary&{before_sha256:string|null;proposed_text:string;before_text:string;diff:string;review_sha256:string;receipt:Record<string,unknown>|null;observation:Record<string,unknown>|null}
type Binding={ownerKind:string;ownerId:string;conversationId:string;conversationRevision:number}
const record=(value:unknown):value is Record<string,any>=>Boolean(value)&&typeof value==='object'&&!Array.isArray(value)
const token=(value:unknown,max=200):value is string=>typeof value==='string'&&value.length>0&&value.length<=max&&!/[\x00-\x1f\x7f]/.test(value)
const hash=(value:unknown):value is string=>typeof value==='string'&&/^[a-f0-9]{64}$/.test(value)
export function isWriteProposalSummary(value:unknown,binding?:Binding):value is WriteProposalSummary{
 if(!record(value)||!/^write_[a-f0-9]{32}$/.test(value.proposal_id)||!token(value.revision)||!token(value.workspace_id)||!hash(value.proposed_sha256)||!['create','modify'].includes(value.mode)||!['PROPOSED','APPLIED','CONFLICT','UNCERTAIN'].includes(value.status))return false
 if(!token(value.path,240)||value.path.startsWith('/')||/[\\:]/.test(value.path)||value.path.split('/').some((part:string)=>!part||part==='.'||part==='..'))return false
 const context=value.context
 if(!record(context)||context.owner_kind!=='agent'||!token(context.owner_id)||!token(context.conversation_id)||!Number.isInteger(context.conversation_revision)||context.conversation_revision<0)return false
 return !binding||(binding.ownerKind==='agent'&&context.owner_id===binding.ownerId&&context.conversation_id===binding.conversationId&&context.conversation_revision<=binding.conversationRevision)
}
function validReview(value:unknown,summary:WriteProposalSummary,binding:Binding):value is Review{
 if(!isWriteProposalSummary(value,binding))return false
 const data=value as unknown as Record<string,any>
 return data.proposal_id===summary.proposal_id&&data.workspace_id===summary.workspace_id&&data.path===summary.path&&data.mode===summary.mode
  &&data.context.owner_kind===summary.context.owner_kind&&data.context.owner_id===summary.context.owner_id&&data.context.conversation_id===summary.context.conversation_id&&data.context.conversation_revision===summary.context.conversation_revision
  &&(data.revision!==summary.revision||data.proposed_sha256===summary.proposed_sha256)
  &&(data.before_sha256===null||hash(data.before_sha256))&&hash(data.review_sha256)
  &&typeof data.proposed_text==='string'&&data.proposed_text.length<=1048576&&typeof data.before_text==='string'&&data.before_text.length<=1048576&&typeof data.diff==='string'&&data.diff.length<=3145728
  &&(data.receipt===null||record(data.receipt))&&(data.observation===null||record(data.observation))
}
const statusLabels={get PROPOSED(){return t('commerce.pending_proposal')},get APPLIED(){return t('commerce.applied')},get CONFLICT(){return t('commerce.revision_conflict')},get UNCERTAIN(){return t('commerce.uncertain_outcome')}}
export default function WorkspaceWriteReview({proposal,ownerKind,ownerId,conversationId,conversationRevision}:{proposal:WriteProposalSummary}&Binding){
  useI18n()

 const uid=useId(),binding={ownerKind,ownerId,conversationId,conversationRevision}
 const bound=isWriteProposalSummary(proposal,binding)
 const scope=JSON.stringify([ownerKind,ownerId,conversationId,conversationRevision,proposal.proposal_id,proposal.revision,proposal.workspace_id,proposal.path,proposal.mode,proposal.context,proposal.proposed_sha256])
 const scopeRef=useRef(scope);scopeRef.current=scope
 const epoch=useRef(0)
 const pendingReviews=useRef(new Map<string,Promise<unknown>>())
 const [reviewScope,setReviewScope]=useState('')
  const [review,setReview]=useState<Review|null>(null),[text,setText]=useState(''),[busy,setBusy]=useState(false),[error, setError] = useState<string|Error>('')
 const [tab,setTab]=useState<'content'|'diff'>('content')
 const dirty=review!==null&&text!==review.proposed_text
 const accept=(value:unknown)=>{
  if(!validReview(value,proposal,binding))throw new Error("commerce.the_review_does_not_match_the_proposal_project_or_conversation")
  setReview(value);setReviewScope(scope);setText(value.proposed_text)
  return value
 }
 async function action(operation:string,args:Record<string,unknown>,signal?:AbortSignal){
  const path=`/api/workspaces/v1/workspaces/${encodeURIComponent(proposal.workspace_id)}/actions`,body=JSON.stringify({operation,...args,context:proposal.context})
  const execute=async()=>{
   const response=await fetch(path,{method:'POST',headers:{'Content-Type':'application/json'},body,signal})
   const data=await response.json()
   if(!response.ok)throw apiError(data,response.status,'commerce')
   return data
  }
  // StrictMode repeats the mount effect. Share only an identical pending
  // read-only review; never cache a result or coalesce a write/confirmation.
  if(operation!=='review_write'||signal)return execute()
  const key=JSON.stringify([path,body]),existing=pendingReviews.current.get(key)
  if(existing)return existing
  const request=execute().finally(()=>{pendingReviews.current.delete(key)})
  pendingReviews.current.set(key,request)
  return request
 }
 async function load(){
  const generation=++epoch.current,captured=scope
  const current=()=>generation===epoch.current&&captured===scopeRef.current
  setReview(null);setReviewScope('');setBusy(true);setError('')
  if(!bound){setBusy(false);setError("commerce.the_proposal_does_not_belong_to_the_current_agent_or_conversation");return}
  try{const result=await action('review_write',{proposal_id:proposal.proposal_id});if(current())accept(result)}
  catch(cause){if(current())setError(cause instanceof Error ? cause :"commerce.could_not_load_the_review")}
  finally{if(current())setBusy(false)}
 }
 useEffect(()=>{void load();return()=>{epoch.current++}},[scope])
 async function revise(){
  if(!bound||reviewScope!==scope||busy||!review||review.status!=='PROPOSED'||!dirty)return
  const generation=epoch.current,captured=scope,submitted=text,previous=review
  const current=()=>generation===epoch.current&&captured===scopeRef.current
  setBusy(true);setError('')
  try{
   const result=await action('revise_write',{proposal_id:previous.proposal_id,expected_revision:previous.revision,text:submitted})
   if(!current())return
   if(!validReview(result,proposal,binding)||result.revision===previous.revision||result.proposed_text!==submitted)throw new Error("commerce.the_new_content_revision_was_not_confirmed")
   accept(result)
  }catch(cause){if(current())setError(cause instanceof Error ? cause :"commerce.could_not_save_the_proposal")}
  finally{if(current())setBusy(false)}
 }
 async function apply(){
  if(!bound||reviewScope!==scope||busy||!review||review.status!=='PROPOSED'||dirty)return
  const generation=epoch.current,captured=scope,seen=review
  const current=()=>generation===epoch.current&&captured===scopeRef.current
  setBusy(true);setError('')
  try{
   const result=await action('apply_write',{proposal_id:seen.proposal_id,expected_revision:seen.revision,review_sha256:seen.review_sha256,confirmation:{confirmed:true,operation:'apply_write',workspace_id:seen.workspace_id,proposal_id:seen.proposal_id,revision:seen.revision,review_sha256:seen.review_sha256}})
   if(current()){const loaded=accept(result);if(loaded.status==='PROPOSED')setError("commerce.the_service_did_not_confirm_application_check_the_status_before_authorizing_again")}
  }catch(cause){
   if(!current())return
   const message=cause instanceof Error ? cause :localMessage('commerce.could_not_confirm_the_write')
   setError(message);setReview(null)
   // Read-only recovery observes a possible effect; it never retries the write.
   try{const observed=await action('review_write',{proposal_id:seen.proposal_id});if(current())accept(observed)}catch{if(current())setError(Object.defineProperty(new Error(),'message',{get:()=>errorMessage(message)+' '+t('commerce.recovery_failed')}))}
  }finally{if(current())setBusy(false)}
 }
 if(!bound)return <section className="workspace-manager workspace-manager--inline workspace-write-review" aria-label={t('commerce.file_review_269')}><p role="alert">{t('commerce.the_proposal_does_not_belong_to_the_current_agent_or_conversation')}</p></section>
 return <section className="workspace-manager workspace-manager--inline workspace-write-review" aria-labelledby={`${uid}-title`}>
  <header><h3 id={`${uid}-title`}>{proposal.mode==='create'?t('commerce.create_file'):t('commerce.modify_file')}</h3></header>
  <p>{t('commerce.project')} <code>{proposal.workspace_id}</code> {t('commerce.file')} <code>{proposal.path}</code></p>
  <p role="status">{busy?t('commerce.checking_review'):review&&reviewScope===scope?statusLabels[review.status]:t('commerce.review_unavailable')}</p>
  {error&&<p role="alert">{errorMessage(error)}</p>}
  <button type="button" disabled={busy} onClick={()=>void load()}>{t('commerce.reload_review')}</button>
  {review&&reviewScope===scope&&<>
   <ServiceTabs<'content'|'diff'> id={uid} label={t('commerce.file_review')} value={tab} onChange={setTab} items={[{id:'content',label:t('commerce.content')},{id:'diff',label:t('commerce.changes')}]}/>
   <section role="tabpanel" id={`${uid}-panel-content`} aria-labelledby={`${uid}-tab-content`} tabIndex={0} hidden={tab!=='content'}><label>{t('commerce.proposed_content')}<textarea rows={12} value={text} maxLength={1048576} disabled={busy} readOnly={review.status!=='PROPOSED'} onChange={event=>setText(event.target.value)}/></label><button type="button" disabled={busy||!dirty||review.status!=='PROPOSED'} onClick={()=>void revise()}>{t('commerce.save_proposal_and_review')}</button></section>
   <section role="tabpanel" id={`${uid}-panel-diff`} aria-labelledby={`${uid}-tab-diff`} tabIndex={0} hidden={tab!=='diff'}><pre>{dirty?t('commerce.save_the_proposal_to_update_the_changes'):review.diff||t('commerce.no_differences_recorded')}</pre><details><summary>{t('commerce.previous_content')}</summary><pre>{review.before_text||t('commerce.new_or_empty_file')}</pre></details></section>
   <details><summary>{t('commerce.identity_and_revision')}</summary><code>{review.proposal_id}</code><code>{review.revision}</code><code>{t('commerce.base')} {review.before_sha256??t('commerce.new_file')}</code><code>{t('commerce.content_285')} {review.proposed_sha256}</code><code>{t('commerce.revision_286')} {review.review_sha256}</code></details>
   {dirty&&<p role="status">{t('commerce.unsaved_edits_save_and_review_before_confirming')}</p>}
   {review.status==='PROPOSED'&&<button type="button" disabled={busy||dirty} onClick={()=>void apply()}>{t('agents.TaskExecution.accept')}</button>}
   {review.status==='CONFLICT'&&<p role="alert">{t('commerce.the_file_or_proposal_changed_this_write_is_not_authorized')}</p>}
   {review.status==='UNCERTAIN'&&<p role="alert">{t('commerce.the_outcome_cannot_be_confirmed_the_write_will_not_be_retried_automatically')}</p>}
   {review.status==='APPLIED'&&!review.receipt&&<p role="alert">{t('commerce.applied_according_to_the_service_receipt_unavailable')}</p>}
   {review.receipt&&<details><summary>{t('commerce.write_receipt')}</summary><pre>{JSON.stringify(review.receipt,null,2)}</pre></details>}
   {review.observation&&<details><summary>{t('commerce.observed_result')}</summary><pre>{JSON.stringify(review.observation,null,2)}</pre></details>}
  </>}
 </section>
}
