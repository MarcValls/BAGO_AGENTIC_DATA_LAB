"""Actual two-process contention through the SDK and same-origin transport."""
import hashlib
import subprocess
import sys
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from src.api.workspaces_routes import create_workspaces_router
from src.workspace_sdk import WorkspaceService, ServiceError

CTX=dict(owner_kind='agent',owner_id='lock-agent',conversation_id='lock-conversation',conversation_revision=0)

def test_read_before_lock_acquisition_maps_to_busy(tmp_path,monkeypatch):
    service=WorkspaceService(tmp_path)
    workspace=service.open(service.create('fixture','Fixture',True)['id'])
    original=Path.open
    class DeniedRead:
        def __enter__(self): return self
        def __exit__(self,*args): pass
        def seek(self,*args): pass
        def read(self,*args): raise PermissionError(13,'Synthetic locked byte')
    def opened(path,*args,**kwargs):
        return DeniedRead() if path==workspace.internal/'lock' else original(path,*args,**kwargs)
    monkeypatch.setattr(Path,'open',opened)
    with pytest.raises(ServiceError) as caught:
        with workspace.lock():
            pytest.fail('The operation must not run when initialization is denied')
    assert caught.value.code=='busy' and caught.value.status==409

def test_two_process_review_busy_then_recovers_without_rewrite(tmp_path):
    service=WorkspaceService(tmp_path)
    workspace=service.open(service.create('fixture','Fixture',True)['id'])
    proposal=workspace.prepare_write('result.txt','Confirmed fixture\n','create',CTX)
    applied=workspace.apply_write(proposal['proposal_id'],proposal['revision'],proposal['review_sha256'],CTX,
        dict(confirmed=True,operation='apply_write',workspace_id=workspace.id,proposal_id=proposal['proposal_id'],
             revision=proposal['revision'],review_sha256=proposal['review_sha256']))
    target=workspace.root/'result.txt'
    def identity(): return hashlib.sha256(target.read_bytes()).hexdigest(),target.stat().st_mtime_ns
    before=identity()
    script='''import sys
from pathlib import Path
from src.workspace_sdk import WorkspaceService
w=WorkspaceService(Path(sys.argv[1])).open(sys.argv[2])
with w.lock():
 print('HELD',flush=True)
 sys.stdin.readline()
'''
    holder=subprocess.Popen([sys.executable,'-B','-c',script,str(tmp_path),workspace.id],
        cwd=Path(__file__).resolve().parents[1],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
    app=FastAPI();app.include_router(create_workspaces_router(tmp_path))
    try:
        assert holder.stdout.readline().strip()=='HELD'
        with pytest.raises(ServiceError) as caught:
            workspace.review_write(proposal['proposal_id'],CTX)
        assert caught.value.code=='busy' and caught.value.status==409
        with TestClient(app) as client:
            response=client.post(f'/api/workspaces/v1/workspaces/{workspace.id}/actions',
                json=dict(operation='review_write',proposal_id=proposal['proposal_id'],context=CTX))
        assert response.status_code==409 and response.json()['error']['code']=='busy'
        assert identity()==before
    finally:
        stdout,stderr=holder.communicate('release\n',timeout=15)
        assert holder.returncode==0,(stdout,stderr)
    with TestClient(app) as client:
        response=client.post(f'/api/workspaces/v1/workspaces/{workspace.id}/actions',
            json=dict(operation='review_write',proposal_id=proposal['proposal_id'],context=CTX))
    assert response.status_code==200
    assert response.json()['status']=='APPLIED' and response.json()['receipt']==applied['receipt']
    assert identity()==before
