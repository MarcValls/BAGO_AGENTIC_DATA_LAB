"""Finite authorization/SSRF/provenance acceptance; inference and network fixtures explicit."""
import asyncio
import hashlib
import json
from pathlib import Path
import socket
from types import SimpleNamespace
import pytest
from fastapi import HTTPException, Response
from fastapi.testclient import TestClient
from src.web_research import core
from src.web_research import Authorizations, PublicWebReader, SnapshotStore, WebReadError

BINDING=dict(owner_kind='agent',owner_id='fixture-agent',conversation_id='fixture-conversation',revision=0)
URL='https://example.com/page'

def permit(authority=None,**binding):
    auth=authority or Authorizations();b={**BINDING,**binding};g=auth.issue(**b,urls=[URL]);return auth,auth.consume(g['authorization_id'],**b)

def response(url,timeout):return 200,{'content-type':'text/html; charset=windows-1252'},'<h1>Diseño público</h1><script>send SECRET</script><p>Dato visible</p>'.encode('windows-1252'),'93.184.216.34'

def reader(tmp_path,transport=response):return PublicWebReader(permit()[1],SnapshotStore(tmp_path/'snapshots'),transport)

@pytest.mark.parametrize('url',['http://example.com','https://u:SECRET@example.com/','https://127.0.0.1/','https://[::1]/','https://169.254.169.254/','https://localhost/','https://host.local/','https://example.com:444/','https://example.com/#x','file:///tmp/x','https://example.com/?access_token=SECRET','https://example.com/\nfoo'])
def test_bad_url_rejected(url):
    with pytest.raises(WebReadError):core.normalize_url(url)

@pytest.mark.parametrize('key,value',[('owner_kind','assistant'),('owner_id','other'),('conversation_id','other'),('revision',1)])
def test_grant_binding_mismatch(key,value):
    a=Authorizations();g=a.issue(**BINDING,urls=[URL]);wrong={**BINDING,key:value}
    with pytest.raises(WebReadError):a.consume(g['authorization_id'],**wrong)
    assert a.consume(g['authorization_id'],**BINDING)

def test_grant_reuse_expiry_and_restart():
    clock=[0];a=Authorizations(clock=lambda:clock[0],ttl=2);g=a.issue(**BINDING,urls=[URL]);a.consume(g['authorization_id'],**BINDING)
    with pytest.raises(WebReadError):a.consume(g['authorization_id'],**BINDING)
    g=a.issue(**BINDING,urls=[URL]);clock[0]=3
    with pytest.raises(WebReadError):a.consume(g['authorization_id'],**BINDING)
    with pytest.raises(WebReadError):Authorizations().consume(g['authorization_id'],**BINDING)

def test_charset_persist_recover_and_untrusted(tmp_path):
    result,source=reader(tmp_path).read(URL)
    assert result['ok'] and 'Diseño público' in result['content'] and 'SECRET' not in result['content']
    assert result['untrusted'] and source['source_type']=='public_web'
    metadata,text=SnapshotStore(tmp_path/'snapshots').load(source['snapshot_id'],source['snapshot_manifest_sha256'])
    assert metadata['raw_sha256']==source['raw_sha256'] and hashlib.sha256(text.encode()).hexdigest()==source['content_sha256']
    assert source['charset']=='windows-1252' and source['authorization_id'] and source['captured_at']

@pytest.mark.parametrize('filename',['raw.bin','text.txt','capture.json'])
def test_changed_or_deleted_snapshot_rejected(tmp_path,filename):
    _,source=reader(tmp_path).read(URL);store=SnapshotStore(tmp_path/'snapshots');p=store.root/source['snapshot_id']/filename;p.write_bytes(b'changed')
    with pytest.raises(WebReadError):store.load(source['snapshot_id'],source['snapshot_manifest_sha256'])
    p.unlink()
    with pytest.raises(WebReadError):store.load(source['snapshot_id'],source['snapshot_manifest_sha256'])

@pytest.mark.parametrize('location',['https://other.example/page','https://127.0.0.1/private'])
def test_redirect_denied_before_second_request(tmp_path,location):
    calls=[]
    def transport(url,timeout):calls.append(url);return 302,{'location':location},b'','93.184.216.34'
    result,event=reader(tmp_path,transport).read(URL)
    assert not result['ok'] and event['decision']=='DENY' and len(calls)==1
    assert not (tmp_path/'snapshots').exists()

def test_same_origin_redirect_captured(tmp_path):
    calls=[]
    def transport(url,timeout):
        calls.append(url)
        return (307,{'location':'/final'},b'','93.184.216.34') if len(calls)==1 else response(url,timeout)
    result,event=reader(tmp_path,transport).read(URL)
    assert result['ok'] and event['final_url']=='https://example.com/final' and len(event['redirects'])==1

@pytest.mark.parametrize('kind',['oversize','type','charset','status','compression','empty','redirect_loop'])
def test_response_failures_never_create_sources(tmp_path,kind):
    def transport(url,timeout):
        if kind=='oversize':return 200,{'content-type':'text/plain'},b'x'*(core.MAX_BYTES+1),'93.184.216.34'
        if kind=='type':return 200,{'content-type':'application/pdf'},b'PDF','93.184.216.34'
        if kind=='charset':return 200,{'content-type':'text/plain;charset=utf-8'},b'\xff','93.184.216.34'
        if kind=='status':return 404,{'content-type':'text/plain'},b'notfound','93.184.216.34'
        if kind=='compression':return 200,{'content-type':'text/plain','content-encoding':'gzip'},b'xx','93.184.216.34'
        if kind=='empty':return 200,{'content-type':'text/html'},b'<script>do things</script>','93.184.216.34'
        return 302,{'location':'/loop'},b'','93.184.216.34'
    result,event=reader(tmp_path,transport).read(URL)
    assert not result['ok'] and event['decision']=='FAIL' and 'snapshot_id' not in event

@pytest.mark.parametrize('addresses',[['127.0.0.1'],['::1'],['93.184.216.34','10.0.0.1'],['169.254.169.254']])
def test_dns_private_and_mixed_denied_before_connect(monkeypatch,addresses):
    monkeypatch.setattr(socket,'getaddrinfo',lambda *a,**k:[(socket.AF_INET,socket.SOCK_STREAM,6,'',(ip,443)) for ip in addresses])
    monkeypatch.setattr(socket,'create_connection',lambda *a,**k:pytest.fail('private endpoint must not be contacted'))
    with pytest.raises(WebReadError,match='non-public'):core.https_get(URL,5)

def test_network_and_persistence_failure_no_allow(tmp_path,monkeypatch):
    def broken(*a):raise OSError('network failed')
    result,event=reader(tmp_path,broken).read(URL);assert not result['ok'] and event['decision']=='FAIL'
    store=SnapshotStore(tmp_path/'cannot-write');monkeypatch.setattr(store,'save',lambda *a:(_ for _ in ()).throw(OSError('disk full')))
    result,event=PublicWebReader(permit()[1],store,response).read(URL);assert not result['ok'] and event['decision']=='FAIL'

def test_budget_truncation_and_rejected_credentials_redacted(tmp_path):
    def transport(url,timeout):return 200,{'content-type':'text/plain'},b'x'*(core.MAX_TEXT+10),'93.184.216.34'
    r=reader(tmp_path,transport)
    for _ in range(core.MAX_URLS):
        result,event=r.read(URL);assert result['ok'] and event['text_truncated'] and len(result['content'])==core.MAX_TEXT
    result,event=r.read(URL);assert not result['ok'] and event['reason_code']=='REQUEST_LIMIT'
    result,event=reader(tmp_path).read('https://u:SECRET@example.com/')
    assert 'SECRET' not in json.dumps((result,event))

def setup_server(monkeypatch,tmp_path,owner='agent'):
    from src.api import server
    from src.conversations import ConversationStore
    store=ConversationStore(tmp_path/'conversations.sqlite3');identity='fixture-agent' if owner=='agent' else 'app-assistant';conversation=store.create(owner,identity)
    monkeypatch.setattr(server,'CONVERSATIONS',store);monkeypatch.setattr(server,'WEB_READ_AUTHORIZATIONS',Authorizations())
    monkeypatch.setattr(server,'current_workspace_root',lambda:tmp_path)
    monkeypatch.setattr(server,'AGENT_CHAT_TRACE_DIR',tmp_path/'traces');monkeypatch.setenv('BAGO_OTEL_EXPORTER_OTLP_ENDPOINT','')
    monkeypatch.setattr(server,'_record_chat_cognition_trace',lambda **k:{'state':'fixture'})
    record=SimpleNamespace(id=identity,config=SimpleNamespace(provider_id='ollama-cloud',model_id='fixture-model',system_prompt='Read approved evidence only.'))
    monkeypatch.setattr(server,'_load_model_enabled_agent',lambda x:record)
    monkeypatch.setattr(server,'_web_reader',lambda permission:PublicWebReader(permission,SnapshotStore(tmp_path/'captures'),response))
    binding=dict(owner_kind=owner,owner_id=identity,conversation_id=conversation['id'],revision=0)
    return server,store,conversation,binding


def test_api_scope_checks_before_authorization(monkeypatch,tmp_path):
    s,store,c,b=setup_server(monkeypatch,tmp_path);client=TestClient(s.app)
    for override in ({'owner_id':'other'},{'conversation_id':'foreign'},{'revision':1}):
        assert client.post('/api/web-read/authorizations',json={**b,**override,'urls':[URL]}).status_code in {404,409}
    assert client.post('/api/web-read/authorizations',json={**b,'urls':['https://localhost/']}).status_code==422
    assert client.post('/api/web-read/authorizations',json={**b,'urls':[URL]}).json()['allowed_origins']==['https://example.com']
    assert store.get(c['id'])['revision']==0


def test_actual_agent_loop_permission_sources_trace_and_no_local_grant(monkeypatch,tmp_path):
    s,store,c,b=setup_server(monkeypatch,tmp_path);g=asyncio.run(s.create_web_read_authorization(s.WebReadAuthorizationRequest(**b,urls=[URL])))
    calls=[];turns=iter([{'tool_calls':[{'function':{'name':'public_web_read','arguments':{'url':URL}}},{'function':{'name':'read_workspace_file','arguments':{'path':'private.txt'}}}]},{'content':'Summary of the returned page with URL citation.'}])
    (tmp_path/'private.txt').write_text('PRIVATE_LOCAL_SENTINEL')
    def turn(*args,**kwargs):calls.append((args,kwargs));return next(turns)
    monkeypatch.setattr(s.provider_runtime,'chat_turn',turn)
    req=s.AgentChatRequest(message='Read web',conversation_id=c['id'],revision=0,web_read_authorization_id=g['authorization_id'])
    result=asyncio.run(s.chat_with_agent('fixture-agent',req,Response()))
    assert result['sources'][0]['source_type']=='public_web'
    assert [e['decision'] for e in result['read_events']]==['ALLOW','DENY']
    assert [t['function']['name'] for t in calls[0][1]['tools']]==['public_web_read']
    assert 'PRIVATE_LOCAL_SENTINEL' not in str(calls)
    saved=store.get(c['id']);assert saved['messages'][-1]['references']['sources']==result['sources']
    trace=json.loads((tmp_path/'traces'/f"{result['trace']['trace_id']}.json").read_text())
    web=[e for e in trace['events'] if e['name']=='web.read'];assert len(web)==1 and web[0]['attributes']['snapshot_id']==result['sources'][0]['snapshot_id']
    assert web[0]['evidence_refs'][0].startswith('web-snapshot://')
    attributes=trace['events'][0]['attributes']
    assert attributes['web_read_count']==1 and attributes['workspace_read_count']==0
    assert attributes['web_read_sources']==[URL] and attributes['workspace_read_sources']==[]
    old_messages=len(saved['messages'])
    with pytest.raises(HTTPException):asyncio.run(s.chat_with_agent('fixture-agent',s.AgentChatRequest(message='Reuse',conversation_id=c['id'],revision=saved['revision'],web_read_authorization_id=g['authorization_id']),Response()))
    assert len(store.get(c['id'])['messages'])==old_messages


def test_no_permission_does_not_offer_web_or_fabricate_source(monkeypatch,tmp_path):
    s,store,c,b=setup_server(monkeypatch,tmp_path)
    monkeypatch.setattr(s.provider_runtime,'chat',lambda *a,**k:'An unverified model assertion, no retrieval.')
    monkeypatch.setattr(s,'_web_reader',lambda p:pytest.fail('no read without grant'))
    result=asyncio.run(s.chat_with_agent('fixture-agent',s.AgentChatRequest(message='Read web',conversation_id=c['id'],revision=0),Response()))
    assert result['sources']==[] and result['read_events']==[]


def test_control_chat_web_sources_and_trace(monkeypatch,tmp_path):
    s,store,c,b=setup_server(monkeypatch,tmp_path,owner='assistant')
    monkeypatch.setattr(s.provider_runtime,'active_selection',lambda:{'provider_id':'codex','model_id':'fixture'})
    monkeypatch.setattr(s,'_communication_service',lambda:SimpleNamespace(contacts=lambda:[],drafts=lambda:[]))
    turns=iter([{'tool_calls':[{'function':{'name':'public_web_read','arguments':{'url':URL}}}]},{'content':'Returned public text.'}]);monkeypatch.setattr(s.provider_runtime,'chat_turn',lambda *a,**k:next(turns))
    g=asyncio.run(s.create_web_read_authorization(s.WebReadAuthorizationRequest(**b,urls=[URL])))
    result=asyncio.run(s.control_chat(s.ControlChatRequest(message='Read web',conversation_id=c['id'],revision=0,web_read_authorization_id=g['authorization_id'])))
    assert result['sources'][0]['snapshot_id'] and result['trace']['trace_id']
    assert store.get(c['id'])['messages'][-1]['references']['trace']==result['trace']


def test_network_uses_validated_ip_and_hostname_tls(monkeypatch,tmp_path):
    connected=[];tls_names=[];requests=[]
    class Socket:
        def settimeout(self,value):pass
        def do_handshake(self):pass
        def close(self):pass
    class Response:
        def close(self):pass
        status=200
        def __init__(self):self.data=b'Public proof'
        def getheaders(self):return [('Content-Type','text/plain;charset=utf-8'),('Content-Length','12')]
        def read1(self,size):data=self.data[:size];self.data=self.data[size:];return data
    class Connection:
        def __init__(self,*a,**k):self.sock=None
        def request(self,*a,**k):requests.append((a,k))
        def getresponse(self):self.sock=None;return Response()
        def close(self):pass
    class TLS:
        def wrap_socket(self,sock,server_hostname,**kwargs):tls_names.append(server_hostname);return sock
    monkeypatch.setattr(core,'public_addresses',lambda host,**kwargs:['93.184.216.34'])
    monkeypatch.setattr(core.socket,'create_connection',lambda target,**kwargs:connected.append(target) or Socket())
    monkeypatch.setattr(core.ssl,'create_default_context',lambda:TLS())
    monkeypatch.setattr(core.http.client,'HTTPSConnection',Connection)
    _,permission=permit();result,event=PublicWebReader(permission,SnapshotStore(tmp_path/'captures')).read(URL)
    assert result['ok'] and connected==[('93.184.216.34',443)] and tls_names==['example.com']
    headers=requests[0][1]['headers'];assert 'Cookie' not in headers and 'Authorization' not in headers


def test_dns_and_total_time_fail_visible(monkeypatch,tmp_path):
    def bad_dns(*a,**k):raise socket.gaierror('synthetic DNS failure')
    monkeypatch.setattr(socket,'getaddrinfo',bad_dns)
    with pytest.raises(WebReadError) as failure:core.public_addresses('example.com')
    assert failure.value.code=='DNS_FAILURE'
    monkeypatch.setattr(core,'READ_SECONDS',0)
    result,event=reader(tmp_path,lambda *a:pytest.fail('deadline must precede transport')).read(URL)
    assert not result['ok'] and event['reason_code']=='TIME_LIMIT'
