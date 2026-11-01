import {useEffect,useId,useRef,useState} from 'react'
import {t,useI18n} from '../i18n'
import './TaskExecutionPanel.css'

type ObjectValue=Record<string,any>
type Model={provider_id:string;model_id:string;state:string;orchestrator_enabled:boolean;agent_types?:string[]}
type Profile={id:string;config:ObjectValue}
type Context={project_id:string;root:string;binding:string;revision:string}
type Execution={execution_id:string;plan_id:string;plan_revision:number;plan_sha256:string;status:string;plan:ObjectValue|null;step_results?:Record<string,ObjectValue>;current_step?:string|null;events?:ObjectValue[]}
const object=(v:unknown):v is ObjectValue=>Boolean(v)&&typeof v==='object'&&!Array.isArray(v)
const text=(v:unknown):v is string=>typeof v==='string'&&v.length>0
const hash=(v:unknown):v is string=>typeof v==='string'&&/^[a-f0-9]{64}$/.test(v)
const statuses=['PREPARING','AWAITING_ACCEPTANCE','ACCEPTED','RUNNING','SUCCEEDED','FAILED_NO_EFFECT','PARTIAL','INCONCLUSIVE','STOP_REQUESTED','STOPPED_BEFORE_EFFECT','STALE','DENIED']
const stateLabels:Record<string,()=>string>={PREPARING:()=>t('agents.TaskExecution.state.PREPARING'),AWAITING_ACCEPTANCE:()=>t('agents.TaskExecution.state.AWAITING_ACCEPTANCE'),ACCEPTED:()=>t('agents.TaskExecution.state.ACCEPTED'),RUNNING:()=>t('agents.TaskExecution.state.RUNNING'),SUCCEEDED:()=>t('agents.TaskExecution.state.SUCCEEDED'),FAILED_NO_EFFECT:()=>t('agents.TaskExecution.state.FAILED_NO_EFFECT'),PARTIAL:()=>t('agents.TaskExecution.state.PARTIAL'),INCONCLUSIVE:()=>t('agents.TaskExecution.state.INCONCLUSIVE'),STOP_REQUESTED:()=>t('agents.TaskExecution.state.STOP_REQUESTED'),STOPPED_BEFORE_EFFECT:()=>t('agents.TaskExecution.state.STOPPED_BEFORE_EFFECT'),STALE:()=>t('agents.TaskExecution.state.STALE'),DENIED:()=>t('agents.TaskExecution.state.DENIED')}
const stateLabel=(status:string)=>stateLabels[status]?.()||status
const preparationFailureLabels=new Map<string,()=>string>([
  ['model_not_eligible',()=>t('agents.TaskExecution.failure.model_not_eligible')],
  ['model_probe_failed',()=>t('agents.TaskExecution.failure.model_probe_failed')],
  ['independent_reviewer_required',()=>t('agents.TaskExecution.failure.independent_reviewer_required')],
  ['required_check_failed',()=>t('agents.TaskExecution.failure.required_check_failed')],
  ['permissions_revision_changed',()=>t('agents.TaskExecution.failure.permissions_revision_changed')],
  ['project_binding_mismatch',()=>t('agents.TaskExecution.failure.permissions_revision_changed')],
  ['profile_revision_changed',()=>t('agents.TaskExecution.failure.profile_revision_changed')],
  ['agent_scope_mismatch',()=>t('agents.TaskExecution.failure.agent_scope_mismatch')],
])
function preparationFailure(record:Execution|null){
  if(record?.status!=='FAILED_NO_EFFECT'||record.plan!==null)return ''
  const event=Array.isArray(record.events)?[...record.events].reverse().find(value=>object(value)&&value.event_type==='PREPARATION_FAILED'):null
  const payload=event?.payload
  const reason=object(payload)&&typeof payload.reason_code==='string'?payload.reason_code:''
  return preparationFailureLabels.get(reason)?.()||t('agents.TaskExecution.failure.unknown')
}
const active=(status:string)=>['PREPARING','ACCEPTED','RUNNING','STOP_REQUESTED'].includes(status)
const modelKey=(m:{provider_id:string;model_id:string})=>JSON.stringify([m.provider_id,m.model_id])
const json=(v:unknown)=>JSON.stringify(v,null,2)
const canonical=(v:any):string=>JSON.stringify(v,(_,item)=>object(item)?Object.fromEntries(Object.keys(item).sort().map(key=>[key,item[key]])):item)
const uuid=()=>crypto.randomUUID()
function execution(value:unknown):Execution{
  if(!object(value)||!/^taskexec_[a-f0-9]{32}$/.test(value.execution_id)||!/^taskplan_[a-f0-9]{32}$/.test(value.plan_id)||!Number.isInteger(value.plan_revision)||value.plan_revision<1||(!hash(value.plan_sha256)&&!(value.plan===null&&value.plan_sha256===''))||!statuses.includes(value.status)||!(value.plan===null||object(value.plan)))throw Error(t('agents.TaskExecution.invalid'))
  if(value.plan===null){if(!['PREPARING','FAILED_NO_EFFECT','DENIED','STOP_REQUESTED','STOPPED_BEFORE_EFFECT','INCONCLUSIVE'].includes(value.status))throw Error(t('agents.TaskExecution.invalid'));return value as Execution}
  const p=value.plan
  if(!object(p.project)||!text(p.project.project_id)||!text(p.project.root)||!text(p.project.binding)||!object(p.agent)||!text(p.agent.agent_id)||!hash(p.agent.profile_sha256)||!object(p.model)||!text(p.model.provider_id)||!text(p.model.model_id)||!Array.isArray(p.steps)||!Array.isArray(p.required_checks)||!object(p.review)||!object(p.scopes)||!Array.isArray(p.scopes.requested)||!Array.isArray(p.scopes.granted))throw Error(t('agents.TaskExecution.invalid'))
  if(p.steps.some((step:unknown)=>!object(step)||!text(step.step_id)||!['filesystem','development','delegation'].includes(step.type)||!Array.isArray(step.depends_on)))throw Error(t('agents.TaskExecution.unsupported'))
  return value as Execution
}
async function request(path:string,options:RequestInit={}):Promise<any>{
  const response=await fetch(path,{cache:'no-store',...options})
  const body=await response.json().catch(()=>null)
  if(!response.ok){const detail=object(body?.error)?body.error:object(body?.detail)?body.detail:{};throw Error(`${text(detail.message)?detail.message:t('agents.TaskExecution.requestFailed')} (${text(detail.code)?detail.code:`HTTP_${response.status}`})`)}
  return body
}
const post=(body:unknown):RequestInit=>({method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)})

type InventoryEntry={path:string;kind:'file'|'directory';snapshot:null|{sha256:string;size:number}}
function inventoryEntries(value:unknown):InventoryEntry[]|null{
  if(!object(value)||!text(value.root)||value.recursive!==false||!Array.isArray(value.entries)||value.entries.length>1000)return null
  const paths=new Set<string>()
  for(const entry of value.entries){
    if(!object(entry)||!text(entry.path)||entry.path.startsWith('/')||/[\\:\u0000-\u001f\u007f]/.test(entry.path)||entry.path.split('/').some((part:string)=>!part||part==='.'||part==='..')||paths.has(entry.path))return null
    paths.add(entry.path)
    if(entry.kind==='directory'){if(entry.snapshot!==null)return null}
    else if(entry.kind==='file'){
      const snapshot=entry.snapshot
      if(!object(snapshot)||!hash(snapshot.sha256)||!Number.isSafeInteger(snapshot.size)||snapshot.size<0||snapshot.size>16*1024*1024||!Number.isInteger(snapshot.mtime_ns)||snapshot.mtime_ns<0||!Number.isInteger(snapshot.inode)||snapshot.inode<0)return null
      // Large SDK mtime_ns/inode integers are not used for decisions or reformatted.
    }else return null
  }
  return value.entries as InventoryEntry[]
}
function InventoryResult({executionStatus,step,result}:{executionStatus:string;step:ObjectValue;result:unknown}){
  // Proposed plan fields are never evidence: use only the durable step result.
  if(!['RUNNING','SUCCEEDED','PARTIAL','INCONCLUSIVE','STOP_REQUESTED'].includes(executionStatus)||step.type!=='filesystem'||step.operation!=='inventory'||!object(result)||result.step_id!==step.step_id||result.status!=='SUCCEEDED')return null
  const receipt=result.receipt
  const entries=object(receipt)&&receipt.status==='PASS'&&receipt.operation==='inventory'?inventoryEntries(receipt.inventory):null
  if(entries===null)return <p className="task-execution-inventory-error" role="alert">{t('agents.TaskExecution.inventory.invalid')}</p>
  return <section className="task-execution-inventory">
    <h4>{t('agents.TaskExecution.inventory.title')}</h4>
    <p className="task-execution-hint">{t('agents.TaskExecution.inventory.bounds')}</p>
    {entries.length===0?<p role="status">{t('agents.TaskExecution.inventory.empty')}</p>:<div className="task-execution-inventory-scroll" role="region" aria-label={t('agents.TaskExecution.inventory.region')} tabIndex={0}>
      <table aria-label={t('agents.TaskExecution.inventory.title')}><thead><tr><th scope="col">{t('agents.TaskExecution.inventory.path')}</th><th scope="col">{t('agents.TaskExecution.inventory.kind')}</th><th scope="col">{t('agents.TaskExecution.inventory.size')}</th><th scope="col">SHA-256</th></tr></thead>
      <tbody>{entries.map(entry=><tr key={entry.path}><td>{entry.path}</td><td>{entry.kind==='file'?t('agents.TaskExecution.inventory.file'):t('agents.TaskExecution.inventory.directory')}</td><td>{entry.snapshot?.size??'—'}</td><td className="task-execution-inventory-sha">{entry.snapshot?.sha256??'—'}</td></tr>)}</tbody></table>
    </div>}
  </section>
}

/** Plans are real backend records; text task answers are never promoted to effects. */
export default function TaskExecutionPanel({taskText='',sourceIdentity='new-task'}:{taskText?:string;sourceIdentity?:string}){
  useI18n()
  const uid=useId(),storageKey=`bago.task-execution.v1:${sourceIdentity}`,pendingKey=`${storageKey}:preparation`
  const [open,setOpen]=useState(false),[task,setTask]=useState(taskText)
  const [models,setModels]=useState<Model[]>([]),[profiles,setProfiles]=useState<Profile[]>([]),[context,setContext]=useState<Context|null>(null)
  const [model,setModel]=useState('auto'),[agent,setAgent]=useState('auto')
  const [record,setRecord]=useState<Execution|null>(null),[loading,setLoading]=useState(false),[preparing,setPreparing]=useState(false),[dispatching,setDispatching]=useState(false),[stopping,setStopping]=useState(false)
  const [error,setError]=useState(''),[retry,setRetry]=useState(0),[unknown,setUnknown]=useState(false)
  const [editing,setEditing]=useState(false),[profile,setProfile]=useState<Profile|null>(null),[profileDraft,setProfileDraft]=useState<ObjectValue|null>(null),[saving,setSaving]=useState(false)
  const generation=useRef(0),prepareKey=useRef(''),prepareIds=useRef(new Map<string,string>()),acceptKeys=useRef(new Map<string,string>())
  const lock=useRef(false),editingRef=useRef(false),mounted=useRef(true),recordRef=useRef<Execution|null>(null)
  const restored=useRef(false),preparingRef=useRef(false)
  const eligible=models.filter(item=>item.orchestrator_enabled===true&&['ready','configured_unverified'].includes(item.state))
  const compatible=profiles.filter(item=>text(item.config.provider_id)&&text(item.config.model_id)&&eligible.some(m=>m.provider_id===item.config.provider_id&&m.model_id===item.config.model_id&&(!m.agent_types||m.agent_types.includes(item.config.type))))
  const frozen=dispatching||Boolean(record&&active(record.status))
  // UI-only pending lock: keep it out of the scheduling effect dependencies,
  // otherwise setPreparing(true) would invalidate its own pending response.
  const controlsBlocked=preparing||frozen
  recordRef.current=record
  useEffect(()=>{mounted.current=true;return()=>{mounted.current=false;generation.current++}},[])
  useEffect(()=>{setTask(taskText);setRecord(null);recordRef.current=null;prepareKey.current='';restored.current=false;generation.current++},[taskText,sourceIdentity])

  function keep(value:Execution){
    setRecord(value);recordRef.current=value
    try{sessionStorage.setItem(storageKey,JSON.stringify({execution_id:value.execution_id,source_task_text:taskText,task,model,agent,accept_key:acceptKeys.current.get(value.plan_sha256)||null}));sessionStorage.removeItem(pendingKey)}catch{/* Keep the pending request identity if the execution projection cannot persist. */}
  }
  useEffect(()=>{
    if(!open)return
    const controller=new AbortController();let current=true
    setLoading(true);setError('');setContext(null)
    void Promise.all([request('/api/providers/chat-models',{signal:controller.signal}),request('/api/agents/list',{signal:controller.signal}),request('/api/project-permissions',{signal:controller.signal})]).then(async([catalog,agents,permissions])=>{
      if(!current)return
      if(!Array.isArray(catalog?.models)||!catalog.models.every((m:any)=>object(m)&&text(m.provider_id)&&text(m.model_id)&&text(m.state))||!Array.isArray(agents?.agents)||!agents.agents.every((a:any)=>object(a)&&text(a.id)&&object(a.config))||!object(permissions)||!text(permissions.project_id)||!text(permissions.root)||!text(permissions.binding)||!text(permissions.revision))throw Error(t('agents.TaskExecution.invalid'))
      setModels(catalog.models);setProfiles(agents.agents)
      if(!restored.current){
        restored.current=true
        let cached:any=null
        try{cached=JSON.parse(sessionStorage.getItem(storageKey)||'null')}catch{/* Ignore malformed local projection. */}
        if(object(cached)&&/^taskexec_[a-f0-9]{32}$/.test(cached.execution_id)&&(cached.source_task_text===undefined||cached.source_task_text===taskText)){
          try{
            const observed=execution(await request(`/api/task-executions/${cached.execution_id}`,{signal:controller.signal}))
            if(!current)return
            if(observed.plan&&(observed.plan.project.project_id!==permissions.project_id||observed.plan.project.binding!==permissions.binding))throw Error(t('agents.TaskExecution.bindingChanged'))
            if(typeof cached.task==='string'&&cached.task.length<=8000)setTask(cached.task)
            if(typeof cached.model==='string')setModel(cached.model)
            if(typeof cached.agent==='string')setAgent(cached.agent)
            if(text(cached.accept_key))acceptKeys.current.set(observed.plan_sha256,cached.accept_key)
            setRecord(observed);recordRef.current=observed;prepareKey.current='restored'
          }catch(cause){if(current){setUnknown(true);setError(cause instanceof Error?cause.message:t('agents.TaskExecution.requestFailed'));prepareKey.current='recovery-failed'}}
        }else{
          let pending:any=null
          try{pending=JSON.parse(sessionStorage.getItem(pendingKey)||'null')}catch{/* Ignore malformed local preparation metadata. */}
          const body=pending?.input
          if(object(pending)&&object(body)&&pending.source_identity===sourceIdentity&&pending.source_task_text===taskText&&pending.fingerprint===canonical({source_identity:sourceIdentity,source_task_text:taskText,input:body})&&body.expected_project_id===permissions.project_id&&body.expected_binding===permissions.binding&&body.expected_permissions_revision===permissions.revision&&typeof body.task_text==='string'&&body.task_text.length<=8000){
            setTask(body.task_text)
            if(body.model_selection?.mode==='auto')setModel('auto')
            else if(body.model_selection?.mode==='explicit'&&text(body.model_selection.provider_id)&&text(body.model_selection.model_id))setModel(modelKey(body.model_selection))
            if(body.agent_selection?.mode==='auto')setAgent('auto')
            else if(body.agent_selection?.mode==='existing'&&text(body.agent_selection.agent_id))setAgent(body.agent_selection.agent_id)
          }
        }
      }
      if(current)setContext(permissions as Context)
    }).catch(cause=>{if(current&&!controller.signal.aborted)setError(cause instanceof Error?cause.message:t('agents.TaskExecution.requestFailed'))}).finally(()=>{if(current)setLoading(false)})
    return()=>{current=false;controller.abort()}
  },[open,retry,storageKey])

  useEffect(()=>{
    if(!open||!context||loading||editing||saving||frozen||unknown||record||!task.trim()||task.length>8000||!eligible.length)return
    const input={task_text:task.trim(),expected_project_id:context.project_id,expected_binding:context.binding,expected_permissions_revision:context.revision,
      model_selection:model==='auto'?{mode:'auto'}:(()=>{const selected=eligible.find(m=>modelKey(m)===model);return selected?{mode:'explicit',provider_id:selected.provider_id,model_id:selected.model_id}:null})(),
      agent_selection:agent==='auto'?{mode:'auto'}:compatible.some(a=>a.id===agent)?{mode:'existing',agent_id:agent}:null}
    if(!input.model_selection||!input.agent_selection)return
    const key=JSON.stringify([input,retry])
    if(prepareKey.current===key||prepareKey.current==='recovery-failed')return
    const current=++generation.current
    const timer=setTimeout(()=>{
      prepareKey.current=key;preparingRef.current=true;setPreparing(true);setError('')
      const fingerprint=canonical({source_identity:sourceIdentity,source_task_text:taskText,input})
      let requestId=prepareIds.current.get(key)
      if(!requestId){
        try{const pending=JSON.parse(sessionStorage.getItem(pendingKey)||'null');if(object(pending)&&pending.fingerprint===fingerprint&&typeof pending.request_id==='string'&&/^[a-f0-9-]{36}$/.test(pending.request_id))requestId=pending.request_id}catch{/* Invalid projection never grants authority. */}
        if(!requestId)requestId=uuid()
        prepareIds.current.set(key,requestId)
      }
      try{sessionStorage.setItem(pendingKey,JSON.stringify({request_id:requestId,fingerprint,source_identity:sourceIdentity,source_task_text:taskText,input}))}
      catch{preparingRef.current=false;setPreparing(false);setError(t('agents.TaskExecution.storageBlocked'));return}
      void request('/api/task-executions/plans',post({request_id:requestId,...input})).then(value=>{
        if(!mounted.current||current!==generation.current||editingRef.current)return
        const next=execution(value)
        if(next.plan&&(next.plan.project.project_id!==context.project_id||next.plan.project.binding!==context.binding))throw Error(t('agents.TaskExecution.bindingChanged'))
        keep(next)
      }).catch(cause=>{if(mounted.current&&current===generation.current)setError(cause instanceof Error?cause.message:t('agents.TaskExecution.requestFailed'))}).finally(()=>{if(mounted.current&&current===generation.current){preparingRef.current=false;setPreparing(false)}})
    },350)
    return()=>{clearTimeout(timer);if(current===generation.current)generation.current++;preparingRef.current=false;setPreparing(false)}
  },[open,context,loading,editing,saving,task,model,agent,retry,frozen,unknown,record])

  function invalidate(change:()=>void){
    if(preparingRef.current||frozen)return
    generation.current++;prepareKey.current='';setRecord(null);recordRef.current=null;setUnknown(false);setError('');setPreparing(false)
    try{sessionStorage.removeItem(storageKey);sessionStorage.removeItem(pendingKey)}catch{/* No authority in this projection. */}
    change()
  }
  async function refresh(){
    const current=recordRef.current;if(!current)return
    try{const value=execution(await request(`/api/task-executions/${current.execution_id}`));if(mounted.current&&recordRef.current?.execution_id===value.execution_id){keep(value);setUnknown(false)}}catch(cause){if(mounted.current){setError(cause instanceof Error?cause.message:t('agents.TaskExecution.requestFailed'));setUnknown(true)}}
  }
  useEffect(()=>{
    if(!record||(!dispatching&&!active(record.status)))return
    const timer=setInterval(()=>void refresh(),1200)
    return()=>clearInterval(timer)
  },[record?.execution_id,record?.status,dispatching])
  async function accept(){
    const seen=recordRef.current
    if(lock.current||editingRef.current||!seen||seen.status!=='AWAITING_ACCEPTANCE'||unknown)return
    lock.current=true;setDispatching(true);setError('')
    let key=acceptKeys.current.get(seen.plan_sha256);if(!key){key=uuid();acceptKeys.current.set(seen.plan_sha256,key)}
    keep(seen)
    try{
      const response=await request(`/api/task-executions/plans/${seen.plan_id}/accept`,post({expected_plan_sha256:seen.plan_sha256,expected_plan_revision:seen.plan_revision,idempotency_key:key,confirmed:true}))
      if(response?.execution_id!==seen.execution_id||response?.plan_id!==seen.plan_id||!statuses.includes(response?.status))throw Error(t('agents.TaskExecution.invalid'))
      await refresh()
    }catch(cause){if(mounted.current){setError(cause instanceof Error?cause.message:t('agents.TaskExecution.requestFailed'));setUnknown(true);await refresh();setUnknown(true)}}
    finally{lock.current=false;if(mounted.current)setDispatching(false)}
  }
  async function stop(){
    const seen=recordRef.current;if(!seen||stopping)return
    setStopping(true);setError('')
    try{await request(`/api/task-executions/${seen.execution_id}/stop`,post({reason:'user_stop'}));await refresh()}
    catch(cause){if(mounted.current){setError(cause instanceof Error?cause.message:t('agents.TaskExecution.requestFailed'));setUnknown(true)}}finally{if(mounted.current)setStopping(false)}
  }
  async function editAgent(){
    const seen=recordRef.current;if(!seen||frozen)return
    editingRef.current=true;setEditing(true);setProfile(null);setProfileDraft(null);generation.current++;setPreparing(false);setError('')
    try{const value=await request(`/api/agents/${encodeURIComponent(seen.plan.agent.agent_id)}`);if(!object(value)||value.id!==seen.plan.agent.agent_id||!object(value.config))throw Error(t('agents.TaskExecution.invalid'));if(mounted.current&&editingRef.current){setProfile(value as Profile);setProfileDraft({...value.config})}}
    catch(cause){if(mounted.current)setError(cause instanceof Error?cause.message:t('agents.TaskExecution.requestFailed'))}
  }
  async function saveProfile(){
    if(!profile||!profileDraft||saving||frozen)return
    setSaving(true);setError('')
    try{
      const latest=await request(`/api/agents/${encodeURIComponent(profile.id)}`)
      if(!object(latest)||latest.id!==profile.id||canonical(latest.config)!==canonical(profile.config))throw Error(t('agents.TaskExecution.profileChanged'))
      const updated=await request(`/api/agents/${encodeURIComponent(profile.id)}`,{method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify({name:profileDraft.name,description:profileDraft.description,type:profile.config.type,system_prompt:profileDraft.system_prompt})})
      if(!object(updated)||updated.id!==profile.id||!object(updated.config))throw Error(t('agents.TaskExecution.invalid'))
      setProfiles(old=>[updated as Profile,...old.filter(p=>p.id!==profile.id)]);editingRef.current=false;setEditing(false);setProfile(null);setProfileDraft(null)
      invalidate(()=>setAgent(profile.id))
    }catch(cause){if(mounted.current)setError(cause instanceof Error?cause.message:t('agents.TaskExecution.requestFailed'))}finally{if(mounted.current)setSaving(false)}
  }
  const steps=(record?.plan?.steps||[]).map((step:any)=>({...step,...record?.step_results?.[step.step_id]}))
  const canAccept=record?.status==='AWAITING_ACCEPTANCE'&&!editing&&!saving&&!dispatching&&!unknown
  return <section className="task-execution" aria-labelledby={`${uid}-title`}>
    <button type="button" className="task-execution-toggle" aria-expanded={open} aria-controls={`${uid}-body`} onClick={()=>setOpen(value=>!value)}><span id={`${uid}-title`}>{t('agents.TaskExecution.title')}</span><span aria-hidden="true">{open?'−':'+'}</span></button>
    {open&&<div id={`${uid}-body`} className="task-execution-body">
      <p className="task-execution-hint">{t('agents.TaskExecution.scope')}</p>
      <label>{t('agents.TaskExecution.task')}<textarea value={task} maxLength={8000} rows={3} disabled={controlsBlocked||editing||saving} onChange={event=>invalidate(()=>setTask(event.target.value))}/></label>
      <div className="task-execution-choices"><label>{t('agents.TaskExecution.model')}<select value={model} disabled={loading||controlsBlocked||editing||saving} onChange={event=>invalidate(()=>setModel(event.target.value))}><option value="auto">{t('agents.TaskExecution.auto')}</option>{models.map(m=><option key={modelKey(m)} value={modelKey(m)} disabled={!eligible.includes(m)}>{m.provider_id} · {m.model_id} · {m.state==='ready'?t('agents.TaskExecution.ready'):m.state==='configured_unverified'?t('agents.TaskExecution.probe'):t('agents.TaskExecution.unavailable')}</option>)}</select></label>
      <label>{t('agents.TaskExecution.agent')}<select value={agent} disabled={loading||controlsBlocked||editing||saving} onChange={event=>invalidate(()=>setAgent(event.target.value))}><option value="auto">{t('agents.TaskExecution.autoAgent')}</option>{compatible.map(a=><option key={a.id} value={a.id}>{a.config.name||a.id} · {a.config.provider_id} / {a.config.model_id}</option>)}</select></label></div>
      {loading&&<p role="status">{t('agents.TaskExecution.loading')}</p>}
      {!loading&&context&&!eligible.length&&<p role="alert">{t('agents.TaskExecution.noModel')}</p>}
      {preparing&&<p role="status">{t('agents.TaskExecution.preparing')}</p>}
      {error&&<p role="alert">{error}</p>}
      {unknown&&<p role="status">{t('agents.TaskExecution.unknown')}</p>}
      {record&&<p className="task-execution-state" role="status">{dispatching?t('agents.TaskExecution.dispatching'):stateLabel(record.status)}</p>}
      {preparationFailure(record)&&<p role="alert">{preparationFailure(record)}</p>}
      {record&&!record.plan&&<><button type="button" onClick={()=>void refresh()}>{t('agents.TaskExecution.refresh')}</button><button type="button" disabled={stopping} onClick={()=>void stop()}>{record.status==='PREPARING'?t('agents.TaskExecution.cancelPlan'):t('agents.TaskExecution.stop')}</button><details><summary>{t('agents.TaskExecution.evidence')}</summary><pre>{json(record)}</pre></details></>}
      {record?.plan&&<>
        <p>{t('agents.TaskExecution.project')}: {record.plan.project.root}</p>
        <div className="task-execution-agent"><span>{t('agents.TaskExecution.agentReady')} · {profiles.find(p=>p.id===record.plan.agent.agent_id)?.config.name||t('agents.TaskExecution.taskAgent')}</span><button type="button" disabled={frozen||editing||saving||record.status!=='AWAITING_ACCEPTANCE'} onClick={()=>void editAgent()}>{t('agents.TaskExecution.edit')}</button><a href={`#${uid}-agents`} onClick={event=>{event.preventDefault();const target=document.getElementById(`${uid}-agents`) as HTMLDetailsElement|null;if(target){target.open=true;target.focus()}}}>{t('agents.TaskExecution.agentsContext')}</a></div>
        <p>{record.plan.model.provider_id} / {record.plan.model.model_id} · {record.plan.model.probe_state==='operation_ready'?t('agents.TaskExecution.operationReady'):t('agents.TaskExecution.notProbed')}</p>
        <p>{t('agents.TaskExecution.review')}: {String(record.plan.review.status)} {record.plan.review.reviewer_id||''}</p>
        {record.status==='SUCCEEDED'&&!steps.some((step:any)=>step.receipt||step.receipt_id)&&<p role="alert">{t('agents.TaskExecution.missingReceipt')}</p>}
        <ol className="task-execution-steps">{steps.map((step:any,index:number)=><li key={step.step_id||index}><strong>{step.step_id||index+1}</strong> · {step.operation||step.type||t('agents.TaskExecution.step')} {step.arguments?.source||''}{step.arguments?.source&&step.arguments?.target?' → ':''}{step.arguments?.target||step.arguments?.path||''}{step.status&&<span> · {statuses.includes(step.status)?stateLabel(step.status):step.status}</span>}{step.reason_code&&<span role="alert"> · {step.reason_code}</span>}{typeof step.arguments?.content==='string'&&<details><summary>{t('agents.TaskExecution.content')}</summary><pre>{step.arguments.content}</pre></details>}<InventoryResult executionStatus={record.status} step={record.plan.steps[index]} result={record.step_results?.[record.plan.steps[index].step_id]}/>{(step.receipt||step.receipt_id)&&<details><summary>{t('agents.TaskExecution.receipt')}</summary><pre>{json(step)}</pre></details>}</li>)}</ol>
        {editing&&<fieldset disabled={saving} className="task-execution-profile"><legend>{t('agents.TaskExecution.editing')}</legend>{profileDraft?<><label>{t('agents.TaskExecution.name')}<input value={profileDraft.name||''} onChange={event=>setProfileDraft({...profileDraft,name:event.target.value})}/></label><label>{t('agents.TaskExecution.description')}<textarea rows={2} value={profileDraft.description||''} onChange={event=>setProfileDraft({...profileDraft,description:event.target.value})}/></label><label>{t('agents.TaskExecution.instructions')}<textarea rows={4} value={profileDraft.system_prompt||''} onChange={event=>setProfileDraft({...profileDraft,system_prompt:event.target.value})}/></label><button type="button" disabled={!profileDraft.name?.trim()||!profileDraft.description?.trim()} onClick={()=>void saveProfile()}>{t('agents.TaskExecution.saveAgent')}</button></>:<p role="status">{t('agents.TaskExecution.loading')}</p>}<button type="button" onClick={()=>{editingRef.current=false;setEditing(false);setProfile(null);setProfileDraft(null)}}>{t('agents.TaskExecution.cancelEdit')}</button></fieldset>}
        <div className="task-execution-actions">{record.status==='AWAITING_ACCEPTANCE'&&<button type="button" className="primary-action" disabled={!canAccept} onClick={()=>void accept()}>{t('agents.TaskExecution.accept')}</button>}{(dispatching||active(record.status)||record.status==='AWAITING_ACCEPTANCE')&&<button type="button" disabled={stopping} onClick={()=>void stop()}>{record.status==='AWAITING_ACCEPTANCE'&&!dispatching?t('agents.TaskExecution.cancelPlan'):t('agents.TaskExecution.stop')}</button>}<button type="button" disabled={loading} onClick={()=>void refresh()}>{t('agents.TaskExecution.refresh')}</button></div>
        <p className="task-execution-hint">{t('agents.TaskExecution.stopScope')}</p>
        <details><summary>{t('agents.TaskExecution.evidence')}</summary><pre>{json(record)}</pre></details>
      </>}
      <details id={`${uid}-agents`} tabIndex={-1}><summary>{t('agents.TaskExecution.agentsContext')}</summary><p>{t('agents.TaskExecution.noExtraRights')}</p><pre>{json({project:context,agents:compatible.map(a=>({id:a.id,name:a.config.name,provider_id:a.config.provider_id,model_id:a.config.model_id}))})}</pre></details>
      {!loading&&!preparing&&!dispatching&&(error||record?.status==='FAILED_NO_EFFECT')&&<button type="button" onClick={()=>{if(recordRef.current?.status==='FAILED_NO_EFFECT'){prepareIds.current.clear();invalidate(()=>setRetry(value=>value+1));return}if(recordRef.current){void refresh();return}prepareKey.current='';setUnknown(false);setRetry(value=>value+1)}}>{t('agents.TaskExecution.retry')}</button>}
    </div>}
  </section>
}
