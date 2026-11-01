"""Independent HTTP verification of governed main-chat CSV reading.

Each case imports the real API in a fresh process with a synthetic project and
SQLite state in /tmp. Only the provider's interpretation is controlled. Guards,
permissions, metadata browsing, file IO, parser/calculator, traces and persistence
are real. Instrumentation observes reads or schedules explicit adversarial edits.
This is not evidence of a live model, Windows, or the user's installation.
"""
from __future__ import annotations

import copy
from decimal import Decimal
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import threading
import time

import pytest


REPO = Path(__file__).resolve().parents[1]
CSV_PATH = "demo-usuario/archivo/pedidos-final.csv"
ORIGINAL = (
    "pedido,cliente,producto,unidades,precio_unitario,descuento_pct,estado\n"
    "P001,Alba,Camiseta,12,18.50,10,pendiente\n"
    "P002,Bruno,Gorra,6,9.00,0,entregado\n"
    "P003,Carmen,Taza,8,6.25,5,pendiente\n"
).encode("utf-8")
ORIGINAL_SHA = "8fe7a2979043c0e992f4e13d84055045ae1fec91bb896d365fe996367acbafe5"
QUESTION = "Analiza pedidos: importe descontado por pedido, pendientes por estado y total general."
PLAN = {
    "derive": [{"name": "importe", "expression": {"op": "mul", "args": [
        {"op": "mul", "args": [{"column": "unidades"}, {"column": "precio_unitario"}]},
        {"op": "sub", "args": [{"number": "1"}, {"op": "div", "args": [
            {"column": "descuento_pct"}, {"number": "100"}]}]},
    ]}}],
    "select": ["pedido", "cliente", "importe"], "group_by": ["estado"],
    "aggregates": [{"op": "sum", "column": "importe", "as": "total"}],
}
SOURCE_FILES = (
    "src/agent_tools/workspace_read.py", "src/agent_tools/csv_chat.py",
    "src/api/server.py", "src/api/schemas.py", "src/conversations/library.py",
    "tools/document-toolkit/document_toolkit/parsers.py",
    "tools/document-toolkit/document_toolkit/csv_query.py", "tests/test_csv_chat_flow.py",
)
CASES = (
    "F10", "F11", "F12", "absent", "invented", "expired", "revoked", "replay",
    "owner_id", "owner_kind", "conversation", "revision", "message", "path",
    "delimiter", "decimal_separator", "legacy_ticket", "archived", "project",
    "binding", "policy_revoked", "policy_regranted", "absolute_path", "traversal",
    "windows_path", "symlink", "hardlink", "hidden_path", "bad_quotes", "bad_width",
    "duplicate_headers", "line_limit", "byte_limit", "not_utf8", "unknown_column",
    "invalid_operator", "no_plan", "multiple_plans", "duplicate_plan_keys",
    "provider_error", "numeric_error", "division_zero", "changed_before",
    "changed_during", "changed_after", "replaced_after", "revoke_during_provider",
    "expiry_during_provider", "stop_before", "stop_during_provider",
    "stop_before_publication", "revoke_before_publication", "legacy_stop",
    "invalid_stop", "mixed_grants", "decimal_comma", "display_limit",
)


def fingerprint(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False,
                                    separators=(",", ":"), allow_nan=False).encode()).hexdigest()


def sanitized(value):
    if isinstance(value, list):
        return [sanitized(item) for item in value]
    if isinstance(value, dict):
        return {key: "[REDACTED]" if "authorization_id" in key else sanitized(item)
                for key, item in value.items()}
    return value


class Rig:
    def __init__(self, directory: Path, case: str):
        self.directory, self.case = directory, case
        os.environ["BAGO_DATA_ROOT"] = str(directory / "data")
        os.environ["BAGO_OTEL_EXPORTER_OTLP_ENDPOINT"] = ""
        os.environ["OTEL_TRACES_SAMPLER"] = "always_on"
        os.environ.pop("BAGO_CONVERSATION_DB_PATH", None)
        sys.path.insert(0, str(REPO))
        from fastapi.testclient import TestClient
        from src.api import server
        from src.project_folders import ProjectFolders, binding_identity
        self.server = server
        self.root = directory / "project"
        self.target = self.root / CSV_PATH
        self.target.parent.mkdir(parents=True)
        self.target.write_bytes(ORIGINAL)
        (self.target.parent / "other.csv").write_bytes(b"secret,value\nUNSELECTED_CELL,999\n")
        self.outside = directory / "outside.csv"
        self.outside.write_bytes(b"secret,value\nEXTERNAL_CELL,777\n")
        server._set_workspace_root(self.root)
        self.folders = ProjectFolders(
            state_directory=server._WORKSPACE_CONFIG_DIR / "project-folders-v1",
            workspace_root=server.current_workspace_root, set_workspace_root=server._set_workspace_root,
            pick_directory=server._pick_workspace_directory,
            binding_identity=lambda: binding_identity(server._WORKSPACE_CONFIG_PATH, server.current_workspace_root()),
            legacy_parent=lambda: None, binding_lock=server._WORKSPACE_LOCK,
        )
        self.bind(self.root)
        self.csv_reads, self.provider_calls, self.http = [], [], []
        self.plan = copy.deepcopy(PLAN)
        self.custom_turn = None
        self.provider_hook = None
        self.read_hook = None
        self.raise_provider = False
        self._original_open = Path.open
        original_open = self._original_open

        def observed_open(path, *args, **kwargs):
            mode = args[0] if args else kwargs.get("mode", "r")
            stream = original_open(path, *args, **kwargs)
            if str(path).lower().endswith(".csv") and "r" in mode:
                self.csv_reads.append(str(path))
                if self.read_hook and Path(path) == self.target:
                    hook = self.read_hook
                    self.read_hook = None

                    class ObservedRead:
                        def __enter__(self):
                            stream.__enter__()
                            return self

                        def __exit__(self, *exit_args):
                            return stream.__exit__(*exit_args)

                        def __getattr__(self, name):
                            return getattr(stream, name)

                        def read(self, *read_args):
                            data = stream.read(*read_args)
                            hook()
                            return data

                    return ObservedRead()
            return stream

        Path.open = observed_open
        selection = {"provider_id": "independent-csv-verifier", "model_id": "controlled-plan", "state": "ready"}
        server.provider_runtime.active_selection = lambda: dict(selection)

        def interpret(provider_id, model_id, messages, **kwargs):
            names = [item["function"]["name"] for item in kwargs.get("tools", [])]
            if names == ["resolve_control_request"]:
                self.provider_calls.append({"tool_names": names, "csv_rows": 0})
                return {"tool_calls": [{"function": {"name": "resolve_control_request",
                    "arguments": {"decision": "workspace_read", "reply": "Solicita el archivo autorizado."}}}]}
            assert names == ["query_csv"], names
            data = json.loads(messages[1]["content"])
            assert "untrusted DATA" in messages[0]["content"]
            self.provider_calls.append({"tool_names": names, "question": data["question"],
                "csv_rows": len(data["csv_data"]["rows"]), "csv_data": data["csv_data"]})
            if self.provider_hook:
                self.provider_hook()
            if self.raise_provider:
                raise RuntimeError("PROVIDER_PRIVATE_DIAGNOSTIC_MUST_NOT_LEAK")
            return copy.deepcopy(self.custom_turn) if self.custom_turn is not None else {
                "tool_calls": [{"function": {"name": "query_csv", "arguments": self.plan}}]}

        server.provider_runtime.chat_turn = interpret
        self.client = TestClient(server.app)
        self.client.__enter__()
        self.conversation = self.call("POST", "/api/conversations", {
            "owner_kind": "assistant", "owner_id": "app-assistant"}).json()
        self.request = {"message": QUESTION,
                        "csv_read": {"path": CSV_PATH, "delimiter": "auto", "decimal_separator": "."}}
        self.policy = self.call("GET", "/api/project-permissions").json()
        self.token = None

    def close(self):
        self.client.__exit__(None, None, None)
        Path.open = self._original_open

    def bind(self, root):
        root.mkdir(parents=True, exist_ok=True)
        current = str(self.server.current_workspace_root())
        plan = self.folders.prepare(mode="existing", path=str(root), name=root.name,
                                    title=root.name, expected_workspace_root=current)
        self.folders.apply(plan["plan_id"], plan_sha256=plan["plan_sha256"], confirmed=True)

    def call(self, method, path, body=None):
        response = self.client.request(method, path, **({"json": body} if body is not None else {}))
        data = response.json()
        self.http.append({"method": method, "path": path.split("/authorizations/")[0] +
                          ("/authorizations/[REDACTED]" if "/authorizations/" in path else ""),
                          "status": response.status_code,
                          "code": (data.get("detail") or {}).get("code") if isinstance(data.get("detail"), dict) else None})
        return response

    def expected(self):
        return {"expected_" + key: self.policy[key] for key in ("project_id", "binding", "revision")}

    def save_read(self):
        self.policy = self.call("GET", "/api/project-permissions").json()
        response = self.call("PUT", "/api/project-permissions", {
            **self.expected(), "read_directories": ["demo-usuario"], "write_directories": [], "confirmed": True})
        assert response.status_code == 200, response.text
        self.policy = response.json()

    def revoke_policy(self):
        self.policy = self.call("GET", "/api/project-permissions").json()
        response = self.call("DELETE", "/api/project-permissions", {**self.expected(), "confirmed": True})
        assert response.status_code == 200, response.text
        self.policy = response.json()

    def grant_body(self):
        return {"owner_kind": "assistant", "owner_id": "app-assistant",
                "conversation_id": self.conversation["id"], "revision": self.conversation["revision"],
                "paths": [self.request["csv_read"]["path"]], "csv_request": copy.deepcopy(self.request),
                "expected_project": {key: self.policy[key] for key in ("project_id", "binding", "revision")}}

    def grant(self, overrides=None):
        body = self.grant_body()
        body.update(overrides or {})
        response = self.call("POST", "/api/workspace-read/authorizations", body)
        if response.status_code == 200:
            self.token = response.json()["authorization_id"]
        return response

    def grant_ok(self):
        response = self.grant()
        assert response.status_code == 200, response.text
        assert not self.csv_reads, self.csv_reads
        assert response.json()["request_sha256"] == fingerprint(self.request)

    def chat_body(self):
        return {"operation": "chat", "conversation_id": self.conversation["id"],
                "revision": self.conversation["revision"], **copy.deepcopy(self.request),
                **({"workspace_read_authorization_id": self.token} if self.token else {})}

    def chat(self, overrides=None):
        body = self.chat_body()
        body.update(overrides or {})
        return self.call("POST", "/api/chat/control", body)

    def revoke(self):
        body = {key: self.grant_body()[key] for key in ("owner_kind", "owner_id", "conversation_id", "revision")}
        response = self.call("DELETE", "/api/workspace-read/authorizations/" + self.token, body)
        assert response.status_code == 200 and response.json()["revoked"] is True, response.text

    def expire(self):
        grants = self.server.WORKSPACE_READ_AUTHORIZATIONS
        with grants._lock:
            grants._grants[self.token]["expires_at"] = time.time() - 1

    def get_saved(self):
        response = self.call("GET", "/api/conversations/" + self.conversation["id"])
        assert response.status_code == 200, response.text
        return response.json()

    def original_bytes(self):
        with self._original_open(self.target, "rb") as stream:
            return stream.read()

    def create_mission(self):
        mission = {"mission_id": "CSV_HTTP_STOP_FIXTURE", "operation": "VERIFICATION",
            "work_items": [{"id": "CHECK", "title": "Synthetic STOP observation", "role": "verification-engineer",
                "depends_on": [], "write_scopes": [], "output_scopes": ["evidence/**"], "required_checks": ["check"]}],
            "terminal_work_items": ["CHECK"], "max_concurrency": 1,
            "audit_scope": {"include": [CSV_PATH], "exclude": [], "fixture_roots": [],
                            "evidence_roots": ["evidence"], "preserved_roots": []}}
        path = self.directory / "stop-mission.json"
        path.write_text(json.dumps(mission), encoding="utf-8")
        self.team("init", "--mission", str(path))

    def team(self, *args):
        command = [sys.executable, str(REPO / ".bago/team/kit/scripts/teamctl.py"), "--root", str(self.root), *args]
        completed = subprocess.run(command, capture_output=True, text=True, timeout=20)
        result = json.loads(completed.stdout)
        assert completed.returncode == 0 and result["status"] == "PASS", result
        return result

    def pause(self):
        self.team("pause", "--reason", "Independent HTTP CSV STOP verification")

    def assert_denied(self, response, code=None, *, io=False, provider=False):
        data = response.json()
        if response.status_code == 200:
            assert data["csv_analysis"]["status"] == "failed", data
            actual_code = data["csv_analysis"]["error"]["code"]
            assert data.get("sources") == []
            assert data["read_events"][0]["executed"] is io
            assert data["read_events"][0]["outcome"] == ("WITHHELD" if io else "DENIED")
        else:
            assert response.status_code in {403, 404, 409, 422}, (response.status_code, data)
            actual_code = data.get("detail", {}).get("code") if isinstance(data.get("detail"), dict) else "validation_error"
        if code:
            assert actual_code in ({code} if isinstance(code, str) else set(code)), (actual_code, data)
        serialized = json.dumps(data, ensure_ascii=False)
        for secret in ("Alba", "Bruno", "Carmen", "UNSELECTED_CELL", "EXTERNAL_CELL", "PROVIDER_PRIVATE_DIAGNOSTIC_MUST_NOT_LEAK"):
            assert secret not in serialized, secret
        assert bool(self.csv_reads) is io, self.csv_reads
        assert bool([x for x in self.provider_calls if x["tool_names"] == ["query_csv"]]) is provider
        if response.status_code == 200:
            saved = self.get_saved()
            last = saved["messages"][-1]
            assert last["references"]["csv_analysis"]["status"] == "failed"
            for secret in ("Alba", "Bruno", "Carmen", "UNSELECTED_CELL", "EXTERNAL_CELL"):
                assert secret not in json.dumps(saved, ensure_ascii=False), secret
        return {"http_status": response.status_code, "code": actual_code,
                "io_executed": io, "query_provider_called": provider, "no_cells_in_response_or_history": True}

    def assert_answer(self, response, *, limited=False):
        assert response.status_code == 200, response.text
        body = response.json()
        result = body["csv_analysis"]
        assert result["status"] == "answered", result
        assert len(self.csv_reads) == 1, self.csv_reads
        calls = [item for item in self.provider_calls if item["tool_names"] == ["query_csv"]]
        assert len(calls) == 1 and calls[0]["csv_rows"] == 3
        assert calls[0]["csv_data"]["rows"][0]["cells"][1] == "Alba"
        assert calls[0]["csv_data"]["rows"][2]["cells"][1] == "Carmen"
        assert result["coverage"]["total_rows"] == result["coverage"]["matched_rows"] == 3
        assert result["coverage"]["complete_input"] is True
        assert Decimal(result["grand_totals"]["values"]["total"]) == Decimal("301.30")
        if not limited:
            assert [Decimal(row["values"]["importe"]) for row in result["selected_rows"]] == [Decimal("199.80"), Decimal("54.00"), Decimal("47.50")]
            assert {row["values"]["estado"]: Decimal(row["values"]["total"]) for row in result["rows"]} == {"pendiente": Decimal("247.30"), "entregado": Decimal("54.00")}
            assert result["rows"][0]["source_rows"] == [2, 4]
            assert result["rows"][0]["source_locations"] == [{"row": 2, "start_line": 2, "end_line": 2}, {"row": 4, "start_line": 4, "end_line": 4}]
        else:
            assert result["selected_truncated"] is True and result["truncated"] is True
            assert len(result["selected_rows"]) == len(result["rows"]) == 1
        assert result["grand_totals"]["source_rows"] == [2, 3, 4]
        assert result["provenance"]["arithmetic"] == "Decimal"
        assert result["provenance"]["formulas_executed"] is False
        assert result["provenance"]["aggregate_scope"] == "all_matched_rows_after_filters"
        assert result["plan_sha256"] == fingerprint(result["plan"])
        pure = {key: value for key, value in result.items() if key not in {"status", "path", "file_sha256", "request_sha256", "result_sha256"}}
        assert result["result_sha256"] == fingerprint(pure)
        assert result["request_sha256"] == fingerprint(self.request)
        raw = self.original_bytes()
        assert result["file_sha256"] == hashlib.sha256(raw).hexdigest()
        if self.case in {"F10", "F11", "F12"}:
            assert raw == ORIGINAL and len(raw) == 183 and result["file_sha256"] == ORIGINAL_SHA
        receipt = body["read_events"][0]
        assert receipt["executed"] is True and receipt["outcome"] == "SUCCESS"
        assert receipt["conversation_id"] == self.conversation["id"]
        assert receipt["request_revision"] == self.conversation["revision"]
        assert receipt["owner_kind"] == "assistant" and receipt["owner_id"] == "app-assistant"
        for field in ("file_sha256", "request_sha256", "plan_sha256", "result_sha256"):
            assert receipt[field] == result[field]
        assert "Interpretación aplicada" in body["assistant_message"]
        assert "1 −" in body["assistant_message"] and "100" in body["assistant_message"]
        assert result["file_sha256"] in body["assistant_message"]
        saved = self.get_saved()
        assert saved == body["conversation"]
        assert saved["revision"] == self.conversation["revision"] + 2
        last = saved["messages"][-1]
        assert last["content"] == body["assistant_message"]
        assert last["references"]["csv_analysis"] == result
        assert last["references"]["sources"] == body["sources"]
        connection = sqlite3.connect("file:" + str(self.server.CONVERSATIONS.database_path) + "?mode=ro", uri=True)
        try:
            row = connection.execute("SELECT revision,(SELECT count(*) FROM messages WHERE conversation_id=c.id) FROM conversations c WHERE id=?", (self.conversation["id"],)).fetchone()
            persisted = connection.execute("SELECT references_json FROM messages WHERE id=?", (last["id"],)).fetchone()[0]
        finally:
            connection.close()
        assert row == (saved["revision"], len(saved["messages"]))
        assert json.loads(persisted)["csv_analysis"] == result
        return {"response": sanitized(body), "saved_get_matches_post": True,
                "independent_sqlite_revision_messages": list(row), "source_bytes": len(raw),
                "source_sha256": result["file_sha256"], "query_input": calls[0],
                "all_three_hashes_independently_recomputed": True}


def exercise(case, rig):
    if case == "F10":
        plain = rig.chat_body()
        plain.pop("csv_read")
        plain["message"] = "Analiza el CSV del proyecto en " + CSV_PATH + ". Calcula pendientes y total general."
        response = rig.call("POST", "/api/chat/control", plain)
        assert response.status_code == 200 and not rig.csv_reads, response.text
        assert response.json().get("sources") == []
        assert "No he leído" in response.json()["assistant_message"]
        rig.conversation = response.json()["conversation"]
        rig.save_read()
        rig.grant_ok()
        result = rig.assert_answer(rig.chat())
        result["path_alone_initial_response"] = response.json()["assistant_message"]
        return result
    rig.save_read()
    if case in {"F11", "F12"}:
        response = rig.chat()
        assert response.status_code == 403
        assert response.json()["detail"]["code"] == "READ_AUTHORIZATION_REQUIRED"
        assert not rig.csv_reads
        metadata = rig.call("POST", "/api/project-permissions/directories", {**rig.expected(), "directory": "demo-usuario/archivo"})
        assert metadata.status_code == 200 and not rig.csv_reads
        assert CSV_PATH in json.dumps(metadata.json())
        assert "Alba" not in json.dumps(metadata.json())
        rig.grant_ok()
        result = rig.assert_answer(rig.chat())
        result["saved_read_without_request_grant_denied"] = True
        result["metadata_selection_reads_no_csv_bytes"] = True
        result["transport"] = [entry["path"] for entry in rig.http]
        assert not any("knowledge" in path or "document" in path for path in result["transport"])
        return result
    if case in {"owner_id", "owner_kind"}:
        response = rig.grant({case: "other-owner" if case == "owner_id" else "agent"})
        return rig.assert_denied(response, "conversation_not_found")
    if case in {"absolute_path", "traversal", "windows_path", "hidden_path", "symlink", "hardlink", "byte_limit"}:
        path = {"absolute_path": str(rig.outside), "traversal": "../outside.csv",
                "windows_path": "C:\\outside.csv", "hidden_path": ".bago/private.csv"}.get(case, CSV_PATH)
        if case == "hidden_path":
            target = rig.root / path
            target.parent.mkdir(exist_ok=True)
            target.write_bytes(b"private,value\nEXTERNAL_CELL,777\n")
        if case in {"symlink", "hardlink"}:
            rig.target.unlink()
            (rig.target.symlink_to(rig.outside) if case == "symlink" else os.link(rig.outside, rig.target))
        if case == "byte_limit":
            rig.target.write_bytes(b"a,b\n" + b"x" * (256 * 1024))
        rig.request["csv_read"]["path"] = path
        return rig.assert_denied(rig.grant())
    if case in {"bad_quotes", "bad_width", "duplicate_headers", "line_limit", "not_utf8", "numeric_error", "decimal_comma"}:
        replacements = {
            "bad_quotes": b'a,b\n"unterminated,2\n', "bad_width": b"a,b\n1,2,3\n",
            "duplicate_headers": b"a,a\n1,2\n", "line_limit": b"a,b\n" + b"1,2\n" * 250,
            "not_utf8": b"a,b\n\xff,2\n",
            "numeric_error": ORIGINAL.replace(b"12,18.50,10", b'12,"18,50",10'),
            "decimal_comma": ORIGINAL.decode().replace(",", ";").replace("18.50", "18,50").replace("9.00", "9,00").replace("6.25", "6,25").encode(),
        }
        rig.target.write_bytes(replacements[case])
        if case == "decimal_comma":
            rig.request["csv_read"].update(delimiter=";", decimal_separator=",")
    if case in {"legacy_stop", "invalid_stop"}:
        state = rig.root / ".bago/team/runtime/state.json"
        state.parent.mkdir(parents=True, exist_ok=True)
        state.write_text(json.dumps({"protocol_version": "0.1.0", "lifecycle": "ACTIVE"}) if case == "legacy_stop" else "{invalid", encoding="utf-8")
        return rig.assert_denied(rig.grant(), "STOP_STATE_UNVERIFIABLE")
    if case in {"stop_before", "stop_during_provider", "stop_before_publication"}:
        rig.create_mission()
    if case == "absent":
        return rig.assert_denied(rig.chat(), "READ_AUTHORIZATION_REQUIRED")
    if case == "invented":
        rig.token = "invented-token"
        return rig.assert_denied(rig.chat(), "READ_AUTHORIZATION_REQUIRED")
    if case == "legacy_ticket":
        response = rig.grant({"csv_request": None, "expected_project": None})
        assert response.status_code == 200
        return rig.assert_denied(rig.chat(), "READ_AUTHORIZATION_REQUIRED")
    rig.grant_ok()
    if case == "replay":
        first = rig.assert_answer(rig.chat())
        reads = len(rig.csv_reads)
        stale = rig.chat()
        assert stale.status_code == 409 and stale.json()["detail"]["code"] == "conversation_revision_conflict"
        current = rig.chat({"revision": first["response"]["revision"]})
        assert current.status_code == 403 and current.json()["detail"]["code"] == "READ_AUTHORIZATION_SCOPE_MISMATCH"
        assert len(rig.csv_reads) == reads
        return {"first_answer_persisted": True, "replay_old_revision_status": 409, "replay_new_revision_status": 403, "no_second_read": True}
    if case in {"expired", "revoked"}:
        rig.expire() if case == "expired" else rig.revoke()
        return rig.assert_denied(rig.chat(), "READ_AUTHORIZATION_" + case.upper())
    if case == "conversation":
        other = rig.call("POST", "/api/conversations", {"owner_kind": "assistant", "owner_id": "app-assistant"}).json()
        return rig.assert_denied(rig.chat({"conversation_id": other["id"]}), "READ_AUTHORIZATION_SCOPE_MISMATCH")
    if case == "revision":
        changed = rig.call("PATCH", "/api/conversations/" + rig.conversation["id"], {"revision": 0, "title": "Concurrent title"})
        assert changed.status_code == 200
        return rig.assert_denied(rig.chat({"revision": changed.json()["revision"]}), "READ_AUTHORIZATION_SCOPE_MISMATCH")
    if case == "archived":
        changed = rig.call("POST", "/api/conversations/" + rig.conversation["id"] + "/archive", {"revision": 0})
        assert changed.status_code == 200
        return rig.assert_denied(rig.chat({"revision": changed.json()["revision"]}), "invalid_csv_chat_request")
    if case in {"message", "path", "delimiter", "decimal_separator"}:
        if case == "message":
            rig.request["message"] = "Una pregunta diferente."
        else:
            rig.request["csv_read"][case] = {"path": "demo-usuario/archivo/other.csv", "delimiter": ";", "decimal_separator": ","}[case]
        return rig.assert_denied(rig.chat(), "READ_AUTHORIZATION_REQUEST_MISMATCH")
    if case == "mixed_grants":
        return rig.assert_denied(rig.chat({"web_read_authorization_id": "unrelated-web-token"}), "invalid_csv_chat_request")
    if case in {"project", "binding"}:
        rig.bind(rig.directory / "other-project")
        if case == "binding":
            rig.bind(rig.root)
        return rig.assert_denied(rig.chat(), "conversation_not_found" if case == "project" else "project_context_changed")
    if case in {"policy_revoked", "policy_regranted"}:
        rig.revoke_policy()
        if case == "policy_regranted":
            rig.save_read()
        return rig.assert_denied(rig.chat(), {"revision_conflict", "permission_denied"})
    if case == "changed_before":
        rig.target.write_bytes(ORIGINAL.replace(b"18.50", b"88.50"))
        return rig.assert_denied(rig.chat(), "FILE_CHANGED_SINCE_AUTHORIZATION")
    if case == "changed_during":
        rig.read_hook = lambda: rig.target.write_bytes(ORIGINAL.replace(b"18.50", b"88.50"))
        return rig.assert_denied(rig.chat(), "FILE_CHANGED_DURING_READ", io=True)
    if case in {"changed_after", "replaced_after"}:
        def change():
            if case == "changed_after":
                rig.target.write_bytes(ORIGINAL.replace(b"18.50", b"88.50"))
            else:
                replacement = rig.target.with_name("replacement.tmp")
                replacement.write_bytes(ORIGINAL)
                os.replace(replacement, rig.target)
        rig.provider_hook = change
        return rig.assert_denied(rig.chat(), "FILE_CHANGED_SINCE_AUTHORIZATION", io=True, provider=True)
    if case == "stop_before":
        rig.pause()
        result = rig.assert_denied(rig.chat(), "STOP_ACTIVE")
        assert rig.get_saved()["messages"] == []
        return result
    if case in {"revoke_during_provider", "expiry_during_provider", "stop_during_provider", "stop_before_publication", "revoke_before_publication"}:
        entered, release = threading.Event(), threading.Event()
        def gate():
            entered.set()
            assert release.wait(15), "test release timed out"
        if case.endswith("publication"):
            original_trace = rig.server._record_agent_chat_trace
            once = [False]
            def observed_trace(*args, **kwargs):
                result = original_trace(*args, **kwargs)
                if not once[0]:
                    once[0] = True
                    gate()
                return result
            rig.server._record_agent_chat_trace = observed_trace
        else:
            rig.provider_hook = gate
        response = {}
        failures = []
        def request():
            try: response["value"] = rig.chat()
            except BaseException as error: failures.append(error)
        thread = threading.Thread(target=request)
        thread.start()
        try:
            assert entered.wait(15), "request did not reach adversarial boundary"
            assert len(rig.csv_reads) == 1
            if case.startswith("revoke"):
                rig.revoke()
                code = "READ_AUTHORIZATION_REVOKED"
            elif case.startswith("expiry"):
                rig.expire()
                code = "READ_AUTHORIZATION_EXPIRED"
            else:
                rig.pause()
                code = "STOP_ACTIVE"
        finally:
            release.set()
            thread.join(20)
        assert not thread.is_alive() and not failures, failures
        return rig.assert_denied(response["value"], code, io=True, provider=True)
    if case == "unknown_column":
        rig.plan = {"select": ["nonexistent_column"]}
    elif case == "invalid_operator":
        rig.plan = {"derive": [{"name": "pwn", "expression": {"op": "exec", "args": [{"number": "1"}, {"number": "2"}]}}], "select": ["pwn"]}
    elif case == "no_plan":
        rig.custom_turn = {"content": "The invented total is 999999."}
    elif case == "multiple_plans":
        rig.custom_turn = {"tool_calls": [{"function": {"name": "query_csv", "arguments": PLAN}}] * 2}
    elif case == "duplicate_plan_keys":
        rig.custom_turn = {"tool_calls": [{"function": {"name": "query_csv", "arguments": '{"select":["pedido"],"select":["cliente"]}'}}]}
    elif case == "provider_error":
        rig.raise_provider = True
    elif case == "division_zero":
        rig.plan = {"derive": [{"name": "invalid", "expression": {"op": "div", "args": [{"column": "unidades"}, {"number": "0"}]}}], "select": ["invalid"]}
    elif case == "display_limit":
        rig.plan["limit"] = 1
    if case in {"decimal_comma", "display_limit"}:
        return rig.assert_answer(rig.chat(), limited=case == "display_limit")
    codes = {"bad_quotes": "CSV_MALFORMED", "bad_width": "CSV_MALFORMED",
        "duplicate_headers": "CSV_HEADER_DUPLICATE", "line_limit": "CSV_LINE_LIMIT", "not_utf8": "NOT_UTF8_TEXT",
        "unknown_column": "CSV_UNKNOWN_COLUMN", "invalid_operator": "CSV_EXPRESSION_INVALID",
        "no_plan": "CSV_INTERPRETATION_REQUIRED", "multiple_plans": "CSV_INTERPRETATION_REQUIRED",
        "duplicate_plan_keys": "CSV_INVALID_QUERY", "provider_error": "CSV_PROVIDER_FAILED",
        "numeric_error": "CSV_NUMERIC_FORMAT", "division_zero": "CSV_DIVISION_BY_ZERO"}
    assert case in codes, case
    before_provider = case in {"bad_quotes", "bad_width", "duplicate_headers", "line_limit", "not_utf8"}
    return rig.assert_denied(rig.chat(), codes[case], io=True, provider=not before_provider)


def child_main(case):
    before = {path: hashlib.sha256((REPO / path).read_bytes()).hexdigest() for path in SOURCE_FILES}
    started = time.time()
    with tempfile.TemporaryDirectory(prefix="adl-csv-http-", dir="/tmp") as temporary:
        rig = Rig(Path(temporary), case)
        try:
            report = exercise(case, rig)
            assert rig.server.SERVER_SOURCE_SHA256_AT_IMPORT == before["src/api/server.py"]
            after = {path: hashlib.sha256((REPO / path).read_bytes()).hexdigest() for path in SOURCE_FILES}
            assert before == after, "implementation changed during independent verification"
            report.update(case=case, status="PASS", verification="REAL_HTTP_FILES_POLICY_STORE_CONTROLLED_INTERPRETER",
                          started_at=started, seconds=round(time.time() - started, 3),
                          source_sha256=before, server_source_sha256_at_import=rig.server.SERVER_SOURCE_SHA256_AT_IMPORT,
                          http=rig.http, csv_read_count=len(rig.csv_reads),
                          query_provider_calls=sum(item["tool_names"] == ["query_csv"] for item in rig.provider_calls),
                          sqlite_root_location="/tmp", live_provider="NOT_RUN", windows="NOT_RUN")
            evidence = os.environ.get("ADL_CSV_FLOW_EVIDENCE_DIR")
            if evidence:
                output = Path(evidence)
                output.mkdir(parents=True, exist_ok=True)
                (output / (case + ".json")).write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            print("CSV_FLOW_EVIDENCE=" + json.dumps({"case": case, "status": "PASS", "seconds": report["seconds"]}))
        finally:
            rig.close()


@pytest.mark.parametrize("case", CASES)
def test_governed_csv_http_flow(case):
    completed = subprocess.run([sys.executable, str(Path(__file__).resolve()), "--case", case],
                               cwd=REPO, capture_output=True, text=True, timeout=75)
    assert completed.returncode == 0, completed.stdout[-4000:] + "\n" + completed.stderr[-10000:]
    assert '"status": "PASS"' in completed.stdout


if __name__ == "__main__":
    assert len(sys.argv) == 3 and sys.argv[1] == "--case" and sys.argv[2] in CASES
    child_main(sys.argv[2])
