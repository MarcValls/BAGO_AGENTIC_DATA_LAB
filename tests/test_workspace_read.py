from pathlib import Path

import hashlib

from src.agent_tools.workspace_read import MAX_FILE_BYTES, read_workspace_file, validate_workspace_read_paths


def test_workspace_reader_can_inspect_a_bounded_range_in_a_source_file_over_32k(tmp_path: Path):
    target = tmp_path / "large_source.py"
    target.write_text("".join(f"line {number}: source text\n" for number in range(1, 5000)), encoding="utf-8")
    assert 32 * 1024 < target.stat().st_size <= MAX_FILE_BYTES

    result, receipt = read_workspace_file(tmp_path, {"path": "large_source.py", "start_line": 400, "end_line": 402}, ["large_source.py"])

    assert result["ok"] is True
    assert result["total_lines"] == 4999
    assert receipt["total_lines"] == 4999
    assert receipt["truncated"] is True
    assert result["content"].splitlines() == ["400: line 400: source text", "401: line 401: source text", "402: line 402: source text"]
    assert receipt["path"] == "large_source.py"
    assert receipt["decision"] == "ALLOW"
    assert receipt["file_sha256"] == hashlib.sha256(target.read_bytes()).hexdigest()
    assert receipt["content_sha256"] == hashlib.sha256(result["content"].encode()).hexdigest()


def test_workspace_reader_keeps_large_file_cap_and_rejects_oversized_input(tmp_path: Path):
    target = tmp_path / "oversized_source.py"
    target.write_bytes(b"x" * (MAX_FILE_BYTES + 1))

    result, receipt = read_workspace_file(tmp_path, {"path": "oversized_source.py", "start_line": 1, "end_line": 1}, ["oversized_source.py"])

    assert result["ok"] is False
    assert "larger than" in result["error"]
    assert receipt["decision"] == "DENY"
    assert receipt["reason_code"] == "FILE_SIZE_LIMIT"


def test_workspace_reader_denies_path_outside_exact_permit(tmp_path: Path):
    (tmp_path / "allowed.txt").write_text("allowed content", encoding="utf-8")
    (tmp_path / "other.txt").write_text("must never reach model", encoding="utf-8")
    allowed = validate_workspace_read_paths(tmp_path, ["allowed.txt"])

    result, receipt = read_workspace_file(tmp_path, {"path": "other.txt"}, allowed)

    assert result["ok"] is False
    assert "must never reach model" not in str(result)
    assert receipt["decision"] == "DENY"
    assert receipt["reason_code"] == "PATH_NOT_AUTHORIZED"


def test_workspace_read_authorization_is_bound_and_single_use(tmp_path: Path):
    from src.agent_tools.workspace_read import WorkspaceReadAuthorizations

    (tmp_path / "allowed.txt").write_text("safe", encoding="utf-8")
    grants = WorkspaceReadAuthorizations()
    permit = grants.issue(tmp_path, owner_kind="agent", owner_id="agent-1", conversation_id="conv-1", revision=2, paths=["allowed.txt"])
    token = permit["authorization_id"]

    assert grants.consume(token, owner_kind="agent", owner_id="agent-2", conversation_id="conv-1", revision=2) is None
    assert grants.consume(token, owner_kind="agent", owner_id="agent-1", conversation_id="conv-1", revision=2) == ["allowed.txt"]
    assert grants.consume(token, owner_kind="agent", owner_id="agent-1", conversation_id="conv-1", revision=2) is None
    valid = grants.issue(tmp_path, owner_kind="agent", owner_id="agent-1", conversation_id="conv-1", revision=2, paths=["allowed.txt"])
    assert grants.consume(valid["authorization_id"], owner_kind="agent", owner_id="agent-1", conversation_id="conv-1", revision=2) == ["allowed.txt"]
    assert grants.consume(valid["authorization_id"], owner_kind="agent", owner_id="agent-1", conversation_id="conv-1", revision=2) is None
