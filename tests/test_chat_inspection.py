import hashlib,json
from pathlib import Path
import pytest
from fastapi.testclient import TestClient
from src.api import server
from src.conversations import ConversationStore
from src.observability.chat_inspection import inspection

TRACE='trace-496fac766f384348'
RUN='agent-chat-275b18ecc8d144d2a65511a1ee31963d'
REPLAY=Path(__file__).resolve().parents[1]/'docs/verification/readme-corporate-20261022/demo'/f'{TRACE}.json'

@pytest.fixture
def env(monkeypatch,tmp_path):
 store=ConversationStore(tmp_path/'library.sqlite3');conversation=store.create('assistant','app-assistant');traces=tmp_path/'traces';traces.mkdir()
 monkeypatch.setattr(server,'CONVERSATIONS',store);monkeypatch.setattr(server,'AGENT_CHAT_TRACE_DIR',traces);monkeypatch.setattr(server,'REPO_ROOT',tmp_path)
 return store,conversation,traces,TestClient(server.app)

def add(env,*,tid=TRACE,hashed=True,data=None):
 store,c,root,_=env;raw=REPLAY.read_bytes() if data is None else json.dumps(data).encode();(root/(tid+'.json')).write_bytes(raw)
 ref={'trace_id':tid,'trace_state':'local_only','execution_id':RUN}
 if hashed:ref['trace_sha256']=hashlib.sha256(raw).hexdigest()
 saved=store.append_message(c['id'],store.get(c['id'])['revision'],'assistant','REPLAY, no new model execution',{'trace':ref})
 return ref,saved

def endpoint(env,query=''):
 return env[3].get(f"/api/conversations/{env[1]['id']}/inspection"+query)

def test_historical_trace_replay_correlates_and_does_not_return_bruma(env):
 add(env);r=endpoint(env);assert r.status_code==200;selected=r.json()['selected'];assert selected['trace']['trace_id']==TRACE;assert selected['execution_id']==RUN;assert selected['integrity']=='hash_verified';assert '5b385699' not in r.text;assert 'evaluation' not in selected['trace']

def test_legacy_replay_is_explicitly_unverified(env):
 add(env,hashed=False);selected=endpoint(env).json()['selected'];assert selected['state']=='available';assert selected['integrity']=='legacy_unverified'

def test_no_trace_and_wrong_conversation_never_fall_back(env):
 assert endpoint(env).json()['state']=='no_artifacts';add(env);other=env[0].create('assistant','app-assistant');r=env[3].get(f"/api/conversations/{other['id']}/inspection?trace_id={TRACE}");assert r.status_code==404;assert TRACE not in r.text
 assert env[3].get('/api/conversations/conv_missing/inspection').status_code==404

@pytest.mark.parametrize('failure',['missing','modified','wrong_hash','wrong_run','wrong_trace','duplicate_event','missing_parent','duplicate_ref'])
def test_invalid_trace_is_not_displayed(env,failure):
 ref,_=add(env);path=env[2]/(TRACE+'.json')
 if failure=='missing':path.unlink()
 elif failure in ('modified','wrong_hash'):path.write_bytes(path.read_bytes()+b' ')
 elif failure=='duplicate_ref':env[0].append_message(env[1]['id'],1,'assistant','duplicate',{'trace':ref})
 else:
  data=json.loads(path.read_bytes())
  if failure=='wrong_run':data['run_id']='foreign-run'
  if failure=='wrong_trace':data['trace_id']='trace-aaaaaaaaaaaaaaaa'
  if failure=='duplicate_event':data['events'][1]['event_id']=data['events'][0]['event_id']
  if failure=='missing_parent':data['events'][1]['parent_event_id']='absent'
  # Legacy no hash fixture isolates structural validation from content hash mismatch.
  c=env[0].create('assistant','app-assistant');env[1].update(c);ref.pop('trace_sha256');env[0].append_message(c['id'],0,'assistant','bad structure',{'trace':ref});path.write_text(json.dumps(data))
 selected=endpoint(env).json()['selected'];assert selected['state'] in ('invalid','unavailable');assert selected['trace'] is None

def test_execution_selection_and_pages_are_scoped(env):
 add(env)
 for i in range(1,24):
  tid='trace-'+f'{i:016x}';data=json.loads(REPLAY.read_bytes());data['trace_id']=tid
  for event in data['events']:event['trace_id']=tid
  add(env,tid=tid,data=data)
 r=endpoint(env,'?limit=20').json();assert r['state']=='selected';assert r['total']==24;assert r['next_offset']==20;assert len(r['executions'])==20
 assert r['selected']['trace_id']=='trace-'+f'{23:016x}'
 assert r['executions'][0]['trace_id']==r['selected']['trace_id']
 assert len(endpoint(env,'?offset=20&limit=20').json()['executions'])==4
 assert endpoint(env,f'?trace_id={TRACE}&execution_id={RUN}').json()['selected']['trace']['trace_id']==TRACE
 assert endpoint(env,f'?trace_id={TRACE}&execution_id=foreign').status_code==404
 assert endpoint(env,'?offset=-1').status_code==422
 assert endpoint(env,'?limit=51').status_code==422
 assert endpoint(env,'?trace_id=../../outside').status_code==422

def test_linked_file_rejected_and_failure_reference_not_promoted(env):
 ref,_=add(env);path=env[2]/(TRACE+'.json');copy=env[2]/'copy.json';path.rename(copy)
 import os
 os.link(copy,path)
 assert endpoint(env).json()['selected']['state']=='invalid'
 path.unlink();copy.rename(path);ref['trace_state']='local_trace_failed'
 c=env[0].create('assistant','app-assistant');env[1].update(c);env[0].append_message(c['id'],0,'assistant','failed persistence',{'trace':ref})
 assert endpoint(env).json()['selected']['state']=='invalid'

def test_writer_metadata_binds_new_trace_bytes(monkeypatch,tmp_path):
 monkeypatch.setattr(server,'AGENT_CHAT_TRACE_DIR',tmp_path);monkeypatch.setenv('BAGO_OTEL_EXPORTER_OTLP_ENDPOINT','')
 meta=server._record_agent_chat_trace(agent_id='fixture-agent',provider_id='fixture',model_id='fixture',started_at_ns=1,ended_at_ns=2)
 raw=(tmp_path/(meta['trace_id']+'.json')).read_bytes();assert meta['trace_sha256']==hashlib.sha256(raw).hexdigest();assert meta['execution_id']==json.loads(raw)['run_id']

def test_out_of_order_events_preserve_failed_status_and_redaction(env):
 data=json.loads(REPLAY.read_bytes());data['events'].reverse();data['events'][0]['status']='DENY';data['events'][0]['attributes']={'redacted':True};add(env,data=data)
 selected=endpoint(env).json()['selected'];assert selected['state']=='available';assert selected['trace']['events'][0]['status']=='DENY';assert selected['trace']['events'][0]['attributes']=={'redacted':True}
def test_writer_persistence_failure_does_not_claim_hash(monkeypatch,tmp_path):
 monkeypatch.setattr(server,'AGENT_CHAT_TRACE_DIR',tmp_path);monkeypatch.setenv('BAGO_OTEL_EXPORTER_OTLP_ENDPOINT','')
 def fail(*args):raise OSError('fixture persistence failure')
 monkeypatch.setattr(server.os,'replace',fail)
 meta=server._record_agent_chat_trace(agent_id='fixture-agent',provider_id='fixture',model_id='fixture',started_at_ns=1,ended_at_ns=2)
 assert meta['trace_state']=='local_trace_failed';assert 'trace_sha256' not in meta
@pytest.mark.parametrize('field',['name','kind'])
@pytest.mark.parametrize('bad',[{},None,[], '__MISSING__'])
def test_malformed_event_display_fields_fail_closed(env,field,bad):
 data=json.loads(REPLAY.read_bytes())
 if bad=='__MISSING__':data['events'][0].pop(field)
 else:data['events'][0][field]=bad
 add(env,hashed=False,data=data)
 selected=endpoint(env).json()['selected'];assert selected['state']=='invalid';assert selected['trace'] is None

@pytest.mark.parametrize('field,bad',[('events',{}),('events',None),('events',[None]),('event_count',True),('event_count',None),('cost_usd',{}),('cost_usd',None),('cost_usd',[]),('evidence_refs',{}),('evidence_refs',None),('evidence_refs',[{}])])
def test_malformed_trace_lists_and_metadata_fail_closed(env,field,bad):
 data=json.loads(REPLAY.read_bytes());data[field]=bad;add(env,hashed=False,data=data)
 selected=endpoint(env).json()['selected'];assert selected['state']=='invalid';assert selected['trace'] is None

@pytest.mark.parametrize('field,bad',[('attributes',None),('attributes',[]),('evidence_refs',None),('evidence_refs',{}),('evidence_refs',[{}]),('sequence',True),('status',{}),('parent_event_id',[]),('start_time_unix_nano',[])])
def test_malformed_event_metadata_fail_closed(env,field,bad):
 data=json.loads(REPLAY.read_bytes());data['events'][0][field]=bad;add(env,hashed=False,data=data)
 assert endpoint(env).json()['selected']['state']=='invalid'

@pytest.mark.parametrize('ref',[[],{'trace_id':{}},{'trace_id':TRACE,'execution_id':[]},{'trace_id':TRACE,'trace_state':{}},{}])
def test_malformed_persisted_reference_reports_error_not_no_artifacts(env,ref):
 env[0].append_message(env[1]['id'],0,'assistant','bad reference fixture',{'trace':ref})
 r=endpoint(env);assert r.status_code==422;assert 'no_artifacts' not in r.text
