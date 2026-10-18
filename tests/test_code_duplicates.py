from __future__ import annotations

from pathlib import Path
import asyncio

from src.agent_tools.code_duplicates import (
    WORKSPACE_DIRECTORY_AUTHORIZATIONS,
    scan_code_duplicates,
    validate_workspace_scan_directories,
)
from src.agent_tools import code_duplicates
from fastapi.testclient import TestClient
from src.api import server
from src.conversations import ConversationStore


def test_scan_finds_exact_blocks_and_similar_python_functions(tmp_path: Path) -> None:
    source = tmp_path / "src"
    source.mkdir()
    (source / "one.py").write_text(
        "def first(value):\n    result = value + 3\n    if result > 4:\n        result = result * 2\n    return result\n\n"
        "alpha = 1\nbeta = 2\ngamma = 3\ndelta = 4\nepsilon = 5\n",
        encoding="utf-8",
    )
    (source / "two.py").write_text(
        "def second(item):\n    output = item + 8\n    if output > 9:\n        output = output * 4\n    return output\n\n"
        "alpha = 1\nbeta = 2\ngamma = 3\ndelta = 4\nepsilon = 5\n",
        encoding="utf-8",
    )

    result, receipt = scan_code_duplicates(tmp_path, {"directory": "src"}, ["src"])

    assert result["ok"] is True
    assert result["files_scanned"] == 2
    assert result["finding_count"] >= 2
    assert {finding["kind"] for finding in result["findings"]} == {
        "exact_block", "similar_python_function_structure",
    }
    assert receipt["decision"] == "ALLOW"
    assert len(receipt["manifest_sha256"]) == 64
    assert "content" not in result


def test_scan_requires_exact_directory_authorization(tmp_path: Path) -> None:
    (tmp_path / "src").mkdir()

    result, receipt = scan_code_duplicates(tmp_path, {"directory": "src"}, [])

    assert result["ok"] is False
    assert receipt["reason_code"] == "DIRECTORY_NOT_AUTHORIZED"


def test_scan_directory_validation_rejects_escape_and_blocked_paths(tmp_path: Path) -> None:
    (tmp_path / "src").mkdir()
    (tmp_path / ".git").mkdir()

    for requested in ("../outside", ".git"):
        try:
            validate_workspace_scan_directories(tmp_path, [requested])
        except ValueError:
            pass
        else:
            raise AssertionError(f"unsafe directory was accepted: {requested}")


def test_scan_marks_results_truncated_at_file_cap(monkeypatch, tmp_path: Path) -> None:
    source = tmp_path / "src"
    source.mkdir()
    (source / "a.js").write_text("const a = 1;\n", encoding="utf-8")
    (source / "b.ts").write_text("const b = 2;\n", encoding="utf-8")
    monkeypatch.setattr(code_duplicates, "MAX_SCAN_FILES", 1)

    result, receipt = scan_code_duplicates(tmp_path, {"directory": "src"}, ["src"])

    assert result["files_scanned"] == 1
    assert result["truncated"] is True
    assert receipt["truncated"] is True


def test_directory_authorization_is_bound_to_owner_revision_and_single_use(tmp_path: Path) -> None:
    (tmp_path / "src").mkdir()
    grant = WORKSPACE_DIRECTORY_AUTHORIZATIONS.issue(
        tmp_path, owner_kind="agent", owner_id="agent-a", conversation_id="conv-a",
        revision=3, directories=["src"],
    )
    token = grant["authorization_id"]

    assert WORKSPACE_DIRECTORY_AUTHORIZATIONS.consume(
        token, owner_kind="agent", owner_id="other-agent", conversation_id="conv-a", revision=3,
    ) is None
    assert WORKSPACE_DIRECTORY_AUTHORIZATIONS.consume(
        token, owner_kind="agent", owner_id="agent-a", conversation_id="conv-a", revision=3,
    ) == ["src"]
    assert WORKSPACE_DIRECTORY_AUTHORIZATIONS.consume(
        token, owner_kind="agent", owner_id="agent-a", conversation_id="conv-a", revision=3,
    ) is None


def test_chat_tool_loop_invokes_scan_and_returns_receipt(monkeypatch, tmp_path: Path) -> None:
    source = tmp_path / "src"
    source.mkdir()
    (source / "one.py").write_text("a = 1\nb = 2\nc = 3\nd = 4\ne = 5\n", encoding="utf-8")
    (source / "two.py").write_text("a = 1\nb = 2\nc = 3\nd = 4\ne = 5\n", encoding="utf-8")
    monkeypatch.setattr(server, "REPO_ROOT", tmp_path)
    turns = iter([
        {"tool_calls": [{"function": {"name": "scan_code_duplicates", "arguments": {"directory": "src"}}}]},
        {"content": "I found an exact duplicate block in src/one.py and src/two.py."},
    ])
    tool_definitions: list[list[dict]] = []

    def fake_chat_turn(_model: str, _messages: list[dict], *, tools: list[dict]) -> dict:
        tool_definitions.append(tools)
        return next(turns)

    monkeypatch.setattr(server.ollama, "chat_turn", fake_chat_turn)
    answer, sources, events, navigation_view = asyncio.run(server._chat_with_workspace_read("test-model", [], [], ["src"]))

    assert "exact duplicate" in answer
    assert sources == []
    assert navigation_view is None
    assert len(tool_definitions[0]) == 2
    assert events[0]["kind"] == "directory_code_scan"
    assert events[0]["files_scanned"] == 2
    assert events[0]["finding_count"] >= 1
    assert len(events[0]["manifest_sha256"]) == 64


def test_scan_authorization_endpoint_binds_directory_to_conversation(monkeypatch, tmp_path: Path) -> None:
    (tmp_path / "src").mkdir()
    monkeypatch.setattr(server, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(server, "CONVERSATIONS", ConversationStore(tmp_path / "conversations.sqlite3"))
    conversation = server.CONVERSATIONS.create("assistant", "app-assistant")

    response = TestClient(server.app).post("/api/workspace-scan/authorizations", json={
        "owner_kind": "assistant", "owner_id": "app-assistant", "conversation_id": conversation["id"],
        "revision": conversation["revision"], "directories": ["src"],
    })

    assert response.status_code == 200
    grant = response.json()
    assert grant["directories"] == ["src"]
    assert server.WORKSPACE_DIRECTORY_AUTHORIZATIONS.consume(
        grant["authorization_id"], owner_kind="assistant", owner_id="app-assistant",
        conversation_id=conversation["id"], revision=conversation["revision"],
    ) == ["src"]


def test_control_scan_run_persists_result_receipt_and_local_trace(monkeypatch, tmp_path: Path) -> None:
    source = tmp_path / "src"
    source.mkdir()
    (source / "one.ts").write_text("const a = 1;\nconst b = 2;\nconst c = 3;\nconst d = 4;\nconst e = 5;\n", encoding="utf-8")
    (source / "two.ts").write_text("const a = 1;\nconst b = 2;\nconst c = 3;\nconst d = 4;\nconst e = 5;\n", encoding="utf-8")
    monkeypatch.setattr(server, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(server, "CONVERSATIONS", ConversationStore(tmp_path / "conversations.sqlite3"))
    conversation = server.CONVERSATIONS.create("assistant", "app-assistant")
    grant = server.WORKSPACE_DIRECTORY_AUTHORIZATIONS.issue(
        tmp_path, owner_kind="assistant", owner_id="app-assistant",
        conversation_id=conversation["id"], revision=conversation["revision"], directories=["src"],
    )

    response = TestClient(server.app).post("/api/workspace-scan/run", json={
        "conversation_id": conversation["id"], "revision": conversation["revision"],
        "authorization_id": grant["authorization_id"], "directory": "src",
    })

    assert response.status_code == 200
    payload = response.json()
    assert payload["result"]["files_scanned"] == 2
    assert payload["result"]["finding_count"] >= 1
    assert payload["receipt"]["decision"] == "ALLOW"
    assert len(payload["receipt"]["manifest_sha256"]) == 64
    assert payload["trace"]["trace_state"] == "local_only"
    assert len(payload["conversation"]["messages"]) == 2
    trace_path = tmp_path / ".bago" / "traces" / "workspace-scans" / f"{payload['trace']['trace_id']}.json"
    assert trace_path.is_file()
