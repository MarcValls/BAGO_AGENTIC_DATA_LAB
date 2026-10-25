"""Deterministic delivery gate over managed BAGO evidence; never sends messages.

The model may propose wording. Only persisted teamctl handoffs and execution
receipts can establish readiness. Local hashes provide integrity, not signing.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path

from src.communications.service import CommunicationError, schedule_value, instant, next_time


def _hash(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
                                    separators=(",", ":"), allow_nan=False).encode()).hexdigest()


def _controller():
    # Load our repository's controller, never executable code from a client workspace.
    path = Path(__file__).resolve().parents[2] / ".bago/team/kit/scripts/teamctl.py"
    spec = importlib.util.spec_from_file_location("delivery_teamctl", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class DeliveryReviewError(ValueError):
    pass


class ReceiptEvidenceProvider:
    """Read a host-owned producer registry and recheck its runtime receipt bytes.

    The model must not have write capability over this registry or receipt/log
    roots. This is a local integrity boundary, not producer authentication.
    No request can add a trusted producer or register its own PASS.
    """

    def __init__(self, workspace_root, registry_path, producer_id):
        self.team = _controller()
        self.root = self.team.root_path(workspace_root)
        self.registry_path = self.team.local_path(self.root, registry_path, exists=True)
        self.producer_id = producer_id

    def load(self, work_id):
        self.team.reject_links(self.registry_path)
        registry = json.loads(self.registry_path.read_text(encoding="utf-8"))
        if registry["producer_id"] != self.producer_id:
            raise DeliveryReviewError("Productor no autorizado.")
        item = registry["runs"][work_id]
        path = self.team.local_path(self.root, item["path"], exists=True)
        if self.team.sha256_file(path) != item["sha256"]:
            raise DeliveryReviewError("El recibo registrado fue modificado.")
        receipt = json.loads(path.read_text(encoding="utf-8"))
        if (receipt["producer_id"] != self.producer_id or receipt["work_id"] != work_id
                or receipt["run_id"] != item["run_id"]):
            raise DeliveryReviewError("Origen o ejecución del recibo no coincide.")
        candidates = receipt["candidate_files"]
        if not candidates or len({x["path"] for x in candidates}) != len(candidates):
            raise DeliveryReviewError("El candidato no tiene archivos únicos.")
        for row in candidates + receipt["artifacts"]:
            actual = self.team.local_path(self.root, row["path"], exists=True)
            if self.team.sha256_file(actual) != row["sha256"]:
                raise DeliveryReviewError("Archivo del recibo modificado: " + row["path"])
        if receipt["candidate_id"] != _hash(sorted(candidates, key=lambda x: x["path"])):
            raise DeliveryReviewError("Identidad del candidato no coincide.")
        if receipt["scope_sha256"] != _hash(receipt["output_scopes"]):
            raise DeliveryReviewError("Identidad del ámbito no coincide.")
        for row in receipt["artifacts"]:
            if not any(self.team.fnmatch.fnmatchcase(row["path"], p) for p in receipt["output_scopes"]):
                raise DeliveryReviewError("Resultado fuera del ámbito del productor.")
        checks = receipt["checks"]
        if not receipt["required_checks"] or len({x["id"] for x in checks}) != len(checks):
            raise DeliveryReviewError("Comprobaciones obligatorias ausentes o duplicadas.")
        for required in receipt["required_checks"]:
            check = next((x for x in checks if x["id"] == required), None)
            if (not check or check.get("executed") is not True or check.get("result") != "PASS"
                    or type(check.get("returncode")) is not int or check["returncode"] != 0
                    or check.get("timed_out") is not False or check.get("spawn_error") is not None
                    or not check.get("command_argv") or not check.get("started_at") or not check.get("finished_at")
                    or check.get("producer_id") != self.producer_id or check.get("run_id") != receipt["run_id"]
                    or check.get("candidate_before") != receipt["candidate_id"]
                    or check.get("candidate_after") != receipt["candidate_id"]
                    or any(check.get(k) != receipt[k] for k in ("mission_id", "candidate_id", "scope_sha256"))):
                raise DeliveryReviewError("La comprobación obligatoria no tiene ejecución PASS válida: " + required)
            if instant(check["finished_at"]) < instant(check["started_at"]):
                raise DeliveryReviewError("Fechas del recibo de comprobación inválidas.")
            if not check.get("logs"):
                raise DeliveryReviewError("La ejecución carece de logs persistidos.")
            for log in check["logs"]:
                log_path = self.team.local_path(self.root, log["path"], exists=True)
                if self.team.sha256_file(log_path) != log["sha256"]:
                    raise DeliveryReviewError("El log de ejecución fue modificado.")
        return {**receipt, "receipt_sha256": item["sha256"],
                "identity_kind": "HOST_REGISTERED_RUNTIME_RECEIPT_PLUS_FILE_HASHES"}


class DeliveryReviewer:
    """Explicit capabilities and workspace allowlists are supplied by the host.

    profile: {capabilities: [delivery.review, delivery.draft], output_scopes: [...]}
    policy is host configuration, never a model-provided request field.
    """

    def __init__(self, workspace_root, state_dir, communications=None, profile=None,
                 policy=None, clock=None, evidence_provider=None):
        self.team = _controller()
        self.root = self.team.root_path(workspace_root)
        self.state_dir = Path(state_dir).resolve()
        self.communications = communications
        self.profile = profile or {"capabilities": [], "output_scopes": []}
        self.policy = policy
        self.evidence_provider = evidence_provider
        self.clock = clock or (lambda: datetime.now(timezone.utc))

    def _permit(self, capability):
        if capability not in self.profile.get("capabilities", []):
            raise DeliveryReviewError("Capacidad no autorizada: " + capability)

    def _record_path(self, review_id):
        if not isinstance(review_id, str) or not re.fullmatch(r"review_[a-f0-9]{32}", review_id):
            raise DeliveryReviewError("Identificador de revisión inválido.")
        path = self.state_dir / (review_id + ".json")
        self.team.reject_links(path)
        return path

    def _allowed(self, path):
        return any(self.team.fnmatch.fnmatchcase(path, pattern)
                   for pattern in self.profile.get("output_scopes", []))

    def _evaluate(self, request):
        errors, missing, outputs = [], [], []
        recipient = None
        binding = {}
        evidence = {}
        try:
            wid = request["work_id"]
            if self.evidence_provider is not None:
                evidence = self.evidence_provider.load(wid)
                handoff = {"outputs": evidence["artifacts"], "findings": evidence.get("findings", [])}
                work = {"required_checks": evidence["required_checks"]}
                binding = {k: evidence[k] for k in ("mission_id", "candidate_id", "scope_sha256")}
                binding.update(receipt_sha256=evidence["receipt_sha256"], identity_kind=evidence["identity_kind"])
            else:
                state = self.team.load_state(self.root)
                self.team._verify(self.root, state)
                if state["lifecycle"] == "PAUSED":
                    raise DeliveryReviewError("La misión está pausada.")
                binding = {"mission_id": state["mission"]["mission_id"],
                           "candidate_id": state["candidate_id"], "scope_sha256": state["scope_sha256"]}
                if state["work_status"][wid]["status"] != "DONE":
                    raise DeliveryReviewError("El trabajo todavía no tiene handoff DONE.")
                handoff = self.team.validate_handoff(self.root, state, wid)
                work = self.team.work_map(state)[wid]
                binding["handoff_sha256"] = state["work_status"][wid]["handoff"]["sha256"]
                binding["identity_kind"] = "ADL_TEAMCTL_IMPLEMENTATION_PLUS_OUTPUT_HASHES"
            if any(request.get(key) != binding[key] for key in ("mission_id", "candidate_id", "scope_sha256")):
                raise DeliveryReviewError("Identidad de misión, candidato o ámbito no coincide.")
            if not work.get("required_checks"):
                raise DeliveryReviewError("La misión no exige ninguna comprobación ejecutada.")
            findings = handoff.get("findings", [])
            if any(f["status"] == "OPEN" and f["severity"] in ("P0", "P1") for f in findings):
                raise DeliveryReviewError("Hay hallazgos P0/P1 abiertos.")
            canonical = {item["path"]: item["sha256"] for item in handoff["outputs"]}
            artifacts = request.get("artifacts")
            if not isinstance(artifacts, list) or not artifacts:
                raise DeliveryReviewError("Se requiere al menos un resultado verificable.")
            seen = set()
            for item in artifacts:
                rel = item["path"]
                path = self.team.local_path(self.root, rel, exists=True)
                if rel in seen or not self._allowed(rel):
                    raise DeliveryReviewError("Resultado duplicado o fuera del ámbito del perfil: " + rel)
                seen.add(rel)
                if canonical.get(rel) != item["sha256"] or self.team.sha256_file(path) != item["sha256"]:
                    raise DeliveryReviewError("Hash no coincide con el handoff y el archivo: " + rel)
                outputs.append({"path": rel, "sha256": item["sha256"]})
            binding["required_checks"] = work["required_checks"]
        except (ValueError, OSError, KeyError, TypeError, ImportError) as exc:
            errors.append(str(exc))
        producer_pending = evidence.get("pending", [])
        producer_risks = evidence.get("risks", [])
        if not isinstance(producer_pending, list) or not isinstance(producer_risks, list):
            errors.append("Pendientes o riesgos del productor inválidos.")
            producer_pending, producer_risks = [], []
        pending = request.get("pending", [])
        risks = request.get("risks", [])
        pending = pending + producer_pending if isinstance(pending, list) else pending
        risks = risks + producer_risks if isinstance(risks, list) else risks
        if not isinstance(pending, list) or not all(isinstance(x, str) for x in pending):
            errors.append("Pendientes inválidos.")
            pending = []
        if pending:
            errors.append("Hay pendientes sin resolver.")
        if not isinstance(risks, list) or not all(isinstance(x, dict) and isinstance(x.get("description"), str)
                                               and type(x.get("blocking")) is bool for x in risks):
            errors.append("Riesgos requieren descripción y blocking explícito.")
            risks = []
        if any(x["blocking"] for x in risks):
            errors.append("Hay riesgos bloqueantes.")
        try:
            schedule = schedule_value(request.get("schedule", {"kind": "now"}))
            next_time(schedule, self.clock())
        except CommunicationError as exc:
            errors.append(str(exc))
            schedule = None
        contact_id = request.get("contact_id")
        if not contact_id:
            missing.append("Falta seleccionar el destinatario de esta entrega.")
        elif self.communications is None:
            missing.append("No hay servicio de contactos conectado.")
        else:
            recipient = next((c for c in self.communications.contacts() if c["id"] == contact_id), None)
            if not recipient or not re.fullmatch(r"\+[1-9][0-9]{7,14}", recipient.get("phone", "")):
                missing.append("El destinatario no existe o carece de teléfono E.164.")
        decision = "bloqueada" if errors else "necesita_aclaracion" if missing else "lista_para_revision"
        kind = "entrega" if decision == "lista_para_revision" else "aviso"
        lines = ["Resultados preparados para revisión." if kind == "entrega" else
                 "La entrega está pendiente de revisión; no se confirma su finalización."]
        if kind == "entrega":
            lines += ["Resultados: " + ", ".join(x["path"] for x in outputs)]
        else:
            lines += errors + missing
        lines += ["Pendiente: " + x for x in pending]
        lines += ["Riesgo: " + x["description"] for x in risks]
        text = "\n".join(lines)
        envelope = {"mission_id": request.get("mission_id"), "candidate_id": request.get("candidate_id"),
                    "scope_sha256": request.get("scope_sha256"), "work_id": request.get("work_id"),
                    "kind": kind, "recipient": recipient, "text": text, "schedule": schedule,
                    "attachments": outputs if kind == "entrega" else []}
        authorization = "sin_politica"
        policy = self.policy
        if policy:
            authorization = "no_coincide"
            try:
                if policy.get("revoked"):
                    authorization = "revocada"
                elif instant(policy["expires_at"]) <= self.clock():
                    authorization = "caducada"
                elif (policy.get("approved") is True and policy.get("actor") and
                      policy.get("envelope_sha256") == _hash(envelope)):
                    authorization = "vigente"
            except (KeyError, TypeError, CommunicationError):
                authorization = "invalida"
        return {"decision": decision, "errors": errors, "missing": missing,
                "binding": binding, "pending": pending, "risks": risks, "envelope": envelope,
                "envelope_sha256": _hash(envelope), "authorization": authorization,
                "send_executed": False, "delivery_receipt": None,
                "model_recommendation": request.get("model_recommendation"),
                "checked_at": self.clock().isoformat()}

    def review(self, request):
        self._permit("delivery.review")
        # Canonical roundtrip prevents caller mutation of persisted evidence.
        request = json.loads(json.dumps(request, allow_nan=False))
        result = self._evaluate(request)
        result.update(review_id="review_" + uuid.uuid4().hex, request=request)
        result["record_sha256"] = _hash(result)
        self.team.reject_links(self.state_dir)
        self.state_dir.mkdir(parents=True, exist_ok=True)
        path = self._record_path(result["review_id"])
        with path.open("x", encoding="utf-8") as stream:
            json.dump(result, stream, ensure_ascii=False, indent=2)
        return result

    def revalidate(self, review_id):
        self._permit("delivery.review")
        saved = json.loads(self._record_path(review_id).read_text(encoding="utf-8"))
        signature = saved.pop("record_sha256")
        if _hash(saved) != signature or saved["review_id"] != review_id:
            raise DeliveryReviewError("El registro de revisión fue modificado.")
        return self.review(saved["request"])

    def prepare_draft(self, review_id):
        self._permit("delivery.draft")
        current = self.revalidate(review_id)
        envelope = current["envelope"]
        if self.communications is None or envelope["recipient"] is None:
            raise DeliveryReviewError("Falta destinatario verificable para el borrador.")
        if self.communications._workspace() != self.root:
            raise DeliveryReviewError("El servicio de comunicaciones pertenece a otro workspace.")
        try:
            draft = self.communications.create_draft(envelope["recipient"]["id"], envelope["text"],
                [x["path"] for x in envelope["attachments"]], envelope["schedule"])
        except (CommunicationError, OSError) as exc:
            return {"review": current, "draft": None, "blocked_attachments": str(exc), "send_executed": False}
        if ([{"path": a["path"], "sha256": a["sha256"]} for a in draft["attachments"]] != envelope["attachments"]
                or draft["recipient"] != envelope["recipient"] or draft["text"] != envelope["text"]
                or draft["schedule"] != envelope["schedule"]):
            self.communications.cancel(draft["id"], draft["revision"], confirmed=True)
            raise DeliveryReviewError("La entrega cambió durante la preparación; borrador cancelado.")
        return {"review": current, "draft": draft, "send_executed": False,
                "next_action": "Revisar y confirmar la revisión exacta mediante comunicaciones existentes."}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("operation", choices=["review", "revalidate", "prepare-draft"])
    parser.add_argument("--workspace", required=True)
    parser.add_argument("--state-dir", required=True)
    parser.add_argument("--profile", required=True, help="Host-owned JSON capability/scope profile")
    parser.add_argument("--request")
    parser.add_argument("--review-id")
    parser.add_argument("--communications-state-dir")
    parser.add_argument("--producer-registry")
    parser.add_argument("--producer-id")
    args = parser.parse_args(argv)
    communications = None
    if args.communications_state_dir:
        from src.communications.service import CommunicationService
        communications = CommunicationService(args.communications_state_dir, workspace_root=args.workspace)
    reviewer = DeliveryReviewer(args.workspace, args.state_dir, communications,
                                json.loads(Path(args.profile).read_text(encoding="utf-8")),
                                evidence_provider=ReceiptEvidenceProvider(args.workspace, args.producer_registry,
                                    args.producer_id) if args.producer_registry else None)
    if args.operation == "review":
        result = reviewer.review(json.loads(Path(args.request).read_text(encoding="utf-8")))
    elif args.operation == "revalidate":
        result = reviewer.revalidate(args.review_id)
    else:
        result = reviewer.prepare_draft(args.review_id)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
