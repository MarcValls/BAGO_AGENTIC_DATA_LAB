"""Real bounded filesystem/policy/grants; controlled interpretation only.

These tests do not claim a live provider or Windows run. HTTP and persisted
conversation integration are independently exercised in test_csv_chat_flow.py.
"""
from __future__ import annotations

from decimal import Decimal
from contextlib import contextmanager
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
import os
from pathlib import Path
import time
import threading

import pytest

from src.agent_tools import csv_chat
from src.agent_tools.workspace_read import (
    WorkspaceReadAuthorizations, WorkspaceReadAuthorizationError,
    read_workspace_file, workspace_file_identity,
)
from src.project_permissions import ProjectContext, ProjectPermissions, PermissionError as ProjectPermissionError


ORIGINAL = (
    "pedido,cliente,producto,unidades,precio_unitario,descuento_pct,estado\n"
    "P001,Alba,Camiseta,12,18.50,10,pendiente\n"
    "P002,Bruno,Gorra,6,9.00,0,entregado\n"
    "P003,Carmen,Taza,8,6.25,5,pendiente\n"
).encode("utf-8")
ORIGINAL_SHA = "8fe7a2979043c0e992f4e13d84055045ae1fec91bb896d365fe996367acbafe5"
PLAN = {
    "derive": [{"name": "importe", "expression": {"op": "mul", "args": [
        {"column": "unidades"}, {"op": "mul", "args": [{"column": "precio_unitario"},
            {"op": "sub", "args": [{"number": "1"}, {"op": "div", "args": [
                {"column": "descuento_pct"}, {"number": "100"}]}]}]}]}}],
    "select": ["pedido", "cliente", "importe"], "group_by": ["estado"],
    "aggregates": [{"op": "sum", "column": "importe", "as": "total"}],
}


@pytest.fixture
def rig(tmp_path, monkeypatch):
    root = tmp_path / "project"
    path = "demo-usuario/archivo/pedidos-final.csv"
    target = root / path
    target.parent.mkdir(parents=True)
    target.write_bytes(ORIGINAL)
    (target.parent / "other.csv").write_text("private,value\nDo not leak,999\n")
    context = {"project_id": "project-a", "binding": "binding-a", "root": root}
    policy = ProjectPermissions(lambda: ProjectContext(**context))
    old = policy.snapshot()
    policy.save(expected_project_id=old["project_id"], expected_binding=old["binding"],
        expected_revision=old["revision"], read_directories=["demo-usuario"], write_directories=[], confirmed=True)
    grants = WorkspaceReadAuthorizations()
    monkeypatch.setattr(csv_chat, "WORKSPACE_READ_AUTHORIZATIONS", grants)
    identity = dict(owner_kind="assistant", owner_id="app-assistant", conversation_id="conv-a", revision=2)
    request = {"message": "Calcula importes por pedido, pendientes y total general.",
        "csv_read": {"path": path, "delimiter": "auto", "decimal_separator": "."}}
    calls = []
    def interpret(messages, **kwargs):
        assert [tool["function"]["name"] for tool in kwargs["tools"]] == ["query_csv"]
        data = json.loads(messages[1]["content"])
        assert data["csv_data"]["rows"][0]["cells"][1] == "Alba"
        calls.append(data)
        return {"tool_calls": [{"function": {"name": "query_csv", "arguments": PLAN}}]}
    return dict(root=root, path=path, target=target, policy=policy, context=context,
                grants=grants, identity=identity, request=request, calls=calls, interpret=interpret)


def issue(rig):
    return csv_chat.issue_csv_authorization(workspace_root=rig["root"], permissions=rig["policy"],
        identity=rig["identity"], paths=[rig["path"]], csv_request=rig["request"],
        expected_project=rig["policy"].snapshot())


def begin(rig, token, **overrides):
    return rig["grants"].begin_csv(token, **{**rig["identity"], **overrides},
        workspace_root=rig["root"], csv_request=rig["request"])


def run(rig, token, grant, interpret=None):
    return csv_chat.run_csv_analysis(workspace_root=rig["root"], permissions=rig["policy"],
        token=token, grant=grant, identity=rig["identity"], csv_request=rig["request"],
        interpret=interpret or rig["interpret"], check_conversation=lambda: None)


def test_original_bytes_actual_read_and_independently_checked_results(rig):
    assert len(ORIGINAL) == 183 and hashlib.sha256(ORIGINAL).hexdigest() == ORIGINAL_SHA
    before = workspace_file_identity(rig["root"], rig["path"])
    token = issue(rig)["authorization_id"]
    result = run(rig, token, begin(rig, token))
    assert result["csv_analysis"]["status"] == "answered", result
    data = result["csv_analysis"]
    assert [Decimal(row["values"]["importe"]) for row in data["selected_rows"]] == [Decimal("199.80"), Decimal("54.00"), Decimal("47.50")]
    assert {r["values"]["estado"]: Decimal(r["values"]["total"]) for r in data["rows"]} == {"pendiente": Decimal("247.30"), "entregado": Decimal("54.00")}
    assert Decimal(data["grand_totals"]["values"]["total"]) == Decimal("301.30")
    assert data["file_sha256"] == ORIGINAL_SHA == result["sources"][0]["file_sha256"]
    assert result["read_events"][0]["executed"] is True
    assert "Interpretación aplicada" in result["answer"] and "SHA-256" in result["answer"]
    assert rig["target"].read_bytes() == ORIGINAL
    assert workspace_file_identity(rig["root"], rig["path"]) == before
    assert len(rig["calls"]) == 1


def test_issuing_grant_is_metadata_only(rig, monkeypatch):
    original = Path.open
    def guarded(path, *args, **kwargs):
        assert path.suffix.lower() != ".csv", "CSV bytes read before request authorization"
        return original(path, *args, **kwargs)
    monkeypatch.setattr(Path, "open", guarded)
    grant = issue(rig)
    assert grant["paths"] == [rig["path"]] and not rig["calls"]


@pytest.mark.parametrize("field,value", [("owner_id", "other"), ("owner_kind", "agent"),
    ("conversation_id", "other"), ("revision", 3)])
def test_grant_cannot_cross_identity_or_revision(rig, field, value):
    token = issue(rig)["authorization_id"]
    with pytest.raises(WorkspaceReadAuthorizationError, match="SCOPE_MISMATCH"):
        begin(rig, token, **{field: value})
    assert begin(rig, token)["paths"] == [rig["path"]]
    with pytest.raises(WorkspaceReadAuthorizationError, match="USED"):
        begin(rig, token)


@pytest.mark.parametrize("state,code", [("absent", "REQUIRED"), ("expired", "EXPIRED"), ("revoked", "REVOKED")])
def test_missing_expired_revoked_have_distinct_diagnostics_and_no_io(rig, state, code):
    token = issue(rig)["authorization_id"]
    if state == "absent": token = "invented"
    if state == "expired": rig["grants"]._grants[token]["expires_at"] = time.time() - 1
    if state == "revoked":
        assert rig["grants"].revoke(token, **rig["identity"], workspace_root=rig["root"])
    with pytest.raises(WorkspaceReadAuthorizationError, match=code): begin(rig, token)
    assert not rig["calls"]


@pytest.mark.parametrize("change", ["message", "path", "delimiter", "decimal_separator"])
def test_grant_binds_question_and_interpretation_options(rig, change):
    token = issue(rig)["authorization_id"]
    if change == "message": rig["request"]["message"] = "A different question"
    else: rig["request"]["csv_read"][change] = {"path": "demo-usuario/archivo/other.csv", "delimiter": ";", "decimal_separator": ","}[change]
    with pytest.raises(WorkspaceReadAuthorizationError, match="REQUEST_MISMATCH"): begin(rig, token)


def test_legacy_ticket_and_csv_ticket_cannot_be_cross_promoted(rig):
    ordinary = rig["grants"].issue(rig["root"], **rig["identity"], paths=[rig["path"]])["authorization_id"]
    with pytest.raises(WorkspaceReadAuthorizationError, match="REQUIRED"): begin(rig, ordinary)
    csv = issue(rig)["authorization_id"]
    assert rig["grants"].consume(csv, **rig["identity"], workspace_root=rig["root"]) is None
    assert begin(rig, csv)["paths"] == [rig["path"]]


def test_saved_project_read_cannot_expand_exact_csv_selection(rig):
    result, receipt = read_workspace_file(rig["root"], {"path": "demo-usuario/archivo/other.csv"},
        [rig["path"]], project_permissions=rig["policy"], expected_project=rig["policy"].snapshot(),
        require_exact_paths=True, include_snapshot=True)
    assert not result["ok"] and receipt["reason_code"] == "PATH_NOT_AUTHORIZED"
    assert "Do not leak" not in str(result)


@pytest.mark.parametrize("mutation", ["in_place", "replace", "revoke", "binding", "expired", "cancel", "stop"])
def test_concurrent_changes_withhold_results_after_real_read(rig, mutation):
    token = issue(rig)["authorization_id"]
    grant = begin(rig, token)
    def mutate(messages, **kwargs):
        turn = rig["interpret"](messages, **kwargs)
        if mutation == "in_place": rig["target"].write_bytes(ORIGINAL.replace(b"18.50", b"99.50"))
        if mutation == "replace":
            replacement = rig["target"].with_suffix(".next")
            replacement.write_bytes(ORIGINAL); os.replace(replacement, rig["target"])
        if mutation == "revoke":
            old = rig["policy"].snapshot()
            rig["policy"].revoke(expected_project_id=old["project_id"], expected_binding=old["binding"], expected_revision=old["revision"], confirmed=True)
        if mutation == "binding": rig["context"]["binding"] = "binding-new"
        if mutation == "expired": rig["grants"]._grants[token]["expires_at"] = time.time() - 1
        if mutation == "cancel": rig["grants"].revoke(token, **rig["identity"], workspace_root=rig["root"])
        if mutation == "stop":
            state = rig["root"] / ".bago/team/runtime/state.json"
            state.parent.mkdir(parents=True); state.write_text('{"lifecycle":"PAUSED"}')
        return turn
    result = run(rig, token, grant, mutate)
    assert result["csv_analysis"]["status"] == "failed", result
    assert not result["sources"] and "Alba" not in json.dumps(result) and "301.30" not in json.dumps(result)
    assert result["read_events"][0]["executed"] is True and len(rig["calls"]) == 1


def test_file_change_between_grant_and_read_sends_no_bytes_to_interpreter(rig):
    token = issue(rig)["authorization_id"]
    grant = begin(rig, token)
    rig["target"].write_bytes(ORIGINAL.replace(b"18.50", b"99.50"))
    result = run(rig, token, grant)
    assert result["csv_analysis"]["error"]["code"] == "FILE_CHANGED_SINCE_AUTHORIZATION"
    assert result["read_events"][0]["executed"] is False and not rig["calls"]


def test_in_place_change_during_bounded_io_is_detected(rig, monkeypatch):
    original_open = Path.open
    class ChangeOnRead:
        def __init__(self, stream): self.stream = stream
        def __enter__(self): self.stream.__enter__(); return self
        def __exit__(self, *args): return self.stream.__exit__(*args)
        def fileno(self): return self.stream.fileno()
        def read(self, *args):
            content = self.stream.read(*args)
            with original_open(rig["target"], "wb") as writer: writer.write(ORIGINAL.replace(b"18.50", b"99.50"))
            return content
    def changed(path, *args, **kwargs):
        stream = original_open(path, *args, **kwargs)
        return ChangeOnRead(stream) if path == rig["target"] and args and args[0] == "rb" else stream
    monkeypatch.setattr(Path, "open", changed)
    result, receipt = read_workspace_file(rig["root"], {"path": rig["path"]}, [rig["path"]])
    assert not result["ok"] and receipt["reason_code"] == "FILE_CHANGED_DURING_READ"
    assert "Alba" not in str(result)


@pytest.mark.parametrize("path", ["../outside.csv", "/tmp/outside.csv", "C:\\outside.csv", "demo-usuario/../../outside.csv", ".bago/private.csv"])
def test_unsafe_paths_are_never_authorized(rig, path):
    rig["path"] = path; rig["request"]["csv_read"]["path"] = path
    with pytest.raises((ValueError, ProjectPermissionError)):
        issue(rig)
    assert not rig["calls"]


@pytest.mark.parametrize("text,code", [(b'a,b\n"unterminated,2\n', "CSV_MALFORMED"),
    (b'a,b\n1,2,3\n', "CSV_MALFORMED"), (b'a,a\n1,2\n', "CSV_HEADER_DUPLICATE"),
    (("a,b\n" + "1,2\n" * 250).encode(), "CSV_LINE_LIMIT")])
def test_malformed_and_overlimit_csv_never_reach_provider(rig, text, code):
    rig["target"].write_bytes(text)
    token = issue(rig)["authorization_id"]
    result = run(rig, token, begin(rig, token))
    assert result["csv_analysis"]["status"] == "failed" and not rig["calls"]
    assert result["csv_analysis"]["error"]["code"].startswith(code)


@pytest.mark.parametrize("turn", [{"content": "The total is definitely 999999"},
    {"tool_calls": [{"function": {"name": "read_workspace_file", "arguments": {"path": "other.csv"}}}]},
    {"tool_calls": [{"function": {"name": "query_csv", "arguments": '{"select":["cliente"],"select":["unidades"]}'}}]},
    {"tool_calls": [{"function": {"name": "query_csv", "arguments": {"select": ["invented"]}}}]}])
def test_interpretation_errors_never_become_a_data_answer(rig, turn):
    token = issue(rig)["authorization_id"]
    result = run(rig, token, begin(rig, token), lambda *a, **kw: turn)
    assert result["csv_analysis"]["status"] == "failed" and not result["sources"]
    assert "999999" not in str(result) and "Alba" not in str(result)


def invalidate_waiting_request(rig, token, invalidation):
    if invalidation == "revoke":
        assert rig["grants"].revoke(token, **rig["identity"], workspace_root=rig["root"])
    elif invalidation == "expire":
        with rig["grants"]._lock:
            rig["grants"]._grants[token]["expires_at"] = time.time() - 1
    else:
        state = rig["root"] / ".bago/team/runtime/state.json"
        state.parent.mkdir(parents=True, exist_ok=True)
        state.write_text('{"lifecycle":"PAUSED"}')


@pytest.mark.parametrize("invalidation,code", [("revoke", "READ_AUTHORIZATION_REVOKED"),
    ("expire", "READ_AUTHORIZATION_EXPIRED"), ("stop", "STOP_ACTIVE")])
def test_waiting_io_rechecks_authority_after_policy_lease(rig, monkeypatch, invalidation, code):
    """Regression for the independently reproduced P1: no bytes after revoke.

    First validation succeeds. Then the real read waits on the real policy
    lock while the request becomes invalid. Events make the order explicit.
    """
    from src.project_permissions import _project_lock
    token = issue(rig)["authorization_id"]
    grant = begin(rig, token)
    ready, proceed, attempted = (threading.Event() for _ in range(3))
    actual_read, actual_lease = csv_chat.read_workspace_file, rig["policy"].lease
    opened = []
    actual_open = Path.open

    def observe_open(path, *args, **kwargs):
        if path == rig["target"] and args and args[0] == "rb": opened.append(path)
        return actual_open(path, *args, **kwargs)

    def delayed_read(*args, **kwargs):
        ready.set()
        assert proceed.wait(5)
        return actual_read(*args, **kwargs)

    @contextmanager
    def observe_lease(*args, **kwargs):
        if ready.is_set(): attempted.set()
        with actual_lease(*args, **kwargs) as value: yield value

    monkeypatch.setattr(csv_chat, "read_workspace_file", delayed_read)
    monkeypatch.setattr(rig["policy"], "lease", observe_lease)
    monkeypatch.setattr(Path, "open", observe_open)
    with ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(run, rig, token, grant)
        assert ready.wait(5)
        with _project_lock(rig["policy"]._paths(rig["root"])[1]):
            proceed.set()
            assert attempted.wait(5)
            invalidate_waiting_request(rig, token, invalidation)
        result = future.result(timeout=5)
    assert result["csv_analysis"]["error"]["code"] == code, result
    assert not opened and not rig["calls"]
    assert result["read_events"][0]["executed"] is False


@pytest.mark.parametrize("invalidation,code", [("revoke", "READ_AUTHORIZATION_REVOKED"),
    ("expire", "READ_AUTHORIZATION_EXPIRED"), ("stop", "STOP_ACTIVE")])
def test_waiting_publication_rechecks_authority_after_policy_lease(rig, monkeypatch, invalidation, code):
    from src.project_permissions import _project_lock
    token = issue(rig)["authorization_id"]
    grant = begin(rig, token)
    attempted = threading.Event()
    actual_lease = rig["policy"].lease
    published = []

    @contextmanager
    def observe_lease(*args, **kwargs):
        attempted.set()
        with actual_lease(*args, **kwargs) as value: yield value

    def publish():
        with csv_chat.csv_effect_guard(workspace_root=rig["root"], permissions=rig["policy"],
            token=token, grant=grant, identity=rig["identity"], check_conversation=lambda: None):
            published.append("result")

    monkeypatch.setattr(rig["policy"], "lease", observe_lease)
    with ThreadPoolExecutor(max_workers=1) as pool:
        with _project_lock(rig["policy"]._paths(rig["root"])[1]):
            future = pool.submit(publish)
            assert attempted.wait(5)
            invalidate_waiting_request(rig, token, invalidation)
        with pytest.raises((csv_chat.CsvChatError, WorkspaceReadAuthorizationError)) as caught:
            future.result(timeout=5)
    assert caught.value.code == code
    assert not published


def test_revoke_acknowledges_only_after_bounded_effect_finishes(rig):
    """An accepted revoke serializes with the existing grant's effect lease."""
    token = issue(rig)["authorization_id"]
    begin(rig, token)
    started, acknowledged = threading.Event(), threading.Event()
    def revoke():
        started.set()
        result = rig["grants"].revoke(token, **rig["identity"], workspace_root=rig["root"])
        acknowledged.set()
        return result
    with ThreadPoolExecutor(max_workers=1) as pool:
        with rig["grants"].lease_csv(token, **rig["identity"], workspace_root=rig["root"]):
            future = pool.submit(revoke)
            assert started.wait(5)
            assert not acknowledged.is_set()
        assert future.result(timeout=5) and acknowledged.is_set()
    with pytest.raises(WorkspaceReadAuthorizationError, match="REVOKED"):
        with rig["grants"].lease_csv(token, **rig["identity"], workspace_root=rig["root"]):
            pytest.fail("A later effect must be denied")
