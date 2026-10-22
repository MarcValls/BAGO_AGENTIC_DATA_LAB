from fastapi.testclient import TestClient

from src.api import server
from src.providers import model_policy, registration


def test_orchestrator_models_are_chat_choices_independent_of_agent_assignment(tmp_path, monkeypatch):
    monkeypatch.setattr(registration, "REGISTRY_PATH", tmp_path / "registry.json")
    catalog = [
        {"provider_id": "ollama-cloud", "model_id": model}
        for model in ("both", "orchestrator-only", "agents-only")
    ]
    policy = model_policy.Policy(
        models=[
            model_policy.ModelUse(provider_id="ollama-cloud", model_id="both", chat=False, orchestrator=True, agent_types=["rag"]),
            model_policy.ModelUse(provider_id="ollama-cloud", model_id="orchestrator-only", chat=False, orchestrator=True),
            model_policy.ModelUse(provider_id="ollama-cloud", model_id="agents-only", chat=False, agent_types=["tool"]),
        ],
        main_chat="ollama-cloud|both",
    )

    model_policy.save(policy, "none", catalog)
    saved, _ = model_policy.read()

    assert model_policy.permits("ollama-cloud", "both")
    assert model_policy.permits("ollama-cloud", "orchestrator-only")
    assert not model_policy.permits("ollama-cloud", "agents-only")
    assert model_policy.permits("ollama-cloud", "agents-only", "tool")
    assert not model_policy.permits("ollama-cloud", "orchestrator-only", "tool")
    assert model_policy.assigned("tool", "ollama-cloud", "both") == ("ollama-cloud", "agents-only")
    assert saved is not None
    assert saved.models[0].chat is True and saved.models[0].orchestrator is True
    assert saved.models[1].chat is True and saved.models[1].orchestrator is True
    assert saved.models[2].chat is False and saved.models[2].orchestrator is False


def test_chat_model_catalog_lists_orchestrators_but_keeps_agent_only_models_available(tmp_path, monkeypatch):
    monkeypatch.setattr(registration, "REGISTRY_PATH", tmp_path / "registry.json")
    catalog = [
        {"provider_id": "ollama-cloud", "model_id": model, "label": "Ollama", "state": "ready"}
        for model in ("orchestrator", "agent-only")
    ]
    policy = model_policy.Policy(
        models=[
            model_policy.ModelUse(provider_id="ollama-cloud", model_id="orchestrator", orchestrator=True),
            model_policy.ModelUse(provider_id="ollama-cloud", model_id="agent-only", agent_types=["rag"]),
        ],
        main_chat="ollama-cloud|orchestrator",
    )
    model_policy.save(policy, "none", catalog)
    monkeypatch.setattr(server.provider_runtime, "model_catalog", lambda: {"models": catalog, "warnings": []})

    response = TestClient(server.app).get("/api/providers/chat-models")

    assert response.status_code == 200
    models = {item["model_id"]: item for item in response.json()["models"]}
    assert models["orchestrator"]["orchestrator_enabled"] is True
    assert models["orchestrator"]["chat_enabled"] is True
    assert models["agent-only"]["orchestrator_enabled"] is False
    assert models["agent-only"]["chat_enabled"] is False
    assert models["agent-only"]["agent_types"] == ["rag"]
