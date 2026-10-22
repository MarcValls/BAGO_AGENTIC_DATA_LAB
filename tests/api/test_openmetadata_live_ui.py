from __future__ import annotations

import json
import subprocess
from fastapi.testclient import TestClient

from src.api import server
from src.metadata import openmetadata_runtime as runtime


def test_status_reports_unavailable_without_leaking_configuration(monkeypatch):
    monkeypatch.setenv("OPENMETADATA_BASE_URL", "http://localhost:18585/api")
    monkeypatch.setenv("OPENMETADATA_HEALTH_URL", "http://localhost:18586/healthcheck")
    monkeypatch.setattr(runtime, "urlopen", lambda *a, **k: (_ for _ in ()).throw(OSError("secret-token")))
    response = TestClient(server.app).get("/api/catalog/openmetadata/status")
    assert response.status_code == 200
    assert response.json() == {"state": "unavailable", "configured": True, "healthy": False, "service_kind": "local_openmetadata"}
    assert "secret-token" not in response.text


def test_remote_endpoint_rejected_before_health_transport(monkeypatch):
    monkeypatch.setenv("OPENMETADATA_BASE_URL", "https://catalog.example/api")
    monkeypatch.setattr(runtime, "urlopen", lambda *a, **k: (_ for _ in ()).throw(AssertionError("transport called")))
    result = runtime.status()
    assert result["configured"] is False
    assert result["healthy"] is False


def test_confirmation_false_never_starts_validation(monkeypatch):
    monkeypatch.setattr(runtime, "run_live_validation", lambda: (_ for _ in ()).throw(AssertionError("validation started")))
    response = TestClient(server.app).post("/api/catalog/openmetadata/live-validation", json={"confirm_run": False})
    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "confirmation_required"


def test_validation_returns_normalized_checks_receipts_and_cleanup(monkeypatch):
    monkeypatch.setenv("OPENMETADATA_BASE_URL", "http://127.0.0.1:18585/api")
    monkeypatch.setenv("OPENMETADATA_HEALTH_URL", "http://127.0.0.1:18586/healthcheck")
    monkeypatch.setenv("OPENMETADATA_USERNAME", "local-user")
    monkeypatch.setenv("OPENMETADATA_PASSWORD", "local-password")

    result = {"status": "PASS", "cleanup_status": "PASS", "checks": [{"name": "health", "status": "PASS", "detail": "healthy"}], "receipts": [{"label": "search", "receipt_id": "r1", "operation": "search", "decision": "ALLOW", "outcome": "SUCCESS", "result_count": 1, "error_kind": None, "path": "/v1/search"}], "error": "ignored-password"}

    monkeypatch.setattr(runtime, "configured_urls", lambda: ("http://127.0.0.1:18585/api", "http://127.0.0.1:18586/healthcheck"))
    def fake_process(args, **kwargs):
        assert args[-1] == "--check"
        assert kwargs["env"]["OPENMETADATA_BASE_URL"] == "http://127.0.0.1:18585/api"
        return subprocess.CompletedProcess(args, 0, json.dumps({k: v for k, v in result.items() if k != "error"}) + "\nEvidence: NOT_WRITTEN (--check)\n", "ignored-password")
    monkeypatch.setattr(runtime.subprocess, "run", fake_process)
    response = TestClient(server.app).post("/api/catalog/openmetadata/live-validation", json={"confirm_run": True})
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "PASS" and data["cleanup_status"] == "PASS"
    assert data["cleanup_requested"] is True
    assert data["checks"][0]["name"] == "health"
    assert data["receipts"][0]["receipt_id"] == "r1"
    assert "ignored-password" not in response.text
    assert "local-password" not in response.text


def test_cleanup_failure_forces_failed_overall_and_exception_is_not_exposed(monkeypatch):
    monkeypatch.setenv("OPENMETADATA_USERNAME", "local-user")
    monkeypatch.setenv("OPENMETADATA_PASSWORD", "secret-pass")
    monkeypatch.setattr(runtime, "configured_urls", lambda: ("http://localhost:18585/api", "http://localhost:18586/healthcheck"))
    def fake_process(args, **kwargs):
        result = {"status": "PASS", "cleanup_status": "PARTIAL", "checks": [], "receipts": []}
        return subprocess.CompletedProcess(args, 0, json.dumps(result) + "\n", "raw exception secret-pass")
    monkeypatch.setattr(runtime.subprocess, "run", fake_process)
    response = TestClient(server.app).post("/api/catalog/openmetadata/live-validation", json={"confirm_run": True})
    assert response.status_code == 200
    assert response.json()["status"] == "FAIL"
    assert response.json()["cleanup_status"] == "PARTIAL"
    assert "secret-pass" not in response.text and "raw exception" not in response.text
