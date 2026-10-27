from __future__ import annotations

import os
import json
import multiprocessing
import subprocess
import tempfile
import threading
import time
from concurrent.futures import ThreadPoolExecutor
import hashlib
from pathlib import Path

import pytest

from src.project_permissions import PermissionError, ProjectContext, ProjectPermissions
from src import project_permissions as permission_module


def _child_read_lease(root_text: str, entered, release, results) -> None:
    root = Path(root_text)
    service = ProjectPermissions(lambda: ProjectContext("project-a", root, "selection-1"))
    try:
        with service.lease("read", ("record.txt",)):
            entered.set()
            if not release.wait(10):
                raise TimeoutError("parent did not release bounded lease")
        results.put("lease:PASS")
    except BaseException as error:
        results.put("lease:FAIL:" + type(error).__name__)


def _child_revoke(root_text: str, revision: str, started, done, results) -> None:
    root = Path(root_text)
    service = ProjectPermissions(lambda: ProjectContext("project-a", root, "selection-1"))
    try:
        started.set()
        service.revoke(expected_project_id="project-a", expected_binding="selection-1",
                       expected_revision=revision, confirmed=True)
        results.put("revoke:PASS")
    except BaseException as error:
        results.put("revoke:FAIL:" + type(error).__name__)
    finally:
        done.set()


def service(root: Path, *, project_id: str = "project-a", binding: str = "selection-1") -> ProjectPermissions:
    return ProjectPermissions(lambda: ProjectContext(project_id, root, binding, "Project A"), clock=lambda: 1_800_000_000)


def save_all(svc: ProjectPermissions, *, read=(), write=(".",)) -> dict:
    current = svc.snapshot()
    return svc.save(expected_project_id=current["project_id"], expected_binding=current["binding"],
                    expected_revision=current["revision"], read_directories=read,
                    write_directories=write, confirmed=True)


def test_snapshot_and_denied_lease_do_not_create_policy_state(tmp_path: Path) -> None:
    root = tmp_path / "project"
    root.mkdir()
    svc = service(root)

    assert svc.snapshot()["state"] == "unconfigured"
    with pytest.raises(PermissionError) as denied:
        with svc.lease("read", ("notes.txt",)):
            pytest.fail("unconfigured project must not yield a lease")
    assert denied.value.code == "permission_denied"
    assert not (root / ".bago").exists()


def test_explicit_save_read_write_and_revoke_change_revision(tmp_path: Path) -> None:
    root = tmp_path / "project"
    (root / "docs").mkdir(parents=True)
    (root / "outputs").mkdir()
    svc = service(root)

    granted = save_all(svc, read=("docs",), write=("outputs",))
    assert granted["state"] == "configured"
    assert granted["read_directories"] == ["docs"]
    assert granted["write_directories"] == ["outputs"]
    assert (root / ".bago/state/PROJECT_PERMISSIONS.json").is_file()

    (root / "docs/report.txt").write_text("readable", encoding="utf-8")
    with svc.lease("read", ("docs/report.txt",)) as lease:
        assert lease["revision"] == granted["revision"]
    with svc.lease("write", ("outputs/result.txt",)):
        pass
    with pytest.raises(PermissionError):
        with svc.lease("write", ("docs/report.txt",)):
            pytest.fail("READ must not implicitly grant WRITE")

    revoked = svc.revoke(expected_project_id=granted["project_id"], expected_binding=granted["binding"],
                         expected_revision=granted["revision"], confirmed=True)
    assert revoked["state"] == "configured"
    assert revoked["read_directories"] == []
    assert revoked["write_directories"] == []
    assert revoked["revision"] != granted["revision"]


def test_stale_revision_and_context_binding_fail_closed(tmp_path: Path) -> None:
    root = tmp_path / "project"
    other_root = tmp_path / "other-project"
    root.mkdir()
    other_root.mkdir()
    current = {"context": ProjectContext("project-a", root, "binding-a")}
    svc = ProjectPermissions(lambda: current["context"])
    initial = svc.snapshot()
    first = svc.save(expected_project_id="project-a", expected_binding="binding-a", expected_revision="none",
                     read_directories=(), write_directories=(".",), confirmed=True)
    with pytest.raises(PermissionError) as stale:
        svc.save(expected_project_id="project-a", expected_binding="binding-a", expected_revision="none",
                 read_directories=(), write_directories=(), confirmed=True)
    assert stale.value.code == "revision_conflict"

    current["context"] = ProjectContext("project-b", other_root, "binding-b")
    with pytest.raises(PermissionError) as rebound:
        with svc.lease("write", ("new.txt",), expected_revision=first["revision"]):
            pytest.fail("old project selection must not retain a lease")
    assert rebound.value.code == "permission_denied"


def test_revision_is_exact_canonical_policy_bytes_and_raw_change_invalidates_cas(tmp_path: Path) -> None:
    root = tmp_path / "project"
    root.mkdir()
    svc = service(root)
    initial = save_all(svc)
    policy_path = root / ".bago/state/PROJECT_PERMISSIONS.json"
    current_bytes = policy_path.read_bytes()
    assert initial["revision"] == hashlib.sha256(current_bytes).hexdigest()

    raw = json.loads(current_bytes.decode("utf-8"))
    raw["updated_at"] += 1
    changed_bytes = permission_module._policy_bytes(raw)
    policy_path.write_bytes(changed_bytes)
    changed = svc.snapshot()
    assert changed["revision"] == hashlib.sha256(changed_bytes).hexdigest()
    assert changed["revision"] != initial["revision"]
    with pytest.raises(PermissionError) as stale:
        svc.revoke(expected_project_id=initial["project_id"], expected_binding=initial["binding"],
                   expected_revision=initial["revision"], confirmed=True)
    assert stale.value.code == "revision_conflict"

    policy_path.write_bytes(b" " + changed_bytes)
    with pytest.raises(PermissionError) as noncanonical:
        svc.snapshot()
    assert noncanonical.value.code == "project_policy_invalid"


def test_copied_policy_does_not_inherit_between_physical_roots(tmp_path: Path) -> None:
    first_root = tmp_path / "project-a"
    second_root = tmp_path / "project-b"
    first_root.mkdir()
    second_root.mkdir()
    first = service(first_root, project_id="same-registered-id")
    granted = save_all(first)
    second_state = second_root / ".bago/state"
    second_state.mkdir(parents=True)
    (second_state / "PROJECT_PERMISSIONS.json").write_bytes((first_root / ".bago/state/PROJECT_PERMISSIONS.json").read_bytes())

    second = service(second_root, project_id="same-registered-id")
    with pytest.raises(PermissionError) as copied:
        second.snapshot()
    assert copied.value.code == "project_policy_invalid"
    assert granted["root"] != str(second_root.resolve())


def test_host_context_lease_requires_root_read_and_exact_ledger_allowlist(tmp_path: Path) -> None:
    root = tmp_path / "project"
    (root / ".bago/context").mkdir(parents=True)
    (root / "docs").mkdir()
    (root / ".bago/context/PROJECT_CONTEXT.md").write_text("synthetic project context", encoding="utf-8")
    svc = service(root)

    save_all(svc, read=("docs",), write=())
    with pytest.raises(PermissionError) as no_root:
        with svc.context_lease((".bago/context/PROJECT_CONTEXT.md",)):
            pytest.fail("subdirectory READ must not authorize host continuity reads")
    assert no_root.value.code == "permission_denied"

    granted = save_all(svc, read=(".",), write=())
    with svc.context_lease((".bago/context/PROJECT_CONTEXT.md",), expected_revision=granted["revision"]) as snapshot:
        assert snapshot["state"] == "configured"
        assert "synthetic project context" not in str(snapshot)
    for forbidden in (".bago/goals/secret/STATUS.md", ".bago/state/PROJECT_PERMISSIONS.json", "src/main.py"):
        with pytest.raises(PermissionError):
            with svc.context_lease((forbidden,)):
                pytest.fail("host context lease must remain limited to exact ledgers")


def test_save_requires_confirmation_and_approved_directories_must_exist(tmp_path: Path) -> None:
    root = tmp_path / "project"
    root.mkdir()
    svc = service(root)
    with pytest.raises(PermissionError) as unconfirmed:
        svc.save(expected_project_id="project-a", expected_binding="selection-1", expected_revision="none",
                 read_directories=(), write_directories=(".",), confirmed=False)
    assert unconfirmed.value.code == "permission_not_confirmed"
    assert not (root / ".bago").exists()
    with pytest.raises(PermissionError):
        save_all(svc, write=("not-created-yet",))


@pytest.mark.parametrize("relative", ["../outside", "C:/outside", "docs\\..\\outside", ".bago/state", ".git/config", "docs/CON.txt", "docs/token.txt"])
def test_traversal_alias_and_governance_paths_are_denied(tmp_path: Path, relative: str) -> None:
    root = tmp_path / "project"
    root.mkdir()
    (root / "docs").mkdir()
    svc = service(root)
    save_all(svc)
    with pytest.raises(PermissionError):
        with svc.lease("read", (relative,)):
            pytest.fail("unsafe path must not receive an IO lease")


def test_valid_private_and_auth_named_project_content_is_not_path_denied(tmp_path: Path) -> None:
    root = tmp_path / "project"
    for directory in (root / "private", root / "browser", root / "src"):
        directory.mkdir(parents=True, exist_ok=True)
    (root / "private/contract.pdf").write_bytes(b"sensitive business contract")
    (root / "browser/browser-flow.md").write_text("browser automation plan", encoding="utf-8")
    (root / "src/auth.py").write_text("def authenticate(): pass", encoding="utf-8")
    svc = service(root)
    granted = save_all(svc, read=(".",), write=())
    with svc.lease("read", ("private/contract.pdf", "browser/browser-flow.md", "src/auth.py"),
                   expected_revision=granted["revision"]):
        pass
    for path in (".env", "credentials/session.json", "private/service_private_key.pem", "private/current_access_token.json"):
        with pytest.raises(PermissionError):
            with svc.lease("read", (path,)):
                pytest.fail("credential material must remain blocked")


def test_lease_rejects_empty_paths_and_dot_means_project_root(tmp_path: Path) -> None:
    root = tmp_path / "project"
    root.mkdir()
    svc = service(root)
    granted = save_all(svc, read=(".",), write=(".",))
    with svc.lease("read", (".",), expected_revision=granted["revision"]):
        assert svc.allowed("write", ".")
    with pytest.raises(PermissionError) as empty:
        with svc.lease("read", ()):
            pytest.fail("empty effect path list must not yield an authorization lease")
    assert empty.value.code == "invalid_permission_request"


def _make_junction(link: Path, target: Path) -> None:
    if os.name == "nt":
        result = subprocess.run([os.environ.get("COMSPEC", "cmd.exe"), "/d", "/c", "mklink", "/J", str(link), str(target)],
                                capture_output=True, text=True, check=False)
        assert result.returncode == 0, f"junction fixture creation failed: {result.stderr or result.stdout}"
    else:
        link.symlink_to(target, target_is_directory=True)


def test_junction_and_hardlink_cannot_extend_project_authority(tmp_path: Path) -> None:
    root = tmp_path / "project"
    outside = tmp_path / "outside"
    root.mkdir()
    outside.mkdir()
    outside_file = outside / "data.txt"
    outside_file.write_text("outside", encoding="utf-8")
    link = root / "linked"
    _make_junction(link, outside)
    svc = service(root)
    with pytest.raises(PermissionError):
        save_all(svc, read=("linked",), write=())
    assert outside_file.read_text(encoding="utf-8") == "outside"

    # Explicitly grant project-root write in a separate clean root, then ensure
    # a hardlink to an outside file is not writable through that alias.
    clean = tmp_path / "clean-project"
    clean.mkdir()
    clean_svc = service(clean)
    save_all(clean_svc)
    outside_link = clean / "linked-data.txt"
    os.link(outside_file, outside_link)
    with pytest.raises(PermissionError):
        with clean_svc.lease("write", ("linked-data.txt",)):
            outside_link.write_text("overwritten", encoding="utf-8")
    assert outside_file.read_text(encoding="utf-8") == "outside"


def test_revoke_waits_for_active_io_lease_then_blocks_new_io(tmp_path: Path) -> None:
    root = tmp_path / "project"
    root.mkdir()
    (root / "report.txt").write_text("before", encoding="utf-8")
    svc = service(root)
    granted = save_all(svc, read=(".",), write=(".",))
    entered = threading.Event()
    release = threading.Event()

    def bounded_io():
        with svc.lease("read", ("report.txt",)):
            with svc.lease("write", ("report.txt",)):
                assert svc.allowed("write", "report.txt")
                entered.set()
                assert release.wait(5)
                (root / "report.txt").write_text("completed before revoke", encoding="utf-8")

    def revoke():
        return svc.revoke(expected_project_id=granted["project_id"], expected_binding=granted["binding"],
                          expected_revision=granted["revision"], confirmed=True)

    with ThreadPoolExecutor(max_workers=2) as pool:
        io_future = pool.submit(bounded_io)
        assert entered.wait(3)
        revoke_future = pool.submit(revoke)
        time.sleep(0.1)
        assert not revoke_future.done(), "revoke must wait for the already-started IO lease"
        release.set()
        io_future.result(timeout=3)
        new_policy = revoke_future.result(timeout=3)
    assert new_policy["write_directories"] == []
    with pytest.raises(PermissionError):
        with svc.lease("write", ("later.txt",)):
            pytest.fail("revoked policy must block later IO")


def test_windows_cross_process_read_lease_serializes_revoke(tmp_path: Path) -> None:
    root = tmp_path / "project"
    root.mkdir()
    (root / "record.txt").write_text("held while another process requests revoke", encoding="utf-8")
    svc = service(root)
    granted = save_all(svc, read=(".",), write=(".",))
    context = multiprocessing.get_context("spawn")
    entered, release = context.Event(), context.Event()
    revoke_started, revoke_done = context.Event(), context.Event()
    results = context.Queue()
    holder = context.Process(target=_child_read_lease, args=(str(root), entered, release, results))
    revoker = context.Process(target=_child_revoke, args=(str(root), granted["revision"], revoke_started, revoke_done, results))
    try:
        holder.start()
        assert entered.wait(6), "child A did not acquire the real OS read lease"
        revoker.start()
        assert revoke_started.wait(6), "child B did not start the revoke request"
        time.sleep(0.25)
        assert not revoke_done.is_set(), "child B must wait while child A holds the OS lease"
        release.set()
        holder.join(8)
        revoker.join(8)
        assert not holder.is_alive()
        assert not revoker.is_alive()
        assert holder.exitcode == 0
        assert revoker.exitcode == 0
        results_received = {results.get(timeout=2), results.get(timeout=2)}
        assert results_received == {"lease:PASS", "revoke:PASS"}
        assert revoke_done.is_set()
    finally:
        release.set()
        for process in (holder, revoker):
            if process.is_alive():
                process.terminate()
                process.join(3)
        results.close()



