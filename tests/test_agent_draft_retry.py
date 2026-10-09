import asyncio
import json

import pytest
from fastapi import HTTPException

from src.api import server


def _valid_proposal():
    return json.dumps({
        "name": "Frontend Auditor",
        "description": "Reviews user-provided frontend findings and suggests scoped fixes.",
        "type": "rag",
        "system_prompt": "Review only findings provided by the user. Separate diagnosis, proposal, and verified work.",
        "tools": [],
        "retrieval_config": None,
        "sandbox_profile": None,
    })


def test_draft_retries_invalid_json_once_and_returns_unpersisted_proposal(monkeypatch):
    outputs = iter(["Here is the agent.", _valid_proposal()])
    calls = []
    monkeypatch.setattr(server, "_selected_model_id", lambda: "gemma4:31b-cloud")
    monkeypatch.setattr(server.ollama, "chat", lambda model, messages: calls.append(messages) or next(outputs))

    response = asyncio.run(server.control_chat(server.ControlChatRequest(
        operation="draft_agent", message="Create a Frontend Auditor agent"
    )))

    assert len(calls) == 2
    assert "previous response was not valid JSON" in calls[1][0]["content"]
    assert response["created"] is False
    assert response["agent_draft"]["name"] == "Frontend Auditor"
    assert response["agent_draft"]["tools"] == []


def test_draft_rejects_invalid_proposal_after_one_retry(monkeypatch):
    calls = []
    monkeypatch.setattr(server, "_selected_model_id", lambda: "gemma4:31b-cloud")
    monkeypatch.setattr(server.ollama, "chat", lambda model, messages: calls.append(messages) or "not json")

    with pytest.raises(HTTPException) as error:
        asyncio.run(server.control_chat(server.ControlChatRequest(
            operation="draft_agent", message="Create an agent"
        )))

    assert error.value.status_code == 502
    assert error.value.detail["code"] == "invalid_agent_draft"
    assert len(calls) == 2

