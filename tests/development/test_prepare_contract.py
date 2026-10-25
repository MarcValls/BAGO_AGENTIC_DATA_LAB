"""The published proposal shapes match validation and disclose no argument values."""
import hashlib
import json
import sys
import pytest
from jsonschema import Draft202012Validator
from src.development import DevelopmentService

@pytest.fixture
def service(tmp_path):
    root=tmp_path/'source';(root/'src').mkdir(parents=True);(root/'src/existing.py').write_bytes(b'VALUE = 1\n')
    profile=tmp_path/'profile.json';profile.write_text(json.dumps({'root':str(root),'state_root':str(tmp_path/'state'),
        'allowed_paths':['src/existing.py','src/new.py'],'checks':{'fixed':[sys.executable,'-c','pass']},'required_checks':['fixed']}))
    return DevelopmentService(profile)

def args(item):return {'changes':[item]}

def invoke(service,changes):
    return service.invoke('development_prepare',changes,'author','conversation',service.root)

def validator(service):
    return Draft202012Validator(service.schemas(['development_prepare'])[0]['function']['parameters'])

def test_original_two_valid_shapes_are_prepared(service):
    for item in [{'path':'src/new.py','old_sha256':None,'content':'NEW = True\n'},
                 {'path':'src/existing.py','old_sha256':hashlib.sha256(b'VALUE = 1\n').hexdigest(),'replacements':[{'old':'VALUE = 1','new':'VALUE = 2'}]}]:
        validator(service).validate(args(item))
        result,receipt=invoke(service,args(item))
        assert result['ok'] and receipt['executed']
    assert not (service.root/'src/new.py').exists()
    assert (service.root/'src/existing.py').read_bytes()==b'VALUE = 1\n'

@pytest.mark.parametrize('item',[
    {'path':'src/new.py','old_sha256':None},
    {'path':'src/new.py','old_sha256':None,'content':'SYNTHETIC_CODE','replacements':None},
    {'path':'src/new.py','old_sha256':None,'content':None},
    {'path':'src/new.py','old_sha256':None,'replacements':None},
    {'path':'src/new.py','old_sha256':None,'content':'SYNTHETIC_CODE','UNSAFE_SECRET_KEY':'SYNTHETIC_SECRET'},
    {'path':'src/new.py','old_sha256':None,'content':'SYNTHETIC_CODE','replacements':[{'old':'a','new':'b'}]},
    [],'SYNTHETIC_ARGUMENT',None])
def test_schema_and_service_reject_ambiguous_missing_null_extra_and_nonobjects(service,item):
    assert list(validator(service).iter_errors(args(item)))
    result,receipt=invoke(service,args(item))
    assert not result['ok'] and result['reason_code']=='invalid_change_shape'
    assert receipt['decision']=='DENY' and not receipt['executed']
    assert result['validation_detail']==receipt['validation_detail']
    serialized=json.dumps([result,receipt])
    assert all(secret not in serialized for secret in ['SYNTHETIC_CODE','SYNTHETIC_SECRET','UNSAFE_SECRET_KEY','SYNTHETIC_ARGUMENT','src/new.py'])
    assert not service.list_changes()

def test_null_optional_field_metadata_is_exact_and_value_free(service):
    result,_=invoke(service,args({'path':'src/new.py','old_sha256':None,'content':'not logged','replacements':None}))
    assert result['validation_detail']=={'change_index':0,'item_type':'object',
        'present_fields':['path','old_sha256','content','replacements'],'null_fields':['old_sha256','replacements'],
        'field_types':{'path':'string','old_sha256':'null','content':'string','replacements':'null'},'unexpected_field_count':0}

@pytest.mark.parametrize('path',[[],{},None,1,False])
def test_nonstring_paths_have_categorical_denial(service,path):
    result,receipt=invoke(service,args({'path':path,'old_sha256':None,'content':'never written'}))
    assert result['reason_code']=='nonstring_path' and not receipt['executed']
    assert not service.list_changes()

def test_duplicate_and_out_of_scope_are_distinct_without_path_leakage(service):
    item={'path':'src/new.py','old_sha256':None,'content':'not logged'}
    result,_=invoke(service,{'changes':[item,item]})
    assert result['reason_code']=='duplicate_change_path' and result['validation_detail']['change_index']==1
    result,_=invoke(service,args(dict(item,path='UNAUTHORIZED_PRIVATE_LOCATION')))
    assert result['reason_code']=='change_scope_denied'
    assert 'UNAUTHORIZED_PRIVATE_LOCATION' not in json.dumps(result)
    assert not service.list_changes()

def test_published_schema_is_standard_and_preserved_by_sdk_tool(service):
    from copilot.tools import Tool
    schema=service.schemas(['development_prepare'])[0]['function']['parameters']
    Draft202012Validator.check_schema(schema)
    tool=Tool(name='development_prepare',description='proposal',handler=lambda _:None,parameters=schema)
    assert tool.parameters==schema
    assert len(schema['properties']['changes']['items']['oneOf'])==2
