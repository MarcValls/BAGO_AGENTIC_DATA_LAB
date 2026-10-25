"""The only internal staging exception is the exact canonical runtime pair."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import sys
import pytest
from src.development import DevelopmentService, DevelopmentError

KIT=['.bago/team/kit/scripts/teamctl.py','.bago/team/kit/scripts/team_safety.py']

def build(tmp_path,extra=None):
    root=tmp_path/'target'; (root/'src').mkdir(parents=True)
    (root/'src/example.py').write_bytes(b'VALUE = 1\n')
    repo=Path(__file__).resolve().parents[2]
    for rel in KIT:
        path=root/rel;path.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(repo/rel,path)
    (root/'.bago/team/kit/scripts/hidden_sibling.py').write_bytes(b'SHOULD_NOT_COPY=True')
    code="import importlib.util; from pathlib import Path; root=Path.cwd(); spec=importlib.util.spec_from_file_location('trusted_controller',root/'.bago/team/kit/scripts/teamctl.py'); module=importlib.util.module_from_spec(spec); spec.loader.exec_module(module); assert module.root_path(root)==root; assert module.local_path(root,'src/example.py').is_file(); assert len(module.sha256_file(root/'src/example.py'))==64; print('trusted kit imported and runtime primitives executed')"
    profile=tmp_path/'profile.json'
    config={'root':str(root),'state_root':str(tmp_path/'state'),'allowed_paths':['src/example.py'],'input_paths':KIT,
            'checks':{'unit':[sys.executable,'-c',code]},'required_checks':['unit']}
    config.update(extra or {});profile.write_text(json.dumps(config),encoding='utf8')
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
    assert 'trusted kit imported' in result['check']['stdout_excerpt']
    result=invoke(service,'development_review',{'change_id':change['change_id'],'approve':True,'reason':'Exact canonical kit and primitives checked'},'reviewer')
    assert result['ok'],result

def test_canonical_input_pair_imports_and_executes_primitives_only(tmp_path):
    profile,root=build(tmp_path);service=DevelopmentService(profile);change=prepare(service)
    record,directory=service._load(change['change_id'])
    for rel in KIT:
        assert rel in record['source_files']
        assert (directory/'source'/rel).read_bytes()==(root/rel).read_bytes()
    assert not (directory/'source/.bago/team/kit/scripts/hidden_sibling.py').exists()
    reviewed(service,change)
    service.apply(change['change_id'],change['patch_sha256'],True)
    assert (root/'src/example.py').read_bytes()==b'VALUE = 2\n'

@pytest.mark.parametrize('path',['.bago/team/runtime/state.json','.bago/providers/config.json','.bago/team/kit/scripts/other.py','.bago/team/kit/protocol/mission.schema.json','.bago/team/kit/scripts/../scripts/teamctl.py'])
def test_arbitrary_internal_inputs_are_rejected(tmp_path,path):
    profile,_=build(tmp_path,{'input_paths':KIT+[path]})
    with pytest.raises(DevelopmentError):DevelopmentService(profile)

@pytest.mark.parametrize('key',['allowed_paths','read_paths'])
def test_even_host_profile_cannot_offer_model_the_trusted_kit(key,tmp_path):
    profile,_=build(tmp_path,{key:[KIT[0]]})
    with pytest.raises(DevelopmentError,match='path_denied'):DevelopmentService(profile)

def test_model_read_write_and_hidden_sibling_candidate_injection_denied(tmp_path):
    profile,_=build(tmp_path);service=DevelopmentService(profile)
    result=invoke(service,'development_read',{'path':KIT[0]})
    assert not result['ok'] and result['reason_code']=='read_scope_denied'
    result=invoke(service,'development_prepare',{'changes':[{'path':KIT[0],'old_sha256':None,'content':'bad'}]})
    assert not result['ok'] and result['reason_code']=='change_scope_denied'
    change=prepare(service);directory=service._directory(change['change_id'])
    (directory/'source/.bago/team/kit/scripts/hidden_sibling.py').write_bytes(b'INJECTED=True')
    result=invoke(service,'development_check',{'change_id':change['change_id'],'check_id':'unit'})
    assert not result['ok'] and result['reason_code']=='path_denied'
    with pytest.raises(DevelopmentError):service.apply(change['change_id'],change['patch_sha256'],True)

@pytest.mark.parametrize('where',['source','candidate'])
def test_trusted_input_tamper_blocks_apply(tmp_path,where):
    profile,root=build(tmp_path);service=DevelopmentService(profile);change=prepare(service);reviewed(service,change)
    base=root if where=='source' else service._directory(change['change_id'])/'source'
    with (base/KIT[1]).open('ab') as handle:handle.write(b'\n# drift\n')
    assert not service.inspect(change['change_id'])['apply_eligible']
    with pytest.raises(DevelopmentError):service.apply(change['change_id'],change['patch_sha256'],True)
    assert (root/'src/example.py').read_bytes()==b'VALUE = 1\n'

def test_trusted_input_hardlink_rejected(tmp_path):
    profile,root=build(tmp_path)
    os.link(root/KIT[1],tmp_path/'second-link.py')
    with pytest.raises(DevelopmentError,match='hardlink_denied'):DevelopmentService(profile)
