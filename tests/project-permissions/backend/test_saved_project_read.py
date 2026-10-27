from __future__ import annotations

from pathlib import Path

from src.agent_tools.workspace_read import read_workspace_file
from src.project_permissions import ProjectContext, ProjectPermissions


def _grant_root_read(root: Path, *, project_id: str = "project-a", binding: str = "binding-a") -> ProjectPermissions:
    service = ProjectPermissions(lambda: ProjectContext(project_id, root, binding, "Synthetic project"))
    snapshot = service.snapshot()
    service.save(
        expected_project_id=snapshot["project_id"],
        expected_binding=snapshot["binding"],
        expected_revision=snapshot["revision"],
        read_directories=["."],
        write_directories=[],
        confirmed=True,
    )
    return service


def test_exact_read_uses_saved_project_policy_without_turn_paths(tmp_path: Path) -> None:
    root = tmp_path / "project"
    root.mkdir()
    (root / "sample_a.py").write_text("def add(a, b):\n    return a + b\n", encoding="utf-8")
    service = _grant_root_read(root)

    result, receipt = read_workspace_file(
        root,
        {"path": "sample_a.py"},
        project_permissions=service,
        expected_project=service.snapshot(),
    )

    assert result["ok"] is True
    assert "def add(a, b):" in result["content"]
    assert receipt is not None
    assert receipt["decision"] == "ALLOW"
    assert receipt["path"] == "sample_a.py"
    assert receipt["project_id"] == "project-a"
    assert receipt["policy_revision"] == service.snapshot()["revision"]


def test_one_turn_paths_do_not_override_absent_project_read_policy(tmp_path: Path) -> None:
    root = tmp_path / "project"
    root.mkdir()
    (root / "sample_a.py").write_text("private fixture content\n", encoding="utf-8")
    service = ProjectPermissions(lambda: ProjectContext("project-a", root, "binding-a"))

    result, receipt = read_workspace_file(
        root,
        {"path": "sample_a.py"},
        authorized_paths=["sample_a.py"],
        project_permissions=service,
    )

    assert result["ok"] is False
    assert "content" not in result
    assert receipt is not None and receipt["decision"] == "DENY"


def test_saved_root_read_still_blocks_protected_paths(tmp_path: Path) -> None:
    root = tmp_path / "project"
    (root / ".bago" / "state").mkdir(parents=True)
    (root / ".bago" / "state" / "PROJECT_STATE.json").write_text("synthetic protected fixture", encoding="utf-8")
    service = _grant_root_read(root)

    result, receipt = read_workspace_file(
        root,
        {"path": ".bago/state/PROJECT_STATE.json"},
        project_permissions=service,
        expected_project=service.snapshot(),
    )

    assert result["ok"] is False
    assert "content" not in result
    assert receipt is not None
    assert receipt["decision"] == "DENY"
    assert receipt["reason_code"] == "project_path_denied"


def test_project_switch_after_turn_snapshot_denies_read(tmp_path: Path) -> None:
    root_a = tmp_path / "project-a"
    root_b = tmp_path / "project-b"
    root_a.mkdir()
    root_b.mkdir()
    (root_a / "sample_a.py").write_text("project a fixture\n", encoding="utf-8")
    selected = {"context": ProjectContext("project-a", root_a, "binding-a")}
    service = ProjectPermissions(lambda: selected["context"])
    initial = service.snapshot()
    service.save(
        expected_project_id=initial["project_id"], expected_binding=initial["binding"],
        expected_revision=initial["revision"], read_directories=["."], write_directories=[], confirmed=True,
    )
    turn_snapshot = service.snapshot()
    selected["context"] = ProjectContext("project-b", root_b, "binding-b")

    result, receipt = read_workspace_file(
        root_a, {"path": "sample_a.py"}, project_permissions=service, expected_project=turn_snapshot,
    )

    assert result["ok"] is False
    assert "content" not in result
    assert receipt is not None and receipt["decision"] == "DENY"
    assert receipt["reason_code"] == "project_context_changed"


def test_revoked_policy_after_turn_snapshot_denies_read(tmp_path: Path) -> None:
    root = tmp_path / "project"
    root.mkdir()
    (root / "sample_a.py").write_text("synthetic fixture\n", encoding="utf-8")
    service = _grant_root_read(root)
    turn_snapshot = service.snapshot()
    service.revoke(
        expected_project_id=turn_snapshot["project_id"],
        expected_binding=turn_snapshot["binding"],
        expected_revision=turn_snapshot["revision"],
        confirmed=True,
    )

    result, receipt = read_workspace_file(
        root, {"path": "sample_a.py"}, project_permissions=service, expected_project=turn_snapshot,
    )

    assert result["ok"] is False
    assert "content" not in result
    assert receipt is not None and receipt["decision"] == "DENY"
    assert receipt["reason_code"] == "revision_conflict"
