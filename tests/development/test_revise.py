"""Immutable, own-candidate revisions retain authority and require fresh checks."""
import hashlib
import json
from pathlib import Path
import sys
import subprocess
import pytest
from jsonschema import Draft202012Validator
from src.development import DevelopmentService, TOOL_IDS

def sha(data):return hashlib.sha256(data).hexdigest()

@pytest.fixture
def service(tmp_path):
    root=tmp_path/'target';(root/'src').mkdir(parents=True)
    (root/'src/a.py').write_bytes(b'VALUE = 1\n')
    (root/'src/dependency.py').write_bytes(b'SAFE = True\n')
    profile=tmp_path/'profile.json'
    profile.write_text(json.dumps({'root':str(root),'state_root':str(tmp_path/'state'),
        'allowed_paths':['src/a.py','src/new.py','src/dependency.py'],
        'checks':{'unit':[sys.executable,'-B','-c',"from pathlib import Path; assert Path('src/a.py').read_bytes().startswith(b'VALUE = '); print('bounded fixture check')"]},
        'required_checks':['unit']}),encoding='utf8')
    result=DevelopmentService(profile);result.test_profile=profile
    return result

def invoke(service,name,args,owner='author',conversation='conversation'):
    return service.invoke(name,args,owner,conversation,service.root)[0]

def parent(service):
    result=invoke(service,'development_prepare',{'changes':[{'path':'src/a.py','old_sha256':sha(b'VALUE = 1\n'),'content':'VALUE = 2\n'},
        {'path':'src/new.py','old_sha256':None,'content':'NEW = 2\n'}]})
    assert result['ok'],result
    return result['change']

def revision(change,**extra):
    return {'change_id':change['change_id'],'expected_sha256':change['patch_sha256'],
        'changes':[{'path':'src/a.py','old_sha256':sha(b'VALUE = 2\n'),'replacements':[{'old':'VALUE = 2','new':'VALUE = 3'}]}],**extra}

def check_and_review(service,change):
    result=invoke(service,'development_check',{'change_id':change['change_id'],'check_id':'unit'})
    assert result['ok'] and result['check']['status']=='PASS',result
    result=invoke(service,'development_review',{'change_id':change['change_id'],'approve':True,'reason':'Exact candidate checked'},owner='reviewer')
    assert result['ok'],result

def tree(directory):return {p.relative_to(directory).as_posix():sha(p.read_bytes()) for p in directory.rglob('*') if p.is_file()}

def test_new_revision_retains_full_patch_parent_bytes_and_original_root_hashes(service):
    old=parent(service);check_and_review(service,old)
    directory=service._directory(old['change_id']);before=tree(directory)
    result=invoke(service,'development_revise',revision(old));assert result['ok'],result
    child=result['change'];record,stage=service._load(child['change_id'])
    assert child['change_id']!=old['change_id'] and tree(directory)==before
    assert child['checks']==[] and child['reviews']==[] and not child['apply_eligible']
    assert {c['path']:c['old_sha256'] for c in child['changes']}=={'src/a.py':sha(b'VALUE = 1\n'),'src/new.py':None}
    assert (stage/'source/src/a.py').read_bytes()==b'VALUE = 3\n'
    assert (stage/'source/src/new.py').read_bytes()==b'NEW = 2\n'
    assert child['revision']=={'parent_change_id':old['change_id'],'parent_patch_sha256':old['patch_sha256'],
        'parent_source_sha256':old['source_sha256'],'new_source_sha256':child['source_sha256'],
        'source_rebased':False,'allow_source_rebase':False}
    assert (service.root/'src/a.py').read_bytes()==b'VALUE = 1\n'
    check_and_review(service,child)
    assert service.apply(child['change_id'],child['patch_sha256'],True)['status']=='APPLIED'
    assert (service.root/'src/a.py').read_bytes()==b'VALUE = 3\n'
    assert tree(directory)==before

def test_explicit_rebase_of_foreign_source_preserves_it_and_requires_fresh_checks(service):
    old=parent(service);check_and_review(service,old);before=tree(service._directory(old['change_id']))
    (service.root/'src/external_adapter.py').write_bytes(b'EXTERNAL = True\n')
    denied=invoke(service,'development_revise',revision(old))
    assert denied['reason_code']=='revision_source_rebase_required'
    result=invoke(service,'development_revise',revision(old,allow_source_rebase=True));assert result['ok'],result
    child=result['change'];assert child['revision']['source_rebased']
    assert child['source_sha256']!=old['source_sha256']
    assert child['checks']==[] and child['reviews']==[] and not child['apply_eligible']
    assert (service._directory(child['change_id'])/'source/src/external_adapter.py').read_bytes()==b'EXTERNAL = True\n'
    check_and_review(service,child);service.apply(child['change_id'],child['patch_sha256'],True)
    assert (service.root/'src/external_adapter.py').read_bytes()==b'EXTERNAL = True\n'
    assert tree(service._directory(old['change_id']))==before

@pytest.mark.parametrize('path,data',[('src/a.py',b'VALUE = 99\n'),('src/new.py',b'FOREIGN = True\n')])
def test_rebase_cannot_overwrite_drift_of_any_proposed_path(service,path,data):
    old=parent(service);(service.root/path).write_bytes(data)
    result=invoke(service,'development_revise',revision(old,allow_source_rebase=True))
    assert not result['ok'] and result['reason_code']=='revision_proposed_source_changed'
    assert (service.root/path).read_bytes()==data

@pytest.mark.parametrize('owner,conversation',[('foreign','conversation'),('author','foreign-conversation')])
def test_author_and_conversation_are_required(service,owner,conversation):
    old=parent(service)
    result=invoke(service,'development_revise',revision(old),owner,conversation)
    assert result['reason_code']=='revision_owner_mismatch'
    assert len(service.list_changes())==1

@pytest.mark.parametrize('fence',['execution.fence','rollback.fence'])
def test_fenced_parent_cannot_be_revised(service,fence):
    old=parent(service);(service._directory(old['change_id'])/fence).write_bytes(b'')
    assert invoke(service,'development_revise',revision(old))['reason_code']=='revision_parent_not_prepared'

def test_applied_parent_is_not_prepared(service):
    old=parent(service);check_and_review(service,old);service.apply(old['change_id'],old['patch_sha256'],True)
    assert invoke(service,'development_revise',revision(old))['reason_code']=='revision_parent_not_prepared'

def test_hash_profile_and_candidate_identity_changes_fail_closed(service):
    old=parent(service)
    assert invoke(service,'development_revise',dict(revision(old),expected_sha256='0'*64))['reason_code']=='revision_hash_mismatch'
    path=service._directory(old['change_id'])/'source/src/a.py';path.write_bytes(b'VALUE = 999\n')
    assert invoke(service,'development_revise',revision(old))['reason_code']=='candidate_changed'
    path.write_bytes(b'VALUE = 2\n')
    config=json.loads(service.test_profile.read_text());config['timeout_seconds']=40;service.test_profile.write_text(json.dumps(config))
    changed_profile=DevelopmentService(service.test_profile)
    assert invoke(changed_profile,'development_revise',revision(old))['reason_code']=='profile_or_identity_changed'

@pytest.mark.parametrize('alter,code',[
    ({'changes':[{'path':'src/unknown.py','old_sha256':None,'content':'bad'}]},'change_scope_denied'),
    ({'changes':[{'path':'src/a.py','old_sha256':'0'*64,'content':'bad'}]},'source_changed'),
    ({'changes':[{'path':'src/a.py','old_sha256':sha(b'VALUE = 2\n'),'replacements':[{'old':'not present','new':'bad'}]}]},'replacement_must_match_once'),
    ({'changes':[{'path':'src/a.py','old_sha256':sha(b'VALUE = 2\n'),'content':'x'*262145}]},'content_limit'),
    ({'allow_source_rebase':'true'},'invalid_rebase_flag'),
    ({'allow_source_rebase':None},'invalid_rebase_flag'),
    ({'changes':[]},'invalid_changes')])
def test_revision_reuses_shape_hash_match_scope_and_size_guards(service,alter,code):
    old=parent(service);before=tree(service._directory(old['change_id']))
    assert invoke(service,'development_revise',dict(revision(old),**alter))['reason_code']==code
    assert tree(service._directory(old['change_id']))==before and len(service.list_changes())==1

def test_revision_can_add_authorized_file_and_preserve_crlf_replacement_bytes(service):
    old=parent(service)
    result=invoke(service,'development_revise',dict(revision(old),changes=[{'path':'src/dependency.py','old_sha256':sha(b'SAFE = True\n'),'content':'SAFE = False\r\n'}]))
    assert result['ok'];child=result['change']
    result=invoke(service,'development_revise',dict(revision(child),changes=[{'path':'src/dependency.py','old_sha256':sha(b'SAFE = False\r\n'),'replacements':[{'old':'False','new':'True'}]}]))
    assert result['ok'],result
    assert (service._directory(result['change']['change_id'])/'source/src/dependency.py').read_bytes()==b'SAFE = True\r\n'

def test_new_proposed_file_is_also_checked_against_original_source_on_rebase(service):
    old=parent(service);(service.root/'src/dependency.py').write_bytes(b'FOREIGN = True\n')
    args=dict(revision(old,allow_source_rebase=True),changes=[{'path':'src/dependency.py','old_sha256':sha(b'SAFE = True\n'),'content':'bad'}])
    assert invoke(service,'development_revise',args)['reason_code']=='revision_proposed_source_changed'

def test_revision_source_cannot_drift_again_between_validation_and_copy(service,monkeypatch):
    old=parent(service);copy_source=service._copy_source
    def changed_copy(destination):
        (service.root/'src/external.py').write_bytes(b'NEW=True\n')
        return copy_source(destination)
    monkeypatch.setattr(service,'_copy_source',changed_copy)
    assert invoke(service,'development_revise',revision(old))['reason_code']=='source_changed_during_revision'
    assert len(service.list_changes())==1

def test_reviewer_separation_and_assignment_include_revise(service,monkeypatch):
    from src.agent_tools.agent_services import AgentServiceSession
    session=object.__new__(AgentServiceSession);session.root=service.root;session.owner_id='author';session.conversation_id='conversation'
    monkeypatch.setenv('BAGO_DEVELOPMENT_PROFILE',str(service.test_profile))
    old=parent(service)
    result,receipt=session.invoke('development_revise',revision(old),{'development_read'})
    assert not result['ok'] and not receipt['executed']
    result,receipt=session.invoke('development_review',{'change_id':old['change_id'],'approve':True,'reason':'no'}, {'development_review','development_revise'})
    assert not result['ok'] and not receipt['executed']
    result,receipt=session.invoke('development_revise',revision(old),{'development_revise'})
    assert result['ok'] and receipt['executed']

def test_revise_schema_is_exact_and_shared_tool_registry(service):
    assert 'development_revise' in TOOL_IDS
    schema=service.schemas(['development_revise'])[0]['function']['parameters'];validator=Draft202012Validator(schema)
    old=parent(service);validator.validate(revision(old));validator.validate(revision(old,allow_source_rebase=True))
    invalid=revision(old);invalid['changes'][0]['content']='ambiguous'
    assert list(validator.iter_errors(invalid))
    assert list(validator.iter_errors(dict(revision(old),allow_source_rebase=None)))
    assert invoke(service,'development_revise',dict(revision(old),argv=['bad']))['reason_code']=='invalid_arguments'

def test_duplicate_changes_and_cumulative_parent_content_limit(service):
    old=parent(service);args=revision(old)
    args['changes']*=2
    assert invoke(service,'development_revise',args)['reason_code']=='duplicate_change_path'
    args=revision(old);args['changes']=[{'path':'src/a.py','old_sha256':sha(b'VALUE = 2\n'),'content':'x'*262144}]
    assert invoke(service,'development_revise',args)['reason_code']=='content_limit'
    assert len(service.list_changes())==1

def test_revision_lineage_tamper_is_detected(service):
    old=parent(service);result=invoke(service,'development_revise',revision(old));assert result['ok']
    child=result['change'];directory=service._directory(child['change_id']);record=json.loads((directory/'record.json').read_text())
    record['revision']['source_rebased']=True;(directory/'record.json').write_text(json.dumps(record))
    assert invoke(service,'development_inspect',{'change_id':child['change_id']})['reason_code']=='revision_identity_changed'

def test_existing_standalone_cli_invokes_revision_without_transport_or_effects(service,tmp_path):
    old=parent(service);args_file=tmp_path/'revision.json';args_file.write_text(json.dumps(revision(old)),encoding='utf8')
    cli=Path(__file__).resolve().parents[2]/'tools/development-cli/development_cli.py'
    result=subprocess.run([sys.executable,'-B',str(cli),'--profile',str(service.test_profile),'invoke','development_revise',
        '--args-file',str(args_file),'--owner-id','author','--conversation-id','conversation','--root',str(service.root)],capture_output=True,text=True)
    assert result.returncode==0,result.stderr
    payload=json.loads(result.stdout);assert payload['result']['ok'],payload
    assert payload['result']['change']['revision']['parent_change_id']==old['change_id']
    assert (service.root/'src/a.py').read_bytes()==b'VALUE = 1\n'

def test_legacy_prepare_multiline_replacement_accepts_lf_from_real_read_of_crlf(service):
    original=b'VALUE = 1\r\nSECOND = 2\r\n'
    (service.root/'src/a.py').write_bytes(original)
    read=invoke(service,'development_read',{'path':'src/a.py','start_line':1,'max_lines':2})
    assert read['ok'] and read['content']=='VALUE = 1\nSECOND = 2'
    assert read['sha256']==sha(original)
    result=invoke(service,'development_prepare',{'changes':[{'path':'src/a.py','old_sha256':read['sha256'],
        'replacements':[{'old':read['content'],'new':'VALUE = 3\nSECOND = 4'}]}]})
    assert result['ok'],result
    stage=service._directory(result['change']['change_id'])/'source/src/a.py'
    assert stage.read_bytes()==b'VALUE = 3\nSECOND = 4\n'
    assert (service.root/'src/a.py').read_bytes()==original

def test_new_revise_multiline_replacement_requires_exact_candidate_crlf(service):
    original=b'VALUE = 2\r\nSECOND = 2\r\n'
    result=invoke(service,'development_prepare',{'changes':[{'path':'src/a.py','old_sha256':sha(b'VALUE = 1\n'),'content':original.decode()}]})
    assert result['ok'];old=result['change'];before=tree(service._directory(old['change_id']))
    args=revision(old,changes=[{'path':'src/a.py','old_sha256':sha(original),
        'replacements':[{'old':'VALUE = 2\nSECOND = 2','new':'VALUE = 3\nSECOND = 3'}]}])
    assert invoke(service,'development_revise',args)['reason_code']=='replacement_must_match_once'
    args['changes'][0]['replacements']=[{'old':'VALUE = 2\r\nSECOND = 2','new':'VALUE = 3\r\nSECOND = 3'}]
    child=invoke(service,'development_revise',args)
    assert child['ok'],child
    stage=service._directory(child['change']['change_id'])/'source/src/a.py'
    assert stage.read_bytes()==b'VALUE = 3\r\nSECOND = 3\r\n'
    assert tree(service._directory(old['change_id']))==before
