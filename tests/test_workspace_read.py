from pathlib import Path

from src.agent_tools.workspace_read import MAX_FILE_BYTES, read_workspace_file


def test_workspace_reader_can_inspect_a_bounded_range_in_a_source_file_over_32k(tmp_path: Path):
    target = tmp_path / "large_source.py"
    target.write_text("".join(f"line {number}: source text\n" for number in range(1, 5000)), encoding="utf-8")
    assert 32 * 1024 < target.stat().st_size <= MAX_FILE_BYTES

    result, receipt = read_workspace_file(tmp_path, {"path": "large_source.py", "start_line": 400, "end_line": 402})

    assert result["ok"] is True
    assert result["content"].splitlines() == ["400: line 400: source text", "401: line 401: source text", "402: line 402: source text"]
    assert receipt == {"path": "large_source.py", "start_line": 400, "end_line": 402}


def test_workspace_reader_keeps_large_file_cap_and_rejects_oversized_input(tmp_path: Path):
    target = tmp_path / "oversized_source.py"
    target.write_bytes(b"x" * (MAX_FILE_BYTES + 1))

    result, receipt = read_workspace_file(tmp_path, {"path": "oversized_source.py", "start_line": 1, "end_line": 1})

    assert result["ok"] is False
    assert "larger than" in result["error"]
    assert receipt is None
