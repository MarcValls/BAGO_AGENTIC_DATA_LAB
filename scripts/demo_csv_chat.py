"""Reproduce a real governed CSV chat with controlled interpretation.

Run with the project's requirements-test.txt environment. By default this uses
real HTTP handlers, READ policy, grants, filesystem, toolkit, SQLite and traces
in a temporary directory. Only the provider/catalog is controlled. --serve
starts that same isolated fixture for the browser runner; it is not deployment.
"""
from __future__ import annotations

import argparse
from decimal import Decimal
import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile


REPO = Path(__file__).resolve().parents[1]
RELATIVE_CSV = "demo-usuario/archivo/pedidos-final.csv"
ORIGINAL_SHA = "8fe7a2979043c0e992f4e13d84055045ae1fec91bb896d365fe996367acbafe5"
QUESTION = "Analiza pedidos: importe descontado por pedido, pendientes por estado y total general."


if not __debug__:
    raise RuntimeError("Run this verification without -O/PYTHONOPTIMIZE; its assertions must remain enabled.")


def configure_fixture(directory: Path, *, port: int = 8080):
    # Process-local isolation: never inherit paths to the user's existing stores.
    for name in tuple(os.environ):
        if name.startswith(("BAGO_", "ADL_")):
            os.environ.pop(name)
    os.environ["BAGO_APP_ROOT"] = str(REPO)
    os.environ["BAGO_DATA_ROOT"] = str(directory / "data")
    os.environ["BAGO_API_PORT"] = str(port)
    os.environ["BAGO_OTEL_EXPORTER_OTLP_ENDPOINT"] = ""
    sys.path.insert(0, str(REPO))
    from src.api import server
    from src.project_folders import ProjectFolders, binding_identity

    evidence = REPO / "docs/verification/csv-chat-20261101/parser"
    original = (evidence / "pedidos-original.csv").read_bytes()
    assert len(original) == 183 and hashlib.sha256(original).hexdigest() == ORIGINAL_SHA
    plan = json.loads((evidence / "historical_query.json").read_text(encoding="utf-8"))
    root = directory / "project"
    target = root / RELATIVE_CSV
    target.parent.mkdir(parents=True)
    target.write_bytes(original)
    server._set_workspace_root(root)
    folders = ProjectFolders(
        state_directory=server._WORKSPACE_CONFIG_DIR / "project-folders-v1",
        workspace_root=server.current_workspace_root,
        set_workspace_root=server._set_workspace_root,
        pick_directory=server._pick_workspace_directory,
        binding_identity=lambda: binding_identity(server._WORKSPACE_CONFIG_PATH, server.current_workspace_root()),
        legacy_parent=lambda: None, binding_lock=server._WORKSPACE_LOCK,
    )
    prepared = folders.prepare(mode="existing", path=str(root), name="csv-historical-demo",
        title="CSV histórico · interpretación controlada", expected_workspace_root=str(root))
    folders.apply(prepared["plan_id"], plan_sha256=prepared["plan_sha256"], confirmed=True)
    policy = server._current_project_permissions()
    old = policy.snapshot()
    current = policy.save(expected_project_id=old["project_id"], expected_binding=old["binding"],
        expected_revision=old["revision"], read_directories=["demo-usuario"],
        write_directories=[], confirmed=True)
    selection = {"provider_id": "csv-controlled-fixture", "model_id": "query-plan-fixture",
        "label": "Interpretación controlada · no modelo real", "state": "ready"}
    server.provider_runtime.active_selection = lambda: dict(selection)
    server.provider_runtime.select_chat_model = lambda *args: dict(selection)
    server.provider_runtime.model_catalog = lambda: {
        "models": [{**selection, "chat_enabled": True, "orchestrator_enabled": True}], "warnings": []}
    server.provider_runtime.describe_providers = lambda: []
    server.export_local_trace_to_otlp = lambda *args, **kwargs: None
    observations = []

    def interpret(provider, model, messages, **kwargs):
        if [item["function"]["name"] for item in kwargs.get("tools", [])] != ["query_csv"]:
            return {"content": "Este servidor de prueba solo interpreta la consulta CSV explícita."}
        data = json.loads(messages[1]["content"])
        observations.append({"question": data["question"], "rows": len(data["csv_data"]["rows"]),
            "columns": data["csv_data"]["columns"], "controlled_interpretation": True})
        return {"tool_calls": [{"function": {"name": "query_csv", "arguments": plan}}]}

    server.provider_runtime.chat_turn = interpret
    return server, target, original, current, observations


def reproduce(server, target, original, policy, observations):
    from fastapi.testclient import TestClient
    with TestClient(server.app) as client:
        created = client.post("/api/conversations", json={"owner_kind": "assistant", "owner_id": "app-assistant"})
        assert created.status_code == 200, created.text
        conversation = created.json()
        question = {"message": QUESTION, "csv_read": {"path": RELATIVE_CSV,
            "delimiter": "auto", "decimal_separator": "."}}
        context = {"conversation_id": conversation["id"], "revision": conversation["revision"]}
        missing = client.post("/api/chat/control", json={"operation": "chat", **context, **question})
        assert missing.status_code == 403 and not observations, missing.text
        grant = client.post("/api/workspace-read/authorizations", json={
            "owner_kind": "assistant", "owner_id": "app-assistant", **context,
            "paths": [RELATIVE_CSV], "csv_request": question,
            "expected_project": {key: policy[key] for key in ("project_id", "binding", "revision")}})
        assert grant.status_code == 200, grant.text
        response = client.post("/api/chat/control", json={"operation": "chat", **context, **question,
            "workspace_read_authorization_id": grant.json()["authorization_id"]})
        assert response.status_code == 200, response.text
        body = response.json()
        analysis = body["csv_analysis"]
        assert analysis["status"] == "answered" and analysis["file_sha256"] == ORIGINAL_SHA, analysis
        assert [Decimal(row["values"]["importe"]) for row in analysis["selected_rows"]] == [
            Decimal("199.80"), Decimal("54.00"), Decimal("47.50")]
        assert {row["values"]["estado"]: Decimal(row["values"]["total"]) for row in analysis["rows"]} == {
            "pendiente": Decimal("247.30"), "entregado": Decimal("54.00")}
        assert Decimal(analysis["grand_totals"]["values"]["total"]) == Decimal("301.30")
        stored_response = client.get("/api/conversations/" + conversation["id"])
        assert stored_response.status_code == 200, stored_response.text
        stored = stored_response.json()
        assert stored["revision"] == body["revision"] == 2
        assert stored["messages"][-1]["references"]["csv_analysis"] == analysis
        assert stored["messages"][-1]["references"]["sources"] == body["sources"]
        assert target.read_bytes() == original and len(observations) == 1
        return {"status": "PASS", "verification": "CONTROLLED_INTERPRETATION_REAL_HTTP_FILESYSTEM_SQLITE",
            "without_request_grant": {"http_status": missing.status_code, "provider_calls": 0},
            "authorized_query": {"http_status": response.status_code, "persisted_revision": stored["revision"],
                "original_unchanged": True, "csv_analysis": analysis, "sources": body["sources"],
                "read_events": body["read_events"], "answer": body["assistant_message"]},
            "provider_observations": observations,
            "not_run": ["live model interpretation", "browser in this command", "user Windows/Brave installation"]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--serve", action="store_true", help="Serve the isolated browser fixture on loopback")
    parser.add_argument("--port", type=int, default=8080)
    parser.add_argument("--output", type=Path, help="Write the HTTP demonstration's JSON evidence")
    args = parser.parse_args()
    if not 1 <= args.port <= 65535:
        parser.error("--port must be between 1 and 65535")
    with tempfile.TemporaryDirectory(prefix="adl-csv-chat-demo-") as temporary:
        server, target, original, policy, observations = configure_fixture(Path(temporary).resolve(), port=args.port)
        if args.serve:
            import uvicorn
            print(json.dumps({"fixture": True, "provider": "controlled interpretation; not a real model",
                "project_root": str(target.parents[2]), "data_root": os.environ["BAGO_DATA_ROOT"],
                "url": f"http://127.0.0.1:{args.port}"}, ensure_ascii=False), flush=True)
            uvicorn.run(server.app, host="127.0.0.1", port=args.port, log_level="warning")
        else:
            report = reproduce(server, target, original, policy, observations)
            encoded = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
            if args.output:
                args.output.parent.mkdir(parents=True, exist_ok=True)
                args.output.write_text(encoded, encoding="utf-8")
            print(encoded)


if __name__ == "__main__":
    main()
