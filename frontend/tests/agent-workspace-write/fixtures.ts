export const context={owner_kind:'agent' as const,owner_id:'agent-fixture',conversation_id:'conv-fixture',conversation_revision:7}
export const summary={proposal_id:'write_'+'a'.repeat(32),revision:'revision-one',workspace_id:'workspace_fixture',path:'results/report.md',mode:'create' as const,status:'PROPOSED' as const,context,proposed_sha256:'a'.repeat(64)}
export const review={...summary,before_sha256:null,proposed_text:'Texto original propuesto',before_text:'',diff:'--- before\n+++ proposed\n+Texto original propuesto',review_sha256:'b'.repeat(64),receipt:null,observation:null}
export const props={proposal:summary,ownerKind:'agent',ownerId:context.owner_id,conversationId:context.conversation_id,conversationRevision:9}
export const response=(body:unknown,status=200)=>({ok:status<400,status,json:async()=>body})
