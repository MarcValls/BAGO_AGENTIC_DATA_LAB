"""Independent adversarial runtime inspection. Provider callback is simulated."""
import importlib.util
from pathlib import Path
import pytest

spec=importlib.util.spec_from_file_location('gex_support',Path(__file__).resolve().parents[2]/'api/test_gex_runtime.py')
support=importlib.util.module_from_spec(spec)
spec.loader.exec_module(support)
env=support.env

@pytest.mark.parametrize('field',['request_digest','permit_id','attempt_id','receipt_id'])
def test_wrong_receipt_binding_never_verified(env,field):
    with env['client']() as (http,router):
        headers,_=support.session(http,env)
        proposed=support.propose(http,headers)
        assert support.decide(http,headers,proposed).json()['state']=='SUCCEEDED'
        control=router.gex_holder['control']
        principal=control.authenticate(headers['Authorization'][7:],support.AGENT)
        record=control._read(proposed['request_id'],principal)
        record['receipt'][field]='f'*64
        control._save(record,principal,'RECEIPT_PERSISTED')
        recovered=http.get('/api/gex/requests/'+proposed['request_id'],headers=headers)
        assert recovered.status_code==200
        assert recovered.json()['state']=='RECONCILIATION_REQUIRED'
        assert recovered.json()['integrity']['receipt_verified'] is False

def test_new_session_can_read_but_cannot_approve_pending_other_session(env):
    with env['client']() as (http,router):
        headers,_=support.session(http,env)
        proposed=support.propose(http,headers)
        dispatch=support.spy_dispatch(router)
        fresh,_=support.session(http,env)
        assert http.get('/api/gex/requests/'+proposed['request_id'],headers=fresh).status_code==200
        response=support.decide(http,fresh,proposed)
        assert response.status_code==409
        assert not dispatch and response.json()['detail']['view']['state']=='DENIED'
