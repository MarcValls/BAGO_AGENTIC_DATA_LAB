"""Scoped child chat turns and reviewed legacy dispatch. No job runner, inherited grants, shell or sends."""
from __future__ import annotations

import asyncio
import hashlib
import json
import os
from pathlib import Path
import re
import threading
import time
import uuid

from src.services.agent_producers import write
from src.conversations import ConversationNotFound

_LOCK=threading.RLock()
_LIVE=set()


def claim_lock(path):
    stream=Path(path).open('r+b');stream.seek(0)
    try:
        if os.name=='nt':
            import msvcrt
            msvcrt.locking(stream.fileno(),msvcrt.LK_NBLCK,1)
        else:
            import fcntl
            fcntl.flock(stream.fileno(),fcntl.LOCK_EX|fcntl.LOCK_NB)
    except OSError:stream.close();raise
    return stream


def claim_active(path):
    try:stream=claim_lock(path)
    except OSError:return True # Cannot prove the owner stopped.
    stream.close();return False


def digest(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=False,default=str).encode()).hexdigest()


class DelegationError(ValueError):
    def __init__(self,code,status=409):self.code=code;self.status=status;super().__init__(code)


class AgentDelegations:
    def __init__(self,*,directory,workspace,conversations,load_agent,resolve_model,execute_turn,
                 authorize_tools,record_trace,trace_root,clock=time.time):
        self.directory=Path(directory);self.workspace=Path(workspace).resolve();self.conversations=conversations
        self.load_agent=load_agent;self.resolve_model=resolve_model;self.execute_turn=execute_turn
        self.authorize_tools=authorize_tools;self.record_trace=record_trace;self.trace_root=Path(trace_root);self.clock=clock

    def _path(self,proposal_id):
        if not isinstance(proposal_id,str) or not re.fullmatch(r'delegation_[0-9a-f]{32}',proposal_id):raise DelegationError('delegation_not_found',404)
        return self.directory/'records'/(proposal_id+'.json')

    def _save(self,record,*,new=False):
        value={k:v for k,v in record.items() if k!='record_sha256'};value['record_sha256']=digest(value)
        write(self._path(record['binding']['proposal_id']),value,new=new)

    def _load(self,proposal_id):
        try:record=json.loads(self._path(proposal_id).read_text(encoding='utf8'))
        except FileNotFoundError:raise DelegationError('delegation_not_found',404) from None
        except (OSError,ValueError):raise DelegationError('delegation_record_changed') from None
        if digest({k:v for k,v in record.items() if k!='record_sha256'})!=record.get('record_sha256'):raise DelegationError('delegation_record_changed')
        if digest(record['binding'])!=record['proposal_sha256']:raise DelegationError('delegation_binding_changed')
        return record

    def _parent(self,conversation_id):
        try:parent=self.conversations.get(conversation_id)
        except ConversationNotFound:raise DelegationError('delegation_parent_not_found',404) from None
        if parent['owner_kind']!='assistant' or parent['owner_id']!='app-assistant':raise DelegationError('delegation_parent_not_found',404)
        return parent

    def public(self,record):
        p={k:v for k,v in record['binding'].items() if k!='workspace'}
        p.update(proposal_sha256=record['proposal_sha256'],state=record['state'])
        for key in ('child_conversation_id','child_revision','child_trace_id','child_trace_sha256','child_trace_state',
                    'receipt_id','receipt_sha256','error_code','assistant_message'):
            p[key]=record.get(key)
        p.update(tools_executed=bool(record.get('tools_executed')),target_written=bool(record.get('target_written')))
        if record.get('orchestration_status'):
            p['orchestration_status']=record['orchestration_status']
        return p

    def propose(self,*,agent_id,task,parent_conversation_id,parent_revision,parent_message_id,parent_trace_id):
        if not isinstance(task,str) or not 1<=len(task.strip())<=8000:raise DelegationError('delegation_task_invalid',422)
        parent=self._parent(parent_conversation_id)
        if parent['status']!='active' or parent_revision!=parent['revision']+1:raise DelegationError('delegation_parent_changed')
        agent=self.load_agent(agent_id);provider,model=self.resolve_model(agent)
        binding={'schema':'agent-delegation.v1','proposal_id':'delegation_'+uuid.uuid4().hex,
            'parent_conversation_id':parent_conversation_id,'parent_revision':parent_revision,
            'parent_message_id':parent_message_id,'parent_trace_id':parent_trace_id,
            'agent_id':agent.id,'agent_name':agent.config.name,'agent_config_sha256':digest(agent.config.model_dump()),
            'provider_id':provider,'model_id':model,'assigned_tools':list(agent.config.tools),
            'task':task.strip(),'task_sha256':hashlib.sha256(task.strip().encode()).hexdigest(),
            'expires_at':self.clock()+900,'workspace':str(self.workspace)}
        record={'binding':binding,'proposal_sha256':digest(binding),'state':'PROPOSED'}
        with _LOCK:self._save(record,new=True)
        return self.public(record)

    def get(self,proposal_id,*,parent_conversation_id):
        with _LOCK:
            record=self._load(proposal_id);self._parent(parent_conversation_id)
            if record['binding']['parent_conversation_id']!=parent_conversation_id:raise DelegationError('delegation_parent_not_found',404)
            if record['binding']['workspace']!=str(self.workspace):raise DelegationError('delegation_workspace_changed')
            key=str(self._path(proposal_id).resolve())
            claim=self.directory/'claims'/(proposal_id+'.json')
            if record['state']=='RUNNING' and claim.exists() and not claim_active(claim):
                record.update(state='INCONCLUSIVE',error_code='delegation_interrupted_no_automatic_retry')
                self._save(record)
            elif record['state']=='PROPOSED' and claim.exists():
                # Do not rewrite a remote owner's pre-dispatch state during its claim setup.
                active=claim_active(claim)
                record.update(state='RUNNING' if active else 'INCONCLUSIVE',error_code=None if active else 'delegation_claimed_no_automatic_retry')
            elif record['state']=='PROPOSED' and record['binding']['expires_at']<=self.clock():
                record.update(state='EXPIRED',error_code='delegation_expired');self._save(record)
            if record.get('receipt_id'):
                receipt_path=self.directory/'receipts'/(record['receipt_id']+'.json')
                try:raw=receipt_path.read_bytes()
                except OSError:raise DelegationError('delegation_receipt_unavailable') from None
                if hashlib.sha256(raw).hexdigest()!=record.get('receipt_sha256'):raise DelegationError('delegation_receipt_changed')
                receipt=json.loads(raw)
                if receipt['proposal_sha256']!=record['proposal_sha256'] or receipt['binding']!=record['binding']:raise DelegationError('delegation_receipt_identity_changed')
                if record.get('child_trace_id'):self._verify_trace(record,record['child_trace_id'],record['child_trace_sha256'],receipt.get('child_execution_id'))
            return record

    def _verify_trace(self,record,trace_id,trace_sha256,execution_id=None):
        if not re.fullmatch(r'trace-[0-9a-f]{16}',trace_id):raise DelegationError('delegation_child_trace_invalid')
        path=self.trace_root/(trace_id+'.json')
        try:raw=path.read_bytes()
        except OSError:raise DelegationError('delegation_child_trace_unverified') from None
        if not trace_sha256 or hashlib.sha256(raw).hexdigest()!=trace_sha256:raise DelegationError('delegation_child_trace_unverified')
        trace=json.loads(raw);events=trace.get('events') or [];attributes=(events[0] if events else {}).get('attributes',{})
        expected={'agent_id':record['binding']['agent_id'],'conversation_id':record['child_conversation_id'],
            'provider_id':record['binding']['provider_id'],'model_id':record['binding']['model_id'],'delegation_id':record['binding']['proposal_id']}
        if trace.get('trace_id')!=trace_id or (execution_id and trace.get('run_id')!=execution_id) or any(attributes.get(k)!=v for k,v in expected.items()):raise DelegationError('delegation_child_trace_identity_changed')
        return trace['run_id']

    def _response(self,record):
        child=None
        if record.get('child_conversation_id'):
            child=self.conversations.get(record['child_conversation_id'])
        return {'agent_delegation':self.public(record),'conversation':self._parent(record['binding']['parent_conversation_id']),
                'child_conversation':child,'assistant_message':record.get('parent_answer','La delegación requiere revisión.')}

    def _observe_child(self,record,result=None,*,trace_override=None):
        child=self.conversations.get(record['child_conversation_id'])
        if child['owner_kind']!='agent' or child['owner_id']!=record['binding']['agent_id']:raise DelegationError('delegation_child_identity_changed')
        record['child_revision']=child['revision']
        last=next((m for m in reversed(child['messages']) if m['role']=='assistant'),None)
        references=(last or {}).get('references',{})
        trace=trace_override if trace_override is not None else ((result or {}).get('trace') or references.get('trace') or {})
        if trace_override is not None and (not isinstance(trace_override,dict) or not trace_override.get('trace_id') or not trace_override.get('trace_sha256') or not trace_override.get('execution_id')):
            raise DelegationError('delegation_child_trace_unverified')
        record.update(child_trace_id=trace.get('trace_id'),child_trace_sha256=trace.get('trace_sha256'),child_trace_state=trace.get('trace_state'))
        if record['child_trace_id']:
            record['child_execution_id']=self._verify_trace(record,record['child_trace_id'],record['child_trace_sha256'],trace.get('execution_id'))
            record['model_invoked']=True
        events=(result or {}).get('read_events') or references.get('read_events') or []
        record['tool_receipts']=events
        record['tools_executed']=any(e.get('executed') is True and e.get('decision')=='ALLOW' for e in events)
        record['target_written']=False
        for event in events:
            output=event.get('output') or {}
            if event.get('tool_name')=='document_export' and event.get('executed') and event.get('decision')=='ALLOW' and output.get('path') and output.get('sha256'):
                path=Path(output['path'])
                if path.is_file() and hashlib.sha256(path.read_bytes()).hexdigest()==output['sha256']:record['target_written']=True
        if result is not None:
            if result.get('agent_id')!=record['binding']['agent_id'] or result.get('conversation_id')!=child['id'] or not last or last.get('content')!=result.get('assistant_message'):
                raise DelegationError('delegation_child_result_mismatch')
            if not record.get('child_trace_sha256'):raise DelegationError('delegation_child_trace_missing')
            record['assistant_message']=result['assistant_message']
            status=result.get('orchestration_status')
            if status in {'OUT_OF_SCOPE','NEEDS_AUTHORIZATION','NEEDS_REVIEW'}:
                record['orchestration_status']=status

    def _finish(self,record,state,error_code=None):
        record.update(state=state,error_code=error_code,finished_at=self.clock())
        answers={'PASSED':f"{record['binding']['agent_name']} completó la tarea dentro de su alcance. Revisa la respuesta y sus evidencias.",
            'OUT_OF_SCOPE':f"{record['binding']['agent_name']} devolvió la tarea por estar fuera de su alcance.",
            'NEEDS_AUTHORIZATION':f"{record['binding']['agent_name']} necesita una autorización adicional. No se ha ampliado ningún permiso.",
            'NEEDS_REVIEW':'No pude comprobar que el resultado cumpla el alcance. No lo doy por completado; requiere revisión.'}
        record['parent_answer']=answers.get(state,'La delegación no está verificada como completada. Revisa el estado y la conversación del agente; no se reintentará automáticamente.')
        receipt_id='delegation-receipt_'+uuid.uuid4().hex
        receipt={'schema':'agent-delegation-receipt.v1','receipt_id':receipt_id,'state':state,'error_code':error_code,
            'proposal_sha256':record['proposal_sha256'],'binding':record['binding'],'human_scope':record.get('human_scope'),
            'started_at':record.get('started_at'),'finished_at':record['finished_at'],'model_invoked':record.get('model_invoked',False),
            'child_conversation_id':record.get('child_conversation_id'),'child_revision':record.get('child_revision'),
            'child_trace_id':record.get('child_trace_id'),'child_trace_sha256':record.get('child_trace_sha256'),
            'child_execution_id':record.get('child_execution_id'),
            'tool_receipts':record.get('tool_receipts',[]),'tools_executed':record.get('tools_executed',False),
            'target_written':record.get('target_written',False),'business_acceptance':'NOT_IMPLIED'}
        receipt_path=self.directory/'receipts'/(receipt_id+'.json');write(receipt_path,receipt)
        record.update(receipt_id=receipt_id,receipt_sha256=hashlib.sha256(receipt_path.read_bytes()).hexdigest())
        trace=self.record_trace(record)
        self.conversations.append_message(record['binding']['parent_conversation_id'],record['parent_running_revision'],
            'assistant',record['parent_answer'],{'agent_delegation':self.public(record),'trace':trace})
        self._save(record) # Publish terminal state only after parent/receipt persistence.

    async def execute(self,proposal_id,*,parent_conversation_id,parent_revision,proposal_sha256,confirm,scope):
        key=str(self._path(proposal_id).resolve())
        with _LOCK:
            record=self.get(proposal_id,parent_conversation_id=parent_conversation_id)
            # A replay is status-only, even if a caller changes its scope or revision.
            if record['state']!='PROPOSED':return self._response(record)
            binding=record['binding'];parent=self._parent(parent_conversation_id)
            if confirm is not True:raise DelegationError('delegation_confirmation_required',422)
            if proposal_sha256!=record['proposal_sha256'] or parent_revision!=binding['parent_revision'] or parent['revision']!=parent_revision or parent['status']!='active':raise DelegationError('delegation_parent_or_proposal_changed')
            agent=self.load_agent(binding['agent_id'])
            if digest(agent.config.model_dump())!=binding['agent_config_sha256'] or tuple(self.resolve_model(agent))!=(binding['provider_id'],binding['model_id']):raise DelegationError('delegation_agent_changed')
            claim_path=self.directory/'claims'/(proposal_id+'.json')
            try:write(claim_path,{'proposal_sha256':record['proposal_sha256'],'human_scope':scope},new=True)
            except FileExistsError:return self._response(self.get(proposal_id,parent_conversation_id=parent_conversation_id))
            except OSError:raise DelegationError('delegation_claim_persistence_failed',503) from None
            # Exclusive creation is the permanent at-most-once fence across processes/restarts.
            lease=claim_lock(claim_path)
            record.update(state='RUNNING',human_scope=scope,started_at=self.clock(),model_invoked=False,parent_running_revision=parent_revision)
            try:
                child=self.conversations.create('agent',agent.id,'Delegación: '+agent.config.name)
                record.update(child_conversation_id=child['id'],child_revision=0)
                grant=self.authorize_tools(agent,child,scope)
            except Exception:
                try:self._finish(record,'FAILED','delegation_scope_or_child_rejected')
                finally:lease.close()
                raise DelegationError('delegation_scope_or_child_rejected',422) from None
            # Both durable snapshots must exist before any provider call.
            try:
                write(self.directory/'started'/(proposal_id+'.json'),record,new=True)
                self._save(record)
                running=self.conversations.append_message(parent_conversation_id,parent_revision,'assistant',
                    'Delegación autorizada; el agente está trabajando.',{'agent_delegation':self.public(record)})
                record['parent_running_revision']=running['revision'];self._save(record)
            except Exception:
                record.update(state='FAILED',error_code='delegation_pre_dispatch_persistence_failed')
                try:self._save(record)
                finally:lease.close()
                raise DelegationError('delegation_pre_dispatch_persistence_failed',503) from None
            _LIVE.add(key)
        try:
            record['dispatch_attempted']=True
            record['model_invoked']=None # A dispatched coroutine is not proof of provider inference.
            result=await self.execute_turn(binding,child,grant)
            self._observe_child(record,result)
            outcome=record.get('orchestration_status')
            self._finish(record,{'OUT_OF_SCOPE':'OUT_OF_SCOPE','NEEDS_AUTHORIZATION':'NEEDS_AUTHORIZATION','NEEDS_REVIEW':'NEEDS_REVIEW'}.get(outcome,'PASSED'))
        except (asyncio.CancelledError,TimeoutError) as error:
            try:
                self._observe_child(record)
                self._finish(record,'INCONCLUSIVE','delegation_cancelled_provider_may_still_run' if isinstance(error,asyncio.CancelledError) else 'delegation_timeout_provider_may_still_run')
            finally:_LIVE.discard(key)
            if isinstance(error,asyncio.CancelledError):raise
        except Exception as error:
            code=getattr(error,'code',None)
            detail=getattr(error,'detail',None)
            if not code and isinstance(detail,dict):code=detail.get('code')
            failure_trace=detail.get('trace') if isinstance(detail,dict) else None
            try:
                self._observe_child(record,trace_override=failure_trace if isinstance(failure_trace,dict) else None)
                self._finish(record,'FAILED',code or 'delegation_child_failed')
            except Exception:
                record.update(state='INCONCLUSIVE',error_code='delegation_result_persistence_uncertain')
                try:self._save(record)
                except Exception:pass # RUNNING remains durable: recovery must never redispatch.
        finally:_LIVE.discard(key);lease.close()
        return self._response(record)
