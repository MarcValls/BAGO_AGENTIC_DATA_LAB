import {vi} from 'vitest'
export const reply=(body:unknown,status=200)=>({ok:status<400,status,json:async()=>body})
export const metadata=(root:string)=>({workspace_root:root,cognition:{profile:'fixture',capacity:6,max_hops:2,max_expansions:4},paths:[],memory:{kind:'conversation_history',state:'present',description:'fixture'}})
export const workspace=(root='D:/selected-project',name='selected-project',title='PROJECT FIXTURE')=>({id:'workspace_fixture',root,name,title,context_files:[]})
export function planFor(input:any,index=1){return {...input,name:input.name||'selected-project',title:input.title||'PROJECT FIXTURE',plan_id:'folder_plan_'+index,plan_sha256:String(index%10).repeat(64),target_root:input.mode==='existing'?input.path:input.path.replace(/[\\/]+$/,'')+'/'+input.name,files:[{path:'.bago/context/PROJECT_CONTEXT.md',action:'preserve'},{path:'.bago/state/PROJECT_STATE.json',action:'create'},{path:'.bago/runtime/ACTIVE_HANDOFF.md',action:'create'},{path:'.workspace-service/manifest.json',action:'create'}],directories:[{path:'.',action:input.mode==='create_child'?'create':'preserve'}],expires_at:'2099-10-25T12:00:00Z'}}
export function receiptFor(plan:any,overrides:Record<string,unknown>={}){return {receipt_id:'receipt_fixture',plan_id:plan.plan_id,plan_sha256:plan.plan_sha256,status:'APPLIED',target_root:plan.target_root,created_files:plan.files.filter((f:any)=>f.action==='create').map((f:any)=>f.path),created_directories:plan.directories.filter((f:any)=>f.action==='create').map((f:any)=>f.path),registry_applied:true,binding_applied:true,actual_workspace_root:plan.target_root,error_code:null,...overrides}}
export type FolderCall={url:string;method:string;body:any}
export function folderFixture(options:{root?:string;workspaces?:any[];browse?:{path:string|null;cancelled:boolean};route?:(url:string,body:any,index:number)=>unknown;plan?:(normal:any)=>any;actions?:(body:any)=>unknown}={}){
 let root=options.root??'D:/selected-project',list=options.workspaces??[],count=0
 const calls:FolderCall[]=[],plans=new Map<string,any>()
 const fetcher=vi.fn(async(url:string,init?:RequestInit)=>{
  const method=init?.method??'GET',body=init?.body?JSON.parse(String(init.body)):null;calls.push({url,method,body})
  const overridden=options.route?.(url,body,calls.length-1);if(overridden!==undefined)return await overridden
  if(url==='/api/chat/context')return reply(metadata(root))
  if(url==='/api/project-folders/v1/config')return reply({workspace_root:root,scope:'global_workspace'})
  if(url==='/api/project-folders/v1/workspaces')return reply({workspaces:list})
  if(url==='/api/project-folders/v1/browse')return reply(options.browse??{path:'E:/chosen-folder',cancelled:false})
  if(url==='/api/project-folders/v1/plans'){count++;const normal=planFor(body,count),plan=options.plan?.(normal)??normal;plans.set(plan.plan_id,plan);return reply(plan)}
  const match=url.match(/^\/api\/project-folders\/v1\/plans\/([^/]+)\/apply$/)
  if(match){const plan=plans.get(decodeURIComponent(match[1]));if(!plan||body?.confirmed!==true||body.plan_sha256!==plan.plan_sha256)return reply({error:{code:'BAD_CONFIRMATION',message:'fixture refusal'}},409);root=plan.target_root;const selected=workspace(root,plan.name,plan.title);list=[...list.filter(w=>w.id!==selected.id),selected];return reply({workspace_root:root,workspace:selected,receipt:receiptFor(plan)})}
  if(url.startsWith('/api/project-folders/v1/workspaces/')&&url.endsWith('/actions')){if(options.actions)return reply(options.actions(body));return reply(body.operation==='list_files'?{files:[],excluded:[]}:body.operation==='trash_list'?{items:[]}:body.operation==='git_init'?{head:null,branch:'main',status:[],conflicts:[]}:{})}
  return reply({error:{code:'UNEXPECTED_ROUTE',message:'Unexpected fixture route'}},404)
 })
 vi.stubGlobal('fetch',fetcher)
 return {calls,fetcher,getRoot:()=>root,setRoot:(next:string)=>{root=next},mutations:()=>calls.filter(c=>c.method!=='GET')}
}
