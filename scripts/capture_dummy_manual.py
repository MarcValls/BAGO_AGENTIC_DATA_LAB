from __future__ import annotations

import json
import os
from pathlib import Path

from playwright.sync_api import sync_playwright


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs" / "agent-chat-control" / "assets" / "manual"
BASE = "http://127.0.0.1:5173"

job = {
    "job_id": "job_demo_593e2eb6", "agent_id": None, "job_type": "demo",
    "status": "success", "created_at": "2026-10-19T12:54:02Z",
    "completed_at": "2026-10-19T12:54:06Z", "duration_ms": 4190,
    "exit_code": 0, "stdout": "Resultado de demostración", "stderr": "",
    "cost_usd": 0.0, "metrics": {},
}
agent = {"id": "agent_demo_soporte", "config": {"name": "Agente de ejemplo", "description": "Responde preguntas usando información ficticia.",
    "type": "rag", "system_prompt": "Usa solo el contexto de demostración.", "tools": ["retrieval.search"],
    "provider_id": "ollama-cloud", "model_id": "qwen3:8b"}}
suite = {
    "id": "suite_demo_01", "name": "Comprobación de respuestas", "agent_id": agent["id"],
    "version": 1, "revision": 1,
    "cases": [{"id": "case_demo_01", "name": "Respuesta breve", "prompt": "Resume el estado de un pedido ficticio.", "must_include": ["pedido"], "must_not_include": ["contraseña"]}],
    "created_at": "2026-10-19T12:00:00Z", "updated_at": "2026-10-19T12:00:00Z",
}
run = {
    "id": "eval_demo_01", "suite_id": suite["id"], "suite_version": 1,
    "suite_name": suite["name"], "agent_id": agent["id"], "agent_name": agent["config"]["name"],
    "agent_config_fingerprint": "demo-only", "provider_id": "ollama-cloud", "model_id": "qwen3:8b",
    "status": "PASS", "total_cases": 1, "passed_cases": 1, "failed_cases": 0,
    "error_cases": 0, "duration_ms": 820, "started_at": "2026-10-19T12:05:00Z",
    "completed_at": "2026-10-19T12:05:01Z",
    "cases": [{"case_id": "case_demo_01", "name": "Respuesta breve", "status": "PASS",
        "checks": [{"name": "must_include", "passed": True, "detail": "Incluye 'pedido'."}],
        "answer_preview": "El pedido ficticio está en preparación.", "duration_ms": 820,
        "trace": {"trace_id": "trace_demo_01", "trace_state": "saved"}}],
}

artifact = {
    "summary": {"status": "PASS", "case": "Caso de demostración", "client": "Cliente de ejemplo",
        "evaluation_checks": [{"name": "Respuesta presente", "passed": True}], "cost_usd": 0.0,
        "retrieval_hits": 1, "ontology_paths": 1, "ontology_outcome": "SUCCESS",
        "sandbox_status": "not_used", "trace_events": 3, "scope": "Datos sintéticos",
        "aws_live": False, "openmetadata_live": False},
    "agent_run": {"run_id": "run_demo_01", "status": "success", "query": "¿Cuál es el estado del pedido de ejemplo?",
        "answer": "El pedido ficticio está en preparación.", "citations": ["pedido_demo.txt · Estado: en preparación."],
        "retrieval": {"eligible_count": 1, "filtered_count": 0, "mode": "hybrid", "pipeline": ["Consulta normalizada", "Búsqueda híbrida", "Contexto reunido"],
            "hits": [{"rank": 1, "score": 0.91, "lexical_score": 0.84, "semantic_score": 0.93,
                "document_id": "pedido_demo", "chunk_id": "pedido_demo_01", "evidence": {"citation": "pedido_demo.txt"}}]},
        "ontology": {"paths": [{"nodes": ["Pedido", "Estado"], "triples": []}], "inferred_triples": [],
            "receipt": {"outcome": "SUCCESS", "contradictions_found": 0}, "sparql_queries": ["SELECT ?estado WHERE { ?pedido demo:estado ?estado }"] , "evidence_refs": []},
        "proposals": []},
    "receipts": {"decision_receipts": [], "mcp_receipts": [], "provider_receipt": None, "sandbox_receipt": None},
    "trace": {"trace_id": "trace_demo_01", "run_id": "run_demo_01", "event_count": 3, "cost_usd": 0.0,
        "events": [{"sequence": i, "status": "success", "kind": kind, "name": name,
            "attributes": {"demo": True}, "evidence_refs": []}
            for i, (kind, name) in enumerate([("input", "Pregunta recibida"), ("retrieval", "Contexto encontrado"), ("answer", "Respuesta preparada")], 1)],
        "evidence_refs": []},
    "evaluation": {"status": "PASS", "score": 1.0, "cost_usd": 0.0,
        "checks": [{"name": "Respuesta presente", "passed": True, "detail": "La respuesta contiene el dato esperado."}], "evidence_refs": []},
}

scan_result = {"result": {"ok": True, "directory": "src", "files_scanned": 3, "files_skipped": 0,
    "lines_scanned": 124, "bytes_scanned": 4096, "finding_count": 1, "truncated": False,
    "manifest_sha256": "0" * 64, "supported_extensions": [".py"],
    "method": {"exact": "Comparación exacta de bloques", "similar": "Comparación estructural acotada"},
    "limitations": ["Resultado sintético para el manual."],
    "findings": [{"kind": "exact_block", "similarity": 1.0,
        "left": {"path": "src/demo_a.py", "start_line": 4, "end_line": 6, "name": "ejemplo_a"},
        "right": {"path": "src/demo_b.py", "start_line": 8, "end_line": 10, "name": "ejemplo_b"}}]},
    "receipt": {"path": "demo/manifest.json", "files_scanned": 3, "finding_count": 1,
        "manifest_sha256": "0" * 64, "duration_ms": 12, "truncated": False,
        "files": [{"path": "src/demo_a.py", "sha256": "1" * 64, "bytes": 1024},
                  {"path": "src/demo_b.py", "sha256": "2" * 64, "bytes": 2048}]},
    "trace": {"trace_id": "trace_scan_demo", "trace_state": "demo"}, "conversation_id": "conv_scan_demo"}


def response_for(path: str, method: str):
    path = path.split("?", 1)[0]
    if path.endswith("/api/health"):
        return {"status": "ok"}
    if path.endswith("/api/jobs/list"):
        return {"jobs": [job]}
    if path.endswith("/api/capabilities/proposals"):
        if method == "POST":
            return {"proposal": {"id": "proposal_demo_01", "capability_id": "demo.read", "capability_fingerprint": "demo",
                "effect": "read", "summary": "Propón una propuesta para demo.read", "requested_scope": "Solo archivos de ejemplo del proyecto.",
                "conversation_id": "conv_scan_demo", "status": "PENDING_REVIEW", "revision": 1,
                "created_at": "2026-10-19T12:00:00Z", "expires_at": "2026-10-26T12:00:00Z", "updated_at": "2026-10-19T12:00:00Z"},
                "authority_notice": "Propuesta ficticia guardada para revisión; no concede permisos ni ejecuta trabajos."}
        return {"proposals": []}
    if path.endswith("/api/capabilities"):
        return {"capabilities": [{"id": "demo.read", "name": "Consulta de ejemplo", "provider": "local",
            "effect": "read", "status": "AVAILABLE", "integration": "mock", "summary": "Capacidad ficticia para ilustrar el catálogo.",
            "limits": {"demo": True}, "source_fingerprints": {}, "source_available": True, "fingerprint": "demo"}]}
    if path.endswith("/api/providers/ollama/status"):
        return {"provider_id": "ollama-cloud", "state": "configured_unverified", "runtime_mode": "host",
            "auth_mode": "local_cli", "model_id": "qwen3:8b", "message": "Estado sintético"}
    if path.endswith("/api/providers/ollama/models"):
        return {"models": [{"provider_id": "ollama-cloud", "model_id": "qwen3:8b", "display_name": "Qwen 3 · 8B (demo)",
            "source": "demo", "availability_confidence": "illustrative"}], "source": "demo"}
    if path.endswith("/api/chat/context"):
        return {"workspace_root": "C:/proyecto-demo", "cognition": {"profile": "BAGO5_CHAT_COGNITION_V0.1", "capacity": 6, "max_hops": 2, "max_expansions": 4},
            "memory": {"kind": "local", "state": "present", "description": "Ubicación ficticia"},
            "paths": [{"id": "project", "label": "Contexto del proyecto", "path": "docs/ejemplo.md", "state": "present", "kind": "file", "purpose": "Ejemplo ilustrativo."}]}
    if path.endswith("/api/artifacts"):
        return artifact
    if path.endswith("/api/agents/list"):
        return {"agents": [agent]}
    if path.endswith("/api/providers/ollama/models"):
        return {"models": [{"model_id": "qwen3:8b", "display_name": "Qwen 3 · 8B (demo)"}]}
    if path.endswith("/api/evaluations/suites"):
        return {"suites": [suite]}
    if path.endswith("/api/evaluations/runs"):
        return {"runs": [run]}
    if "/api/evaluations/suites/" in path and path.endswith("/run"):
        return {"run": run}
    if path.endswith("/api/evaluations/suites") and method == "POST":
        return {"suite": suite}
    if path.endswith("/api/conversations") and method == "POST":
        return {"id": "conv_scan_demo", "revision": 1}
    if path.endswith("/api/workspace-scan/authorizations"):
        return {"authorization_id": "auth_scan_demo"}
    if path.endswith("/api/workspace-scan/run"):
        return scan_result
    if path.endswith("/api/chat/context/check-path"):
        return {"path": "docs/ejemplo.md", "state": "present", "kind": "file"}
    if path.endswith("/api/providers/ollama/verify"):
        return {"model_available": True, "model_id": "qwen3:8b"}
    return {}


def install_mock(page):
    def handle(route):
        request = route.request
        body = response_for(request.url, request.method)
        route.fulfill(status=200, content_type="application/json", body=json.dumps(body, ensure_ascii=False))
    page.route("**/api/**", handle)


def capture(page, name: str):
    page.screenshot(path=str(OUT / name), full_page=True, animations="disabled")
    print(name, flush=True)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(viewport={"width": 1600, "height": 1100}, device_scale_factor=1)
        page = context.new_page()
        page.on("pageerror", lambda error: print("PAGEERROR:", error, flush=True))
        page.on("console", lambda message: print("CONSOLE:", message.text, flush=True) if message.type == "error" else None)
        install_mock(page)
        page.goto(BASE, wait_until="networkidle")
        page.get_by_role("main", name="Chat view").wait_for()
        page.wait_for_timeout(500)
        capture(page, "05-chat-vista-completa.png")

        # Chat workflows: prepare one exact-file read and a capability proposal.
        page.get_by_label("Allow project file reads").check()
        page.get_by_label("Project-relative paths").fill("docs/ejemplo.md")
        capture(page, "30-chat-lectura-autorizacion-preparada.png")
        page.goto(BASE, wait_until="networkidle")
        page.get_by_role("main", name="Chat view").wait_for()
        page.get_by_label("Message the assistant or selected agent").fill("Prepara una propuesta de capacidad demo.read con alcance limitado a archivos de ejemplo")
        page.get_by_role("button", name="Send").click()
        page.locator(".capability-chat-card").wait_for()
        capture(page, "31-chat-propuesta-capacidad-revision.png")
        page.get_by_label("Requested scope").fill("Solo archivos de ejemplo del proyecto.")
        page.get_by_role("button", name="Save proposal").click()
        page.get_by_text("proposal_demo_01", exact=True).wait_for()
        capture(page, "32-chat-propuesta-capacidad-guardada-demo.png")

        page.goto(BASE, wait_until="networkidle")
        page.get_by_role("main", name="Chat view").wait_for()

        for label, filename in [("Capabilities", "06-capacidades.png"), ("Agent Builder", "07-creador-agentes.png"),
                                ("Agent Runs", "08-ejecuciones-agente.png"), ("Agent Evaluation Lab", "09-laboratorio-evaluacion.png")]:
            page.get_by_role("navigation", name="Interaction layer").get_by_role("button", name=label).click()
            page.wait_for_timeout(350)
            capture(page, filename)

        # Bounded scan surface can be opened from Agent Runs without touching workspace files.
        page.get_by_role("navigation", name="Interaction layer").get_by_role("button", name="Agent Runs").click()
        page.wait_for_timeout(300)
        capture(page, "10-escaner-carpetas-inicial.png")
        page.get_by_label("Project-relative source directory").fill("src")
        page.get_by_label("Authorize one read-only scan of this exact directory for this run.").check()
        capture(page, "11-escaner-autorizacion.png")
        page.get_by_role("button", name="Scan for duplicate code").click()
        page.get_by_text("Read-only scan complete").wait_for()
        capture(page, "12-escaner-resultado-demo.png")

        # Agent builder wizard: template -> configuration -> preview -> mocked save.
        page.get_by_role("navigation", name="Interaction layer").get_by_role("button", name="Agent Builder").click(force=True)
        page.get_by_text("Basic RAG Agent", exact=True).click()
        page.wait_for_timeout(200)
        capture(page, "13-agente-plantilla.png")
        page.get_by_role("button", name="Preview").click()
        capture(page, "14-agente-revision.png")
        page.get_by_role("button", name="Save Agent").click()
        page.wait_for_timeout(1250)
        capture(page, "15-agente-guardado-demo.png")

        # Evaluation Lab: select seeded suite, review and deterministic mocked run.
        page.get_by_role("navigation", name="Interaction layer").get_by_role("button", name="Agent Evaluation Lab").click()
        page.locator(".eval-suite-option").filter(has_text="Comprobación de respuestas").click()
        page.wait_for_timeout(200)
        capture(page, "16-evaluacion-revision-demo.png")
        page.get_by_role("button", name="Run evaluation").click()
        page.get_by_text("PASS · Comprobación de respuestas v1").wait_for(timeout=3000)
        capture(page, "17-evaluacion-resultado-demo.png")

        # Data layer: take each view through the actual navigation controls.
        page.get_by_role("button", name="Open Inspect").click()
        data_views = [
            ("Decision Inspector", "18-inspector-decision.png"),
            ("Job History", "19-historial-jobs.png"),
            ("Summary", "20-resumen.png"),
            ("Retrieval & Ontology", "21-recuperacion-ontologia.png"),
            ("Authorization", "22-autorizacion.png"),
            ("Trace", "23-traza.png"),
            ("Evaluation", "24-evaluacion.png"),
        ]
        nav = page.get_by_role("navigation", name="Data views")
        for label, filename in data_views:
            nav.get_by_role("button", name=label).click()
            page.wait_for_timeout(300)
            capture(page, filename)
        nav.get_by_role("button", name="Job History").click()
        page.locator("tbody tr").first.click()
        capture(page, "33-job-seleccionado.png")
        # Inspector's internal decision/trace/action modes.
        nav.get_by_role("button", name="Decision Inspector").click()
        for label, filename in [("Trace", "25-inspector-traza.png"), ("Actions", "26-inspector-acciones.png")]:
            button = page.get_by_role("navigation", name="Inspector views").get_by_role("button", name=label, exact=True)
            if button.count():
                button.click()
                page.wait_for_timeout(150)
                capture(page, filename)
        page.get_by_role("button", name="Back to Workspace").click()

        # Settings pages. No API key is entered and no provider writes are made.
        page.get_by_role("button", name="Open settings").click()
        capture(page, "27-ajustes-proveedor.png")
        page.get_by_role("button", name="Check model listing").click()
        page.get_by_text("is listed by the configured provider").wait_for()
        capture(page, "34-ajustes-comprobacion-modelo.png")
        page.get_by_role("navigation", name="Settings sections").get_by_role("button", name="Cognition & context").click()
        page.locator("#context-locations-title").click()
        page.wait_for_timeout(250)
        capture(page, "28-ajustes-cognicion-contexto.png")
        page.get_by_label("BAGO5 experimental").check()
        capture(page, "35-ajustes-modo-bago5.png")

        browser.close()


if __name__ == "__main__":
    main()
