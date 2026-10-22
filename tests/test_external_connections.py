"""Real TCP transport and denial checks for external connections."""
import asyncio
import hashlib
import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.api.connection_routes import create_connection_router
from src.connections import service, security, transports


@pytest.fixture
def remote():
    state = {"calls": [], "required": ["text"], "status": 200, "secret": ""}
    class Handler(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"
        def log_message(self, *_):
            pass
        def send_json(self, value, status=200):
            raw = json.dumps(value).encode()
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)
        def do_GET(self):
            state["calls"].append(("GET", self.path, self.headers.get("Authorization"), self.headers.get("Host")))
            if self.path.startswith("/redirect"):
                self.send_response(302)
                self.send_header("Location", "/api")
                self.send_header("Content-Length", "0")
                self.end_headers()
            else:
                self.send_json({"ok": True, "echo": state["secret"]}, state["status"])
        def do_POST(self):
            body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            state["calls"].append(("POST", self.path, body, self.headers.get("Authorization")))
            if self.path != "/mcp":
                self.send_json({"body": body}, state["status"])
                return
            method = body.get("method")
            if "id" not in body:
                self.send_json({}, 202)
                return
            if method == "initialize":
                result = {"protocolVersion": "2025-11-25", "capabilities": {"tools": {}}, "serverInfo": {"name": "tcp-test", "version": "1"}}
            elif method == "tools/list":
                result = {"tools": [{"name": "echo", "description": "TCP echo", "inputSchema": {"type": "object", "properties": {"text": {"type": "string", "minLength": 2}}, "required": state["required"], "additionalProperties": False}}]}
            elif method == "tools/call":
                result = {"content": [{"type": "text", "text": body["params"]["arguments"]["text"] + state["secret"]}], "isError": state["status"] != 200}
            else:
                self.send_json({"jsonrpc": "2.0", "id": body["id"], "error": {"code": -32601, "message": "Unsupported"}})
                return
            self.send_json({"jsonrpc": "2.0", "id": body["id"], "result": result})
    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{server.server_port}", state
    server.shutdown()
    server.server_close()


@pytest.fixture
def client(tmp_path, monkeypatch):
    store = {}
    class Keyring:
        def set_password(self, namespace, key, value): store[(namespace, key)] = value
        def get_password(self, namespace, key): return store.get((namespace, key))
        def delete_password(self, namespace, key): del store[(namespace, key)]
    monkeypatch.setattr(service, "_secure_keyring", lambda: Keyring())
    manager = service.ConnectionService(tmp_path / "registry.json", tmp_path / "evidence")
    app = FastAPI()
    app.include_router(create_connection_router(manager))
    return TestClient(app), manager, store


def create(client, remote, **overrides):
    browser = client[0]
    response = browser.post("/api/connections", json={"name": "TCP test", "kind": "http_api", "url": remote[0] + "/api", "allow_private": True, **overrides})
    assert response.status_code == 200, response.text
    return response.json()


def discover(client, connection):
    response = client[0].post(f"/api/connections/{connection['id']}/discover", json={"confirmed": True})
    assert response.status_code == 200, response.text
    return response.json()["tools"][0]


def invoke(client, connection, tool, **overrides):
    response = client[0].post(f"/api/connections/{connection['id']}/invoke", json={"tool_name": tool["name"], "arguments": {}, "effect": "READ", "tool_fingerprint": tool["fingerprint"], "confirmed": True, **overrides})
    assert response.status_code == 200, response.text
    return response.json()


def test_http_get_observed_receipt_and_credentials_write_only(client, remote):
    remote[1]["secret"] = "secret-value-123"
    connection = create(client, remote, auth_mode="bearer", credential=remote[1]["secret"])
    assert connection["state"] == "configured"
    assert remote[1]["calls"] == []
    tool = discover(client, connection)
    assert remote[1]["calls"] == []  # API descriptor is not a connectivity probe.
    result = invoke(client, connection, tool, arguments={"q": "hello"})
    assert result["execution_outcome"] == "SUCCESS"
    assert result["actual_effect"] == {"called": True}
    assert remote[1]["calls"][0][2] == "Bearer secret-value-123"
    evidence = Path(result["evidence"]["path"]).read_bytes()
    assert hashlib.sha256(evidence).hexdigest() == result["evidence"]["sha256"]
    assert b"secret-value-123" not in evidence
    assert "secret-value-123" not in json.dumps(result)
    assert "secret-value-123" not in client[1].registry_path.read_text()
    assert "secret-value-123" not in client[0].get("/api/connections").text
    assert client[0].delete(f"/api/connections/{connection['id']}").json() == {"deleted": True}
    assert client[2] == {}


def test_confirmation_and_stale_fingerprint_never_start_transport(client, remote):
    connection = create(client, remote)
    denied = client[0].post(f"/api/connections/{connection['id']}/discover", json={"confirmed": False})
    assert denied.status_code == 403
    tool = discover(client, connection)
    for overrides in ({"confirmed": False}, {"tool_fingerprint": "stale"}, {"arguments": {"nested": {"x": 1}}}):
        result = invoke(client, connection, tool, **overrides)
        assert result["execution_outcome"] == "DENIED"
        assert result["actual_effect"]["called"] is False
        assert Path(result["evidence"]["path"]).exists()
    assert remote[1]["calls"] == []


def test_http_post_cannot_be_downgraded(client, remote):
    connection = create(client, remote, method="POST")
    tool = discover(client, connection)
    assert invoke(client, connection, tool)["execution_outcome"] == "DENIED"
    assert remote[1]["calls"] == []
    result = invoke(client, connection, tool, effect="WRITE", arguments={"payload": [1, 2]})
    assert result["execution_outcome"] == "SUCCESS"
    assert remote[1]["calls"][0][2] == {"payload": [1, 2]}


@pytest.mark.parametrize("path,status", [("/api", 503), ("/redirect", 200)])
def test_transport_failure_never_success(client, remote, path, status):
    remote[1]["status"] = status
    connection = create(client, remote, url=remote[0] + path)
    result = invoke(client, connection, discover(client, connection))
    assert result["execution_outcome"] == "ERROR"
    assert result["actual_effect"]["called"] is True
    assert len(remote[1]["calls"]) == 1


def test_real_mcp_http_discover_validate_reconnect_and_call(client, remote):
    connection = create(client, remote, kind="mcp", url=remote[0] + "/mcp")
    tool = discover(client, connection)
    assert not any(c[2].get("method") == "tools/call" for c in remote[1]["calls"])
    count = len(remote[1]["calls"])
    invalid = invoke(client, connection, tool, arguments={"text": "x"})
    assert invalid["execution_outcome"] == "DENIED"
    assert len(remote[1]["calls"]) == count
    result = invoke(client, connection, tool, arguments={"text": "hello"})
    assert result["execution_outcome"] == "SUCCESS", result
    assert sum(c[2].get("method") == "tools/list" for c in remote[1]["calls"]) == 2
    assert sum(c[2].get("method") == "tools/call" for c in remote[1]["calls"]) == 1
    remote[1]["required"] = []
    stale = invoke(client, connection, tool, arguments={"text": "hello"})
    assert stale["error"]["code"] == "stale_tool"
    assert stale["actual_effect"]["called"] is False
    assert sum(c[2].get("method") == "tools/call" for c in remote[1]["calls"]) == 1


@pytest.mark.parametrize("url,private", [
    ("http://example.com/api", False), ("https://169.254.169.254/latest", True),
    ("http://0.0.0.0/api", True), ("https://[::1]/api", False),
    ("https://user:password@example.com", False), ("https://example.com/api?token=secret", False),
    ("https://example.com/#fragment", False), ("http://224.0.0.1/api", True)])
def test_disallowed_destinations(client, url, private):
    response = client[0].post("/api/connections", json={"name": "bad", "kind": "mcp", "url": url, "allow_private": private})
    assert response.status_code == 422
    assert set(response.json()["detail"]) == {"code", "message"}


def test_docker_has_fixed_no_shell_command_and_no_browser_origin(client, monkeypatch):
    monkeypatch.setattr(transports.shutil, "which", lambda _: "C:/Docker/docker.exe")
    executable, args = transports.docker_command("profile")
    assert executable == "C:/Docker/docker.exe"
    assert args == ["mcp", "gateway", "run", "--profile", "profile", "--watch=false", "--log-calls=false"]
    for profile in ("--dangerous", "x; calc", "../profile"):
        assert client[0].post("/api/connections", json={"name": "bad", "kind": "docker_mcp", "profile": profile}).status_code == 422
    assert client[0].post("/api/connections", headers={"Origin": "https://evil.example"}, json={}).status_code == 403


def test_strict_boolean_validation_and_body_bounds(client):
    response = client[0].post("/api/connections", json={"name": "bad", "kind": "mcp", "url": "https://example.com", "allow_private": "true", "credential": "SECRET"})
    assert response.status_code == 422
    assert "SECRET" not in response.text
    response = client[0].post("/api/connections", content="x" * (81 * 1024))
    assert response.status_code == 413


def test_mcp_error_and_secret_echo_are_not_success_or_leaked(client, remote):
    remote[1]["secret"] = "mcp-secret-123"
    connection = create(client, remote, kind="mcp", url=remote[0] + "/mcp", auth_mode="bearer", credential=remote[1]["secret"])
    tool = discover(client, connection)
    result = invoke(client, connection, tool, arguments={"text": "hello"})
    assert result["execution_outcome"] == "SUCCESS"
    assert "mcp-secret-123" not in json.dumps(result)
    assert "mcp-secret-123" not in Path(result["evidence"]["path"]).read_text()
    remote[1]["status"] = 500
    result = invoke(client, connection, tool, arguments={"text": "hello"})
    assert result["execution_outcome"] == "ERROR"
    assert result["actual_effect"]["called"] is True


def test_pinned_destination_does_not_repeat_dns_at_connect(client, remote, monkeypatch):
    # The configured logical hostname remains Host; HTTPX gets a literal peer.
    original = security.resolve_target
    resolved = []
    async def resolver(url, allow_private):
        resolved.append(url)
        return "127.0.0.1"
    monkeypatch.setattr(security, "resolve_target", resolver)
    url = remote[0].replace("127.0.0.1", "logical.test") + "/api"
    connection = create(client, remote, url=url)
    result = invoke(client, connection, discover(client, connection))
    assert result["execution_outcome"] == "SUCCESS"
    assert len(resolved) == 1
    assert remote[1]["calls"][0][3].startswith("logical.test:")


def test_dns_rebinding_to_metadata_denied_before_peer_connect(monkeypatch):
    loop = None
    async def run():
        async def answer(*args, **kwargs):
            return [(2, 1, 6, "", ("169.254.169.254", 443))]
        monkeypatch.setattr(asyncio.get_running_loop(), "getaddrinfo", answer)
        with pytest.raises(security.ConnectionError, match="destino"):
            await security.resolve_target("https://rebinding.test/mcp", True)
    asyncio.run(run())


def test_docker_preflight_denies_missing_and_mutable_images(monkeypatch):
    from types import SimpleNamespace
    image = "mcp/test@sha256:" + "a" * 64
    calls = []
    def run(args, **kwargs):
        calls.append(args)
        if args[1:3] == ["mcp", "profile"]:
            return SimpleNamespace(stdout=json.dumps({"servers": [{"snapshot": {"server": {"image": image}}}]}).encode(), returncode=0)
        return SimpleNamespace(returncode=1)
    monkeypatch.setattr(transports.subprocess, "run", run)
    with pytest.raises(security.ConnectionError) as error:
        transports.docker_preflight("docker", "profile")
    assert error.value.code == "docker_image_missing"
    assert len(calls) == 2
    image = "mcp/test:latest"
    calls.clear()
    with pytest.raises(security.ConnectionError) as error:
        transports.docker_preflight("docker", "profile")
    assert error.value.code == "docker_profile_unsupported"
    assert len(calls) == 1


def test_receipt_mismatch_and_expired_permit_fail_closed(client, remote, monkeypatch):
    from dataclasses import replace
    from src.adapters.mcp_adapter import GovernedMCPAdapter
    connection = create(client, remote)
    tool = discover(client, connection)
    original = GovernedMCPAdapter.call
    async def mismatched(self, session, request, permit):
        receipt = await original(self, session, request, permit)
        return replace(receipt, request_id="unrelated-request")
    monkeypatch.setattr(GovernedMCPAdapter, "call", mismatched)
    result = invoke(client, connection, tool)
    assert result["execution_outcome"] == "ERROR"
    assert result["error"]["code"] == "receipt_mismatch"
    monkeypatch.setattr(GovernedMCPAdapter, "call", original)
    authorize = GovernedMCPAdapter.authorize
    def expired(self, request, **kwargs):
        return replace(authorize(self, request, **kwargs), expires_at="2000-01-01T00:00:00+00:00")
    monkeypatch.setattr(GovernedMCPAdapter, "authorize", expired)
    before = len(remote[1]["calls"])
    result = invoke(client, connection, tool)
    assert result["execution_outcome"] != "SUCCESS"
    assert result["actual_effect"]["called"] is False
    assert len(remote[1]["calls"]) == before


def test_response_bounds_are_enforced():
    import httpx
    class Chunks(httpx.AsyncByteStream):
        async def __aiter__(self):
            yield b"x" * (security.MAX_RESPONSE + 1)
        async def aclose(self): pass
    async def run():
        with pytest.raises(security.ConnectionError) as error:
            async for _ in security.BoundedStream(Chunks()): pass
        assert error.value.code == "response_too_large"
    asyncio.run(run())


def test_bounded_stdio_uses_sdk_session_with_real_repository_fixture():
    import os
    import sys
    from mcp import ClientSession
    fixture = Path(__file__).resolve().parents[1] / "scripts/local_mcp_server.py"
    async def run():
        async with transports.bounded_stdio(sys.executable, [str(fixture)], dict(os.environ)) as (reader, writer):
            async with ClientSession(reader, writer) as session:
                await session.initialize()
                tools = await session.list_tools()
                assert {t.name for t in tools.tools} == {"get_lab_status", "propose_lab_note"}
                result = await session.call_tool("get_lab_status", {})
                assert result.isError is False
    asyncio.run(run())


def test_bounded_stdio_rejects_oversized_wire_frame_before_parse():
    import os
    import sys
    async def run():
        async with transports.bounded_stdio(sys.executable, ["-c", "import sys;sys.stdout.write('x'*2200000+'\\n');sys.stdout.flush()"], dict(os.environ)) as (reader, writer):
            response = await asyncio.wait_for(reader.receive(), 5)
            assert isinstance(response, security.ConnectionError)
            assert response.code == "stdio_invalid_response"
    asyncio.run(run())


def test_server_exposes_connection_registry_without_external_request(monkeypatch):
    from src.api import server
    monkeypatch.setattr(service.ConnectionService, "all", lambda self: {"connections": []})
    response = TestClient(server.app).get("/api/connections")
    assert response.status_code == 200
    assert response.json() == {"connections": []}


def test_server_connection_validation_never_echoes_submitted_secret():
    from src.api import server
    response = TestClient(server.app).post("/api/connections", json={"kind": "arbitrary-command", "credential": "secret-do-not-echo"})
    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "invalid_request"
    assert "secret-do-not-echo" not in response.text
