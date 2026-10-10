import json

from fastapi.testclient import TestClient

from src.api import server


def _write_team_snapshot(root, *, status="CLAIMED"):
    team_dir = root / ".codex-team"
    team_dir.mkdir(parents=True)
    state = {
        "updated_at": "2026-10-09T19:00:00+02:00",
        "terminal_gate": "OPEN",
        "mission": {
            "mission_id": "TEST_MISSION",
            "title": "Monitor fixture",
            "objective": "Exercise live team status",
            "max_concurrency": 3,
            "work_items": [
                {
                    "id": "W01",
                    "title": "Prepare fixture",
                    "role": "team-orchestrator",
                    "depends_on": [],
                }
            ],
        },
        "work_status": {
            "W01": {
                "status": status,
                "agent": "/agent/one",
                "claimed_at": "2026-10-09T19:00:00+02:00",
                "done_at": None,
            }
        },
    }
    (team_dir / "state.json").write_text(json.dumps(state), encoding="utf-8")
    (team_dir / "events.jsonl").write_text(
        json.dumps({
            "at": "2026-10-09T19:00:00+02:00",
            "kind": "CLAIM",
            "work_id": "W01",
            "agent": "/agent/one",
            "role": "team-orchestrator",
            "text": "private note must not be exposed",
        }) + "\n",
        encoding="utf-8",
    )


def test_team_status_is_read_only_sanitized_and_reflects_file_updates(tmp_path, monkeypatch):
    _write_team_snapshot(tmp_path)
    monkeypatch.setattr(server, "REPO_ROOT", tmp_path)

    with TestClient(server.app) as client:
        first = client.get("/api/team/status")
        assert first.status_code == 200
        payload = first.json()
        assert payload["mission"]["id"] == "TEST_MISSION"
        assert payload["active_agents"] == ["/agent/one"]
        assert payload["counts"] == {"CLAIMED": 1}
        assert payload["recent_events"][0]["kind"] == "CLAIM"
        assert "text" not in payload["recent_events"][0]

        state_path = tmp_path / ".codex-team" / "state.json"
        state = json.loads(state_path.read_text(encoding="utf-8"))
        state["work_status"]["W01"]["status"] = "DONE"
        state_path.write_text(json.dumps(state), encoding="utf-8")

        second = client.get("/api/team/status")
        assert second.status_code == 200
        assert second.json()["counts"] == {"DONE": 1}
        assert second.json()["active_agents"] == []


def test_team_status_reports_missing_or_invalid_state(tmp_path, monkeypatch):
    monkeypatch.setattr(server, "REPO_ROOT", tmp_path)

    with TestClient(server.app) as client:
        missing = client.get("/api/team/status")
        assert missing.status_code == 404

        team_dir = tmp_path / ".codex-team"
        team_dir.mkdir()
        (team_dir / "state.json").write_text("{", encoding="utf-8")
        invalid = client.get("/api/team/status")
        assert invalid.status_code == 503
        assert "invalid JSON" in invalid.json()["detail"]

        (team_dir / "state.json").write_text("[]", encoding="utf-8")
        invalid_root = client.get("/api/team/status")
        assert invalid_root.status_code == 503
        assert "JSON object" in invalid_root.json()["detail"]
