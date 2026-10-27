from __future__ import annotations

import asyncio
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient
from starlette.requests import Request

from src.api.project_permissions_routes import create_project_permissions_router
from src.project_permissions import ProjectContext, ProjectPermissions


def test_routes_use_strict_confirmed_payload_and_no_store(tmp_path: Path) -> None:
    root = tmp_path / "project"
    (root / "docs").mkdir(parents=True)
    service = ProjectPermissions(lambda: ProjectContext("project-a", root, "binding-a", "Project A"))
    app = FastAPI()
    app.include_router(create_project_permissions_router(lambda: service))
    client = TestClient(app)

    initial = client.get("/api/project-permissions")
    assert initial.status_code == 200
    assert initial.headers["cache-control"] == "no-store"
    assert initial.json()["state"] == "unconfigured"
    assert not (root / ".bago").exists()

    body = {
        "expected_project_id": "project-a",
        "expected_binding": "binding-a",
        "expected_revision": "none",
        "read_directories": ["docs"],
        "write_directories": [],
        "confirmed": True,
    }
    saved = client.put("/api/project-permissions", json=body)
    assert saved.status_code == 200
    assert saved.headers["cache-control"] == "no-store"
    assert saved.json()["read_directories"] == ["docs"]

    bad = client.put("/api/project-permissions", json={**body, "unexpected": "field"})
    assert bad.status_code == 422
    assert bad.json()["detail"]["code"] == "invalid_permission_request"

    raw_duplicate = ('{"expected_project_id":"project-a","expected_project_id":"project-a",'
                    '"expected_binding":"binding-a","expected_revision":"none",'
                    '"read_directories":[],"write_directories":[],"confirmed":true}')
    duplicate = client.put("/api/project-permissions", content=raw_duplicate.encode("utf-8"),
                           headers={"content-type": "application/json"})
    assert duplicate.status_code == 422

    revoked = client.request("DELETE", "/api/project-permissions", json={
        "expected_project_id": "project-a", "expected_binding": "binding-a",
        "expected_revision": saved.json()["revision"], "confirmed": True,
    })
    assert revoked.status_code == 200
    assert revoked.json()["read_directories"] == []
    assert revoked.json()["write_directories"] == []


def test_route_accepts_exact_file_scope_and_lists_file_entries(tmp_path: Path) -> None:
    root = tmp_path / "project"
    root.mkdir()
    (root / "notes.txt").write_text("safe", encoding="utf-8")
    service = ProjectPermissions(lambda: ProjectContext("project-a", root, "binding-a", "Project A"))
    app = FastAPI()
    app.include_router(create_project_permissions_router(lambda: service))
    client = TestClient(app)

    initial = client.get("/api/project-permissions").json()
    saved = client.put("/api/project-permissions", json={
        "expected_project_id": "project-a", "expected_binding": "binding-a",
        "expected_revision": initial["revision"], "read_directories": ["notes.txt"],
        "write_directories": [], "confirmed": True,
    })
    assert saved.status_code == 200
    listing = client.post("/api/project-permissions/directories", json={
        "expected_project_id": "project-a", "expected_binding": "binding-a",
        "expected_revision": saved.json()["revision"], "directory": ".",
    })
    assert listing.status_code == 200
    assert listing.json()["files"] == [{"name": "notes.txt", "path": "notes.txt"}]


def test_routes_reject_untrusted_origins(tmp_path: Path) -> None:
    root = tmp_path / "project"
    root.mkdir()
    service = ProjectPermissions(lambda: ProjectContext("project-a", root, "binding-a"))
    app = FastAPI()
    app.state.gex_trusted_origins = ("http://127.0.0.1:8093",)
    app.include_router(create_project_permissions_router(lambda: service))
    response = TestClient(app).get("/api/project-permissions", headers={"origin": "https://attacker.example"})
    assert response.status_code == 403
    assert response.headers["cache-control"] == "no-store"
    assert response.json()["detail"]["code"] == "origin_denied"
    assert not (root / ".bago").exists()


def test_oversized_json_is_rejected_while_streaming(tmp_path: Path) -> None:
    root = tmp_path / "project"
    root.mkdir()
    service = ProjectPermissions(lambda: ProjectContext("project-a", root, "binding-a"))
    app = FastAPI()
    app.include_router(create_project_permissions_router(lambda: service))
    payload = b"{" + (b" " * (16 * 1024)) + b"}"
    route = next(route for route in app.routes if getattr(route, "path", None) == "/api/project-permissions" and "PUT" in getattr(route, "methods", set()))
    chunks = [payload[:8192], payload[8192:]]

    async def receive():
        if chunks:
            chunk = chunks.pop(0)
            return {"type": "http.request", "body": chunk, "more_body": bool(chunks)}
        return {"type": "http.request", "body": b"", "more_body": False}

    request = Request({"type": "http", "http_version": "1.1", "method": "PUT",
                       "scheme": "http", "path": "/api/project-permissions", "raw_path": b"/api/project-permissions",
                       "query_string": b"", "headers": [(b"content-type", b"application/json")],
                       "server": ("127.0.0.1", 8093), "client": ("127.0.0.1", 12345), "app": app}, receive)
    response = asyncio.run(route.endpoint(request))
    assert response.status_code == 422
    import json
    assert json.loads(response.body)["detail"]["code"] == "invalid_permission_request"
    assert not (root / ".bago").exists()
