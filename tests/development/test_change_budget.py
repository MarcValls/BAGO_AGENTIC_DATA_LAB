"""Host-only aggregate budgets preserve existing scopes and per-file limits."""
import hashlib
import json
from pathlib import Path
import sys
import pytest
from src.development import DevelopmentService, DevelopmentError

MISSING=object()
SIZES=(215463,40215,17374)
PATHS=('src/first.txt','src/second.txt','src/third.txt')

def sha(data):return hashlib.sha256(data).hexdigest()

def build(tmp_path,budget=MISSING):
    root=tmp_path/'target';(root/'src').mkdir(parents=True)
    for path in PATHS[:2]:(root/path).write_bytes(b'original\n')
    state=tmp_path/'state';profile=tmp_path/'profile.json'
    data={'root':str(root),'state_root':str(state),'allowed_paths':list(PATHS),
        'checks':{'fixed':[sys.executable,'-B','-c',"from pathlib import Path; assert Path('src/first.txt').is_file()"]},'required_checks':['fixed']}
    if budget is not MISSING:data['max_change_bytes']=budget
    profile.write_text(json.dumps(data),encoding='utf8')
    return profile,root,state

def invoke(service,name,args):return service.invoke(name,args,'author','conversation',service.root)[0]

def changes(count=3):
    return [{'path':path,'old_sha256':sha(b'original\n') if i<2 else None,'content':chr(65+i)*SIZES[i]} for i,path in enumerate(PATHS[:count])]

def test_default_budget_denies_same_273052_expanded_bytes(tmp_path):
    profile,root,_=build(tmp_path);service=DevelopmentService(profile)
    assert sum(len(c['content'].encode('utf8')) for c in changes())==273052
    result=invoke(service,'development_prepare',{'changes':changes()})
    assert not result['ok'] and result['reason_code']=='content_limit'
    assert service.list_changes()==[]
    assert (root/PATHS[0]).read_bytes()==b'original\n' and not (root/PATHS[2]).exists()

def test_explicit_host_budget_524288_allows_273052_without_application(tmp_path):
    profile,root,_=build(tmp_path,524288);service=DevelopmentService(profile)
    result=invoke(service,'development_prepare',{'changes':changes()})
    assert result['ok'],result
    record,stage=service._load(result['change']['change_id'])
    assert sum((stage/'source'/p).stat().st_size for p in PATHS)==273052
    assert record['checks']=={} and record['review'] is None
    with pytest.raises(DevelopmentError,match='mandatory_checks_missing_or_failed'):
        service.apply(record['change_id'],record['patch_sha256'],True)
    assert (root/PATHS[0]).read_bytes()==b'original\n' and not (root/PATHS[2]).exists()

@pytest.mark.parametrize('budget',[None,False,True,0,-1,1.5,'SYNTHETIC_SECRET_VALUE',[],{},1048577])
def test_invalid_host_budget_fails_closed_without_value_leak_or_state_creation(tmp_path,budget):
    profile,_,state=build(tmp_path,budget)
    with pytest.raises(DevelopmentError) as failed:DevelopmentService(profile)
    assert failed.value.code=='invalid_change_budget'
    assert str(failed.value)=='invalid_change_budget' and failed.value.diagnostics is None
    assert not state.exists()

@pytest.mark.parametrize('budget',[1,262144,524288,1048576])
def test_exact_integer_host_boundaries_accepted(tmp_path,budget):
    profile,_,_=build(tmp_path,budget);service=DevelopmentService(profile)
    assert service.max_change_bytes==budget

@pytest.mark.parametrize('budget,allowed',[(MISSING,False),(524288,True)])
def test_revision_counts_retained_parent_files_not_just_small_increment(tmp_path,budget,allowed):
    profile,root,_=build(tmp_path,budget);service=DevelopmentService(profile)
    original=invoke(service,'development_prepare',{'changes':changes(2)})
    assert original['ok'];parent=original['change'];parent_record=service._directory(parent['change_id'])/'record.json';before=parent_record.read_bytes()
    small=changes()[2:]
    assert len(small[0]['content'].encode('utf8'))==17374
    result=invoke(service,'development_revise',{'change_id':parent['change_id'],'expected_sha256':parent['patch_sha256'],'changes':small})
    assert result['ok'] is allowed,result
    if allowed:
        child=result['change'];record,stage=service._load(child['change_id'])
        assert child['change_id']!=parent['change_id'] and child['checks']==[] and child['reviews']==[]
        assert sum((stage/'source'/p).stat().st_size for p in PATHS)==273052
    else:assert result['reason_code']=='content_limit'
    assert parent_record.read_bytes()==before and not (root/PATHS[2]).exists()

def test_budget_counts_utf8_and_expanded_replacements(tmp_path):
    profile,_,_=build(tmp_path,16);service=DevelopmentService(profile)
    result=invoke(service,'development_prepare',{'changes':[{'path':PATHS[2],'old_sha256':None,'content':'é'*8}]})
    assert result['ok'],result
    parent=result['change'];assert len(('é'*8).encode('utf8'))==16
    result=invoke(service,'development_revise',{'change_id':parent['change_id'],'expected_sha256':parent['patch_sha256'],
        'changes':[{'path':PATHS[2],'old_sha256':sha(('é'*8).encode('utf8')),'replacements':[{'old':'é'*8,'new':'é'*9}]}]})
    assert not result['ok'] and result['reason_code']=='content_limit'
    assert len(service.list_changes())==1

def test_prepare_also_counts_replacement_result_not_compact_input_length(tmp_path):
    profile,root,_=build(tmp_path,16);service=DevelopmentService(profile)
    result=invoke(service,'development_prepare',{'changes':[{'path':PATHS[0],'old_sha256':sha(b'original\n'),
        'replacements':[{'old':'original','new':'é'*9}]}]})
    assert result['reason_code']=='content_limit'
    assert (root/PATHS[0]).read_bytes()==b'original\n'

def test_host_budget_does_not_lift_read_or_per_file_limits(tmp_path):
    profile,root,_=build(tmp_path,1048576);service=DevelopmentService(profile)
    result=invoke(service,'development_prepare',{'changes':[{'path':PATHS[2],'old_sha256':None,'content':'x'*262145}]})
    assert result['reason_code']=='content_limit'
    (root/PATHS[0]).write_bytes(b'x'*262145)
    assert invoke(service,'development_read',{'path':PATHS[0]})['reason_code']=='read_limit'
    result=invoke(service,'development_prepare',{'changes':[{'path':PATHS[0],'old_sha256':sha(b'x'*262145),'replacements':[{'old':'x','new':'y'}]}]})
    assert result['reason_code']=='replacement_source_changed'

def test_model_cannot_supply_budget_or_gain_paths(tmp_path):
    profile,_,_=build(tmp_path,524288);service=DevelopmentService(profile)
    schema=json.dumps(service.schemas(['development_prepare','development_revise']))
    assert 'max_change_bytes' not in schema
    assert invoke(service,'development_prepare',{'changes':changes(),'max_change_bytes':1048576})['reason_code']=='invalid_arguments'
    result=invoke(service,'development_prepare',{'changes':[{'path':'src/not_allowed.txt','old_sha256':None,'content':'x'}]})
    assert result['reason_code']=='change_scope_denied'
    parent=invoke(service,'development_prepare',{'changes':changes(2)})['change']
    result=invoke(service,'development_revise',{'change_id':parent['change_id'],'expected_sha256':parent['patch_sha256'],
        'changes':changes()[2:],'max_change_bytes':1048576})
    assert result['reason_code']=='invalid_arguments'

def test_budget_edit_changes_profile_identity_and_does_not_resign_existing_parent(tmp_path):
    profile,_,_=build(tmp_path);service=DevelopmentService(profile)
    parent=invoke(service,'development_prepare',{'changes':changes(2)})['change']
    before=(service._directory(parent['change_id'])/'record.json').read_bytes()
    data=json.loads(profile.read_text(encoding='utf8'));data['max_change_bytes']=524288;profile.write_text(json.dumps(data),encoding='utf8')
    changed=DevelopmentService(profile)
    assert changed.profile_sha256!=service.profile_sha256
    result=invoke(changed,'development_revise',{'change_id':parent['change_id'],'expected_sha256':parent['patch_sha256'],
        'changes':changes()[2:],'allow_source_rebase':True})
    assert result['reason_code']=='profile_or_identity_changed'
    assert (service._directory(parent['change_id'])/'record.json').read_bytes()==before
