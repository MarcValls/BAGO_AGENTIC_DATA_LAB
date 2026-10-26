"""SW04 deadline and partial-execution repairs; no external network/inference."""
import asyncio
import importlib.util
import json
from pathlib import Path
import socket
import sqlite3
import threading
import time
from types import SimpleNamespace
import pytest
from fastapi import HTTPException,Response
from src.web_research import core

spec=importlib.util.spec_from_file_location('public_web_fixture_helpers',Path(__file__).parent/'test_public_web_read.py');helpers=importlib.util.module_from_spec(spec);spec.loader.exec_module(helpers)
URL='https://example.com/page'

@pytest.mark.parametrize('phase',['headers','body','stalled_header'])
def test_absolute_deadline_interrupts_real_protocol_socket(monkeypatch,phase,tmp_path):
    client,remote=socket.socketpair();closed=threading.Event();writes=[]
    class TLSProxy:
        def __getattr__(self,name):return getattr(client,name)
        def do_handshake(self):pass
    class Context:
        def wrap_socket(self,sock,**kwargs):return TLSProxy()
    def server():
        try:
            if phase=='headers':parts=[b'HTTP/1.1 200 OK\r\n']+[b'X-Test: value\r\n']*80+[b'Content-Type: text/plain\r\nContent-Length: 2\r\n\r\nok']
            elif phase=='stalled_header':parts=[b'HTTP/1.1 200 OK\r\nX-Long: ']+[b'x']*300+[b'\r\nContent-Length: 2\r\n\r\nok']
            else:parts=[b'HTTP/1.1 200 OK\r\nContent-Type: text/plain\r\nContent-Length: 300\r\n\r\n']+[b'x']*300
            for part in parts:
                time.sleep(.01);remote.sendall(part);writes.append(len(part))
        except (BrokenPipeError,ConnectionResetError,OSError):pass
        finally:remote.close();closed.set()
    worker=threading.Thread(target=server,daemon=True);worker.start()
    monkeypatch.setattr(core,'public_addresses',lambda *a,**k:['93.184.216.34'])
    monkeypatch.setattr(core.socket,'create_connection',lambda *a,**k:client)
    monkeypatch.setattr(core.ssl,'create_default_context',lambda:Context())
    started=time.monotonic()
    with pytest.raises(core.WebReadError) as error:core.https_get(URL,.10)
    elapsed=time.monotonic()-started
    worker.join(.2)
    assert error.value.code=='TIME_LIMIT' and elapsed<=.22
    assert client.fileno()==-1 and closed.is_set()
    (tmp_path/'observation.json').write_text(json.dumps({'phase':phase,'budget':.1,'tolerance':.12,'elapsed':elapsed,'client_closed':client.fileno()==-1,'writer_stopped':closed.is_set(),'parts_sent':len(writes)}))


def test_short_dns_deadline_cannot_continue_http(monkeypatch):
    def delayed(*a,**k):time.sleep(.08);return [(socket.AF_INET,socket.SOCK_STREAM,6,'',('93.184.216.34',443))]
    monkeypatch.setattr(socket,'getaddrinfo',delayed)
    monkeypatch.setattr(socket,'create_connection',lambda *a,**k:pytest.fail('no HTTP after timeout'))
    start=time.monotonic()
    with pytest.raises(core.WebReadError) as error:core.https_get(URL,.02)
    assert error.value.code=='TIME_LIMIT' and time.monotonic()-start<.12
    time.sleep(.09) # resolver finishes, but cannot connect or create a capture


def failing_turn(server,decision='ALLOW'):
    calls=[]
    def turn(*a,**k):
        calls.append(1)
        if len(calls)==1:
            return {'tool_calls':[{'function':{'name':'public_web_read','arguments':{'url':URL if decision!='DENY' else 'https://other.example/page'}}}]}
        raise server.ollama.ProviderError('fixture_provider_failed','Synthetic provider failed after read')
    return turn,calls

@pytest.mark.parametrize('owner',['agent','assistant'])
@pytest.mark.parametrize('decision',['ALLOW','DENY','FAIL'])
def test_read_outcome_preserves_failed_agent_trace_or_blocks_unrouted_assistant(monkeypatch,tmp_path,owner,decision):
    s,store,c,b=helpers.setup_server(monkeypatch,tmp_path,owner)
    if owner=='assistant':
        monkeypatch.setattr(s.provider_runtime,'active_selection',lambda:{'provider_id':'codex','model_id':'fixture'})
        monkeypatch.setattr(s,'_communication_service',lambda:SimpleNamespace(contacts=lambda:[],drafts=lambda:[]))
    if decision=='FAIL':
        def broken(*a):raise OSError('network failure fixture')
        monkeypatch.setattr(s,'_web_reader',lambda permission:core.PublicWebReader(permission,core.SnapshotStore(tmp_path/'captures'),broken))
    turn,calls=failing_turn(s,decision);monkeypatch.setattr(s.provider_runtime,'chat_turn',turn)
    exported=[];monkeypatch.setenv('BAGO_OTEL_EXPORTER_OTLP_ENDPOINT','http://127.0.0.1:9/fixture-only')
    monkeypatch.setattr(s,'export_local_trace_to_otlp',lambda trace,**k:exported.append(trace) or SimpleNamespace(exported=True,jaeger_trace_id='fixture-otlp-id'))
    g=asyncio.run(s.create_web_read_authorization(s.WebReadAuthorizationRequest(**b,urls=[URL])))
    foreign=store.create(owner,'foreign-owner');foreign_before=store.get(foreign['id'])
    kwargs=dict(message='Research fixture',conversation_id=c['id'],revision=0,web_read_authorization_id=g['authorization_id'])
    if owner=='assistant':
        result=asyncio.run(s.control_chat(s.ControlChatRequest(**kwargs)))
        assert result['sources']==[] and result['read_events']==[]
        assert len(calls)==1 and not (tmp_path/'captures').exists()
        last=store.get(c['id'])['messages'][-1]
        assert last['role']=='assistant' and last['references']['trace']==result['trace']
        assert len(exported)==1 and exported[0].events[0].status=='COMPLETED'
        assert store.get(foreign['id'])==foreign_before
        return
    with pytest.raises(HTTPException) as error:
        asyncio.run(s.chat_with_agent('fixture-agent',s.AgentChatRequest(**kwargs),Response()))
    detail=error.value.detail;saved=store.get(c['id']);last=saved['messages'][-1]
    assert error.value.status_code==503 and detail['code']=='fixture_provider_failed' and detail['execution_state']=='FAILED'
    assert last['role']=='assistant' and last['status']=='failed' and last['content']==''
    assert last['references']['execution_failure']['response_received'] is False
    assert last['references']['read_events'][0]['decision']==decision
    assert detail['revision']==saved['revision'] and detail['trace']==last['references']['trace']
    assert detail['evidence_persistence']=={'conversation':'persisted','trace':'persisted'}
    trace=json.loads((tmp_path/'traces'/f"{detail['trace']['trace_id']}.json").read_text())
    assert trace['events'][0]['status']=='FAILED' and trace['events'][0]['attributes']['conversation_id']==c['id']
    assert trace['events'][0]['attributes']['outcome']=='provider_failed'
    assert len(exported)==1 and exported[0].events[0].status=='FAILED'
    assert [e['status'] for e in trace['events'] if e['name']=='web.read']==[decision]
    if decision=='ALLOW':
        source=last['references']['sources'][0]
        metadata,text=core.SnapshotStore(tmp_path/'captures').load(source['snapshot_id'],source['snapshot_manifest_sha256'])
        assert metadata['text_sha256']==source['content_sha256'] and metadata['binding']['conversation_id']==c['id']
    else:assert last['references']['sources']==[]
    assert store.get(foreign['id'])==foreign_before and len(calls)==2

@pytest.mark.parametrize('failure',['trace','conversation'])
def test_persistence_failure_visible_no_durable_link_claim(monkeypatch,tmp_path,failure):
    s,store,c,b=helpers.setup_server(monkeypatch,tmp_path)
    turn,calls=failing_turn(s);monkeypatch.setattr(s.provider_runtime,'chat_turn',turn)
    if failure=='trace':
        blocked=tmp_path/'blocked';blocked.write_text('not a directory');monkeypatch.setattr(s,'AGENT_CHAT_TRACE_DIR',blocked)
    else:
        original=store.append_message
        def append(*a,**k):
            if k.get('status')=='failed':raise sqlite3.OperationalError('synthetic persistence failure')
            return original(*a,**k)
        monkeypatch.setattr(store,'append_message',append)
    g=asyncio.run(s.create_web_read_authorization(s.WebReadAuthorizationRequest(**b,urls=[URL])))
    with pytest.raises(HTTPException) as error:asyncio.run(s.chat_with_agent('fixture-agent',s.AgentChatRequest(message='Research',conversation_id=c['id'],revision=0,web_read_authorization_id=g['authorization_id']),Response()))
    assert error.value.status_code==503 and error.value.detail['evidence_persistence'][failure]=='failed'
    if failure=='trace':assert error.value.detail['trace']['trace_state']=='local_trace_failed'
    else:assert error.value.detail['revision'] is None and [m['role'] for m in store.get(c['id'])['messages']]==['user']

@pytest.mark.parametrize('status,expected',[('FAILED','ERROR'),('COMPLETED','OK'),('ALLOW','OK')])
def test_otlp_failed_mapping_preserves_local_status_and_success(status,expected):
    from src.observability.local_trace import LocalTrace,TraceEvent,TraceKind
    from src.observability.otel_bridge import RecordingSpanExporter,export_local_trace
    event=TraceEvent(event_id='fixture-root',trace_id='fixture-local',sequence=0,name='agent.chat',kind=TraceKind.WORKFLOW,status=status,attributes={'conversation_id':'fixture-conversation'})
    trace=LocalTrace(trace_id='fixture-local',run_id='fixture-run',events=(event,));before=trace.to_json();exporter=RecordingSpanExporter()
    receipt=export_local_trace(trace,exporter=exporter,endpoint='http://127.0.0.1:9/fixture-only')
    assert receipt.exported and exporter.spans[0].status.status_code.name==expected
    assert exporter.spans[0].attributes['bago.status']==status and trace.to_json()==before
