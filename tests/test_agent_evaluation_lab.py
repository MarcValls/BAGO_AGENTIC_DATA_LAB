import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from src.api import server
from src.evaluation.agent_lab import (
    EvaluationStore, EvaluationValidationError, SuiteConflict, config_fingerprint, contains_credential,
    evaluate_answer, overall_status, redact_credentials, validate_cases,
)
from src.providers.ollama import ProviderError


def valid_cases():
    return [
        {"id": "case_pass", "name": "required text", "prompt": "synthetic prompt", "must_include": ["green"]},
        {"id": "case_fail", "name": "missing text", "prompt": "second prompt", "must_include": ["absent"]},
        {"id": "case_error", "name": "provider error", "prompt": "third prompt"},
    ]


def test_sqlite_suites_are_versioned_and_revision_conflicts_are_rejected(tmp_path: Path):
    store = EvaluationStore(tmp_path / "workspace", tmp_path / "eval.sqlite3")
    suite = store.create_suite("Regression", "agent_12345678", valid_cases())
    updated = store.update_suite(suite["id"], "Regression v2", "agent_12345678", valid_cases()[:1], 0)

    assert suite["id"].startswith("evalsuite_")
    assert (suite["version"], suite["revision"]) == (1, 0)
    assert (updated["version"], updated["revision"]) == (2, 1)
    assert store.get_suite(suite["id"], 1)["name"] == "Regression"
    assert store.get_suite(suite["id"])["name"] == "Regression v2"
    with pytest.raises(SuiteConflict):
        store.update_suite(suite["id"], "stale", "agent_12345678", valid_cases(), 0)


@pytest.mark.parametrize("cases", [[], [{"name": "x", "prompt": ""}],
    [{"id": "case_dup", "name": "a", "prompt": "ok"}, {"id": "case_dup", "name": "b", "prompt": "ok"}],
    [{"id": "case_bad", "name": "a", "prompt": "ok", "unexpected": True}],
    [{"id": "case_long", "name": "a", "prompt": "x" * 4001}]])
def test_case_validation_rejects_bad_limits_and_fields(cases):
    with pytest.raises(EvaluationValidationError):
        validate_cases(cases)


def test_deterministic_checks_and_suite_statuses():
    checks, status = evaluate_answer("The answer is GREEN", {"must_include": ["green"], "must_not_include": ["red"]}, True)
    assert status == "PASS"
    assert {item["name"] for item in checks} == {"response_non_empty", "must_include", "must_not_include", "trace_local_saved"}
    assert overall_status(["PASS", "PASS"]) == "PASS"
    assert overall_status(["PASS", "FAIL"]) == "FAIL"
    assert overall_status(["PASS", "ERROR"]) == "PARTIAL"
    assert overall_status(["ERROR", "ERROR"]) == "ERROR"
    assert config_fingerprint({"b": 2, "a": 1}) == config_fingerprint({"a": 1, "b": 2})
    assert redact_credentials("Bearer abc123 remains private") == "[REDACTED] remains private"


def test_suite_rejects_credential_like_prompt_material():
    with pytest.raises(EvaluationValidationError, match="credentials"):
        validate_cases([{"id": "case_secret", "name": "secret", "prompt": "api_key=do-not-store"}])


def test_unlabeled_high_entropy_secrets_are_rejected_and_redacted():
    token = "aB3dE7gH1jK5mN9pQ2rT6vX8zC4fG0hJ"
    assert contains_credential(token)
    assert redact_credentials(f"unlabeled value {token}") == "unlabeled value [REDACTED]"
    with pytest.raises(EvaluationValidationError, match="credentials"):
        validate_cases([{"id": "case_token", "name": "secret token", "prompt": f"Use {token}"}])


def test_only_one_active_run_per_suite(tmp_path: Path):
    store = EvaluationStore(tmp_path / "workspace", tmp_path / "db.sqlite3")
    assert store.acquire_suite_run("evalsuite_one", "evalrun_one") is True
    assert store.acquire_suite_run("evalsuite_one", "evalrun_two") is False
    store.release_suite_run("evalsuite_one", "evalrun_one")
    assert store.acquire_suite_run("evalsuite_one", "evalrun_two") is True
    store.release_suite_run("evalsuite_one", "evalrun_two")


def test_suite_api_create_update_validation_and_conflict(monkeypatch, tmp_path: Path):
    monkeypatch.setattr(server, "EVALUATIONS", EvaluationStore(tmp_path / "workspace", tmp_path / "db.sqlite3"))
    monkeypatch.setattr(server, "_load_agent", lambda _id: _agent())
    client = TestClient(server.app)
    response = client.post("/api/evaluations/suites", json={"name": "suite", "agent_id": "agent_12345678", "cases": valid_cases()})
    assert response.status_code == 200
    suite = response.json()["suite"]
    update_body = {"name": "suite v2", "agent_id": "agent_12345678", "cases": valid_cases()[:1], "expected_revision": 0}
    updated = client.put(f"/api/evaluations/suites/{suite['id']}", json=update_body)
    assert updated.status_code == 200 and updated.json()["suite"]["version"] == 2
    stale = client.put(f"/api/evaluations/suites/{suite['id']}", json=update_body)
    assert stale.status_code == 409
    invalid = client.post("/api/evaluations/suites", json={"name": "bad", "agent_id": "agent_12345678", "cases": []})
    assert invalid.status_code == 422


def test_run_preflights_model_and_never_falls_back_to_fixtures(monkeypatch, tmp_path: Path):
    store = EvaluationStore(tmp_path / "workspace", tmp_path / "db.sqlite3")
    suite = store.create_suite("preflight", "agent_12345678", valid_cases())
    monkeypatch.setattr(server, "EVALUATIONS", store)
    monkeypatch.setattr(server, "_load_agent", lambda _id: _agent())
    monkeypatch.setattr(server.ollama, "status", lambda: {"provider_id": "ollama-cloud", "state": "needs_authentication"})
    monkeypatch.setattr(server.ollama, "chat", lambda *_args: pytest.fail("preflight must happen before inference"))
    client = TestClient(server.app)
    response = client.post(f"/api/evaluations/suites/{suite['id']}/run", json={"revision": 0, "model_id": "gemma4:31b-cloud"})
    assert response.status_code == 503
    assert response.json()["detail"]["code"] == "provider_not_ready"


def test_unlisted_model_is_rejected_before_inference(monkeypatch, tmp_path: Path):
    store = EvaluationStore(tmp_path / "workspace", tmp_path / "db.sqlite3")
    suite = store.create_suite("model preflight", "agent_12345678", valid_cases())
    monkeypatch.setattr(server, "EVALUATIONS", store)
    monkeypatch.setattr(server, "_load_agent", lambda _id: _agent())
    monkeypatch.setattr(server.ollama, "status", lambda: {"provider_id": "ollama-cloud", "state": "configured_unverified"})
    monkeypatch.setattr(server.ollama, "discover_models", lambda: {"models": [{"model_id": "other-model"}]})
    monkeypatch.setattr(server.ollama, "chat", lambda *_args: pytest.fail("unlisted model cannot reach inference"))
    client = TestClient(server.app)
    response = client.post(f"/api/evaluations/suites/{suite['id']}/run", json={"revision": 0, "model_id": "gemma4:31b-cloud"})
    assert response.status_code == 503
    assert response.json()["detail"]["code"] == "model_unavailable"


def test_real_run_api_preserves_case_trace_correlation_redacts_payload_and_has_no_side_effects(monkeypatch, tmp_path: Path):
    store = EvaluationStore(tmp_path / "workspace", tmp_path / "db.sqlite3")
    suite = store.create_suite("synthetic contract", "agent_12345678", valid_cases())
    monkeypatch.setattr(server, "EVALUATIONS", store)
    monkeypatch.setattr(server, "EVALUATION_TRACE_DIR", tmp_path / "traces")
    monkeypatch.setattr(server, "_load_agent", lambda _id: _agent())
    monkeypatch.setattr(server.ollama, "status", lambda: {"provider_id": "ollama-cloud", "state": "configured_unverified"})
    monkeypatch.setattr(server.ollama, "discover_models", lambda: {"models": [{"model_id": "gemma4:31b-cloud"}]})
    calls = []

    def provider_call(model, messages):
        calls.append((model, messages))
        prompt = messages[-1]["content"]
        if prompt == "third prompt":
            raise ProviderError("provider_timeout", "sensitive upstream details omitted")
        return "A green response." if prompt == "synthetic prompt" else "api_key=redact-this Another response."

    monkeypatch.setattr(server.ollama, "chat", provider_call)
    monkeypatch.setattr(server, "save_job", lambda *_args, **_kwargs: pytest.fail("evaluation must not create jobs"))
    monkeypatch.setenv("BAGO_OTEL_EXPORTER_OTLP_ENDPOINT", "")
    monkeypatch.setattr(server, "REPO_ROOT", tmp_path / "workspace")

    client = TestClient(server.app)
    response = client.post(f"/api/evaluations/suites/{suite['id']}/run", json={"revision": 0, "model_id": "gemma4:31b-cloud"})
    assert response.status_code == 200, response.text
    run = response.json()["run"]
    assert len(calls) == 3
    assert all(call[0] == "gemma4:31b-cloud" and len(call[1]) == 2 for call in calls)
    assert [item["status"] for item in run["cases"]] == ["PASS", "FAIL", "ERROR"]
    assert run["status"] == "PARTIAL"
    assert run["provider_id"] == "ollama-cloud" and run["usage"] == {"status": "not_reported"}
    assert store.get_run(run["id"]) == run
    assert client.get("/api/evaluations/runs").json()["runs"][0]["id"] == run["id"]
    assert client.get(f"/api/evaluations/runs/{run['id']}").json()["run"]["id"] == run["id"]
    assert "redact-this" not in json.dumps(run)
    assert "[REDACTED]" in run["cases"][1]["answer_preview"]
    for item in run["cases"]:
        trace = item["trace"]
        payload = json.loads((tmp_path / "traces" / f"{trace['trace_id']}.json").read_text(encoding="utf-8"))
        assert payload["trace_id"] == trace["trace_id"]
        assert payload["run_id"] == run["id"]
        event = payload["events"][0]
        assert event["attributes"]["evaluation_case_id"] == item["case_id"]
        assert event["attributes"]["cost_status"] == "not_reported"
        assert event["status"] == {"PASS": "SUCCESS", "FAIL": "FAILURE", "ERROR": "ERROR"}[item["status"]]
        serialized = json.dumps(payload)
        assert "synthetic prompt" not in serialized and "green response" not in serialized
        assert "sensitive upstream details" not in serialized
        assert "cost_usd" not in payload
    assert not list((tmp_path / "workspace").glob("**/*"))


def test_stale_run_revision_is_rejected_before_provider_preflight(monkeypatch, tmp_path: Path):
    store = EvaluationStore(tmp_path / "workspace", tmp_path / "db.sqlite3")
    suite = store.create_suite("stale", "agent_12345678", valid_cases())
    monkeypatch.setattr(server, "EVALUATIONS", store)
    monkeypatch.setattr(server, "_load_agent", lambda _id: pytest.fail("stale revision must be rejected first"))
    response = TestClient(server.app).post(f"/api/evaluations/suites/{suite['id']}/run", json={"revision": 99, "model_id": "gemma4:31b-cloud"})
    assert response.status_code == 409


def _agent():
    return server.AgentResponse.model_validate({
        "id": "agent_12345678", "created_at": "2026-10-10T00:00:00Z",
        "config": {"name": "Safe agent", "description": "Test only", "type": "rag",
                   "system_prompt": "Only answer from the synthetic input.", "provider_id": "ollama-cloud",
                   "model_id": "gemma4:31b-cloud", "tools": [], "retrieval_config": None, "sandbox_profile": None},
    })
