"""Read-only conversation-scoped LocalTrace inspection. No demo or model fallback."""
import math
import hashlib
import json
from pathlib import Path
import re
import stat

TRACE_ID = re.compile(r'trace-[a-f0-9]{16}\Z')
EXECUTION_ID = re.compile(r'[A-Za-z0-9][A-Za-z0-9_.-]{0,127}\Z')

class InspectionError(ValueError):
    def __init__(self, code, status=422):
        self.code, self.status = code, status
        super().__init__(code)

def _object(pairs):
    result={}
    for key,value in pairs:
        if key in result:raise InspectionError('duplicate_json_field')
        result[key]=value
    return result

def _constant(value):
    raise InspectionError('invalid_json_number')

def _text(value):
    return isinstance(value,str) and bool(value.strip())

def _string_list(value):
    return isinstance(value,list) and all(isinstance(item,str) for item in value)

def _event_shape(event):
    if not isinstance(event,dict):return False
    if not all(_text(event.get(key)) for key in ('event_id','trace_id','name','status')):return False
    if event.get('kind') not in {'workflow','retrieval','reasoning','authorization','tool','execution','receipt','sandbox'}:return False
    if type(event.get('sequence')) is not int or event['sequence']<0:return False
    if not isinstance(event.get('attributes'),dict) or not _string_list(event.get('evidence_refs')):return False
    if event.get('parent_event_id') is not None and not _text(event['parent_event_id']):return False
    start,end=event.get('start_time_unix_nano'),event.get('end_time_unix_nano')
    if start is not None or end is not None:
        if type(start) is not int or type(end) is not int or start<0 or end<start:return False
    return True

def _linked(path):
    info=path.lstat()
    return stat.S_ISLNK(info.st_mode) or bool(getattr(info,'st_file_attributes',0)&1024)

def _read_trace(trace_id, roots):
    found=[]
    for root in roots:
        root=Path(root)
        target=root/(trace_id+'.json')
        if not target.exists() and not target.is_symlink():
            continue
        if _linked(root) or _linked(target) or not target.resolve().is_relative_to(root.resolve()):
            raise InspectionError('linked_trace')
        before=target.stat()
        if not stat.S_ISREG(before.st_mode) or before.st_nlink != 1 or before.st_size>2*1024*1024:
            raise InspectionError('invalid_trace_file')
        raw=target.read_bytes();after=target.stat()
        if (before.st_ino,before.st_size,before.st_mtime_ns)!=(after.st_ino,after.st_size,after.st_mtime_ns):
            raise InspectionError('trace_changed_during_read')
        found.append((raw,hashlib.sha256(raw).hexdigest()))
    if len(found)>1:
        raise InspectionError('ambiguous_trace_file')
    return found[0] if found else None

def inspection(conversation, roots, *, trace_id=None, execution_id=None, offset=0, limit=20):
    if trace_id is not None and not TRACE_ID.fullmatch(trace_id):
        raise InspectionError('invalid_trace_id')
    if execution_id is not None and not EXECUTION_ID.fullmatch(execution_id):
        raise InspectionError('invalid_execution_id')
    if offset<0 or not 1<=limit<=50:
        raise InspectionError('invalid_page')
    if not isinstance(conversation,dict) or not _text(conversation.get('id')) or type(conversation.get('revision')) is not int or conversation['revision']<0 or not isinstance(conversation.get('messages'),list):raise InspectionError('invalid_conversation_metadata')
    refs=[];seen=set();duplicates=set()
    for message in conversation.get('messages',[]):
        if not isinstance(message,dict) or not _text(message.get('id')):raise InspectionError('invalid_message_metadata')
        if message.get('role')!='assistant':continue
        references=message.get('references',{})
        if not isinstance(references,dict):raise InspectionError('invalid_trace_reference')
        ref=references.get('trace')
        if ref is None:continue
        if not isinstance(ref,dict) or not isinstance(ref.get('trace_id'),str) or not TRACE_ID.fullmatch(ref['trace_id']):raise InspectionError('invalid_trace_reference')
        if ref.get('execution_id') is not None and (not isinstance(ref['execution_id'],str) or not EXECUTION_ID.fullmatch(ref['execution_id'])):raise InspectionError('invalid_execution_reference')
        if ref.get('trace_state') is not None and not _text(ref['trace_state']):raise InspectionError('invalid_trace_state')
        tid=ref['trace_id']
        if tid in seen:duplicates.add(tid);continue
        seen.add(tid);refs.append({'trace_id':tid,'message_id':message['id'],'execution_id':ref.get('execution_id') if isinstance(ref.get('execution_id'),str) else None,'reference':ref})
    # Conversation messages are persisted in sequence order. The default is
    # the newest referenced execution, even if its evidence is unavailable:
    # never silently replace an invalid current run with an older success.
    refs.reverse()
    envelope={'schema':'bago.chat.inspection.v1','conversation_id':conversation['id'],'revision':conversation['revision'],'state':'no_artifacts' if not refs else 'selection_required','executions':[{k:v for k,v in item.items() if k!='reference'} for item in refs[offset:offset+limit]],'total':len(refs),'offset':offset,'next_offset':offset+limit if offset+limit<len(refs) else None,'selected':None}
    choices=refs
    if trace_id is None and execution_id is None and choices:choices=choices[:1]
    if trace_id is not None:choices=[r for r in choices if r['trace_id']==trace_id]
    if execution_id is not None:choices=[r for r in choices if r['execution_id']==execution_id or (trace_id is not None and r['execution_id'] is None)]
    if (trace_id is not None or execution_id is not None) and not choices:
        raise InspectionError('execution_not_in_conversation',404)
    if len(choices)!=1:return envelope
    item=choices[0];ref=item['reference'];tid=item['trace_id']
    selected={k:v for k,v in item.items() if k!='reference'}
    selected.update(state='unavailable',trace=None,sha256=None,integrity='not_available',limitations=['No governed decision/evaluation/authorization bundle was produced by this chat trace.'])
    envelope.update(state='selected',selected=selected)
    try:
        if not TRACE_ID.fullmatch(tid) or tid in duplicates:raise InspectionError('ambiguous_or_invalid_trace_reference')
        found=_read_trace(tid,roots)
        if found is None:
            selected['reason']='trace_file_missing';return envelope
        raw,digest=found;expected=ref.get('trace_sha256')
        if expected is not None and (not isinstance(expected,str) or not re.fullmatch('[a-f0-9]{64}',expected) or expected!=digest):raise InspectionError('trace_hash_mismatch')
        data=json.loads(raw,object_pairs_hook=_object,parse_constant=_constant)
        if not isinstance(data,dict):raise InspectionError('invalid_trace_structure')
        run=data.get('run_id');events=data.get('events')
        cost=data.get('cost_usd')
        if type(data.get('event_count')) is not int or not _string_list(data.get('evidence_refs')) or type(cost) not in (int,float) or not math.isfinite(cost) or cost<0:raise InspectionError('invalid_trace_metadata')
        if data.get('trace_id')!=tid or not isinstance(run,str) or not EXECUTION_ID.fullmatch(run) or not isinstance(events,list) or data.get('event_count')!=len(events):raise InspectionError('trace_identity_mismatch')
        if (ref.get('execution_id') is not None and ref['execution_id']!=run) or (execution_id is not None and execution_id!=run):raise InspectionError('execution_identity_mismatch')
        ids=set();sequences=set()
        for event in events:
            if not _event_shape(event) or event.get('trace_id')!=tid or not isinstance(event.get('event_id'),str) or not event['event_id'] or event['event_id'] in ids or type(event.get('sequence')) is not int or event['sequence']<0 or event['sequence'] in sequences or not isinstance(event.get('status'),str):raise InspectionError('invalid_trace_events')
            ids.add(event['event_id']);sequences.add(event['sequence'])
        byid={e['event_id']:e for e in events}
        for event in events:
            parent=event.get('parent_event_id')
            if parent is not None and (not isinstance(parent,str) or parent not in byid or byid[parent]['sequence']>=event['sequence']):raise InspectionError('invalid_trace_parent')
        selected.update(state='available',trace=data,sha256=digest,execution_id=run,integrity='hash_verified' if expected else 'legacy_unverified')
        ordered=sorted(sequences)
        if ordered and any(index != sequence for index,sequence in enumerate(ordered)):selected['limitations'].append('Trace sequence has gaps; missing events are not reconstructed.')
        if not expected:selected['limitations'].append('Legacy reference has no persisted content hash: original byte integrity is unverified.')
        if ref.get('trace_state')=='local_trace_failed':raise InspectionError('persistence_failed_reference')
    except (InspectionError,OSError,ValueError,TypeError,AttributeError,RecursionError) as error:
        selected.update(state='invalid',trace=None,sha256=None,integrity='not_available',reason=error.code if isinstance(error,InspectionError) else 'trace_unreadable')
    return envelope
