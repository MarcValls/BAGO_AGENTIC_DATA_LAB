import hashlib
import json
from pathlib import Path
import subprocess
import sys
import pytest
from src.development import DevelopmentService, DevelopmentError

def sha(value): return hashlib.sha256(value.encode()).hexdigest()

@pytest.fixture
def service(tmp_path):
    root=tmp_path/'target'; (root/'src').mkdir(parents=True); (root/'src/example.py').write_bytes(b'VALUE = 1\n')
    profile={'root':str(root),'state_root':str(tmp_path/'state'),'allowed_paths':['src/example.py','src/new.py'],
             'checks':{'unit':[sys.executable,'-c','from src.example import VALUE; assert VALUE == 2']},'required_checks':['unit'],'timeout_seconds':10}
    path=tmp_path/'profile.json'; path.write_text(json.dumps(profile),encoding='utf8')
    return DevelopmentService(path)

def call(service,name,args,owner='author'):
    result,receipt=service.invoke(name,args,owner_id=owner,conversation_id='conv-'+owner,root=service.root)
    return result,receipt

def prepare(service):
    result,_=call(service,'development_prepare',{'changes':[{'path':'src/example.py','old_sha256':sha('VALUE = 1\n'),'replacements':[{'old':'VALUE = 1','new':'VALUE = 2'}]}]})
    assert result['ok'], result
    return result['change']

def ready(service):
    change=prepare(service)
    result,_=call(service,'development_check',{'change_id':change['change_id'],'check_id':'unit'})
    assert result['check']['status']=='PASS',result
    result,_=call(service,'development_review',{'change_id':change['change_id'],'approve':True,'reason':'Inspected exact candidate and real check.'},owner='reviewer')
    assert result['ok'],result
    return result['change']

def test_full_prepare_check_independent_review_apply_rollback_and_cli(service,tmp_path):
    change=ready(service); assert change['apply_eligible']
    applied=service.apply(change['change_id'],change['patch_sha256'],True)
    assert applied['status']=='APPLIED'; assert (service.root/'src/example.py').read_text()=='VALUE = 2\n'
    assert applied['rollback_eligible']
    rolled=service.rollback(change['change_id'],change['patch_sha256'],True)
    assert rolled['status']=='ROLLED_BACK'; assert (service.root/'src/example.py').read_text()=='VALUE = 1\n'
    profile=tmp_path/'profile.json'
    result=subprocess.run([sys.executable,'tools/development-cli/development_cli.py','--profile',str(profile),'inspect',change['change_id']],capture_output=True,text=True)
    assert result.returncode==0,result.stderr
    assert json.loads(result.stdout)['change']['status']=='ROLLED_BACK'

@pytest.mark.parametrize('path',['../outside.py','src/../outside.py','C:/outside.py','src/x.py:stream','src/.env','src/secrets.py','src/new.py/../example.py'])
def test_path_escape_and_sensitive_denied(service,path):
    result,receipt=call(service,'development_prepare',{'changes':[{'path':path,'old_sha256':None,'content':'bad'}]})
    assert not result['ok']; assert not receipt['executed']

def test_source_stale_during_prepare_and_apply(service):
    change=ready(service)
    (service.root/'src/example.py').write_text('foreign edit')
    assert not service.inspect(change['change_id'])['apply_eligible']
    with pytest.raises(DevelopmentError,match='source_changed'): service.apply(change['change_id'],change['patch_sha256'],True)
    result,_=call(service,'development_prepare',{'changes':[{'path':'src/example.py','old_sha256':sha('VALUE = 1\n'),'content':'VALUE=2'}]})
    assert not result['ok']

def test_checks_missing_and_author_review_denied(service):
    change=prepare(service)
    result,_=call(service,'development_review',{'change_id':change['change_id'],'approve':True,'reason':'self'})
    assert result['reason_code']=='independent_reviewer_required'
    result,_=call(service,'development_review',{'change_id':change['change_id'],'approve':True,'reason':'review'},owner='reviewer')
    assert result['reason_code']=='mandatory_checks_missing_or_failed'
    with pytest.raises(DevelopmentError):service.apply(change['change_id'],change['patch_sha256'],True)

def test_unregistered_check_and_injected_arguments_denied(service):
    change=prepare(service)
    result,_=call(service,'development_check',{'change_id':change['change_id'],'check_id':'unit','argv':['evil']})
    assert result['reason_code']=='invalid_arguments'
    result,_=call(service,'development_check',{'change_id':change['change_id'],'check_id':'evil'})
    assert result['reason_code']=='check_not_registered'

def test_candidate_mutation_blocks_check_review_and_apply(service):
    change=ready(service)
    (service._directory(change['change_id'])/'source/src/example.py').write_text('VALUE=999')
    result,_=call(service,'development_check',{'change_id':change['change_id'],'check_id':'unit'})
    assert result['reason_code']=='candidate_changed'
    assert not service.inspect(change['change_id'])['apply_eligible']
    with pytest.raises(DevelopmentError,match='candidate_changed'):service.apply(change['change_id'],change['patch_sha256'],True)

def test_rejected_review_missing_receipt_and_duplicate_apply(service):
    change=ready(service)
    call(service,'development_review',{'change_id':change['change_id'],'approve':False,'reason':'reject'},owner='reviewer')
    with pytest.raises(DevelopmentError,match='approved_independent_review_required'):service.apply(change['change_id'],change['patch_sha256'],True)
    call(service,'development_review',{'change_id':change['change_id'],'approve':True,'reason':'accept'},owner='reviewer')
    service.apply(change['change_id'],change['patch_sha256'],True)
    with pytest.raises(DevelopmentError,match='execution_already_started'):service.apply(change['change_id'],change['patch_sha256'],True)

@pytest.mark.parametrize('tamper',['receipt','stdout','record'])
def test_check_receipt_tamper_blocks_apply(service,tamper):
    change=ready(service)
    record,directory=service._load(change['change_id'])
    if tamper=='record':
        record['checks']['unit']['returncode']=8; (directory/'record.json').write_text(json.dumps(record))
    else:
        receipt=Path(record['checks']['unit']['receipt_path'])
        (receipt if tamper=='receipt' else receipt.parent/'stdout.log').write_text('changed')
    with pytest.raises(DevelopmentError):service.apply(change['change_id'],change['patch_sha256'],True)

def test_confirmation_and_root_identity_required(service,tmp_path):
    change=ready(service)
    with pytest.raises(DevelopmentError,match='confirmation_required'):service.apply(change['change_id'],'0'*64,True)
    with pytest.raises(DevelopmentError,match='confirmation_required'):service.apply(change['change_id'],change['patch_sha256'],False)
    result,_=service.invoke('development_read',{'path':'src/example.py'},'author','conv',tmp_path)
    assert result['reason_code']=='development_root_mismatch'

def test_mutating_check_fails_and_cannot_be_reviewed(service):
    service.checks['unit']=[sys.executable,'-c',"from pathlib import Path; Path('src/example.py').write_text('VALUE=2')"]
    change=prepare(service)
    result,_=call(service,'development_check',{'change_id':change['change_id'],'check_id':'unit'})
    assert result['check']['status']=='FAIL'; assert result['check']['reason']=='candidate_changed'

def test_create_and_rollback_preserve_absence(service):
    result,_=call(service,'development_prepare',{'changes':[{'path':'src/example.py','old_sha256':sha('VALUE = 1\n'),'content':'VALUE = 2\n'},{'path':'src/new.py','old_sha256':None,'content':'NEW = True\n'}]})
    change=result['change']; call(service,'development_check',{'change_id':change['change_id'],'check_id':'unit'})
    call(service,'development_review',{'change_id':change['change_id'],'approve':True,'reason':'reviewed both files'},owner='reviewer')
    service.apply(change['change_id'],change['patch_sha256'],True); assert (service.root/'src/new.py').exists()
    service.rollback(change['change_id'],change['patch_sha256'],True); assert not (service.root/'src/new.py').exists()

def test_restart_fence_prevents_replay_and_backup_tamper(service):
    change=ready(service); directory=service._directory(change['change_id'])
    (directory/'execution.fence').write_bytes(b'')
    with pytest.raises(DevelopmentError,match='execution_already_started'):service.apply(change['change_id'],change['patch_sha256'],True)
    assert not service.inspect(change['change_id'])['apply_eligible']

def test_read_ranges_and_exact_replacements(service):
    result,_=call(service,'development_read',{'path':'src/example.py','start_line':1,'max_lines':1})
    assert result['content']=='VALUE = 1'; assert result['sha256']==sha('VALUE = 1\n')
    result,_=call(service,'development_prepare',{'changes':[{'path':'src/example.py','old_sha256':sha('VALUE = 1\n'),'replacements':[{'old':'absent','new':'bad'}]}]})
    assert result['reason_code']=='replacement_must_match_once'
