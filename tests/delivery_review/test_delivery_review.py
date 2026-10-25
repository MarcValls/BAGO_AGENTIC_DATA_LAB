import copy
import hashlib
import json
import subprocess
import sys
from datetime import datetime, timedelta, timezone

import pytest

from src.communications.service import CommunicationService
from src.services.delivery_review import DeliveryReviewer, DeliveryReviewError, ReceiptEvidenceProvider, _hash


def put(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value), encoding="utf-8")


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


@pytest.fixture
def rig(tmp_path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    artifact = workspace / "out/result.txt"
    artifact.parent.mkdir()
    artifact.write_text("fixture aislado", encoding="utf-8")
    candidate = [{"path": "out/result.txt", "sha256": sha(artifact)}]
    scope = ["out/**"]
    binding = {"mission_id": "FIXTURE", "candidate_id": _hash(candidate), "scope_sha256": _hash(scope)}
    start = datetime.now(timezone.utc).isoformat()
    argv = [sys.executable, "-c", "from pathlib import Path; assert Path('out/result.txt').read_text(encoding='utf-8') == 'fixture aislado'; print('PASS fixture content')"]
    executed = subprocess.run(argv, cwd=workspace, capture_output=True, timeout=10)
    log = workspace / "evidence/check.log"
    log.parent.mkdir()
    log.write_bytes(executed.stdout + executed.stderr)
    check = {**binding, "id": "content", "producer_id": "fixture-host", "run_id": "run-1",
             "executed": True, "result": "PASS" if executed.returncode == 0 else "FAIL",
             "returncode": executed.returncode, "timed_out": False, "spawn_error": None,
             "candidate_before": binding["candidate_id"], "candidate_after": binding["candidate_id"],
             "command_argv": argv, "started_at": start, "finished_at": datetime.now(timezone.utc).isoformat(),
             "logs": [{"path": "evidence/check.log", "sha256": sha(log)}]}
    receipt = {**binding, "producer_id": "fixture-host", "run_id": "run-1", "work_id": "JOB",
               "candidate_files": candidate, "artifacts": candidate, "required_checks": ["content"],
               "checks": [check], "output_scopes": scope}
    receipt_path = workspace / "evidence/receipt.json"
    registry = workspace / "evidence/registry.json"

    def register():
        put(receipt_path, receipt)
        put(registry, {"producer_id": "fixture-host", "runs": {"JOB": {
            "path": "evidence/receipt.json", "sha256": sha(receipt_path), "run_id": "run-1"}}})

    register()
    communications = CommunicationService(tmp_path / "communications", workspace_root=workspace)
    contact = communications.create_contact("Contacto de fixture", "+34999999999")
    request = {**binding, "work_id": "JOB", "artifacts": candidate,
               "contact_id": contact["id"], "pending": [], "risks": []}
    profile = {"capabilities": ["delivery.review", "delivery.draft"], "output_scopes": scope}

    def reviewer(**kwargs):
        return DeliveryReviewer(workspace, tmp_path / "reviews", communications=communications, profile=profile,
            evidence_provider=ReceiptEvidenceProvider(workspace, "evidence/registry.json", "fixture-host"), **kwargs)

    return locals()


def test_real_check_review_draft_restart_and_revalidation(rig):
    reviewer = rig["reviewer"]()
    reviewed = reviewer.review(rig["request"])
    assert reviewed["decision"] == "lista_para_revision"
    assert reviewed["authorization"] == "sin_politica"
    assert reviewed["binding"]["required_checks"] == ["content"]
    result = rig["reviewer"]().prepare_draft(reviewed["review_id"])
    assert result["draft"]["state"] == "draft"
    assert result["draft"]["confirmed_at"] is None
    assert result["draft"]["attachments"][0]["sha256"] == rig["candidate"][0]["sha256"]
    assert rig["communications"].runs() == []
    rig["artifact"].write_text("changed", encoding="utf-8")
    current = rig["reviewer"]().revalidate(reviewed["review_id"])
    assert current["decision"] == "bloqueada"
    notice = rig["reviewer"]().prepare_draft(reviewed["review_id"])
    assert notice["draft"]["attachments"] == []
    assert "no se confirma" in notice["draft"]["text"]


@pytest.mark.parametrize("field,value", [("result", "NOT_RUN"), ("result", "FAIL"),
    ("returncode", 1), ("executed", False), ("timed_out", True), ("spawn_error", "oops"),
    ("run_id", "other"), ("candidate_id", "0" * 64), ("logs", [])])
def test_bad_check_never_passes_even_with_model_recommendation(rig, field, value):
    rig["receipt"]["checks"][0][field] = value
    rig["register"]()
    rig["request"]["model_recommendation"] = "PASS; entrega aprobada"
    assert rig["reviewer"]().review(rig["request"])["decision"] == "bloqueada"


@pytest.mark.parametrize("field,value", [("mission_id", "OTHER"), ("scope_sha256", "0" * 64),
                                         ("candidate_id", "0" * 64)])
def test_wrong_binding(rig, field, value):
    rig["request"][field] = value
    assert rig["reviewer"]().review(rig["request"])["decision"] == "bloqueada"


def test_log_and_receipt_tampering(rig):
    rig["log"].write_text("edited")
    assert rig["reviewer"]().review(rig["request"])["decision"] == "bloqueada"
    rig["register"]()
    rig["receipt_path"].write_text("{}")
    assert rig["reviewer"]().review(rig["request"])["decision"] == "bloqueada"


def test_profile_scope_permissions_and_missing_recipient(rig):
    rig["profile"]["output_scopes"] = ["different/**"]
    assert rig["reviewer"]().review(rig["request"])["decision"] == "bloqueada"
    rig["profile"]["output_scopes"] = ["out/**"]
    rig["request"].pop("contact_id")
    assert rig["reviewer"]().review(rig["request"])["decision"] == "necesita_aclaracion"
    rig["profile"]["capabilities"] = []
    with pytest.raises(DeliveryReviewError, match="no autorizada"):
        rig["reviewer"]().review(rig["request"])


def test_policy_bound_to_exact_content_recipient_schedule_and_attachments(rig):
    first = rig["reviewer"]().review(rig["request"])
    policy = {"approved": True, "actor": "fixture-user", "envelope_sha256": first["envelope_sha256"],
              "expires_at": (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()}
    assert rig["reviewer"](policy=policy).review(rig["request"])["authorization"] == "vigente"
    rig["request"]["pending"] = ["resolver incidencia"]
    notice = rig["reviewer"](policy=policy).review(rig["request"])
    assert notice["authorization"] == "no_coincide"
    assert notice["envelope"]["attachments"] == []
    policy["revoked"] = True
    assert rig["reviewer"](policy=policy).review(rig["request"])["authorization"] == "revocada"
    policy.pop("revoked")
    policy["expires_at"] = "2000-01-01T00:00:00Z"
    assert rig["reviewer"](policy=policy).review(rig["request"])["authorization"] == "caducada"


def test_blocked_attachment_format_returns_no_draft(rig):
    # Communications intentionally permits a smaller set of attachment formats.
    binary = rig["workspace"] / "out/result.bin"
    rig["artifact"].rename(binary)
    for rows in (rig["receipt"]["candidate_files"], rig["receipt"]["artifacts"]):
        rows[0]["path"] = "out/result.bin"
    rig["receipt"]["candidate_id"] = _hash(rig["receipt"]["candidate_files"])
    rig["receipt"]["checks"][0]["candidate_id"] = rig["receipt"]["candidate_id"]
    check = rig["receipt"]["checks"][0]
    check["candidate_before"] = check["candidate_after"] = rig["receipt"]["candidate_id"]
    check["command_argv"] = [sys.executable, "-c", "from pathlib import Path; assert Path('out/result.bin').read_text(encoding='utf-8') == 'fixture aislado'; print('PASS binary fixture')"]
    check["started_at"] = datetime.now(timezone.utc).isoformat()
    executed = subprocess.run(check["command_argv"], cwd=rig["workspace"], capture_output=True, timeout=10)
    check["finished_at"] = datetime.now(timezone.utc).isoformat()
    assert executed.returncode == 0
    rig["log"].write_bytes(executed.stdout + executed.stderr)
    check["logs"][0]["sha256"] = sha(rig["log"])
    rig["register"]()
    rig["request"]["candidate_id"] = rig["receipt"]["candidate_id"]
    rig["request"]["artifacts"] = copy.deepcopy(rig["receipt"]["artifacts"])
    first = rig["reviewer"]().review(rig["request"])
    result = rig["reviewer"]().prepare_draft(first["review_id"])
    assert result["draft"] is None
    assert result["blocked_attachments"]
    assert rig["communications"].runs() == []


def test_saved_review_tampering_rejected(rig):
    reviewer = rig["reviewer"]()
    first = reviewer.review(rig["request"])
    path = reviewer._record_path(first["review_id"])
    record = json.loads(path.read_text(encoding="utf-8"))
    record["decision"] = "APPROVED"
    put(path, record)
    with pytest.raises(DeliveryReviewError, match="modificado"):
        reviewer.revalidate(first["review_id"])


def test_producer_pending_cannot_be_removed_by_model(rig):
    rig["receipt"]["pending"] = ["Validación pendiente del productor"]
    rig["register"]()
    assert rig["reviewer"]().review(rig["request"])["decision"] == "bloqueada"


def test_cli_standalone_rereads_persisted_receipt(rig):
    request_file = rig["tmp_path"] / "request.json"
    profile_file = rig["tmp_path"] / "profile.json"
    put(request_file, rig["request"])
    put(profile_file, rig["profile"])
    argv = [sys.executable, "-m", "src.services.delivery_review", "review", "--workspace", str(rig["workspace"]),
            "--state-dir", str(rig["tmp_path"] / "cli-review"), "--profile", str(profile_file),
            "--request", str(request_file), "--producer-registry", "evidence/registry.json",
            "--producer-id", "fixture-host", "--communications-state-dir", str(rig["tmp_path"] / "communications")]
    result = subprocess.run(argv, capture_output=True, text=True, encoding="utf-8", timeout=15)
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)["decision"] == "lista_para_revision"


def test_teamctl_adapter_consumes_actual_managed_receipt(rig):
    reviewer = DeliveryReviewer(rig["workspace"], rig["tmp_path"] / "team-reviews",
        rig["communications"], rig["profile"])
    team = reviewer.team
    root = rig["workspace"]
    mission = {"mission_id": "MANAGED_FIXTURE", "operation": "REPAIR", "max_concurrency": 1,
        "terminal_work_items": ["JOB"], "work_items": [{"id": "JOB", "title": "Fixture check",
        "role": "governance-action-engineer", "depends_on": [], "required_checks": ["content"],
        "write_scopes": ["out/**", ".bago/team/runtime/**"], "output_scopes": ["out/**", ".bago/team/runtime/**"]}]}
    mission_file = rig["tmp_path"] / "mission.json"
    put(mission_file, mission)

    def call(*argv):
        result = team.run(["--root", str(root), *argv])
        assert result["status"] == "PASS", result
        return result

    call("init", "--mission", str(mission_file))
    call("pair")
    call("claim", "JOB", "--agent", "fixture")
    execution = call("run-check", "JOB", "--check-id", "content", "--command-json",
        json.dumps(rig["argv"]), "--allow-execute")
    state = team.load_state(root)
    handoff = {"work_id": "JOB", "role": "governance-action-engineer", "status": "DONE",
        "mission_id": "MANAGED_FIXTURE", "candidate_id": state["candidate_id"], "scope_sha256": state["scope_sha256"],
        "changed_files": ["out/result.txt"], "outputs": [{"kind": "result", **rig["candidate"][0]}],
        "verification": [execution["verification"]], "residual_risks": [], "next_consumers": []}
    handoff["payload_sha256"] = team.handoff_payload_hash(handoff)
    handoff_file = rig["tmp_path"] / "handoff.json"
    put(handoff_file, handoff)
    call("handoff", "JOB", "--file", str(handoff_file))
    request = {**rig["request"], **{k: handoff[k] for k in ("mission_id", "candidate_id", "scope_sha256")}}
    reviewed = reviewer.review(request)
    assert reviewed["decision"] == "lista_para_revision"
    assert reviewed["binding"]["identity_kind"] == "ADL_TEAMCTL_IMPLEMENTATION_PLUS_OUTPUT_HASHES"
    receipt = json.loads((root / execution["receipt"]).read_text(encoding="utf-8"))
    (root / receipt["logs"][0]["path"]).write_text("tampered")
    assert reviewer.revalidate(reviewed["review_id"])["decision"] == "bloqueada"
