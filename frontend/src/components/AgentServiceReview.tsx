import {useEffect,useRef,useState} from 'react'
import {t,useI18n} from '../i18n'

export type FilesystemProposal={proposal_id:string;owner_id:string;conversation_id:string;plan_sha256:string;root:string;status:string}
type Binding={ownerId:string;conversationId:string;revision:number}
type Review=FilesystemProposal&{conversation_revision:number;review_token:string|null;plan:{operation:string;source:string|null;target:string;content:string|null;sha256:string};receipt?:unknown}

export default function AgentServiceReview({proposal,ownerId,conversationId,revision}:Binding&{proposal:FilesystemProposal}){
  useI18n()
  const scope=JSON.stringify([proposal,ownerId,conversationId,revision])
  const scopeRef=useRef(scope);scopeRef.current=scope
  const operationKeys={write:'agentTools.write',mkdir:'agentTools.mkdir',copy:'agentTools.copy',move:'agentTools.move',rename:'agentTools.rename',trash:'agentTools.trash',restore:'agentTools.restore'} as const
  const epoch=useRef(0)
  const [review,setReview]=useState<Review|null>(null),[approved,setApproved]=useState(false),[busy,setBusy]=useState(false),[failed,setFailed]=useState(false)
  const bound=proposal?.owner_id===ownerId&&proposal?.conversation_id===conversationId&&/^fsproposal_[a-f0-9]{32}$/.test(proposal?.proposal_id||'')&&/^[a-f0-9]{64}$/.test(proposal?.plan_sha256||'')
  const valid=(data:Review)=>data?.proposal_id===proposal.proposal_id&&data.owner_id===ownerId&&data.conversation_id===conversationId&&data.root===proposal.root&&data.plan_sha256===proposal.plan_sha256&&data.plan?.sha256===proposal.plan_sha256&&data.conversation_revision===revision
  async function call(action:string,args:Record<string,unknown>={}){
    const response=await fetch(`/api/agent-tools/filesystem/${encodeURIComponent(proposal.proposal_id)}/${action}`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({owner_id:ownerId,conversation_id:conversationId,revision,...args})})
    const data=await response.json()
    if(!response.ok||!valid(data))throw new Error('review_rejected')
    return data as Review
  }
  async function load(){
    const generation=++epoch.current,captured=scope
    setApproved(false);setReview(null);setBusy(true);setFailed(false)
    if(!bound){setBusy(false);return}
    try{const value=await call('review');if(generation===epoch.current&&scopeRef.current===captured)setReview(value)}
    catch{if(generation===epoch.current&&scopeRef.current===captured)setFailed(true)}
    finally{if(generation===epoch.current&&scopeRef.current===captured)setBusy(false)}
  }
  useEffect(()=>{void load();return()=>{epoch.current++}},[scope])
  async function apply(){
    if(!bound||busy||!approved||!review?.review_token||review.status!=='PROPOSED')return
    const captured=scope,generation=epoch.current,seen=review
    setBusy(true);setApproved(false);setReview({...seen,review_token:null})
    try{const value=await call('execute',{review_token:seen.review_token,plan_sha256:seen.plan_sha256,confirmed:true});if(scopeRef.current===captured&&epoch.current===generation)setReview(value)}
    catch{if(scopeRef.current===captured&&epoch.current===generation){setReview(null);setFailed(true)}}
    finally{if(scopeRef.current===captured&&epoch.current===generation)setBusy(false)}
  }
  if(!bound)return <section aria-label={t('agentTools.fsReview')}><p role="alert">{t('agentTools.reviewMismatch')}</p></section>
  return <section className="workspace-manager workspace-manager--inline" aria-label={t('agentTools.fsReview')}>
    <h3>{t('agentTools.fsReview')}</h3><p><code>{proposal.root}</code></p>
    <button type="button" disabled={busy} onClick={()=>void load()}>{t('agentTools.loadReview')}</button>
    {failed&&<p role="alert">{t('agentTools.reviewFailed')}</p>}
    {review&&<><p role="status">{review.status}</p><dl><dt>{t('agentTools.operation')}</dt><dd>{operationKeys[review.plan.operation as keyof typeof operationKeys]?t(operationKeys[review.plan.operation as keyof typeof operationKeys]):review.plan.operation}</dd><dt>{t('agentTools.source')}</dt><dd>{review.plan.source||'—'}</dd><dt>{t('agentTools.target')}</dt><dd>{review.plan.target}</dd></dl>
      {review.plan.content!==null&&<label>{t('agentTools.content')}<textarea rows={5} value={review.plan.content} readOnly/></label>}
      {review.status==='PROPOSED'&&review.review_token&&<><label><input type="checkbox" checked={approved} disabled={busy} onChange={event=>setApproved(event.target.checked)}/>{t('agentTools.approvePlan')}</label><button type="button" disabled={busy||!approved} onClick={()=>void apply()}>{t('agentTools.confirmExecute')}</button></>}
      <details><summary>{t('agentTools.details')}</summary><pre>{JSON.stringify({plan_sha256:review.plan_sha256,receipt:review.receipt},null,2)}</pre></details>
    </>}
  </section>
}
