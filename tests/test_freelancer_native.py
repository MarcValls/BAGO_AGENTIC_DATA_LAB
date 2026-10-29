"""Candidate-bound account, authorization and privacy regression cases."""
import json
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.api.connection_routes import create_connection_router
from src.connections import service as connection_service
from src.connections import freelancer_readonly
from src.connections.freelancer_authorization import FreelancerAuthorizationError, FreelancerReadChallenges


class FakeKeyring:
    def __init__(self):
        self.values = {}

    def set_password(self, namespace, key, value):
        self.values[(namespace, key)] = value

    def get_password(self, namespace, key):
        return self.values.get((namespace, key))

    def delete_password(self, namespace, key):
        self.values.pop((namespace, key), None)


class FakeFreelancerAdapter:
    calls = []
    on_read = None

    def __init__(self, token, *, environment):
        assert token == "test-oauth-secret"
        self.environment = environment

    async def read(self, operation, arguments):
        self.calls.append((self.environment, operation, arguments))
        if type(self).on_read:
            type(self).on_read(operation)
        if operation == "account.read":
            return {"data": {"id": 42, "username": "ada"}}
        if operation == "messages.read":
            return {"operation": operation, "environment": self.environment,
                    "data": {"messages": [{"id": 9, "thread_id": arguments["thread_id"],
                                             "message": "PRIVATE-BODY-MUST-NOT-PERSIST"}]},
                    "untrusted_remote_data": True}
        return {"operation": operation, "environment": self.environment,
                "data": {"projects": [{"id": 123, "title": "Example"}]},
                "untrusted_remote_data": True}


@pytest.fixture
def native(tmp_path, monkeypatch):
    keyring = FakeKeyring()
    monkeypatch.setattr(connection_service, "_secure_keyring", lambda: keyring)
    monkeypatch.setattr(freelancer_readonly, "FreelancerReadAdapter", FakeFreelancerAdapter)
    FakeFreelancerAdapter.calls = []
    FakeFreelancerAdapter.on_read = None
    manager = connection_service.ConnectionService(tmp_path / "registry.json", tmp_path / "receipts")
    latest = {"id": "conversation-1", "owner_kind": "assistant", "owner_id": "app-assistant",
              "revision": 4, "status": "active"}

    def owned(conversation_id, owner_kind, owner_id):
        if (conversation_id, owner_kind, owner_id) != (latest["id"], latest["owner_kind"], latest["owner_id"]):
            from fastapi import HTTPException
            raise HTTPException(404, "conversation_not_found")
        return dict(latest)

    app = FastAPI()
    app.state.gex_trusted_origins = ("http://testserver",)
    app.include_router(create_connection_router(manager, owned_conversation=owned,
                                                 freelancer_challenges=FreelancerReadChallenges()))
    yield TestClient(app), manager, keyring, latest


def browser_post(client, path, payload=None):
    return client.post(path, json=payload or {}, headers={"Origin": "http://testserver"})


def connected(native):
    client = native[0]
    response = browser_post(client, "/api/connections/freelancer", {
        "name": "Personal sandbox", "environment": "sandbox", "credential": "test-oauth-secret"})
    assert response.status_code == 200, response.text
    item = response.json()
    assert "test-oauth-secret" not in response.text
    assert item["state"] == "configured_unverified"
    verified = browser_post(client, f"/api/connections/freelancer/{item['id']}/verify")
    assert verified.status_code == 200, verified.text
    assert verified.json()["state"] == "connected"
    assert verified.json()["account_id"] == 42
    return item["id"]


def test_account_link_uses_keyring_and_is_write_only(native):
    client, manager, keyring, _ = native
    response = browser_post(client, "/api/connections/freelancer", {
        "name": "Personal sandbox", "environment": "sandbox", "credential": "test-oauth-secret"})
    assert response.status_code == 200
    connection = response.json()
    assert connection["state"] == "configured_unverified"
    assert connection["has_credential"] is True
    assert "credential" not in connection and "token" not in connection
    assert "test-oauth-secret" not in response.text
    assert keyring.values
    assert "test-oauth-secret" not in manager.registry_path.read_text(encoding="utf-8")
    assert "test-oauth-secret" not in client.get("/api/connections/freelancer").text
    assert client.get("/api/connections/freelancer").headers["cache-control"] == "no-store, private"
    assert client.get("/api/connections").json()["connections"] == []


def test_private_message_read_requires_challenge_is_single_use_and_leaves_metadata_only(native):
    client, manager, _, _ = native
    identifier = connected(native)
    challenge = browser_post(client, f"/api/connections/freelancer/{identifier}/challenge", {
        "conversation_id": "conversation-1", "conversation_revision": 4,
        "operation": "messages.read", "arguments": {"thread_id": 5, "limit": 10}})
    assert challenge.status_code == 200, challenge.text
    assert challenge.json()["operation"] == "messages.read"
    payload = {"challenge_id": challenge.json()["challenge_id"],
               "conversation_id": "conversation-1", "conversation_revision": 4}
    result = browser_post(client, f"/api/connections/freelancer/{identifier}/read", payload)
    assert result.status_code == 200, result.text
    assert result.headers["cache-control"] == "no-store, private"
    assert result.json()["data"]["messages"][0]["message"] == "PRIVATE-BODY-MUST-NOT-PERSIST"
    assert result.json()["receipt"]["operation"] == "messages.read"
    assert "PRIVATE-BODY-MUST-NOT-PERSIST" not in json.dumps(result.json()["receipt"])
    assert "PRIVATE-BODY-MUST-NOT-PERSIST" not in manager.registry_path.read_text(encoding="utf-8")
    receipt_files = list((manager.evidence_dir).glob("*.json"))
    assert len(receipt_files) == 1
    assert "PRIVATE-BODY-MUST-NOT-PERSIST" not in receipt_files[0].read_text(encoding="utf-8")
    replay = browser_post(client, f"/api/connections/freelancer/{identifier}/read", payload)
    assert replay.status_code == 403
    assert len([call for call in FakeFreelancerAdapter.calls if call[1] == "messages.read"]) == 1


def test_origin_owner_revision_and_environment_are_bound(native):
    client, _, _, latest = native
    identifier = connected(native)
    body = {"conversation_id": latest["id"], "conversation_revision": 4,
            "operation": "projects.search", "arguments": {"query": "data", "limit": 2}}
    assert client.post(f"/api/connections/freelancer/{identifier}/challenge", json=body).status_code == 403
    wrong_conversation = {**body, "conversation_id": "other"}
    assert browser_post(client, f"/api/connections/freelancer/{identifier}/challenge", wrong_conversation).status_code == 404
    stale = {**body, "conversation_revision": 3}
    assert browser_post(client, f"/api/connections/freelancer/{identifier}/challenge", stale).status_code == 409
    challenge = browser_post(client, f"/api/connections/freelancer/{identifier}/challenge", body).json()
    latest["revision"] = 5
    wrong_revision_read = browser_post(client, f"/api/connections/freelancer/{identifier}/read", {
        "challenge_id": challenge["challenge_id"], "conversation_id": latest["id"], "conversation_revision": 4})
    assert wrong_revision_read.status_code == 409
    assert not any(call[1] == "projects.search" for call in FakeFreelancerAdapter.calls)


def test_generic_invoke_cannot_dispatch_freelancer_and_disconnect_revokes_local_secret(native):
    client, _, keyring, _ = native
    identifier = connected(native)
    response = browser_post(client, f"/api/connections/{identifier}/invoke", {
        "tool_name": "messages.read", "arguments": {"thread_id": 5}, "effect": "READ",
        "tool_fingerprint": "x", "confirmed": True})
    assert response.status_code == 403
    deleted = client.delete(f"/api/connections/freelancer/{identifier}", headers={"Origin": "http://testserver"})
    assert deleted.status_code == 200
    assert all(identifier not in key for _, key in keyring.values)
    assert client.get("/api/connections/freelancer").json()["connections"] == []


def test_switching_chat_during_remote_read_discards_private_response(native):
    client, manager, _, latest = native
    identifier = connected(native)
    challenge = browser_post(client, f"/api/connections/freelancer/{identifier}/challenge", {
        "conversation_id": latest["id"], "conversation_revision": latest["revision"],
        "operation": "messages.read", "arguments": {"thread_id": 5}}).json()
    FakeFreelancerAdapter.on_read = lambda operation: latest.update(revision=latest["revision"] + 1) if operation == "messages.read" else None
    response = browser_post(client, f"/api/connections/freelancer/{identifier}/read", {
        "challenge_id": challenge["challenge_id"], "conversation_id": latest["id"], "conversation_revision": 4})
    assert response.status_code == 409
    assert "PRIVATE-BODY-MUST-NOT-PERSIST" not in response.text
    receipt = next(manager.evidence_dir.glob("*.json"))
    assert "PRIVATE-BODY-MUST-NOT-PERSIST" not in receipt.read_text(encoding="utf-8")


def test_challenge_expires_and_cannot_be_replayed():
    clock = [10.0]
    challenges = FreelancerReadChallenges(clock=lambda: clock[0])
    binding = {"connection_id": "conn-a", "connection_revision": "rev-a",
               "environment": "sandbox", "account_id": 42, "conversation_id": "chat-a",
               "conversation_revision": 9}
    challenge = challenges.issue(**binding, operation="project.read", arguments={"project_id": 77})
    clock[0] += 91
    with pytest.raises(FreelancerAuthorizationError, match="authorization_expired"):
        challenges.consume(challenge["challenge_id"], **binding)

    challenge = challenges.issue(**binding, operation="project.read", arguments={"project_id": 77})
    consumed = challenges.consume(challenge["challenge_id"], **binding)
    assert consumed == {"operation": "project.read", "arguments": {"project_id": 77}}
    with pytest.raises(FreelancerAuthorizationError, match="authorization_expired"):
        challenges.consume(challenge["challenge_id"], **binding)
