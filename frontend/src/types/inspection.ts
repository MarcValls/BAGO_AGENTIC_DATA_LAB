export type InspectionSelection = {conversationId: string; revision?: number; traceId?: string; executionId?: string}
export type InspectionEvent = {event_id: string; trace_id: string; sequence: number; name: string; kind: string; status: string; parent_event_id?: string | null; attributes: Record<string, unknown>; evidence_refs: string[];start_time_unix_nano?:number;end_time_unix_nano?:number}
export type ConversationInspection = {schema: 'bago.chat.inspection.v1'; conversation_id: string; revision: number; state: 'no_artifacts' | 'selection_required' | 'selected'; total: number; offset: number; next_offset: number | null; executions: Array<{trace_id: string; execution_id: string | null; message_id: string}>; selected: null | {trace_id: string; execution_id: string | null; message_id: string; state: 'available' | 'unavailable' | 'invalid'; reason?: string; integrity: string; sha256: string | null; limitations: string[]; trace: null | {trace_id: string; run_id: string; events: InspectionEvent[];event_count:number;cost_usd:number;evidence_refs:string[]}}}
const record=(value:unknown):value is Record<string,unknown>=>value!==null&&typeof value==='object'&&!Array.isArray(value)
const text=(value:unknown):value is string=>typeof value==='string'&&Boolean(value.trim())
const strings=(value:unknown):value is string[]=>Array.isArray(value)&&value.every(item=>typeof item==='string')
const integer=(value:unknown):value is number=>typeof value==='number'&&Number.isSafeInteger(value)&&value>=0
const traceId=(value:unknown):value is string=>typeof value==='string'&&/^trace-[a-f0-9]{16}$/.test(value)
const runId=(value:unknown):value is string=>typeof value==='string'&&/^[A-Za-z0-9][A-Za-z0-9_.-]{0,127}$/.test(value)
const hash=(value:unknown)=>typeof value==='string'&&/^[a-f0-9]{64}$/.test(value)
function eventShape(value:unknown,tid:string):value is InspectionEvent {
 if(!record(value)||!text(value.event_id)||value.trace_id!==tid||!integer(value.sequence)||!text(value.name)||!text(value.status)||typeof value.kind!=='string'||!['workflow','retrieval','reasoning','authorization','tool','execution','receipt','sandbox'].includes(value.kind)||!record(value.attributes)||!strings(value.evidence_refs))return false
 if(value.parent_event_id!==null&&value.parent_event_id!==undefined&&!text(value.parent_event_id))return false
 const start=value.start_time_unix_nano,end=value.end_time_unix_nano
 if(start!==undefined||end!==undefined){if(typeof start!=='number'||typeof end!=='number'||!Number.isFinite(start)||!Number.isInteger(start)||start<0||!Number.isFinite(end)||!Number.isInteger(end)||end<start)return false}
 return true
}
/** Validate every field consumed by React; malformed/foreign payloads stay unavailable. */
export function isConversationInspection(value:unknown,selection:InspectionSelection):value is ConversationInspection {
 if(!record(value)||value.schema!=='bago.chat.inspection.v1'||value.conversation_id!==selection.conversationId||!integer(value.revision)||!integer(value.total)||!integer(value.offset)||!Array.isArray(value.executions)||value.executions.length>50||value.executions.length>value.total||!['no_artifacts','selection_required','selected'].includes(String(value.state)))return false
 if(value.next_offset!==null&&(!integer(value.next_offset)||value.next_offset<=value.offset||value.next_offset>value.total))return false
 const ids=new Set<string>()
 for(const item of value.executions){if(!record(item)||!traceId(item.trace_id)||ids.has(item.trace_id)||!text(item.message_id)||(item.execution_id!==null&&!runId(item.execution_id)))return false;ids.add(item.trace_id)}
 if(value.selected===null)return value.state!=='selected'&&(value.state!=='no_artifacts'||value.total===0)
 if(value.state!=='selected'||!record(value.selected))return false
 const selected=value.selected
 if(!traceId(selected.trace_id)||!text(selected.message_id)||(selected.execution_id!==null&&!runId(selected.execution_id))||!strings(selected.limitations)||(selected.reason!==undefined&&!text(selected.reason))||!['available','unavailable','invalid'].includes(String(selected.state)))return false
 if(selection.traceId&&selected.trace_id!==selection.traceId)return false
 if(selection.executionId&&selected.execution_id!==selection.executionId)return false
 if(selected.state!=='available')return selected.trace===null&&selected.sha256===null&&selected.integrity==='not_available'
 if(!hash(selected.sha256)||!['hash_verified','legacy_unverified'].includes(String(selected.integrity))||!record(selected.trace))return false
 const trace=selected.trace
 if(trace.trace_id!==selected.trace_id||!runId(trace.run_id)||trace.run_id!==selected.execution_id||!Array.isArray(trace.events)||!integer(trace.event_count)||trace.event_count!==trace.events.length||typeof trace.cost_usd!=='number'||!Number.isFinite(trace.cost_usd)||trace.cost_usd<0||!strings(trace.evidence_refs))return false
 const events:InspectionEvent[]=[];const eventIds=new Map<string,number>();const sequences=new Set<number>()
 for(const item of trace.events){if(!eventShape(item,selected.trace_id)||eventIds.has(item.event_id)||sequences.has(item.sequence))return false;events.push(item);eventIds.set(item.event_id,item.sequence);sequences.add(item.sequence)}
 for(const item of events){if(item.parent_event_id&&(eventIds.get(item.parent_event_id)===undefined||eventIds.get(item.parent_event_id)!>=item.sequence))return false}
 return true
}
