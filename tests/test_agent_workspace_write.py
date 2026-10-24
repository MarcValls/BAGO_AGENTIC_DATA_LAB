"""AW-1 deterministic isolated SDK/API/selected-agent acceptance; no live provider."""
import asyncio
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import pytest
from fastapi import HTTPException, Response
from src.workspace_sdk import WorkspaceService, ServiceError, API
from src.workspace_sdk import workspace_service as core

CTX = {"owner_kind":"agent","owner_id":"fixture-agent","conversation_id":"fixture-conversation","conversation_revision":0}

@pytest.fixture
def w(tmp_path):
    parent=tmp_path/"owned";parent.mkdir()
    service=WorkspaceService(parent);info=service.create("fixture","Fixture",True)
    return service.open(info["id"])

def prepare(w,mode="create",text="new\n"):
    if mode=="modify":(w.root/"result.txt").write_bytes(b"before\n")
    return w.prepare_write("result.txt",text,mode,CTX)

def apply(w,p,**changes):
    args=dict(proposal_id=p["proposal_id"],expected_revision=p["revision"],review_sha256=p["review_sha256"],context=CTX,
        confirmation=dict(confirmed=True,operation="apply_write",workspace_id=w.id,proposal_id=p["proposal_id"],revision=p["revision"],review_sha256=p["review_sha256"]))
    args.update(changes);return w.apply_write(**args)

@pytest.mark.parametrize("mode",["create","modify"])
def test_prepare_review_confirm_restart_replay(w,mode,monkeypatch):
    p=prepare(w,mode);before=(w.root/"result.txt").read_bytes() if mode=="modify" else None
    assert p["status"]=="PROPOSED" and p["diff"] and p["receipt"] is None
    assert ((w.root/"result.txt").read_bytes() if mode=="modify" else None)==before
    reopened=WorkspaceService(w.parent).open(w.id)
    assert reopened.review_write(p["proposal_id"],CTX)==p
    with pytest.raises(ServiceError):apply(reopened,p,confirmation={})
    result=apply(reopened,p)
    assert result["status"]=="APPLIED" and result["receipt"]["after_sha256"]==core.sha(b"new\n")
    assert (w.root/"result.txt").read_bytes()==b"new\n"
    monkeypatch.setattr(core.Workspace,"_write",lambda *a:pytest.fail("APPLIED replay must not write"))
    assert apply(WorkspaceService(w.parent).open(w.id),p)==result

def test_revision_invalidates_approval(w):
    p=prepare(w);q=w.revise_write(p["proposal_id"],p["revision"],"edited",CTX)
    assert q["revision"]!=p["revision"] and q["review_sha256"]!=p["review_sha256"]
    with pytest.raises(ServiceError):apply(w,p)
    with pytest.raises(ServiceError):w.revise_write(p["proposal_id"],p["revision"],"stale",CTX)
    assert not (w.root/"result.txt").exists()
    assert apply(w,q)["status"]=="APPLIED"

@pytest.mark.parametrize("change",["modified","deleted","created"])
def test_base_changes_block_confirmation(w,change):
    p=prepare(w,"create" if change=="created" else "modify")
    target=w.root/"result.txt"
    if change=="deleted":target.unlink()
    else:target.write_bytes(b"outside change")
    assert w.review_write(p["proposal_id"],CTX)["status"]=="CONFLICT"
    with pytest.raises(ServiceError):apply(w,p)
    assert target.read_bytes()==b"outside change" if target.exists() else change=="deleted"

@pytest.mark.parametrize("path",["../escape","/absolute","C:/absolute",".env",".workspace-service/x",".git/config",".bago/other","CON.txt","a/../b","a\\b"])
def test_path_denied(w,path):
    with pytest.raises(ServiceError):w.prepare_write(path,"text","create",CTX)

@pytest.mark.parametrize("field,value",[("owner_id","foreign"),("conversation_id","foreign"),("conversation_revision",1),("owner_kind","assistant")])
def test_wrong_context_denied(w,field,value):
    p=prepare(w)
    with pytest.raises(ServiceError):w.review_write(p["proposal_id"],{**CTX,field:value})
    assert not (w.root/"result.txt").exists()

def test_foreign_workspace_and_tamper(w):
    p=prepare(w)
    other=WorkspaceService(w.parent).create("other","Other",True)
    with pytest.raises(ServiceError):WorkspaceService(w.parent).open(other["id"]).review_write(p["proposal_id"],CTX)
    file=w._proposal_path(p["proposal_id"]);data=json.loads(file.read_text());data["proposed_text"]="tamper";file.write_text(json.dumps(data))
    with pytest.raises(ServiceError):w.review_write(p["proposal_id"],CTX)

def test_symlink_and_hardlink_denied(w,tmp_path):
    outside=tmp_path/"outside";outside.write_text("outside")
    # Hard links work without Windows developer privileges.
    os.link(outside,w.root/"hard.txt")
    with pytest.raises(ServiceError):w.prepare_write("hard.txt","new","modify",CTX)
    try:(w.root/"link.txt").symlink_to(outside)
    except OSError:return
    with pytest.raises(ServiceError):w.prepare_write("link.txt","new","modify",CTX)

@pytest.mark.parametrize("phase",["prepare","intent","target","receipt","final"])
def test_persistence_failure_and_readonly_restart(w,monkeypatch,phase):
    if phase=="prepare":
        monkeypatch.setattr(w,"_proposal_save",lambda *a:(_ for _ in ()).throw(OSError("disk")))
        with pytest.raises(OSError):prepare(w)
        assert not (w.root/"result.txt").exists();return
    p=prepare(w);original=core.atomic;calls=[]
    def atomic(path,content):
        calls.append(path)
        if phase=="intent" and path.parent.name=="write-proposals":raise OSError("intent")
        if phase=="target" and path.name=="result.txt":raise OSError("target")
        if phase=="receipt" and path.parent.name=="receipts":raise OSError("receipt")
        if phase=="final" and path.parent.name=="write-proposals" and json.loads(content)["status"]!="PROPOSED":raise OSError("final")
        return original(path,content)
    monkeypatch.setattr(core,"atomic",atomic)
    if phase=="intent":
        with pytest.raises(OSError):apply(w,p)
        assert not (w.root/"result.txt").exists();return
    result=apply(w,p);assert result["status"]=="UNCERTAIN"
    before=(w.root/"result.txt").read_bytes() if (w.root/"result.txt").exists() else None
    recovered=WorkspaceService(w.parent).open(w.id).review_write(p["proposal_id"],CTX)
    assert recovered["status"]=="UNCERTAIN"
    assert recovered["observation"]["matches_proposed"]==(phase in {"receipt","final"})
    with pytest.raises(ServiceError):apply(w,p)
    assert ((w.root/"result.txt").read_bytes() if (w.root/"result.txt").exists() else None)==before

def test_dispatch_unknown_apply_arguments_and_no_implicit_confirmation(w):
    p=prepare(w);api=API(WorkspaceService(w.parent));url=f"/api/workspaces/v1/workspaces/{w.id}/actions"
    with pytest.raises(ServiceError):api.dispatch("POST",url,{"operation":"apply_write","proposal_id":p["proposal_id"],"text":"override"})
    assert api.dispatch("POST",url,{"operation":"review_write","proposal_id":p["proposal_id"],"context":CTX})[1]==p

spec=importlib.util.spec_from_file_location("aw_web_helpers",Path(__file__).parent/"test_public_web_read.py")
helpers=importlib.util.module_from_spec(spec);spec.loader.exec_module(helpers)

def setup(monkeypatch,tmp_path):
    s,store,c,b=helpers.setup_server(monkeypatch,tmp_path)
    parent=tmp_path/"owned";parent.mkdir();service=WorkspaceService(parent);info=service.create("chat","Chat",True);w=service.open(info["id"])
    monkeypatch.setenv("BAGO_WORKSPACE_PARENT",str(parent));monkeypatch.setattr(s,"current_workspace_root",lambda:w.root)
    return s,store,c,w

def turns(s,monkeypatch,fields=None,fail=False):
    calls=[]
    def turn(*a,**k):
        calls.append((a,k))
        if len(calls)==1:return {"tool_calls":[{"function":{"name":"propose_workspace_write","arguments":fields or {"path":"answer.md","text":"Public summary","mode":"create"}}}]}
        if fail:raise s.ollama.ProviderError("fixture_failed","fixture")
        return {"content":"A proposal is available for review."}
    monkeypatch.setattr(s.provider_runtime,"chat_turn",turn);return calls

@pytest.mark.parametrize("fail",[False,True])
def test_selected_agent_proposes_and_preserves_failed_partial(monkeypatch,tmp_path,fail):
    s,store,c,w=setup(monkeypatch,tmp_path);calls=turns(s,monkeypatch,fail=fail)
    req=s.AgentChatRequest(message="Propose file",conversation_id=c["id"],revision=0,allow_workspace_write_proposals=True)
    if fail:
        with pytest.raises(HTTPException) as err:asyncio.run(s.chat_with_agent("fixture-agent",req,Response()))
        result=err.value.detail;assert result["execution_state"]=="FAILED"
    else:result=asyncio.run(s.chat_with_agent("fixture-agent",req,Response()))
    summary=result["workspace_write_proposal"]
    assert not (w.root/"answer.md").exists() and "before_text" not in str(calls)
    assert summary["context"]=={**CTX,"conversation_id":c["id"]}
    assert store.get(c["id"])["messages"][-1]["references"]["workspace_write_proposal"]==summary
    tools=[t["function"]["name"] for t in calls[0][1]["tools"]]
    assert tools==["propose_workspace_write"] and "resolve_control_request" not in tools
    assert w.review_write(summary["proposal_id"],summary["context"])["status"]=="PROPOSED"

@pytest.mark.parametrize("extra",[{"confirmed":True},{"workspace_id":"foreign"},{"context":CTX},{"commands":"run"},{"mode":"delete"}])
def test_model_cannot_expand_scope(monkeypatch,tmp_path,extra):
    s,store,c,w=setup(monkeypatch,tmp_path);turns(s,monkeypatch,{"path":"answer.md","text":"x","mode":"create",**extra})
    result=asyncio.run(s.chat_with_agent("fixture-agent",s.AgentChatRequest(message="x",conversation_id=c["id"],revision=0,allow_workspace_write_proposals=True),Response()))
    assert "workspace_write_proposal" not in result and result["read_events"][0]["decision"]=="DENY"
    assert not (w.root/"answer.md").exists()

def test_no_permission_no_tool_and_foreign_root(monkeypatch,tmp_path):
    s,store,c,w=setup(monkeypatch,tmp_path)
    monkeypatch.setattr(s.provider_runtime,"chat_turn",lambda *a,**k:pytest.fail("no proposal loop without permission"))
    monkeypatch.setattr(s.provider_runtime,"chat",lambda *a:"No write access")
    result=asyncio.run(s.chat_with_agent("fixture-agent",s.AgentChatRequest(message="x",conversation_id=c["id"],revision=0),Response()))
    assert "workspace_write_proposal" not in result
    monkeypatch.setattr(s,"current_workspace_root",lambda:tmp_path)
    with pytest.raises(HTTPException):asyncio.run(s.chat_with_agent("fixture-agent",s.AgentChatRequest(message="x",conversation_id=c["id"],revision=result["revision"],allow_workspace_write_proposals=True),Response()))

def test_cli_standalone_new_process(w,tmp_path):
    cli=Path(core.__file__).resolve();env={k:v for k,v in os.environ.items() if k!="PYTHONPATH" and not k.startswith("BAGO")}
    def run(args,data=None):
        p=subprocess.run([sys.executable,"-B",str(cli),"--parent",str(w.parent),*args],cwd=tmp_path,env=env,input=json.dumps(data) if data else None,text=True,encoding="utf8",capture_output=True)
        assert p.returncode==0,p.stdout+p.stderr
        return json.loads(p.stdout)
    p=run(["action","--workspace-id",w.id,"--json","-"],{"operation":"prepare_write","path":"cli.md","mode":"create","text":"CLI result","context":CTX})
    assert not (w.root/"cli.md").exists()
    q=run(["action","--workspace-id",w.id,"--json","-"],{"operation":"review_write","proposal_id":p["proposal_id"],"context":CTX})
    assert q==p
    r=run(["action","--workspace-id",w.id,"--json","-"],{"operation":"apply_write","proposal_id":p["proposal_id"],"context":CTX,"expected_revision":p["revision"],"review_sha256":p["review_sha256"],"confirmation":{"confirmed":True,"operation":"apply_write","workspace_id":w.id,"proposal_id":p["proposal_id"],"revision":p["revision"],"review_sha256":p["review_sha256"]}})
    assert r["status"]=="APPLIED" and (w.root/"cli.md").read_bytes()==b"CLI result"


def test_unsolicited_proposal_in_read_loop_is_denied(monkeypatch,tmp_path):
    s,store,c,w=setup(monkeypatch,tmp_path);calls=turns(s,monkeypatch)
    grant=asyncio.run(s.create_web_read_authorization(s.WebReadAuthorizationRequest(owner_kind="agent",owner_id="fixture-agent",conversation_id=c["id"],revision=0,urls=[helpers.URL])))
    result=asyncio.run(s.chat_with_agent("fixture-agent",s.AgentChatRequest(message="read",conversation_id=c["id"],revision=0,web_read_authorization_id=grant["authorization_id"]),Response()))
    assert result["read_events"][0]["reason_code"]=="proposal_permission_required"
    assert "propose_workspace_write" not in str(calls[0][1]["tools"])
    assert not (w.internal/"write-proposals").exists()


def test_web_read_and_proposal_share_conversation_trace(monkeypatch,tmp_path):
    s,store,c,w=setup(monkeypatch,tmp_path)
    events=iter([{"tool_calls":[{"function":{"name":"public_web_read","arguments":{"url":helpers.URL}}}]},
        {"tool_calls":[{"function":{"name":"propose_workspace_write","arguments":{"path":"public.md","text":"Observed public proof","mode":"create"}}}]}, {"content":"Review prepared."}])
    monkeypatch.setattr(s.provider_runtime,"chat_turn",lambda *a,**k:next(events))
    grant=asyncio.run(s.create_web_read_authorization(s.WebReadAuthorizationRequest(owner_kind="agent",owner_id="fixture-agent",conversation_id=c["id"],revision=0,urls=[helpers.URL])))
    result=asyncio.run(s.chat_with_agent("fixture-agent",s.AgentChatRequest(message="read and propose",conversation_id=c["id"],revision=0,web_read_authorization_id=grant["authorization_id"],allow_workspace_write_proposals=True),Response()))
    last=store.get(c["id"])["messages"][-1]["references"]
    assert last["sources"][0]["source_type"]=="public_web" and last["workspace_write_proposal"]==result["workspace_write_proposal"]
    trace=json.loads((tmp_path/"traces"/(result["trace"]["trace_id"]+".json")).read_text())
    assert {e["name"] for e in trace["events"]}>={"web.read","workspace.propose_write"}
    assert not (w.root/"public.md").exists()


def test_proposal_persistence_failure_cannot_return_chat_success(monkeypatch,tmp_path):
    s,store,c,w=setup(monkeypatch,tmp_path);turns(s,monkeypatch)
    monkeypatch.setattr(core.Workspace,"_proposal_save",lambda *a:(_ for _ in ()).throw(OSError("disk")))
    with pytest.raises(HTTPException) as err:asyncio.run(s.chat_with_agent("fixture-agent",s.AgentChatRequest(message="x",conversation_id=c["id"],revision=0,allow_workspace_write_proposals=True),Response()))
    assert err.value.status_code==503 and err.value.detail["code"]=="proposal_persistence_failed"
    last=store.get(c["id"])["messages"][-1]
    assert last["status"]=="failed" and last["content"]=="" and last["references"]["read_events"][0]["decision"]=="FAIL"
    assert not (w.root/"answer.md").exists()


def test_conversation_failure_returns_existing_proposal_but_no_success(monkeypatch,tmp_path):
    s,store,c,w=setup(monkeypatch,tmp_path);turns(s,monkeypatch);original=store.append_message
    def append(*a,**k):
        if a[2]=="assistant":raise OSError("conversation disk")
        return original(*a,**k)
    monkeypatch.setattr(store,"append_message",append)
    with pytest.raises(HTTPException) as err:asyncio.run(s.chat_with_agent("fixture-agent",s.AgentChatRequest(message="x",conversation_id=c["id"],revision=0,allow_workspace_write_proposals=True),Response()))
    assert err.value.status_code==503 and err.value.detail["execution_state"]=="FAILED"
    p=err.value.detail["workspace_write_proposal"]
    assert w.review_write(p["proposal_id"],p["context"])["status"]=="PROPOSED"
    assert not (w.root/"answer.md").exists()


def test_wrong_conversation_and_changed_manifest_block(monkeypatch,tmp_path):
    s,store,c,w=setup(monkeypatch,tmp_path)
    other=store.create("agent","foreign")
    monkeypatch.setattr(s.provider_runtime,"chat_turn",lambda *a,**k:pytest.fail("foreign conversation must fail first"))
    with pytest.raises(HTTPException):asyncio.run(s.chat_with_agent("fixture-agent",s.AgentChatRequest(message="x",conversation_id=other["id"],revision=0,allow_workspace_write_proposals=True),Response()))
    manifest=w.internal/"manifest.json";record=json.loads(manifest.read_text());record["revision"]="changed";manifest.write_text(json.dumps(record))
    with pytest.raises(ServiceError):w.prepare_write("blocked.md","x","create",CTX)


@pytest.mark.parametrize("text",["\0", "x"*(core.MAX+1), 'password="abcdefghijklmnopqrst"'], ids=["binary","size","credential"])
def test_invalid_text_denied(w,text):
    with pytest.raises(ServiceError):w.prepare_write("safe.txt",text,"create",CTX)


def test_rest_api_actions_reuse_real_core_and_preserve_original_write(w):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from src.api.workspaces_routes import create_workspaces_router
    app=FastAPI();app.include_router(create_workspaces_router(w.parent));client=TestClient(app)
    url=f"/api/workspaces/v1/workspaces/{w.id}/actions"
    p=client.post(url,json={"operation":"prepare_write","path":"api.md","mode":"create","text":"API","context":CTX}).json()
    assert not (w.root/"api.md").exists()
    q=client.post(url,json={"operation":"review_write","proposal_id":p["proposal_id"],"context":CTX})
    assert q.status_code==200 and q.json()==p
    wrong=client.post(url,json={"operation":"apply_write","proposal_id":p["proposal_id"],"expected_revision":p["revision"],"review_sha256":p["review_sha256"],"context":CTX,"confirmation":{}})
    assert wrong.status_code==400 and not (w.root/"api.md").exists()
    confirmation=dict(confirmed=True,operation="apply_write",workspace_id=w.id,proposal_id=p["proposal_id"],revision=p["revision"],review_sha256=p["review_sha256"])
    result=client.post(url,json={"operation":"apply_write","proposal_id":p["proposal_id"],"expected_revision":p["revision"],"review_sha256":p["review_sha256"],"context":CTX,"confirmation":confirmation})
    assert result.status_code==200 and result.json()["status"]=="APPLIED" and (w.root/"api.md").read_bytes()==b"API"
