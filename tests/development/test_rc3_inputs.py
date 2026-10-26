"""Host-selected external runtime inputs use the immutable source-base contract."""
import hashlib
import json
from pathlib import Path
import sys
import pytest
from src.development import DevelopmentService, DevelopmentError

INPUT='docs/governed-execution/GEX_V1_SCHEMA.json'

def build(tmp_path,inputs=None):
    root=tmp_path/'target'; (root/'src').mkdir(parents=True)
    (root/'src/example.py').write_bytes(b'VALUE = 1\n')
    path=root/INPUT; path.parent.mkdir(parents=True); path.write_bytes(b'{"scope":"synthetic"}\n')
    (path.parent/'UNSELECTED.json').write_bytes(b'{}')
    profile=tmp_path/'profile.json'
    profile.write_text(json.dumps({'root':str(root),'state_root':str(tmp_path/'state'),'allowed_paths':['src/example.py'],
        'input_paths':[INPUT] if inputs is None else inputs,
        'checks':{'unit':[sys.executable,'-c',"import json; from pathlib import Path; assert json.loads(Path('docs/governed-execution/GEX_V1_SCHEMA.json').read_text())['scope']=='synthetic'; from src.example import VALUE; assert VALUE==2"]},'required_checks':['unit']}))
    return profile,root

def invoke(service,name,args,owner='author'):
    return service.invoke(name,args,owner,'conv-'+owner,service.root)[0]

def prepare(service):
    result=invoke(service,'development_prepare',{'changes':[{'path':'src/example.py','old_sha256':hashlib.sha256(b'VALUE = 1\n').hexdigest(),'content':'VALUE = 2\n'}]})
    assert result['ok'],result
    return result['change']

def reviewed(service,change):
    result=invoke(service,'development_check',{'change_id':change['change_id'],'check_id':'unit'})
    assert result['ok'] and result['check']['status']=='PASS',result
    result=invoke(service,'development_review',{'change_id':change['change_id'],'approve':True,'reason':'Runtime input and check inspected'},'reviewer')
    assert result['ok'],result

def test_exact_host_external_input_stages_and_executes_without_siblings(tmp_path):
    profile,root=build(tmp_path); service=DevelopmentService(profile); change=prepare(service)
    record,directory=service._load(change['change_id']); candidate=directory/'source'
    assert (candidate/INPUT).read_bytes()==(root/INPUT).read_bytes()
    assert INPUT in record['source_files'] and INPUT in record['candidate_files']
    assert not (candidate/'docs/governed-execution/UNSELECTED.json').exists()
    reviewed(service,change)
    assert service.inspect(change['change_id'])['apply_eligible']
    service.apply(change['change_id'],change['patch_sha256'],True)
    assert (root/INPUT).read_bytes()==b'{"scope":"synthetic"}\n'

@pytest.mark.parametrize('at',['before_check','after_review'])
@pytest.mark.parametrize('mutation',['modified','deleted'])
def test_runtime_input_drift_blocks_real_apply(tmp_path,at,mutation):
    profile,root=build(tmp_path); service=DevelopmentService(profile); change=prepare(service)
    if at=='after_review':reviewed(service,change)
    if mutation=='modified':(root/INPUT).write_bytes(b'{"scope":"changed"}\n')
    else:(root/INPUT).unlink()
    if at=='before_check':
        result=invoke(service,'development_check',{'change_id':change['change_id'],'check_id':'unit'})
        assert not result['ok'] and result['reason_code'] in {'source_changed','required_input_unavailable'}
    assert not service.inspect(change['change_id'])['apply_eligible']
    with pytest.raises(DevelopmentError):service.apply(change['change_id'],change['patch_sha256'],True)
    assert (root/'src/example.py').read_bytes()==b'VALUE = 1\n'

@pytest.mark.parametrize('inputs',[[INPUT,INPUT],['docs/missing.json'],['docs'],['../escape.json'],['docs/*.json'],['docs/.env'],['docs/secrets.json'],INPUT])
def test_inputs_must_be_exact_available_ordinary_nonsecret_files(tmp_path,inputs):
    profile,_=build(tmp_path,inputs)
    with pytest.raises(DevelopmentError):DevelopmentService(profile)

def test_model_cannot_expand_inputs_or_argv(tmp_path):
    profile,_=build(tmp_path); service=DevelopmentService(profile)
    result=invoke(service,'development_prepare',{'changes':[],'input_paths':['docs/extra.json']})
    assert not result['ok'] and result['reason_code']=='invalid_arguments'
    change=prepare(service)
    result=invoke(service,'development_check',{'change_id':change['change_id'],'check_id':'unit','input_paths':['docs/extra.json']})
    assert not result['ok'] and result['reason_code']=='invalid_arguments'
    assert 'input_paths' not in json.dumps(service.schemas(['development_prepare','development_check']))
