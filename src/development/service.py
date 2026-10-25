"""Host-profile development API. Agent proposals never authorize target writes."""
from __future__ import annotations
import contextlib
import difflib
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import time
import uuid

TOOL_IDS = frozenset({'development_read', 'development_prepare', 'development_revise', 'development_check', 'development_inspect', 'development_review'})
MAX_TEXT = 262144
MAX_CHANGE_BYTES_CEILING = 1048576
BLOCKED = re.compile(r'(?i)(^\.|credential|secret|token|password|\.pem$|\.key$|\.env)')
TRUSTED_INTERNAL_INPUTS = frozenset({'.bago/team/kit/scripts/teamctl.py', '.bago/team/kit/scripts/team_safety.py'})

class DevelopmentError(ValueError):
    def __init__(self, code, message=None, *, diagnostics=None):
        self.code = code
        self.diagnostics = diagnostics
        super().__init__(message or code)

def change_diagnostics(change, index):
    """Only fixed field names/types; never values, arbitrary keys or paths."""
    fields=('path','old_sha256','content','replacements')
    def kind(value):
        if value is None:return 'null'
        if isinstance(value,bool):return 'boolean'
        if isinstance(value,str):return 'string'
        if isinstance(value,list):return 'array'
        if isinstance(value,dict):return 'object'
        if isinstance(value,(int,float)):return 'number'
        return 'other'
    present=[name for name in fields if isinstance(change,dict) and name in change]
    return {'change_index':index,'item_type':kind(change),'present_fields':present,
            'null_fields':[name for name in present if change[name] is None],
            'field_types':{name:kind(change[name]) for name in present},
            'unexpected_field_count':sum(name not in fields for name in change) if isinstance(change,dict) else 0}

def digest(data):
    return hashlib.sha256(data).hexdigest()

def encoded(data):
    return json.dumps(data, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False).encode('utf8')

def atomic(path, data):
    temporary = path.with_name('tmp_' + uuid.uuid4().hex[:12])
    temporary.write_bytes(encoded(data))
    os.replace(temporary, path)

def safe(root, relative):
    if not isinstance(relative, str) or not relative or '\\' in relative or ':' in relative or relative.startswith('/'):
        raise DevelopmentError('path_denied')
    parts = relative.split('/')
    if any(p in {'', '.', '..'} or BLOCKED.search(p) for p in parts):
        raise DevelopmentError('path_denied')
    target = root
    for part in parts:
        target = target / part
        if target.is_symlink() or (target.exists() and getattr(target.lstat(), 'st_file_attributes', 0) & 1024):
            raise DevelopmentError('link_denied')
    if target.exists() and target.is_file() and target.stat().st_nlink != 1:
        raise DevelopmentError('hardlink_denied')
    return target

def file_hash(path):
    return digest(path.read_bytes()) if path.is_file() else None

def descriptors():
    return [{'id': name, 'name': name.replace('_', ' '), 'name_en': name, 'assignable': True,
             'status': 'AVAILABLE' if os.getenv('BAGO_DEVELOPMENT_PROFILE') else 'UNAVAILABLE',
             'provider': 'Host bounded development profile', 'effect': 'READ_REVIEW' if name.endswith(('read','inspect','review')) else 'PREPARE_CHECK',
             'summary': 'Development candidate operations under a fixed host profile; target application requires human confirmation.',
             'limits': {'host_profile_required': True, 'shell': False, 'model_apply': False},
             'source_paths': ['src/development/service.py']} for name in sorted(TOOL_IDS)]

class DevelopmentService:
    def __init__(self, profile_path=None):
        profile_path = profile_path or os.getenv('BAGO_DEVELOPMENT_PROFILE')
        if not profile_path:
            raise DevelopmentError('development_profile_required')
        self.profile = json.loads(Path(profile_path).read_text(encoding='utf8'))
        self.max_change_bytes=self.profile.get('max_change_bytes',MAX_TEXT)
        if type(self.max_change_bytes)!=int or not 1<=self.max_change_bytes<=MAX_CHANGE_BYTES_CEILING:
            raise DevelopmentError('invalid_change_budget')
        self.root = Path(self.profile['root']).resolve(strict=True)
        self.state = Path(self.profile['state_root']).resolve()
        if self.state == self.root or self.root in self.state.parents or self.state in self.root.parents:
            raise DevelopmentError('state_root_must_be_separate')
        # Profiles are host-owned authority. Reject links even when resolution would hide them.
        for raw in (Path(self.profile['root']), Path(self.profile['state_root'])):
            for p in [raw, *raw.parents]:
                if p.is_symlink() or (p.exists() and getattr(p.lstat(),'st_file_attributes',0) & 1024):
                    raise DevelopmentError('profile_link_denied')
        self.allowed = frozenset(self.profile['allowed_paths'])
        self.readable = self.allowed | frozenset(self.profile.get('read_paths', []))
        if not self.allowed or len(self.allowed) > 50:
            raise DevelopmentError('invalid_profile_scope')
        for p in self.readable:
            safe(self.root, p)
        input_paths=self.profile.get('input_paths',[])
        if not isinstance(input_paths,list) or len(input_paths)>1000 or not all(isinstance(p,str) for p in input_paths) or len(set(input_paths))!=len(input_paths):
            raise DevelopmentError('invalid_input_paths')
        self.input_paths=tuple(input_paths)
        self.internal_inputs=TRUSTED_INTERNAL_INPUTS.intersection(self.input_paths)
        self.internal_ancestors=frozenset('/'.join(p.split('/')[:i]) for p in self.internal_inputs for i in range(1,len(p.split('/'))))
        for p in self.input_paths:
            if any(mark in p for mark in '*?[]'):
                raise DevelopmentError('invalid_input_paths')
            if not self._input_path(self.root,p).is_file():
                raise DevelopmentError('required_input_unavailable')
        self.checks = self.profile.get('checks', {})
        self.required = self.profile.get('required_checks', list(self.checks))
        if not self.required or not set(self.required) <= set(self.checks):
            raise DevelopmentError('required_checks_missing')
        for name, argv in self.checks.items():
            if not re.fullmatch('[A-Za-z0-9_-]{1,64}', name) or not isinstance(argv,list) or not argv or not all(isinstance(a,str) and '\x00' not in a for a in argv):
                raise DevelopmentError('invalid_check_profile')
        self.profile_sha256 = digest(encoded(self.profile))
        self.state.mkdir(parents=True, exist_ok=True)
        self.root_identity=(self.root.stat().st_dev,self.root.stat().st_ino)
        self.state_identity=(self.state.stat().st_dev,self.state.stat().st_ino)

    def _roots_current(self):
        for root,identity in ((self.root,self.root_identity),(self.state,self.state_identity)):
            for p in [root,*root.parents]:
                if p.is_symlink() or (p.exists() and getattr(p.lstat(),'st_file_attributes',0)&1024):
                    raise DevelopmentError('root_link_changed')
            if not root.is_dir() or (root.stat().st_dev,root.stat().st_ino)!=identity:
                raise DevelopmentError('root_identity_changed')

    @contextlib.contextmanager
    def lock(self):
        self._roots_current()
        lock = self.state / 'operation.lock'
        try:
            fd = os.open(lock, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        except FileExistsError:
            raise DevelopmentError('operation_busy_or_interrupted') from None
        try:
            os.close(fd)
            yield
        finally:
            lock.unlink(missing_ok=True)

    def schemas(self, assigned):
        common={'path':{'type':'string'},'old_sha256':{'type':['string','null']}}
        replacement={'type':'object','properties':{'old':{'type':'string','minLength':1},'new':{'type':'string'}},'required':['old','new'],'additionalProperties':False}
        shapes=[]
        for field,definition in (('content',{'type':'string'}),('replacements',{'type':'array','minItems':1,'maxItems':50,'items':replacement})):
            shapes.append({'type':'object','properties':{**common,field:definition},'required':['path','old_sha256',field],'additionalProperties':False})
        definitions = {
            'development_read': ({'path': {'type':'string'}, 'start_line':{'type':'integer'}, 'max_lines':{'type':'integer'}}, ['path']),
            'development_prepare': ({'changes': {'type':'array','minItems':1,'maxItems':50,'items':{'oneOf':shapes}}}, ['changes']),
            'development_revise': ({'change_id':{'type':'string'},'expected_sha256':{'type':'string','pattern':'^[a-f0-9]{64}$'},
                'changes':{'type':'array','minItems':1,'maxItems':50,'items':{'oneOf':shapes}},
                'allow_source_rebase':{'type':'boolean','default':False}}, ['change_id','expected_sha256','changes']),
            'development_check': ({'change_id':{'type':'string'},'check_id':{'type':'string'}}, ['change_id','check_id']),
            'development_inspect': ({'change_id':{'type':'string'}}, ['change_id']),
            'development_review': ({'change_id':{'type':'string'},'approve':{'type':'boolean'},'reason':{'type':'string'}}, ['change_id','approve','reason'])}
        return [{'type':'function','function':{'name':n,'description':'Bounded development operation; proposal/check/review never applies target code.', 'parameters':{'type':'object','properties':definitions[n][0],'required':definitions[n][1],'additionalProperties':False}}} for n in sorted(set(assigned)&TOOL_IDS)]

    def _directory(self, change_id):
        self._roots_current()
        if not isinstance(change_id,str) or not re.fullmatch('dev_[0-9a-f]{32}',change_id):
            raise DevelopmentError('invalid_change_id')
        return safe(self.state, 'candidates/' + change_id)

    def _load(self, change_id):
        directory = self._directory(change_id)
        record = json.loads((directory/'record.json').read_text(encoding='utf8'))
        if record['profile_sha256'] != self.profile_sha256 or record['change_id'] != change_id:
            raise DevelopmentError('profile_or_identity_changed')
        if digest(encoded(record['changes'])) != record['patch_sha256']:
            raise DevelopmentError('patch_identity_changed')
        if digest(encoded(record.get('source_files'))) != record.get('source_sha256'):
            raise DevelopmentError('source_manifest_changed')
        if 'revision' in record and digest(encoded(record['revision']))!=record.get('revision_sha256'):
            raise DevelopmentError('revision_identity_changed')
        return record, directory

    def _stage_path(self, root, relative, *, directory=False):
        permitted=self.internal_ancestors if directory else self.internal_inputs
        if relative not in permitted:
            return safe(root,relative)
        # Only two literal host-declared kit files and their necessary parent
        # directories bypass dot-name rejection. Never used for model access.
        target=root
        for part in relative.split('/'):
            target=target/part
            if target.is_symlink() or (target.exists() and getattr(target.lstat(),'st_file_attributes',0)&1024):
                raise DevelopmentError('link_denied')
        if target.exists() and target.is_file() and target.stat().st_nlink!=1:
            raise DevelopmentError('hardlink_denied')
        return target

    def _input_path(self, root, relative):
        if relative not in self.input_paths:
            raise DevelopmentError('input_not_registered')
        return self._stage_path(root,relative)

    def _snapshot(self, root):
        result = {}
        for path in sorted(root.rglob('*')):
            rel = path.relative_to(root).as_posix()
            self._stage_path(root, rel, directory=path.is_dir())
            if path.is_file():
                result[rel] = file_hash(path)
        return result

    def _validate_candidate(self, record, directory):
        if self._snapshot(directory/'source') != record['candidate_files']:
            raise DevelopmentError('candidate_changed')

    def _selected_source_files(self):
        """One finite selection shared by copying and every source-base check."""
        self._roots_current()
        selected={}; count=total=0
        skipped={'node_modules','__pycache__','venv','env','dist','build'}
        for directory,folders,files in os.walk(self.root,followlinks=False):
            current=Path(directory)
            folders[:]=sorted(n for n in folders if not BLOCKED.search(n) and n not in skipped
                              and (current!=self.root or n in {'src','tests','tools','scripts','frontend'}))
            for name in folders:
                safe(self.root,(current/name).relative_to(self.root).as_posix())
            for name in sorted(files):
                if BLOCKED.search(name): continue
                rel=(current/name).relative_to(self.root).as_posix()
                path=safe(self.root,rel)
                if not path.is_file(): raise DevelopmentError('source_nonregular_file')
                count+=1; total+=path.stat().st_size
                if count>20000 or total>150_000_000: raise DevelopmentError('source_copy_limit')
                selected[rel]=file_hash(path)
        # Additional runtime dependencies are exact, host-owned files only.
        # They share the same manifest/copy/drift boundary as ordinary source.
        for rel in self.input_paths:
            path=self._input_path(self.root,rel)
            if not path.is_file(): raise DevelopmentError('required_input_unavailable')
            if rel not in selected:
                count+=1; total+=path.stat().st_size
                if count>20000 or total>150_000_000: raise DevelopmentError('source_copy_limit')
            selected[rel]=file_hash(path)
        return selected

    def _validate_source(self, record):
        if self._selected_source_files()!=record['source_files']:
            raise DevelopmentError('source_changed')

    def _copy_source(self, destination):
        destination.mkdir()
        selected=self._selected_source_files()
        for rel in selected:
            checked=self._input_path(self.root,rel) if rel in self.input_paths else safe(self.root,rel)
            target=self._input_path(destination,rel) if rel in self.input_paths else safe(destination,rel)
            target.parent.mkdir(parents=True,exist_ok=True)
            shutil.copyfile(checked,target)
        if self._selected_source_files()!=selected or self._snapshot(destination)!=selected:
            raise DevelopmentError('source_changed_during_copy')
        return selected

    def _normalized_changes(self, changes, base_root, *, preserve_replacement_eol=False):
        if not isinstance(changes,list) or not 1 <= len(changes) <= 50:
            raise DevelopmentError('invalid_changes')
        normalized=[]; seen=set(); total_content_bytes=0
        for index,c in enumerate(changes):
            diagnostics=change_diagnostics(c,index)
            if not isinstance(c,dict) or set(c) not in ({'path','old_sha256','content'}, {'path','old_sha256','replacements'}):
                raise DevelopmentError('invalid_change_shape',diagnostics=diagnostics)
            if not isinstance(c['path'],str):
                raise DevelopmentError('nonstring_path',diagnostics=diagnostics)
            if c['old_sha256'] is not None and not isinstance(c['old_sha256'],str):
                raise DevelopmentError('invalid_change_shape',diagnostics=diagnostics)
            if ('content' in c and not isinstance(c['content'],str)) or ('replacements' in c and not isinstance(c['replacements'],list)):
                raise DevelopmentError('invalid_change_shape',diagnostics=diagnostics)
            if c['path'] in seen:
                raise DevelopmentError('duplicate_change_path',diagnostics=diagnostics)
            if c['path'] not in self.allowed:
                raise DevelopmentError('change_scope_denied',diagnostics=diagnostics)
            c=dict(c)
            if 'replacements' in c:
                original=safe(base_root,c['path'])
                if not original.is_file() or original.stat().st_size>MAX_TEXT or file_hash(original)!=c['old_sha256']:
                    raise DevelopmentError('replacement_source_changed')
                text=(original.read_bytes().decode('utf8') if preserve_replacement_eol
                      else original.read_text(encoding='utf8'))
                replacements=c.pop('replacements')
                if not isinstance(replacements,list) or not 1<=len(replacements)<=50: raise DevelopmentError('invalid_replacements')
                for item in replacements:
                    if not isinstance(item,dict) or set(item)!={'old','new'} or not all(isinstance(v,str) for v in item.values()) or not item['old'] or text.count(item['old'])!=1:
                        raise DevelopmentError('replacement_must_match_once')
                    text=text.replace(item['old'],item['new'],1)
                c['content']=text
            if not isinstance(c['content'],str) or len(c['content'].encode('utf8'))>MAX_TEXT:
                raise DevelopmentError('content_limit')
            total_content_bytes+=len(c['content'].encode('utf8'))
            if total_content_bytes>self.max_change_bytes: raise DevelopmentError('content_limit')
            if file_hash(safe(base_root,c['path'])) != c['old_sha256']:
                raise DevelopmentError('source_changed')
            seen.add(c['path']); normalized.append(dict(c, new_sha256=digest(c['content'].encode('utf8'))))
        return normalized

    def _prepare(self, args, owner_id, conversation_id, *, revision=None, expected_source_files=None):
        normalized=self._normalized_changes(args['changes'],self.root,preserve_replacement_eol=False)
        identity='dev_'+uuid.uuid4().hex; directory=self._directory(identity); directory.mkdir(parents=True)
        candidate=directory/'source'; source_files=self._copy_source(candidate)
        if expected_source_files is not None and source_files!=expected_source_files:
            raise DevelopmentError('source_changed_during_revision')
        for c in normalized:
            if source_files.get(c['path'])!=c['old_sha256']:
                raise DevelopmentError('source_changed_during_prepare')
            target=safe(candidate,c['path']); target.parent.mkdir(parents=True,exist_ok=True); target.write_bytes(c['content'].encode('utf8'))
        record={'change_id':identity,'profile_sha256':self.profile_sha256,'author_id':owner_id,'conversation_id':conversation_id,
                'status':'PREPARED','changes':normalized,'patch_sha256':digest(encoded(normalized)),
                'candidate_files':self._snapshot(candidate),'source_files':source_files,
                'source_sha256':digest(encoded(source_files)),'checks':{},'review':None}
        if revision is not None:
            record['revision']={**revision,'new_source_sha256':record['source_sha256']}
            record['revision_sha256']=digest(encoded(record['revision']))
        self._validate_source(record)
        atomic(directory/'record.json',record)
        return self._inspect(record,directory)

    def _revise(self, args, owner_id, conversation_id):
        parent,directory=self._load(args['change_id'])
        if parent['author_id']!=owner_id or parent['conversation_id']!=conversation_id:
            raise DevelopmentError('revision_owner_mismatch')
        if args['expected_sha256']!=parent['patch_sha256']:
            raise DevelopmentError('revision_hash_mismatch')
        if parent['status']!='PREPARED' or (directory/'execution.fence').exists() or (directory/'rollback.fence').exists():
            raise DevelopmentError('revision_parent_not_prepared')
        allow_rebase=args.get('allow_source_rebase',False)
        if type(allow_rebase)!=bool:
            raise DevelopmentError('invalid_rebase_flag')
        self._validate_candidate(parent,directory)
        revisions=self._normalized_changes(args['changes'],directory/'source',preserve_replacement_eol=True)
        current_source=self._selected_source_files()
        source_rebased=current_source!=parent['source_files']
        if source_rebased and not allow_rebase:
            raise DevelopmentError('revision_source_rebase_required')
        # Retain every parent change. Compact edits refer to candidate bytes,
        # while the new full patch retains original target preconditions.
        combined={c['path']:{'path':c['path'],'old_sha256':c['old_sha256'],'content':c['content']} for c in parent['changes']}
        for change in revisions:
            path=change['path']
            original=combined[path]['old_sha256'] if path in combined else parent['source_files'].get(path)
            combined[path]={'path':path,'old_sha256':original,'content':change['content']}
        for change in combined.values():
            if file_hash(safe(self.root,change['path']))!=change['old_sha256']:
                raise DevelopmentError('revision_proposed_source_changed')
        revision={'parent_change_id':parent['change_id'],'parent_patch_sha256':parent['patch_sha256'],
                  'parent_source_sha256':parent['source_sha256'],'source_rebased':source_rebased,
                  'allow_source_rebase':allow_rebase}
        return self._prepare({'changes':list(combined.values())},owner_id,conversation_id,
            revision=revision,expected_source_files=current_source)

    def _inspect(self, record, directory):
        diff=[]
        for c in record['changes']:
            old=safe(self.root,c['path'])
            before=old.read_text(encoding='utf8').splitlines(True) if old.is_file() and old.stat().st_size<=MAX_TEXT else []
            diff.extend(difflib.unified_diff(before,c['content'].splitlines(True),fromfile=c['path'],tofile=c['path']))
        reviewed=record.get('review') or {}
        checks_ok=self._passed(record)
        eligible=checks_ok and reviewed.get('approved') is True and reviewed.get('reviewer_id')!=record['author_id'] and reviewed.get('checks_sha256')==digest(encoded(record['checks'])) and not (directory/'execution.fence').exists()
        if eligible:
            try:
                self._verify_checks(record); self._validate_candidate(record,directory); self._validate_source(record)
                eligible=all(file_hash(safe(self.root,c['path']))==c['old_sha256'] for c in record['changes'])
            except (DevelopmentError,OSError,ValueError,KeyError): eligible=False
        return {k:v for k,v in record.items() if k not in {'candidate_files','source_files','changes','checks','review'}} | {
            'author':{'owner_id':record['author_id'],'conversation_id':record['conversation_id']},
            'checks':list(record['checks'].values()),'reviews':[reviewed] if reviewed else [],
            'apply_eligible':eligible,'rollback_eligible':record['status']=='APPLIED' and not (directory/'rollback.fence').exists(),
            'changes':[{k:v for k,v in c.items() if k!='content'} for c in record['changes']], 'diff':''.join(diff)[:65536]}

    def inspect(self, change_id):
        record,directory=self._load(change_id)
        return self._inspect(record,directory)

    def list_changes(self):
        parent=self.state/'candidates'
        # Interrupted/failed preparation directories remain evidence, not usable changes.
        return [self.inspect(p.name) for p in sorted(parent.iterdir()) if p.is_dir() and (p/'record.json').is_file()] if parent.exists() else []

    def _passed(self, record):
        return all(record['checks'].get(name,{}).get('status')=='PASS' and record['checks'][name].get('patch_sha256')==record['patch_sha256'] for name in self.required)

    def _check(self, record, directory, check_id):
        if check_id not in self.checks: raise DevelopmentError('check_not_registered')
        if (directory/'execution.fence').exists(): raise DevelopmentError('execution_already_started')
        self._validate_candidate(record,directory); self._validate_source(record)
        check_run=directory/('check_'+uuid.uuid4().hex); check_run.mkdir()
        record['checks'][check_id]={'check_id':check_id,'status':'RUNNING','patch_sha256':record['patch_sha256']}
        record['review']=None; atomic(directory/'record.json',record)
        argv=self.checks[check_id]; executable=self.profile.get('python_executable')
        argv=[(executable if a=='{python}' and executable else a).replace('{candidate}',str(directory/'source')) for a in argv]
        environment={k:v for k,v in os.environ.items() if k.upper() in {'SYSTEMROOT','WINDIR','PATH','TEMP','TMP','COMSPEC'}}
        environment.update({'PYTHONDONTWRITEBYTECODE':'1','PYTEST_DISABLE_PLUGIN_AUTOLOAD':'1','PYTHONIOENCODING':'utf-8','PYTEST_ADDOPTS':'-p no:cacheprovider'})
        timeout=min(max(float(self.profile.get('timeout_seconds',120)),1),600)
        started=time.time_ns(); status='FAIL'; code=None; reason=None
        with (check_run/'stdout.log').open('wb') as out, (check_run/'stderr.log').open('wb') as err:
            try:
                process=subprocess.Popen(argv,cwd=directory/'source',env=environment,stdout=out,stderr=err,shell=False)
                deadline=time.monotonic()+timeout
                while process.poll() is None:
                    if time.monotonic()>deadline or out.tell()+err.tell()>2_000_000:
                        process.kill(); process.wait(); reason='timeout_or_output_limit'; break
                    time.sleep(.025)
                code=process.returncode
                status='PASS' if code==0 and reason is None else 'FAIL'
            except (OSError,ValueError): reason='process_start_failed'
        try:
            after_files=self._snapshot(directory/'source')
            if after_files!=record['candidate_files']: status='FAIL'; reason='candidate_changed'
        except (DevelopmentError,OSError):
            after_files=None; status='FAIL'; reason='candidate_invalid'
        try: self._validate_source(record)
        except (DevelopmentError,OSError): status='FAIL'; reason='source_changed'
        result={'check_id':check_id,'status':status,'returncode':code,'reason':reason,'argv':argv,
                'started_at_ns':started,'finished_at_ns':time.time_ns(),'patch_sha256':record['patch_sha256'],
                'candidate_before_sha256':digest(encoded(record['candidate_files'])),
                'candidate_after_sha256':digest(encoded(after_files)) if after_files is not None else None,
                'source_sha256':record['source_sha256'],
                'stdout_sha256':file_hash(check_run/'stdout.log'),'stderr_sha256':file_hash(check_run/'stderr.log'),
                'receipt_id':check_run.name,'execution_class':'HOST_BOUNDED_PROCESS_NOT_OS_SANDBOX'}
        for stream in ('stdout','stderr'):
            log=check_run/(stream+'.log'); size=log.stat().st_size
            with log.open('rb') as handle:
                first=handle.read(4096)
                if size>8192:
                    handle.seek(-4096,os.SEEK_END); excerpt=first+b'\n[... bounded excerpt ...]\n'+handle.read(4096)
                else: excerpt=first+handle.read(4096)
            result[stream+'_excerpt']=excerpt.decode('utf8',errors='replace')
            result[stream+'_bytes']=size
            result[stream+'_truncated']=size>8192
        atomic(check_run/'receipt.json',result)
        result['receipt_path']=str(check_run/'receipt.json'); result['receipt_sha256']=file_hash(check_run/'receipt.json')
        record['checks'][check_id]=result; record['review']=None; atomic(directory/'record.json',record)
        return result

    def _verify_checks(self, record):
        if not self._passed(record): raise DevelopmentError('mandatory_checks_missing_or_failed')
        for name in self.required:
            check=record['checks'][name]
            path=Path(check['receipt_path'])
            if path.parent.parent != self._directory(record['change_id']) or file_hash(path)!=check['receipt_sha256']:
                raise DevelopmentError('check_receipt_changed')
            saved=json.loads(path.read_text(encoding='utf8'))
            if saved != {k:v for k,v in check.items() if k not in {'receipt_path','receipt_sha256'}}:
                raise DevelopmentError('check_receipt_mismatch')
            for name in ('stdout','stderr'):
                if file_hash(path.parent/(name+'.log'))!=saved[name+'_sha256']:
                    raise DevelopmentError('check_log_changed')

    def invoke(self,name,args,owner_id,conversation_id,root):
        receipt={'kind':'development_tool','tool_name':name,'receipt_id':'devtool_'+uuid.uuid4().hex,'decision':'DENY','executed':False,'path':str(self.root)}
        try:
            if Path(root).resolve()!=self.root: raise DevelopmentError('development_root_mismatch')
            if not isinstance(owner_id,str) or not owner_id or not isinstance(conversation_id,str) or not conversation_id: raise DevelopmentError('owner_required')
            if isinstance(args,str): args=json.loads(args)
            if not isinstance(args,dict) or name not in TOOL_IDS: raise DevelopmentError('invalid_arguments')
            required={'development_read':{'path'},'development_prepare':{'changes'},'development_revise':{'change_id','expected_sha256','changes'},'development_check':{'change_id','check_id'},'development_inspect':{'change_id'},'development_review':{'change_id','approve','reason'}}[name]
            optional={'start_line','max_lines'} if name=='development_read' else {'allow_source_rebase'} if name=='development_revise' else set()
            if not required <= set(args) or set(args)-required-optional: raise DevelopmentError('invalid_arguments')
            with self.lock():
                if name=='development_read':
                    if args['path'] not in self.readable: raise DevelopmentError('read_scope_denied')
                    path=safe(self.root,args['path']); data=path.read_bytes()
                    if len(data)>MAX_TEXT: raise DevelopmentError('read_limit')
                    start=args.get('start_line',1); count=args.get('max_lines',250)
                    if type(start)!=int or start<1 or type(count)!=int or not 1<=count<=250: raise DevelopmentError('read_range')
                    lines=data.decode('utf8').splitlines(); result={'path':args['path'],'sha256':digest(data),'start_line':start,'end_line':min(len(lines),start+count-1),'content':'\n'.join(lines[start-1:start-1+count])}
                elif name=='development_prepare': result={'change':self._prepare(args,owner_id,conversation_id)}
                elif name=='development_revise': result={'change':self._revise(args,owner_id,conversation_id)}
                else:
                    record,directory=self._load(args['change_id'])
                    self._validate_candidate(record,directory)
                    if name=='development_check': result={'check':self._check(record,directory,args['check_id']),'change':self.inspect(record['change_id'])}
                    elif name=='development_review':
                        if owner_id==record['author_id']: raise DevelopmentError('independent_reviewer_required')
                        if type(args['approve'])!=bool or not isinstance(args['reason'],str) or not 1<=len(args['reason'])<=4000: raise DevelopmentError('invalid_review')
                        self._verify_checks(record); self._validate_source(record)
                        record['review']={'reviewer_id':owner_id,'conversation_id':conversation_id,'approved':args['approve'],'reason':args['reason'],'patch_sha256':record['patch_sha256'],'checks_sha256':digest(encoded(record['checks']))}
                        atomic(directory/'record.json',record); result={'change':self._inspect(record,directory)}
                    else: result={'change':self._inspect(record,directory)}
            receipt.update(decision='ALLOW',executed=True,result_sha256=digest(encoded(result)))
            return dict(result,ok=True),receipt
        except (DevelopmentError,KeyError,TypeError,ValueError,OSError) as error:
            receipt['reason_code']=getattr(error,'code','development_operation_failed')
            result={'ok':False,'reason_code':receipt['reason_code']}
            if getattr(error,'diagnostics',None) is not None:
                result['validation_detail']=error.diagnostics
                receipt['validation_detail']=error.diagnostics
            return result,receipt

    def apply(self,change_id,expected_sha256,confirmed):
        with self.lock():
            record,directory=self._load(change_id)
            if confirmed is not True or expected_sha256!=record['patch_sha256']: raise DevelopmentError('confirmation_required')
            if (directory/'execution.fence').exists(): raise DevelopmentError('execution_already_started')
            self._validate_candidate(record,directory); self._verify_checks(record); self._validate_source(record)
            review=record.get('review') or {}
            if review.get('approved') is not True or review.get('reviewer_id')==record['author_id'] or review.get('patch_sha256')!=expected_sha256 or review.get('checks_sha256')!=digest(encoded(record['checks'])):
                raise DevelopmentError('approved_independent_review_required')
            for c in record['changes']:
                if file_hash(safe(self.root,c['path']))!=c['old_sha256']: raise DevelopmentError('source_changed')
            backup=directory/'backups'; backup.mkdir()
            for i,c in enumerate(record['changes']):
                path=safe(self.root,c['path'])
                if path.exists(): (backup/str(i)).write_bytes(path.read_bytes())
            self._validate_source(record)
            fd=os.open(directory/'execution.fence',os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600); os.close(fd)
            record['status']='INCONCLUSIVE'; atomic(directory/'record.json',record)
            try:
                for c in record['changes']:
                    path=safe(self.root,c['path']); path.parent.mkdir(parents=True,exist_ok=True); path.write_bytes(c['content'].encode('utf8'))
                if any(file_hash(safe(self.root,c['path']))!=c['new_sha256'] for c in record['changes']): raise DevelopmentError('post_write_mismatch')
                record['status']='APPLIED'; record['apply_receipt']={'receipt_id':'apply_'+uuid.uuid4().hex,'patch_sha256':expected_sha256,'files':[{k:v for k,v in c.items() if k!='content'} for c in record['changes']]}
                atomic(directory/'record.json',record)
            except (OSError,DevelopmentError):
                raise DevelopmentError('apply_inconclusive') from None
            return self._inspect(record,directory)

    def rollback(self,change_id,expected_sha256,confirmed):
        with self.lock():
            record,directory=self._load(change_id)
            if confirmed is not True or expected_sha256!=record['patch_sha256']: raise DevelopmentError('confirmation_required')
            if record['status']!='APPLIED' or (directory/'rollback.fence').exists(): raise DevelopmentError('rollback_unavailable')
            for i,c in enumerate(record['changes']):
                if file_hash(safe(self.root,c['path']))!=c['new_sha256']: raise DevelopmentError('source_changed')
                if c['old_sha256'] is not None and file_hash(directory/'backups'/str(i))!=c['old_sha256']: raise DevelopmentError('backup_changed')
            fd=os.open(directory/'rollback.fence',os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600); os.close(fd)
            record['status']='INCONCLUSIVE'; atomic(directory/'record.json',record)
            for i,c in enumerate(record['changes']):
                path=safe(self.root,c['path'])
                if c['old_sha256'] is None: path.unlink()
                else: path.write_bytes((directory/'backups'/str(i)).read_bytes())
            record['status']='ROLLED_BACK'; record['rollback_receipt']={'receipt_id':'rollback_'+uuid.uuid4().hex,'patch_sha256':expected_sha256}; atomic(directory/'record.json',record)
            return self._inspect(record,directory)
