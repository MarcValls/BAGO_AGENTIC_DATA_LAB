"""Human-reviewed filesystem and delivery adapters over existing standalone services."""
from pathlib import Path
import os
from datetime import datetime,timezone
import hashlib
import json
import secrets
import threading
import time
import uuid

from src.agent_tools.filesystem_tools import FS_TOOL_IDS,FilesystemSession,FilesystemToolkit
from src.services.agent_producers import ProducerStore,RELATIVE,write
from src.services.delivery_review import DeliveryReviewer

from src.development import TOOL_IDS as DEVELOPMENT_TOOL_IDS

DELIVERY_TOOL_IDS=frozenset({'delivery_review','delivery_revalidate','delivery_prepare_draft'})
SERVICE_TOOL_IDS=FS_TOOL_IDS|DELIVERY_TOOL_IDS|DEVELOPMENT_TOOL_IDS
_LOCK=threading.RLock()
_REVIEWS={}


def descriptors():
    return [{'id':name,'name':label,'name_en':english,'status':'AVAILABLE','assignable':True,'provider':'Local governed service',
             'effect':'DRAFT' if name=='delivery_prepare_draft' else 'READ_REVIEW',
             'summary':'Revisa evidencias del productor y prepara avisos o entregas para confirmación; nunca envía.',
             'limits':{'requires_user_opt_in':True,'send':False},'source_paths':['src/agent_tools/agent_services.py','src/services/delivery_review.py','src/services/agent_producers.py']}
            for name,label,english in [('delivery_review','Revisar entregas','Review deliveries'),('delivery_revalidate','Revalidar una revisión','Revalidate a review'),('delivery_prepare_draft','Preparar borrador de aviso o entrega','Prepare notification or delivery draft')]]


def _protected(path):
    if path is None or path=='.':return False
    if not isinstance(path,str):return True
    return any(p.startswith('.') or p.casefold() in {'node_modules','venv','__pycache__'} for p in path.replace('\\','/').split('/'))


class AgentServiceSession:
    def __init__(self,*,workspace,root,owner_id,conversation_id,communications,review_work_id=None,contact_id=None,allow_draft=False):
        self.workspace=Path(workspace).resolve();self.root=Path(root).resolve()
        self.owner_id=owner_id;self.conversation_id=conversation_id;self.communications=communications
        self.review_work_id=review_work_id;self.contact_id=contact_id;self.allow_draft=allow_draft
        self.state=self.workspace/'.bago/traces/agent-tools'
        self.producers=ProducerStore(self.workspace)
        self.source_binding=self.producers.summary(self.producers.load_registered(review_work_id)) if review_work_id else None
        self.contact_snapshot=next((c for c in communications.contacts() if c['id']==contact_id),None) if communications and contact_id else None

    def schemas(self,assigned):
        result=FilesystemSession().tool_schemas({'root':str(self.root),'tools':assigned})
        if set(assigned) & DEVELOPMENT_TOOL_IDS and os.environ.get('BAGO_DEVELOPMENT_PROFILE'):
            from src.development import DevelopmentService
            result.extend(DevelopmentService().schemas(assigned))
        for name in sorted(set(assigned)&DELIVERY_TOOL_IDS):
            if name=='delivery_prepare_draft' and not self.allow_draft:continue
            props={'work_id':{'type':'string'}} if name=='delivery_review' else {'review_id':{'type':'string'}}
            result.append({'type':'function','function':{'name':name,'description':
                'Review only the human-selected producer run and contact. Missing mandatory acceptance remains blocked. Draft creation never sends.',
                'parameters':{'type':'object','properties':props,'required':[] if name=='delivery_review' else ['review_id'],'additionalProperties':False}}})
        return result

    def _reviewer(self,assigned):
        capabilities=['delivery.review']
        if 'delivery_prepare_draft' in assigned and self.allow_draft:capabilities.append('delivery.draft')
        return DeliveryReviewer(self.workspace,self.state/'delivery-reviews',communications=self.communications,
            profile={'capabilities':capabilities,'output_scopes':[RELATIVE+'/*']},evidence_provider=self.producers.provider())

    def _bind_review(self,result):
        review=result.get('review',result)
        if 'review_id' in review:
            write(self.state/'review-bindings'/(review['review_id']+'.json'),{'owner_id':self.owner_id,'conversation_id':self.conversation_id,
                'work_id':self.review_work_id,'contact_id':self.contact_id,'record_sha256':review['record_sha256']})

    def _owned_review(self,review_id):
        if not isinstance(review_id,str) or not review_id.startswith('review_') or len(review_id)!=39 or not all(c in '0123456789abcdef' for c in review_id[7:]):raise ValueError('invalid review id')
        binding=json.loads((self.state/'review-bindings'/(review_id+'.json')).read_text(encoding='utf8'))
        if binding!={'owner_id':self.owner_id,'conversation_id':self.conversation_id,'work_id':self.review_work_id,'contact_id':self.contact_id,'record_sha256':binding['record_sha256']}:raise ValueError('review belongs to another owner, conversation, run or contact')
        saved=json.loads((self.state/'delivery-reviews'/(review_id+'.json')).read_text(encoding='utf8'))
        if saved.get('record_sha256')!=binding['record_sha256']:raise ValueError('review binding changed')

    def invoke(self,name,args,assigned):
        if name in DEVELOPMENT_TOOL_IDS:
            from src.development import DevelopmentService
            if name not in assigned or (name == 'development_review' and set(assigned) & {'development_prepare','development_check','development_revise'}):
                return {'ok':False,'error':'development_assignment_or_reviewer_separation_required'}, {'kind':'development_tool','tool_name':name,'decision':'DENY','executed':False}
            try:
                return DevelopmentService().invoke(name,args,owner_id=self.owner_id,conversation_id=self.conversation_id,root=self.root)
            except (OSError,ValueError,RuntimeError) as error:
                return {'ok':False,'error':getattr(error,'code','development_profile_unavailable')}, {'kind':'development_tool','tool_name':name,'decision':'DENY','executed':False}
        receipt={'kind':'filesystem_tool' if name in FS_TOOL_IDS else 'delivery_tool','tool_name':name,'decision':'DENY',
            'executed':False,'path':str(self.root),'receipt_id':'service_'+uuid.uuid4().hex,'send_executed':False}
        try:
            args=json.loads(args) if isinstance(args,str) else args
            if name not in assigned or name not in SERVICE_TOOL_IDS or not isinstance(args,dict):raise ValueError('tool not assigned or invalid arguments')
            if name in FS_TOOL_IDS:
                if any(_protected(args.get(key)) for key in ('path','source','target')):raise ValueError('internal paths are not available to agent tools')
                if isinstance(args.get('content'),str) and len(args['content'])>65536:raise ValueError('text exceeds UI review limit')
                if name=='filesystem_inventory':
                    if set(args)-{'path'}:raise ValueError('unexpected inventory arguments')
                    toolkit=FilesystemToolkit(self.root);folder=toolkit._path(args.get('path','.'),allow_dot=True)
                    if not folder.is_dir():raise ValueError('inventory requires a directory')
                    entries=[]
                    for item in sorted(folder.iterdir(),key=lambda p:p.name.casefold()):
                        relative=item.relative_to(self.root).as_posix()
                        if _protected(relative) or item.name=='trash':continue
                        if len(entries)>=1000:raise ValueError('inventory limit exceeded; choose a narrower folder')
                        toolkit._plain(item)
                        entries.append({'path':relative,'kind':'directory' if item.is_dir() else 'file','snapshot':None if item.is_dir() else toolkit._snapshot(item)})
                    result={'root':str(self.root),'entries':entries,'recursive':False,'excluded':'hidden/internal paths'}
                    native={'status':'VERIFIED'}
                else:result,native=FilesystemSession().invoke(name,args,{'root':str(self.root),'tools':assigned})
                if name=='filesystem_plan':
                    if any(_protected(result.get(key)) for key in ('source','target')):raise ValueError('resolved filesystem plan targets an internal path')
                    proposal='fsproposal_'+uuid.uuid4().hex
                    binding={'proposal_id':proposal,'owner_id':self.owner_id,'conversation_id':self.conversation_id,'root':str(self.root),
                        'plan_id':result['id'],'plan_sha256':result['sha256'],'status':'PROPOSED','expires_at':result['expires_at'],'plan':result}
                    write(self.state/'filesystem-proposals'/(proposal+'.json'),binding)
                    result={'proposal_id':proposal,'plan':result,'state':'PROPOSED','executed':False}
                    receipt['filesystem_proposal']={k:binding[k] for k in ('proposal_id','owner_id','conversation_id','plan_sha256','root','status')}
                receipt.update(executed=True,decision='ALLOW',outcome=native['status'])
            else:
                if not self.review_work_id:raise ValueError('select a producer run before reviewing')
                registered=self.producers.load_registered(self.review_work_id)
                if self.producers.summary(registered)!=self.source_binding:raise ValueError('delegated producer candidate changed')
                if self.contact_id and next((c for c in self.communications.contacts() if c['id']==self.contact_id),None)!=self.contact_snapshot:raise ValueError('selected recipient changed')
                reviewer=self._reviewer(assigned)
                if name=='delivery_review':
                    if set(args)-{'work_id'} or args.get('work_id',self.review_work_id)!=self.review_work_id:raise ValueError('producer run was not selected by the user')
                    request={k:registered[k] for k in ('work_id','mission_id','candidate_id','scope_sha256','artifacts')}
                    request.update(contact_id=self.contact_id,pending=registered.get('pending',[]),risks=registered.get('risks',[]),schedule={'kind':'now'})
                    result=reviewer.review(request)
                else:
                    if set(args)!={'review_id'}:raise ValueError('expected exact review id')
                    self._owned_review(args['review_id'])
                    if name=='delivery_prepare_draft' and not self.allow_draft:raise ValueError('draft consent required')
                    result=reviewer.prepare_draft(args['review_id']) if name=='delivery_prepare_draft' else reviewer.revalidate(args['review_id'])
                self._bind_review(result)
                current=result.get('review',result)
                receipt.update(executed=True,decision='ALLOW',outcome=current['decision'],delivery_review={k:current[k] for k in ('review_id','decision','errors','missing','pending','authorization','send_executed')})
                if result.get('draft'):receipt['communication_draft_id']=result['draft']['id']
            receipt['result_sha256']=hashlib.sha256(json.dumps(result,sort_keys=True).encode()).hexdigest()
            path=self.state/'calls'/(receipt['receipt_id']+'.json');write(path,{'receipt':receipt,'result':result})
            receipt.update(evidence_path=str(path),evidence_sha256=hashlib.sha256(path.read_bytes()).hexdigest())
            return result,receipt
        except (ValueError,OSError,TypeError,KeyError) as error:
            receipt.update(decision='FAIL' if receipt['executed'] else 'DENY',reason_code='AGENT_SERVICE_REJECTED',reason=str(error))
            return {'state':'FAILED','error':str(error),'send_executed':False},receipt


def _proposal_path(workspace,proposal_id):
    if not isinstance(proposal_id,str) or not proposal_id.startswith('fsproposal_') or len(proposal_id)!=43 or not all(c in '0123456789abcdef' for c in proposal_id[11:]):raise ValueError('invalid proposal id')
    return Path(workspace).resolve()/'.bago/traces/agent-tools/filesystem-proposals'/(proposal_id+'.json')


def review_filesystem(*,workspace,proposal_id,owner_id,conversation_id,revision):
    with _LOCK:
        path=_proposal_path(workspace,proposal_id);saved=json.loads(path.read_text(encoding='utf8'))
        if saved['owner_id']!=owner_id or saved['conversation_id']!=conversation_id:raise ValueError('foreign filesystem proposal')
        if time.time()>=saved['expires_at']:raise ValueError('filesystem plan expired')
        from src.agent_tools.document_tools import checked_directory
        root=checked_directory(saved['root'],workspace)
        actual=FilesystemToolkit(root)._load('plans',saved['plan_id'])
        if actual!=saved['plan'] or actual['sha256']!=saved['plan_sha256']:raise ValueError('filesystem plan changed')
        toolkit=FilesystemToolkit(root)
        final=toolkit.state/'receipts'/(saved['plan_id']+'.json')
        pending=toolkit.state/'receipts'/(saved['plan_id']+'.pending.json')
        if final.exists():
            observed=json.loads(final.read_text(encoding='utf8'))
            from src.agent_tools.filesystem_tools import _MODULE
            if observed.get('plan_sha256')!=saved['plan_sha256'] or _MODULE.digest({k:v for k,v in observed.items() if k!='sha256'})!=observed.get('sha256'):raise ValueError('filesystem receipt changed')
            saved.update(status=observed['status'],receipt=observed)
        elif pending.exists():saved['status']='UNCERTAIN'
        token=None
        if saved['status']=='PROPOSED':
            token=secrets.token_urlsafe(32)
            _REVIEWS[token]={'workspace':str(Path(workspace).resolve()),'proposal_id':proposal_id,'owner_id':owner_id,
                'conversation_id':conversation_id,'revision':revision,'plan_sha256':saved['plan_sha256'],'expires_at':time.time()+300}
        return {**saved,'review_token':token,'conversation_revision':revision}


def execute_filesystem(*,workspace,proposal_id,owner_id,conversation_id,revision,review_token,plan_sha256,confirmed):
    with _LOCK:
        token=_REVIEWS.pop(review_token,None)
        expected={'workspace':str(Path(workspace).resolve()),'proposal_id':proposal_id,'owner_id':owner_id,
                  'conversation_id':conversation_id,'revision':revision,'plan_sha256':plan_sha256}
        if confirmed is not True or token is None or token['expires_at']<=time.time() or any(token[k]!=v for k,v in expected.items()):raise ValueError('exact current human review required')
        saved=review_filesystem(workspace=workspace,proposal_id=proposal_id,owner_id=owner_id,conversation_id=conversation_id,revision=revision)
        if saved['review_token']:_REVIEWS.pop(saved['review_token'],None)
        if saved['status']!='PROPOSED' or saved['plan_sha256']!=plan_sha256:raise ValueError('proposal no longer executable')
        receipt=FilesystemToolkit(saved['root']).execute(saved['plan_id'],approval={'root':saved['root'],'plan_sha256':plan_sha256,
            'operations':[saved['plan']['operation']],'actor':'human-ui:'+owner_id,'expires_at':time.time()+60})
        saved.update(status=receipt['status'],receipt=receipt,review_token=None)
        target=Path(saved['root'])/saved['plan']['target']
        if receipt['status']=='VERIFIED' and target.is_file() and saved['plan']['operation']!='trash':
            try:
                saved['production']=ProducerStore(workspace).register(owner_id=owner_id,conversation_id=conversation_id,
                    source_root=saved['root'],outputs=[target],receipt=receipt)
            except (OSError,ValueError) as error:
                saved['production_error']=str(error)
        write(_proposal_path(workspace,proposal_id),saved,new=False)
        return saved
