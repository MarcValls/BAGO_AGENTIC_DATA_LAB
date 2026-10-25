"""Regressions for independently reproduced RC1 source drift and feedback gaps."""
import hashlib
import json
from pathlib import Path
import sys
import pytest
from src.development import DevelopmentService, DevelopmentError

def setup_service(tmp_path,argv=None):
    root=tmp_path/'target'; (root/'src').mkdir(parents=True)
    (root/'src/example.py').write_bytes(b'VALUE = 1\n')
    (root/'src/dependency.py').write_bytes(b'SAFE = True\n')
    profile=tmp_path/'profile.json'
    profile.write_text(json.dumps({'root':str(root),'state_root':str(tmp_path/'state'),
        'allowed_paths':['src/example.py'], 'checks':{'unit':argv or [sys.executable,'-c','from src.example import VALUE; from src.dependency import SAFE; assert VALUE == 2 and SAFE']}, 'required_checks':['unit']}))
    return DevelopmentService(profile)

def invoke(service,name,args,owner='author'):
    return service.invoke(name,args,owner,'conv-'+owner,service.root)[0]

def prepare(service):
    result=invoke(service,'development_prepare',{'changes':[{'path':'src/example.py','old_sha256':hashlib.sha256(b'VALUE = 1\n').hexdigest(),'content':'VALUE = 2\n'}]})
    assert result['ok'],result
    return result['change']

def checked(service,change):
    result=invoke(service,'development_check',{'change_id':change['change_id'],'check_id':'unit'})
    assert result['ok'] and result['check']['status']=='PASS',result

def reviewed(service,change):
    checked(service,change)
    result=invoke(service,'development_review',{'change_id':change['change_id'],'approve':True,'reason':'Independent exact checked source.'},'reviewer')
    assert result['ok'],result

@pytest.mark.parametrize('at',['before_check','after_check','after_review'])
@pytest.mark.parametrize('mutation',['modified','added','deleted'])
def test_all_copied_source_dependency_drift_blocks_real_apply(tmp_path,at,mutation):
    service=setup_service(tmp_path); change=prepare(service)
    if at=='after_check':checked(service,change)
    if at=='after_review':reviewed(service,change)
    dependency=service.root/'src/dependency.py'
    if mutation=='modified':dependency.write_bytes(b'SAFE = False\n')
    elif mutation=='added':(service.root/'src/new_dependency.py').write_bytes(b'EXTRA = True\n')
    else:dependency.unlink()
    if at=='before_check':
        result=invoke(service,'development_check',{'change_id':change['change_id'],'check_id':'unit'})
        assert not result['ok'] and result['reason_code']=='source_changed'
    if at=='after_check':
        result=invoke(service,'development_review',{'change_id':change['change_id'],'approve':True,'reason':'would be stale'},'reviewer')
        assert not result['ok'] and result['reason_code']=='source_changed'
    assert not service.inspect(change['change_id'])['apply_eligible']
    with pytest.raises(DevelopmentError):service.apply(change['change_id'],change['patch_sha256'],True)
    assert (service.root/'src/example.py').read_bytes()==b'VALUE = 1\n'
    assert not (service._directory(change['change_id'])/'execution.fence').exists()

def test_source_copy_must_match_recorded_stable_manifest(tmp_path,monkeypatch):
    service=setup_service(tmp_path)
    import src.development.service as module
    original=module.shutil.copyfile
    def racing_copy(source,destination):
        result=original(source,destination)
        if Path(source).name=='dependency.py': Path(source).write_bytes(b'SAFE = False\n')
        return result
    monkeypatch.setattr(module.shutil,'copyfile',racing_copy)
    result=invoke(service,'development_prepare',{'changes':[{'path':'src/example.py','old_sha256':hashlib.sha256(b'VALUE = 1\n').hexdigest(),'content':'VALUE = 2\n'}]})
    assert not result['ok'] and result['reason_code']=='source_changed_during_copy'
    assert not list((service.state/'candidates').glob('*/record.json'))
    assert service.list_changes()==[]

def test_failed_checks_return_actionable_bounded_real_logs_and_inspect(tmp_path):
    argv=[sys.executable,'-c',"import sys; print('AssertionError: expected 2 actual 1'); print('diagnostic-start'+'x'*12000+'diagnostic-end',file=sys.stderr); sys.exit(1)"]
    service=setup_service(tmp_path,argv); change=prepare(service)
    result=invoke(service,'development_check',{'change_id':change['change_id'],'check_id':'unit'})
    assert result['ok']; check=result['check']
    assert check['status']=='FAIL' and check['returncode']==1
    assert 'AssertionError: expected 2 actual 1' in check['stdout_excerpt']
    assert 'diagnostic-start' in check['stderr_excerpt'] and 'diagnostic-end' in check['stderr_excerpt']
    assert len(check['stderr_excerpt'])<8300 and check['stderr_truncated']
    assert not check['stdout_truncated']
    persisted=service.inspect(change['change_id'])['checks'][0]
    assert persisted['stderr_excerpt']==check['stderr_excerpt']
    assert check['stderr_sha256']==hashlib.sha256(Path(check['receipt_path']).with_name('stderr.log').read_bytes()).hexdigest()
    assert not service.inspect(change['change_id'])['apply_eligible']

def test_candidate_placeholder_expands_only_in_fixed_host_argv(tmp_path):
    code="import sys; from pathlib import Path; assert sys.argv[1] == 'type=bind,source='+str(Path.cwd())+',target=/candidate,readonly'; print(sys.argv[1])"
    argv=[sys.executable,'-c',code,'type=bind,source={candidate},target=/candidate,readonly']
    service=setup_service(tmp_path,argv); change=prepare(service)
    result=invoke(service,'development_check',{'change_id':change['change_id'],'check_id':'unit'})
    assert result['check']['status']=='PASS',result
    expected='type=bind,source='+str(service._directory(change['change_id'])/'source')+',target=/candidate,readonly'
    assert result['check']['argv'][-1]==expected
    assert expected in result['check']['stdout_excerpt']
    denied=invoke(service,'development_check',{'change_id':change['change_id'],'check_id':'unit','argv':['arbitrary']})
    assert not denied['ok'] and denied['reason_code']=='invalid_arguments'

def test_source_drift_during_check_is_failed_receipt(tmp_path):
    root=tmp_path/'target'
    code="from pathlib import Path; Path("+repr(str(root/'src/dependency.py'))+").write_text('SAFE=False'); print('executed then source changed')"
    service=setup_service(tmp_path,[sys.executable,'-c',code]); change=prepare(service)
    result=invoke(service,'development_check',{'change_id':change['change_id'],'check_id':'unit'})
    assert result['check']['status']=='FAIL' and result['check']['reason']=='source_changed'
    assert 'executed then source changed' in result['check']['stdout_excerpt']
