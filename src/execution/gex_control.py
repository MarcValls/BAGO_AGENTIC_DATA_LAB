"""Operator-provisioned, durable control plane for one immutable fixture read."""
from __future__ import annotations

import base64
from dataclasses import dataclass, replace
from datetime import datetime, timedelta, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import secrets
import subprocess
import threading
import uuid
from collections.abc import Mapping

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from jsonschema import Draft202012Validator, FormatChecker
from src.capabilities.manager import workspace_identity
from src.execution.identity import GexIdentityStore, AuthenticatedPrincipal, AuthenticationError
from src.execution.ledger.sqlite_ledger import ExecutionLedger, LedgerError, StoreUnavailableError
from src.execution.permit import PermitKeyRegistry, AuthorizationClaims, PermitVerificationContext
from src.execution.permit.permit_v1 import _canonical, issue_permit, _parse_stamp, _stamp
from src.execution.adapters.fixture_read import FIXTURE_ID, FIXTURE_SHA256, FixtureReadRequest

CONTRACT = "gex-runtime/v1"
POLICY_REVISION = "gex-fixture-human-v1"
CONSTRAINTS = {"sandbox_profile": "read_only_agent", "network": "deny", "timeout_ms": 1000,
               "max_output_bytes": 65536, "write_scope": "none", "egress_allowlist": []}
ARGUMENT_SCHEMA = {"type": "object", "properties": {"fixture_id": {"type": "string", "const": FIXTURE_ID}},
                   "required": ["fixture_id"], "additionalProperties": False}
TOOL_SCHEMA = {"type": "function", "function": {"name": "fixture.read", "description": "Propose reading the immutable synthetic customer summary. Human approval is mandatory.", "parameters": ARGUMENT_SCHEMA}}
ROOT = Path(__file__).resolve().parents[2]
SCHEMA = json.loads((ROOT / "docs/governed-execution/GEX_V1_SCHEMA.json").read_text(encoding="utf-8"))
PINNED_SCHEMA = json.loads(Path(__file__).with_name("ledger").joinpath("gex_event_schema.json").read_text(encoding="utf-8"))


def contains_credential(value):
    """Reject recognizable credentials before user/config text reaches a model.

    This is an ingress guard in addition to never adding authenticated headers
    to provider messages; it does not claim to recognize every arbitrary secret.
    """
    return bool(re.search(r"bago_gex_(?:key|session)_v1_[A-Za-z0-9_-]+|\bsk-[A-Za-z0-9_-]{12,}|\bgh[pousr]_[A-Za-z0-9]{12,}|github_pat_[A-Za-z0-9_]{12,}|Bearer\s+[A-Za-z0-9_.-]{12,}", value))


class ControlError(RuntimeError):
    def __init__(self, code, status=409, *, persisted=False, view=None):
        super().__init__(code)
        self.code, self.status, self.persisted, self.view = code, status, persisted, view


def strict_json(raw):
    def pairs(items):
        value = {}
        for key, item in items:
            if key in value:
                raise ValueError("duplicate JSON member")
            value[key] = item
        return value
    value = json.loads(raw, object_pairs_hook=pairs,
        parse_constant=lambda _: (_ for _ in ()).throw(ValueError("nonfinite JSON")))
    _canonical(value)
    return value


def digest(domain, value):
    return hashlib.sha256(("ADL:GEX:" + domain + ":v1\n").encode("ascii") + _canonical(value)).hexdigest()


def validate(kind, value):
    _canonical(value)
    definitions = SCHEMA["$defs"] if kind in SCHEMA["$defs"] else PINNED_SCHEMA["$defs"]
    Draft202012Validator({"$ref": "#/$defs/" + kind, "$defs": definitions},
                        format_checker=FormatChecker()).validate(value)


def whole_request_digest(request):
    validate("GEXRequestV1", request)
    if uuid.UUID(request["request_id"]).version != 4:
        raise ValueError("request UUID must be v4")
    interval = (_parse_stamp(request["expires_at"]) - _parse_stamp(request["proposed_at"])).total_seconds()
    if not 0 < interval <= 300:
        raise ValueError("request lifetime exceeds policy")
    return digest("REQUEST", request)


def session_binding(principal):
    return hashlib.sha256(b"ADL:GEX:SESSION:v1\n" + principal.session_id.encode("utf-8")).hexdigest()


def _git(root, *args):
    result = subprocess.run(["git", "-C", str(root), *args], capture_output=True, timeout=10, check=False)
    if result.returncode:
        raise ControlError("WORKSPACE_INVALID", 503)
    return result.stdout


def workspace_snapshot(root):
    """Bind root/index/HEAD and actual dirty bytes, including ignored files.

    Links contribute their link text and never authorize following outside root.
    Public identity contains no absolute root or remote credential-bearing URL.
    """
    root = Path(root).resolve(strict=True)
    commit = _git(root, "rev-parse", "HEAD").decode().strip()
    if not re.fullmatch(r"[0-9a-f]{40,64}", commit):
        raise ControlError("WORKSPACE_INVALID", 503)
    branch = _git(root, "rev-parse", "--abbrev-ref", "HEAD").decode().strip()
    paths = set(_git(root, "ls-files", "-z", "--cached", "--others", "--exclude-standard").split(b"\0"))
    paths.update(_git(root, "ls-files", "-z", "--others", "--ignored", "--exclude-standard").split(b"\0"))
    tree = hashlib.sha256(_git(root, "ls-files", "--stage", "-z"))
    for path in sorted(paths - {b""}):
        file = root / os.fsdecode(path)
        tree.update(path + b"\0")
        if file.is_symlink():
            tree.update(b"SYMLINK\0" + os.fsencode(os.readlink(file)))
        elif file.is_file():
            if not file.resolve().is_relative_to(root):
                raise ControlError("WORKSPACE_INVALID", 503)
            tree.update(b"FILE\0" + hashlib.sha256(file.read_bytes()).digest())
        elif not file.exists():
            tree.update(b"DELETED")
        else:
            raise ControlError("WORKSPACE_INVALID", 503)
    common = (root / _git(root, "rev-parse", "--git-common-dir").decode().strip()).resolve()
    body = {"workspace_id": workspace_identity(root)[0], "repository_identity": digest("REPOSITORY", str(common)),
            "branch": branch, "commit_sha": commit, "context_revision": tree.hexdigest(), "root_identity": digest("ROOT", str(root))}
    return {**body, "binding_fingerprint": digest("WORKSPACE", body)}


def registry_snapshot():
    here = Path(__file__).parent
    registration = {"id": "fixture.read", "version": "1", "state": "ENABLED", "profile": "single-process-local",
        "fixture_id": FIXTURE_ID, "fixture_sha256": FIXTURE_SHA256, "schema": ARGUMENT_SCHEMA, "constraints": CONSTRAINTS,
        "adapter_sha256": hashlib.sha256((here / "adapters/fixture_read.py").read_bytes()).hexdigest(),
        "oracle_sha256": hashlib.sha256((here / "adapters/fixture_observer.py").read_bytes()).hexdigest()}
    return {"id": "fixture.read", "version": "1", "registry_digest": digest("REGISTRY", registration),
            "schema_digest": digest("SCHEMA", ARGUMENT_SCHEMA), "executor_kind": "local", "effect": "READ"}


_IMPORTED_REGISTRY = registry_snapshot()


def policy_snapshot():
    return {"revision": POLICY_REVISION, "policy_digest": digest("POLICY", {"revision": POLICY_REVISION,
        "result": "REQUIRE_HUMAN", "constraints": CONSTRAINTS, "self_approval": True, "capability_id": "fixture.read"})}


def operation_summary(request):
    return {"capability": request["capability"], "arguments": request["operation"]["arguments"],
        "workspace_binding_fingerprint": request["workspace"]["binding_fingerprint"], "effect_scope": request["operation"]["effect_scope"],
        "constraints": request["constraints"], "request_digest": whole_request_digest(request), "expires_at": request["expires_at"]}


class OwnerLock:
    """Lifetime OS lock. Never infer liveness from a PID or a stale file."""
    def __init__(self, path):
        self.file = None
        try:
            self.file = Path(path).open("a+b")
            if Path(path).stat().st_size == 0:
                self.file.write(b"0")
                self.file.flush()
            self.file.seek(0)
            if os.name == "nt":
                import msvcrt
                msvcrt.locking(self.file.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(self.file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            if self.file:
                self.file.close()
            self.file = None
            raise ControlError("OWNER_CONTENTION", 503) from None

    def close(self):
        if self.file:
            if os.name == "nt":
                import msvcrt
                self.file.seek(0)
                msvcrt.locking(self.file.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                import fcntl
                fcntl.flock(self.file.fileno(), fcntl.LOCK_UN)
            self.file.close()
            self.file = None


def configured_paths(state_dir, workspace, identity_path=None):
    state, work = Path(state_dir).expanduser(), Path(workspace).expanduser()
    if not state.is_absolute() or not work.is_absolute():
        raise ControlError("CONFIGURATION_INVALID", 503)
    state, work = state.resolve(), work.resolve(strict=True)
    identity = Path(identity_path).expanduser() if identity_path else state / "identity.sqlite3"
    if not identity.is_absolute():
        raise ControlError("CONFIGURATION_INVALID", 503)
    identity = identity.resolve()
    if state.is_relative_to(work) or work.is_relative_to(state) or identity.is_relative_to(work):
        raise ControlError("STATE_INSIDE_WORKSPACE", 503)
    if not work.is_dir():
        raise ControlError("WORKSPACE_INVALID", 503)
    workspace_snapshot(work)
    return state, work, identity


def _protect(path):
    path.chmod(0o700 if path.is_dir() else 0o600)
    if os.name == "nt":
        import csv
        # Restrict inherited access to the current Windows user. This is still
        # a local current-user profile, not isolation against administrators.
        identity = subprocess.run(["whoami", "/user", "/fo", "csv", "/nh"],
            capture_output=True, text=True, timeout=10, check=True)
        sid = next(csv.reader([identity.stdout.strip()]))[1]
        if not re.fullmatch(r"S-[0-9-]+", sid):
            raise ControlError("STATE_PROTECTION_FAILED", 503)
        grant = "*" + sid + (":(OI)(CI)F" if path.is_dir() else ":F")
        result = subprocess.run(["icacls", str(path), "/inheritance:r", "/grant:r", grant],
            capture_output=True, timeout=10, check=False)
        if result.returncode:
            raise ControlError("STATE_PROTECTION_FAILED", 503)


def provision(*, state_dir, workspace, principal_id, agent_id, load_agent):
    """Trusted CLI-only bootstrap. Raw API key is returned once, never stored."""
    if not re.fullmatch(r"principal_[a-z0-9][a-z0-9_-]{1,63}", principal_id) or not re.fullmatch(r"agent_[0-9a-f]{8,32}", agent_id):
        raise ControlError("PROVISIONING_INPUT_INVALID", 422)
    agent = load_agent(agent_id)
    record = agent.model_dump(mode="json") if hasattr(agent, "model_dump") else dict(agent)
    if record.get("id") != agent_id:
        raise ControlError("AGENT_UNAVAILABLE", 409)
    _canonical(record)
    state, work, identity = configured_paths(state_dir, workspace, os.environ.get("BAGO_GEX_IDENTITY_DB_PATH"))
    state.mkdir(parents=True, exist_ok=True)
    _protect(state)
    owner = OwnerLock(state / "owner.lock")
    try:
        config_path, key_path = state / "runtime-config.json", state / "signing-key.pem"
        if config_path.exists() or key_path.exists():
            raise ControlError("PROVISIONING_CONFLICT", 409)
        config = {"contract_version": CONTRACT, "issuer": "adl-local-gex", "key_id": "gexkey_" + uuid.uuid4().hex,
            "workspace_root": str(work), "workspace_id": workspace_identity(work)[0], "identity_db": str(identity),
            "policy_revision": POLICY_REVISION, "registry_version": "1"}
        key = Ed25519PrivateKey.generate()
        with key_path.open("xb") as stream:
            stream.write(key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()))
            stream.flush()
            os.fsync(stream.fileno())
        _protect(key_path)
        identity_store = GexIdentityStore(identity)
        credential_id, api_key = identity_store.provision_principal(principal_id=principal_id, workspace_root=work, allowed_agent_ids=[agent_id])
        ExecutionLedger(state / "execution.sqlite3")
        with config_path.open("x", encoding="utf-8") as stream:
            stream.write(_canonical(config).decode("utf-8"))
            stream.flush()
            os.fsync(stream.fileno())
        for file in (config_path, identity, state / "execution.sqlite3"):
            _protect(file)
        return {"principal_id": principal_id, "credential_id": credential_id, "api_key": api_key, "agent_id": agent_id,
            "workspace_id": config["workspace_id"], "state_dir": str(state), "workspace_root": str(work),
            "issuer": config["issuer"], "key_id": config["key_id"]}
    finally:
        owner.close()


@dataclass(frozen=True)
class ValidatedExecutionAuthority:
    """Internal whole-envelope seam. Callback rereads persisted signed controls."""
    request: Mapping
    principal: AuthenticatedPrincipal
    validate_live: object


class GexControl:
    def __init__(self, *, state_dir, workspace_root, load_agent, provider_resolver):
        state, work, identity = configured_paths(state_dir, workspace_root, os.environ.get("BAGO_GEX_IDENTITY_DB_PATH"))
        self.owner, self.lock = None, threading.RLock()
        self.load_agent, self.provider_resolver = load_agent, provider_resolver
        self.workspace_root, self.state_dir = work, state
        try:
            if not state.is_dir():
                raise ControlError("NOT_PROVISIONED", 503)
            self.owner = OwnerLock(state / "owner.lock")
            config = strict_json((state / "runtime-config.json").read_bytes())
            if set(config) != {"contract_version", "issuer", "key_id", "workspace_root", "workspace_id", "identity_db", "policy_revision", "registry_version"} or config["contract_version"] != CONTRACT or config["workspace_root"] != str(work) or config["workspace_id"] != workspace_identity(work)[0] or config["identity_db"] != str(identity) or config["policy_revision"] != POLICY_REVISION or config["registry_version"] != "1":
                raise ControlError("CONFIGURATION_INVALID", 503)
            for path in (state / "signing-key.pem", state / "runtime-config.json", state / "execution.sqlite3", state / "owner.lock", identity):
                if path.resolve().is_relative_to(work):
                    raise ControlError("STATE_INSIDE_WORKSPACE", 503)
                if not path.is_file():
                    raise ControlError("NOT_PROVISIONED", 503)
            key = serialization.load_pem_private_key((state / "signing-key.pem").read_bytes(), password=None)
            if not isinstance(key, Ed25519PrivateKey):
                raise ControlError("SIGNING_KEY_INVALID", 503)
            self.config = config
            self._pinned_registry = registry_snapshot()
            if self._pinned_registry != _IMPORTED_REGISTRY:
                raise ControlError("RUNTIME_CODE_CHANGED", 503)
            self.keys = PermitKeyRegistry(issuer=config["issuer"], active_key_id=config["key_id"], private_keys={config["key_id"]: key}, public_keys={config["key_id"]: key.public_key()})
            self.identity = GexIdentityStore(identity)
            self.ledger = ExecutionLedger(state / "execution.sqlite3", event_profile="runtime")
            from src.execution.gex_service import GexExecutionService
            self.service = GexExecutionService(identity_store=self.identity, ledger=self.ledger, keys=self.keys,
                workspace_root=work, agent_exists=self.agent_exists)
            self._recover_controls()
        except Exception:
            self.close()
            raise

    def close(self):
        if self.owner:
            self.owner.close()
            self.owner = None

    def _agent(self, agent_id):
        agent = self.load_agent(agent_id)
        result = agent.model_dump(mode="json") if hasattr(agent, "model_dump") else dict(agent)
        if result.get("id") != agent_id:
            raise ControlError("AGENT_UNAVAILABLE", 403)
        _canonical(result)
        if contains_credential(json.dumps(result, ensure_ascii=True)):
            raise ControlError("AGENT_CONFIG_CREDENTIAL_DENIED", 409)
        return result

    def agent_exists(self, agent_id):
        try:
            return self._agent(agent_id).get("id") == agent_id
        except Exception:
            return False

    def authenticate(self, token, agent_id):
        try:
            principal = self.identity.authenticate_session(token, requested_agent_id=agent_id, agent_exists=self.agent_exists)
            if principal.workspace_id != self.config["workspace_id"]:
                raise AuthenticationError("workspace denied")
            return principal
        except AuthenticationError as exc:
            scope = "scope" in str(exc)
            raise ControlError("AGENT_SCOPE_DENIED" if scope else "AUTHENTICATION_REQUIRED", 403 if scope else 401) from None

    def create_session(self, api_key, agent_id, ttl):
        try:
            scope = self.identity.authenticate_credential(api_key)
        except AuthenticationError:
            raise ControlError("AUTHENTICATION_REQUIRED", 401) from None
        if agent_id not in scope["allowed_agent_ids"] or scope["workspace_id"] != self.config["workspace_id"]:
            raise ControlError("AGENT_SCOPE_DENIED", 403)
        if not self.agent_exists(agent_id):
            raise ControlError("AGENT_SCOPE_DENIED", 403)
        try:
            _, token = self.identity.create_session(api_key, requested_agent_id=agent_id, ttl_seconds=ttl)
            principal = self.authenticate(token, agent_id)
        except AuthenticationError as exc:
            scope = "scope" in str(exc)
            raise ControlError("AGENT_SCOPE_DENIED" if scope else "AUTHENTICATION_REQUIRED", 403 if scope else 401) from None
        return {"session_id": principal.session_id, "session_token": token, "principal_id": principal.principal_id,
            "workspace_id": principal.workspace_id, "agent_id": principal.agent_id, "issued_at": principal.issued_at, "expires_at": principal.expires_at}

    def revoke(self, token, principal):
        self.identity.revoke_session(principal.session_id, requester_session_token=token,
            requester_agent_id=principal.agent_id, agent_exists=self.agent_exists)
        return {"status": "REVOKED", "session_id": principal.session_id}

    def _save(self, record, principal, kind, create=False):
        self.ledger.save_control(record, principal_id=principal.principal_id, workspace_id=principal.workspace_id,
            agent_id=principal.agent_id, kind=kind, create=create)

    def _read(self, request_id, principal):
        record = self.ledger.read_control(request_id, principal_id=principal.principal_id,
            workspace_id=principal.workspace_id, agent_id=principal.agent_id)
        if record is None:
            raise ControlError("REQUEST_NOT_FOUND", 404)
        return record

    def _authority(self, principal):
        self.check_runtime()
        agent = self._agent(principal.agent_id)
        config_digest = digest("AGENT", agent)
        workspace = workspace_snapshot(self.workspace_root)
        if workspace["workspace_id"] != principal.workspace_id:
            raise ControlError("STALE_AUTHORITY", 409)
        current_registry = registry_snapshot()
        if current_registry != self._pinned_registry:
            raise ControlError("RUNTIME_CODE_CHANGED", 503)
        return {"principal": {"issuer": self.keys.issuer, "subject": principal.principal_id, "session_binding": session_binding(principal), "auth_strength": "verified"},
            "agent": {"agent_id": principal.agent_id, "config_digest": config_digest, "revision": config_digest},
            "workspace": workspace, "capability": current_registry, "constraints": dict(CONSTRAINTS),
            "policy": policy_snapshot(), "context_revision": workspace["context_revision"]}

    def check_runtime(self):
        if registry_snapshot() != self._pinned_registry:
            raise ControlError("RUNTIME_CODE_CHANGED", 503)

    def _fresh(self, record, principal):
        self._verify_proposal_artifacts(record)
        request = record["request"]
        if not request or whole_request_digest(request) != record["request_digest"]:
            raise ControlError("REQUEST_INTEGRITY_INVALID", 409)
        if datetime.now(timezone.utc) >= _parse_stamp(request["expires_at"]):
            raise ControlError("REQUEST_EXPIRED", 409)
        if any(request[key] != value for key, value in self._authority(principal).items()):
            raise ControlError("STALE_AUTHORITY", 409)
        if request["operation"] != {"arguments": {"fixture_id": FIXTURE_ID}, "target": "registered-immutable-fixture", "effect_scope": "read:fixture:sample"}:
            raise ControlError("STALE_AUTHORITY", 409)
        return request

    def _proposal(self, turn):
        if not isinstance(turn, Mapping):
            raise ValueError("invalid response")
        calls, content = turn.get("tool_calls"), turn.get("content")
        native = None
        if calls:
            if not isinstance(calls, list) or len(calls) != 1:
                raise ValueError("multiple calls")
            function = calls[0].get("function") if isinstance(calls[0], Mapping) else None
            if not isinstance(function, Mapping) or not isinstance(function.get("name"), str):
                raise ValueError("invalid call")
            args = function.get("arguments")
            if isinstance(args, str):
                if len(args.encode("utf-8")) > 8192:
                    raise ValueError("arguments limit")
                args = strict_json(args)
            native = {"tool_name": function["name"], "arguments": args}
        textual = None
        if isinstance(content, str) and content.strip():
            if len(content.encode("utf-8")) > 16384:
                raise ValueError("response limit")
            try:
                textual = strict_json(content)
            except Exception:
                if native is None:
                    raise ValueError("no proposal") from None
        if native is None and textual is None:
            raise ValueError("no proposal")
        if native is not None and textual is not None and native != textual:
            raise ValueError("contradictory proposal")
        proposal = native or textual
        if not isinstance(proposal, dict) or set(proposal) != {"tool_name", "arguments"} or not isinstance(proposal["tool_name"], str) or not isinstance(proposal["arguments"], dict):
            raise ValueError("invalid proposal")
        if len(_canonical(proposal)) > 8192:
            raise ValueError("proposal limit")
        # Do not retain arbitrary rejected arguments which may contain secrets.
        if proposal != {"tool_name": "fixture.read", "arguments": {"fixture_id": FIXTURE_ID}}:
            raise ValueError("unregistered proposal")
        return proposal

    def _proposal_envelope(self, record, principal, turn):
        """CR04: authenticated proposal identity precedes capability lookup."""
        tool, raw_arguments = "[no_validated_tool]", b"ADL:GEX:NO_ARGUMENT_BYTES:v1\n"
        candidate = None
        if isinstance(turn, Mapping):
            calls = turn.get("tool_calls")
            if isinstance(calls, list) and len(calls) == 1 and isinstance(calls[0], Mapping):
                candidate = calls[0].get("function")
            elif isinstance(turn.get("content"), str):
                raw_arguments = turn["content"][:16384].encode("utf-8", errors="replace")
                try:
                    parsed = strict_json(turn["content"][:16384])
                    if isinstance(parsed, dict):
                        candidate = {"name": parsed.get("tool_name"), "arguments": parsed.get("arguments")}
                except Exception:
                    pass
        if isinstance(candidate, Mapping):
            name = candidate.get("name")
            if isinstance(name, str) and re.fullmatch(r"[a-z][a-z0-9_.]{0,63}", name):
                tool = name
            args = candidate.get("arguments")
            if isinstance(args, str):
                raw_arguments = args.encode("utf-8", errors="replace")[:8192]
            else:
                try:
                    raw_arguments = _canonical(args)[:8192]
                except Exception:
                    raw_arguments = b"ADL:GEX:UNSUPPORTED_ARGUMENT_BYTES:v1\n"
        envelope = {"contract_version": "gex-proposal/v1", "request_id": record["request_id"],
            "run_id": record["run_id"], "proposal_id": record["proposal_id"], "agent_id": principal.agent_id,
            "principal_subject": principal.principal_id,
            "workspace_binding_fingerprint": self._authority(principal)["workspace"]["binding_fingerprint"],
            "requested_tool": tool, "raw_arguments_sha256": hashlib.sha256(raw_arguments).hexdigest(),
            "received_at": _stamp(datetime.now(timezone.utc))}
        envelope["proposal_digest"] = digest("PROPOSAL", envelope)
        validate("ToolProposalEnvelopeV1", envelope)
        record["_proposal_envelope"] = envelope
        record["proposal"]["proposal_digest"] = envelope["proposal_digest"]
        record["proposal"]["tool_name"] = tool

    def _persist_proposal_denial(self, record, principal, code, kind="DENIED"):
        self._save(record, principal, kind, True)
        envelope = record["_proposal_envelope"]
        denial = {"contract_version": "gex-proposal-denial/v1", "receipt_id": "gexproposaldenial_" + uuid.uuid4().hex,
            "request_id": record["request_id"], "run_id": record["run_id"], "proposal_id": record["proposal_id"],
            "proposal_digest": envelope["proposal_digest"], "requested_tool": envelope["requested_tool"],
            "reason_code": code, "decision": "DENY", "evidence_refs": ["proposal-digest:" + envelope["proposal_digest"]],
            "origin_event_ids": [event.event_id for event in self.ledger.events_for_request(record["request_id"])],
            "persisted_at": _stamp(datetime.now(timezone.utc))}
        validate("ProposalDenialReceiptV1", denial)
        record["_proposal_denial"] = denial
        self._save(record, principal, "DENIED")

    def _verify_proposal_artifacts(self, record):
        envelope = record["_proposal_envelope"]
        validate("ToolProposalEnvelopeV1", envelope)
        unsigned = {key: value for key, value in envelope.items() if key != "proposal_digest"}
        if digest("PROPOSAL", unsigned) != envelope["proposal_digest"] or envelope["proposal_digest"] != record["proposal"]["proposal_digest"] or any(envelope[key] != record[key] for key in ("request_id", "run_id", "proposal_id")):
            raise ControlError("PROPOSAL_INTEGRITY_INVALID", 409)
        if record["request"] is not None:
            request = record["request"]
            if envelope["principal_subject"] != request["principal"]["subject"] or envelope["agent_id"] != request["agent"]["agent_id"] or envelope["workspace_binding_fingerprint"] != request["workspace"]["binding_fingerprint"]:
                raise ControlError("PROPOSAL_INTEGRITY_INVALID", 409)
        denial = record.get("_proposal_denial")
        if denial is not None:
            validate("ProposalDenialReceiptV1", denial)
            expected = {"request_id": record["request_id"], "run_id": record["run_id"], "proposal_id": record["proposal_id"],
                "proposal_digest": envelope["proposal_digest"], "requested_tool": envelope["requested_tool"],
                "reason_code": record["error"]["code"], "decision": "DENY"}
            events = self.ledger.events_for_request(record["request_id"])
            origins = denial["origin_event_ids"]
            if any(denial[key] != value for key, value in expected.items()) or not origins or origins != [event.event_id for event in events[:len(origins)]]:
                raise ControlError("PROPOSAL_DENIAL_INTEGRITY_INVALID", 409)

    def propose(self, task, principal):
        with self.lock:
            if contains_credential(task) or re.search(r"bago_gex_(?:key|session)_v1_[A-Za-z0-9_-]+", task):
                raise ControlError("TASK_CREDENTIAL_DENIED", 422)
            agent = self._agent(principal.agent_id)
            self._authority(principal)  # Refuse stale loaded code before inference.
            config = agent.get("config", {})
            provider_id, model_id = config.get("provider_id"), config.get("model_id")
            if not isinstance(provider_id, str) or not provider_id or not isinstance(model_id, str) or not model_id:
                raise ControlError("AGENT_PROVIDER_UNCONFIGURED", 409)
            record = {"contract_version": CONTRACT, "request_id": str(uuid.uuid4()), "run_id": "gexrun_" + uuid.uuid4().hex,
                "proposal_id": "gexproposal_" + uuid.uuid4().hex, "state": "DENIED", "task": task,
                "provider": {"provider_id": provider_id, "model_id": model_id},
                "proposal": {"tool_name": "[no_validated_tool]", "arguments": {}, "proposal_digest": digest("PROPOSAL", {})},
                "request": None, "request_digest": None, "policy_decision": None, "approval": None,
                "permit": None, "receipt": None, "error": None, "synthetic": True,
                "_provenance": {"task_sha256": hashlib.sha256(task.encode("utf-8")).hexdigest(),
                    "agent_record_digest": digest("AGENT", agent), "provider_response_sha256": None,
                    "oracle_code_sha256": hashlib.sha256(Path(__file__).with_name("adapters").joinpath("fixture_observer.py").read_bytes()).hexdigest()}}
            messages = [{"role": "system", "content": str(config.get("system_prompt", ""))},
                {"role": "system", "content": "Proposal only. You cannot execute. The only registered tool is fixture.read with arguments {\"fixture_id\":\"" + FIXTURE_ID + "\"}. Propose exactly one native tool call, or exactly JSON {\"tool_name\":\"fixture.read\",\"arguments\":{\"fixture_id\":\"" + FIXTURE_ID + "\"}}. It reads immutable synthetic data with no network or writes; a human must approve it. Do not fabricate execution or results."},
                {"role": "user", "content": task}]
            try:
                _, chat = self.provider_resolver(provider_id)
                turn = chat(model_id, messages, tools=[TOOL_SCHEMA], options={"temperature": 0})
            except Exception:
                record["error"] = {"code": "PROVIDER_FAILED", "message": "El proveedor no pudo producir una propuesta."}
                self._proposal_envelope(record, principal, {})
                self._persist_proposal_denial(record, principal, "PROVIDER_FAILED", "CONTROL_FAILED")
                raise ControlError("PROVIDER_FAILED", 502, persisted=True, view=self.view(record, principal)) from None
            # Bounded provider bytes are hashed as provenance, never stored raw.
            safe_response = {}
            if isinstance(turn, Mapping):
                for name in ("content", "tool_calls"):
                    item = turn.get(name)
                    if isinstance(item, str):
                        safe_response[name] = item[:16384]
                    elif isinstance(item, list):
                        safe_response[name] = str(item)[:16384]
            record["_provenance"]["provider_response_sha256"] = hashlib.sha256(json.dumps(safe_response, ensure_ascii=True, sort_keys=True).encode()).hexdigest()
            self._proposal_envelope(record, principal, turn)
            try:
                proposal = self._proposal(turn)
            except Exception:
                bounded = {}
                if isinstance(turn, Mapping):
                    for name in ("content", "tool_calls"):
                        value = turn.get(name)
                        if isinstance(value, str):
                            bounded[name] = value[:16384]
                        elif name == "tool_calls" and isinstance(value, list):
                            bounded[name] = str(value)[:16384]
                    # Preserve a safe public tool identifier for human review,
                    # but never persist arbitrary denied provider arguments.
                    functions = turn.get("tool_calls")
                    if isinstance(functions, list) and len(functions) == 1 and isinstance(functions[0], Mapping):
                        function = functions[0].get("function")
                        if isinstance(function, Mapping) and isinstance(function.get("name"), str) and re.fullmatch(r"[a-z][a-z0-9_.]{0,63}", function["name"]):
                            record["proposal"]["tool_name"] = function["name"]
                record["error"] = {"code": "PROPOSAL_DENIED", "message": "El proveedor no propuso una única lectura registrada válida."}
                self._persist_proposal_denial(record, principal, "PROPOSAL_DENIED")
                return self.view(record, principal)
            record["proposal"] = {**proposal, "proposal_digest": record["_proposal_envelope"]["proposal_digest"]}
            instant = datetime.now(timezone.utc)
            expires = min(instant + timedelta(seconds=300), _parse_stamp(principal.expires_at))
            request = {"contract_version": "gex-request/v1", "request_id": record["request_id"], "run_id": record["run_id"],
                "proposal_id": record["proposal_id"], **self._authority(principal),
                "operation": {"arguments": proposal["arguments"], "target": "registered-immutable-fixture", "effect_scope": "read:fixture:sample"},
                "proposed_at": _stamp(instant), "expires_at": _stamp(expires), "nonce": secrets.token_urlsafe(32)}
            if request["agent"]["config_digest"] != digest("AGENT", agent):
                raise ControlError("STALE_AUTHORITY", 409)
            record["request"], record["request_digest"] = request, whole_request_digest(request)
            record["state"] = "AWAITING_APPROVAL"
            self._save(record, principal, "PROPOSED", True)
            policy = {"contract_version": "gex-policy-decision/v1", "decision_id": "gexdecision_" + uuid.uuid4().hex,
                "request_id": record["request_id"], "request_digest": record["request_digest"], "policy_revision": POLICY_REVISION,
                "actor": "adl-gex-policy", "result": "REQUIRE_HUMAN", "reason_code": "EXPLICIT_AUTHENTICATED_APPROVAL_REQUIRED",
                "constraints_effective": dict(CONSTRAINTS), "timestamp": _stamp(instant)}
            validate("PolicyDecisionV1", policy)
            record["policy_decision"] = policy
            self._save(record, principal, "POLICY_DECIDED")
            self._save(record, principal, "APPROVAL_REQUESTED")
            return self.view(record, principal)

    def _signed_approval(self, record, principal, decision, reason):
        request = record["request"]
        approval = {"contract_version": "gex-approval/v1", "approval_id": "gexapproval_" + uuid.uuid4().hex,
            "decision_id": record["policy_decision"]["decision_id"], "request_digest": record["request_digest"],
            "actor": principal.principal_id, "principal_subject": principal.principal_id,
            "workspace_binding_fingerprint": request["workspace"]["binding_fingerprint"],
            "operation_summary_digest": digest("OPERATION_SUMMARY", operation_summary(request)),
            "decision": decision, "issued_at": _stamp(datetime.now(timezone.utc)), "expires_at": request["expires_at"],
            "auth_context_ref": session_binding(principal), "evidence_ref": "decision-reason-sha256:" + hashlib.sha256(reason.encode()).hexdigest(),
            "key_id": self.keys.active_key_id, "signature_algorithm": "Ed25519"}
        approval["signature"] = base64.urlsafe_b64encode(self.keys.signing_key().sign(b"ADL:GEX:APPROVAL:v1\n" + _canonical(approval))).decode("ascii").rstrip("=")
        validate("ApprovalV1", approval)
        return approval

    def _verify_approval(self, record, *, live_principal=None):
        try:
            return self._verify_approval_claims(record, live_principal=live_principal)
        except ControlError:
            raise
        except Exception:
            raise ControlError("APPROVAL_INVALID", 409) from None

    def _verify_approval_claims(self, record, *, live_principal=None):
        approval, request, policy = record["approval"], record["request"], record["policy_decision"]
        validate("ApprovalV1", approval)
        validate("PolicyDecisionV1", policy)
        if approval["signature_algorithm"] != "Ed25519" or approval["key_id"] != self.keys.active_key_id:
            raise ControlError("APPROVAL_INVALID", 409)
        sig = approval["signature"]
        raw = base64.urlsafe_b64decode(sig + "==")
        if len(raw) != 64 or base64.urlsafe_b64encode(raw).decode().rstrip("=") != sig:
            raise ControlError("APPROVAL_INVALID", 409)
        self.keys.verification_key(self.keys.issuer, approval["key_id"]).verify(raw,
            b"ADL:GEX:APPROVAL:v1\n" + _canonical({k: v for k, v in approval.items() if k != "signature"}))
        expected = {"decision_id": policy["decision_id"], "request_digest": record["request_digest"],
            "actor": request["principal"]["subject"], "principal_subject": request["principal"]["subject"],
            "workspace_binding_fingerprint": request["workspace"]["binding_fingerprint"],
            "operation_summary_digest": digest("OPERATION_SUMMARY", operation_summary(request)),
            "expires_at": request["expires_at"], "auth_context_ref": request["principal"]["session_binding"]}
        if any(approval[k] != v for k, v in expected.items()) or policy["request_id"] != request["request_id"] or policy["request_digest"] != record["request_digest"] or policy["result"] != "REQUIRE_HUMAN" or policy["constraints_effective"] != request["constraints"] or policy["policy_revision"] != request["policy"]["revision"]:
            raise ControlError("APPROVAL_INVALID", 409)
        if not _parse_stamp(request["proposed_at"]) <= _parse_stamp(approval["issued_at"]) < _parse_stamp(approval["expires_at"]):
            raise ControlError("APPROVAL_INVALID", 409)
        decision = record.get("_decision")
        if not isinstance(decision, dict) or decision.get("actor") != approval["actor"] or decision.get("decision") != approval["decision"] or approval["evidence_ref"] != "decision-reason-sha256:" + hashlib.sha256(decision["reason"].encode()).hexdigest():
            raise ControlError("APPROVAL_INVALID", 409)
        if live_principal is not None and (approval["decision"] != "APPROVED" or approval["auth_context_ref"] != session_binding(live_principal) or datetime.now(timezone.utc) >= _parse_stamp(approval["expires_at"])):
            raise ControlError("APPROVAL_INVALID", 409)
        return True

    def _verify_permit_signature(self, record):
        try:
            return self._verify_permit_claims(record)
        except ControlError:
            raise
        except Exception:
            raise ControlError("PERMIT_INVALID", 409) from None

    def _verify_permit_claims(self, record):
        # Historical readback verifies original signature/bindings without
        # reviving the old session, permit lifetime or execution authority.
        request, permit = record["request"], record["permit"]
        from src.execution.permit.permit_v1 import _claims_for_signature, _validate_claims
        _validate_claims(permit)
        signature = permit["signature"]
        if not re.fullmatch(r"[A-Za-z0-9_-]{86}", signature):
            raise ControlError("PERMIT_INVALID", 409)
        raw = base64.urlsafe_b64decode(signature + "==")
        if base64.urlsafe_b64encode(raw).decode().rstrip("=") != signature:
            raise ControlError("PERMIT_INVALID", 409)
        self.keys.verification_key(permit["issuer"], permit["key_id"]).verify(raw, _claims_for_signature(permit))
        expected = {"request_digest": record["request_digest"], "principal_subject": request["principal"]["subject"],
            "session_binding": request["principal"]["session_binding"], "agent_id": request["agent"]["agent_id"],
            "agent_config_digest": request["agent"]["config_digest"], "workspace_binding_fingerprint": request["workspace"]["binding_fingerprint"],
            "capability_id": request["capability"]["id"], "capability_version": request["capability"]["version"],
            "registry_digest": request["capability"]["registry_digest"], "effect_scope": request["operation"]["effect_scope"],
            "operation_digest": FixtureReadRequest(request["request_id"], FIXTURE_ID).operation_digest,
            "policy_revision": request["policy"]["revision"], "constraints_effective": request["constraints"],
            "authorization_source": {"decision_id": record["policy_decision"]["decision_id"], "approval_id": record["approval"]["approval_id"], "auto_rule_id": None}}
        if any(permit[k] != value for k, value in expected.items()) or _parse_stamp(permit["expires_at"]) > _parse_stamp(request["expires_at"]):
            raise ControlError("PERMIT_INVALID", 409)
        return True

    def _live_execution(self, request_id, principal, token):
        if self.authenticate(token, principal.agent_id) != principal:
            raise ControlError("STALE_AUTHORITY", 409)
        record = self._read(request_id, principal)
        request = self._fresh(record, principal)
        self._verify_approval(record, live_principal=principal)
        self._verify_permit_signature(record)
        if record["state"] != "APPROVED":
            raise ControlError("REQUEST_TERMINAL", 409)
        return request

    def _receipt_fields(self, record):
        receipt, request = record["receipt"], record["request"]
        dispatched = receipt["attempt_id"] is not None
        sandbox = receipt["sandbox_receipt"] or {}
        return {"contract_version": "gex-receipt/v1", "receipt_id": receipt["receipt_id"],
            "request_digest": record["request_digest"], "attempt_id": receipt["attempt_id"],
            "decision_id": record["policy_decision"]["decision_id"],
            "approval_id": (record["approval"] or {}).get("approval_id"), "permit_id": receipt["permit_id"],
            "capability_id": request["capability"]["id"], "capability_version": request["capability"]["version"],
            "status": receipt["status"], "observed_effect": {"effect": "READ" if dispatched else "NONE",
                "fixture_id": FIXTURE_ID, "synthetic": True, "verification_state": receipt["verification_state"],
                "executor_output_sha256": receipt["executor_output_sha256"], "observed_sha256": receipt["observed_sha256"],
                "output_bytes": len(receipt["output"].encode("utf-8")) if isinstance(receipt["output"], str) else 0},
            "error_code": receipt["error_code"], "execution_boundary_id": sandbox.get("sandbox_id") if dispatched else None,
            "actual_limits": sandbox.get("gex_effective_constraints") if dispatched else None,
            "input_sha256": hashlib.sha256(_canonical(request["operation"]["arguments"])).hexdigest(),
            "output_sha256": receipt["executor_output_sha256"], "evidence_refs": receipt["evidence_refs"],
            "persisted_at": receipt["persisted_at"]}

    def _attach_full_receipt(self, record):
        """CR03: preserve normative ReceiptV1 as durable execution evidence."""
        full = {**self._receipt_fields(record), "origin_event_ids": [
            event.event_id for event in self.ledger.events_for_request(record["request_id"])]}
        validate("ReceiptV1", full)
        record["receipt"]["gex_receipt"] = full

    def _attach_denial(self, record, code):
        """No dispatch claim: a durable denial after full registration."""
        record["receipt"] = {"receipt_id": "gexdenial_" + uuid.uuid4().hex,
            "request_digest": record["request_digest"], "attempt_id": None,
            "permit_id": (record["permit"] or {}).get("permit_id"), "status": "DENIED",
            "verification_state": "NOT_EXECUTED", "verification_result_id": None,
            "observed_sha256": None, "executor_output_sha256": None, "fixture_id": FIXTURE_ID,
            "synthetic": True, "output": None, "sandbox_receipt": None,
            "persisted_at": _stamp(datetime.now(timezone.utc)),
            "evidence_refs": ["control-denial:" + code], "error_code": code}
        self._attach_full_receipt(record)

    def _verify_full_receipt(self, record):
        receipt = record["receipt"]
        full = receipt.get("gex_receipt")
        validate("ReceiptV1", full)
        if any(full[key] != value for key, value in self._receipt_fields(record).items()):
            return False
        events = self.ledger.events_for_request(record["request_id"])
        receipt_index = next((index for index, event in enumerate(events) if event.kind == "RECEIPT_PERSISTED" and event.payload_ref.startswith("control-artifact-sha256:")), None)
        if receipt_index is None or full["origin_event_ids"] != [event.event_id for event in events[:receipt_index]]:
            return False
        if receipt["attempt_id"] is not None:
            sandbox = receipt["sandbox_receipt"]
            required = {"PROPOSED", "POLICY_DECIDED", "APPROVAL_REQUESTED", "APPROVED", "PERMIT_ISSUED", "PERMIT_CONSUMED", "DISPATCH_INTENT", "RECEIPT_PERSISTED", "EFFECT_OBSERVED"}
            if not required.issubset({event.kind for event in events[:receipt_index]}):
                return False
            if (full["actual_limits"] != record["request"]["constraints"] or sandbox.get("profile") != "read_only_agent"
                    or sandbox.get("filesystem_mode") != "read_only" or sandbox.get("network_mode") != "deny"
                    or sandbox.get("argv") != [] or not full["execution_boundary_id"]
                    or full["observed_effect"]["output_bytes"] > record["request"]["constraints"]["max_output_bytes"]):
                return False
        return True

    def _normative_verification(self, record):
        receipt = record["receipt"]
        success = receipt["verification_state"] == "VERIFIED_SUCCESS"
        result = {"contract_version": "gex-verification-result/v1", "verification_id": receipt["verification_result_id"],
            "receipt_id": receipt["receipt_id"], "receipt_digest": digest("RECEIPT", receipt["gex_receipt"]),
            "request_digest": record["request_digest"], "attempt_id": receipt["attempt_id"],
            "verifier_id": "adl.fixture-independent-observer", "verifier_version": "1",
            "outcome": "VERIFIED_SUCCESS" if success else "VERIFIED_FAILURE" if receipt["observed_sha256"] else "INCONCLUSIVE",
            "postcondition_digest": receipt["observed_sha256"],
            "evidence_refs": ["oracle-code-sha256:" + record["_provenance"]["oracle_code_sha256"],
                "legacy-observer-result:" + receipt["verification_result_id"]],
            "reason_code": "EXPECTED_EXECUTOR_ORACLE_HASHES_MATCH" if success else "INDEPENDENT_POSTCONDITION_NOT_CONFIRMED",
            "verified_at": _stamp(datetime.now(timezone.utc))}
        validate("VerificationResultV1", result)
        return result

    def _verify_normative_verification(self, record):
        receipt = record["receipt"]
        result = receipt.get("gex_verification")
        validate("VerificationResultV1", result)
        durable = self.ledger.runtime_verification(receipt["verification_result_id"])
        if durable != result or result["receipt_digest"] != digest("RECEIPT", receipt["gex_receipt"]):
            return False
        expected = {"verification_id": receipt["verification_result_id"], "receipt_id": receipt["receipt_id"],
            "request_digest": record["request_digest"], "attempt_id": receipt["attempt_id"],
            "verifier_id": "adl.fixture-independent-observer", "verifier_version": "1",
            "outcome": "VERIFIED_SUCCESS", "postcondition_digest": receipt["observed_sha256"],
            "reason_code": "EXPECTED_EXECUTOR_ORACLE_HASHES_MATCH",
            "evidence_refs": ["oracle-code-sha256:" + record["_provenance"]["oracle_code_sha256"],
                "legacy-observer-result:" + receipt["verification_result_id"]]}
        return all(result[key] == value for key, value in expected.items())

    def decide(self, request_id, submitted_digest, decision, reason, principal, token):
        with self.lock:
            if contains_credential(reason) or re.search(r"bago_gex_(?:key|session)_v1_[A-Za-z0-9_-]+", reason):
                raise ControlError("DECISION_CREDENTIAL_DENIED", 422)
            record = self._read(request_id, principal)
            if record["state"] != "AWAITING_APPROVAL":
                self.ledger.record_control_replay(record)
                code = "PERMIT_REPLAY" if decision == "APPROVED" and record["permit"] else "REQUEST_TERMINAL"
                raise ControlError(code, 409, persisted=True, view=self.view(record, principal))
            if submitted_digest != record["request_digest"]:
                raise ControlError("REQUEST_DIGEST_MISMATCH", 409, persisted=True, view=self.view(record, principal))
            try:
                self._fresh(record, principal)
            except ControlError as error:
                record["state"] = "EXPIRED" if error.code == "REQUEST_EXPIRED" else "DENIED"
                record["error"] = {"code": error.code, "message": "La autorización revisada ya no coincide con el estado actual."}
                self._save(record, principal, record["state"])
                self._attach_denial(record, error.code)
                self._save(record, principal, "RECEIPT_PERSISTED")
                raise ControlError(error.code, 409, persisted=True, view=self.view(record, principal)) from None
            if decision in {"APPROVED", "REJECTED"}:
                record["approval"] = self._signed_approval(record, principal, decision, reason)
            record["state"] = decision
            record["_decision"] = {"actor": principal.principal_id, "reason": reason, "decision": decision,
                                   "timestamp": _stamp(datetime.now(timezone.utc))}
            self._save(record, principal, decision)
            if decision != "APPROVED":
                record["receipt"] = {"receipt_id": "gexdenial_" + uuid.uuid4().hex, "request_digest": record["request_digest"], "attempt_id": None, "permit_id": None,
                    "status": "DENIED", "verification_state": "NOT_EXECUTED", "verification_result_id": None,
                    "observed_sha256": None, "executor_output_sha256": None, "fixture_id": FIXTURE_ID, "synthetic": True,
                    "output": None, "sandbox_receipt": None, "persisted_at": _stamp(datetime.now(timezone.utc)),
                    "evidence_refs": ["decision-reason-sha256:" + hashlib.sha256(reason.encode()).hexdigest()], "error_code": decision}
                self._attach_full_receipt(record)
                self._save(record, principal, "RECEIPT_PERSISTED")
                return self.view(record, principal)
            self._verify_approval(self._read(request_id, principal), live_principal=principal)
            instant, request = datetime.now(timezone.utc), record["request"]
            self._fresh(record, principal)
            ttl = int((_parse_stamp(request["expires_at"]) - instant).total_seconds())
            if ttl < 1:
                raise ControlError("REQUEST_EXPIRED", 409, persisted=True)
            claims = AuthorizationClaims(request_digest=record["request_digest"], agent_config_digest=request["agent"]["config_digest"],
                capability_id="fixture.read", capability_version="1", registry_digest=request["capability"]["registry_digest"],
                effect_scope=request["operation"]["effect_scope"], operation_digest=FixtureReadRequest(request_id, FIXTURE_ID).operation_digest,
                policy_revision=request["policy"]["revision"], constraints_effective=request["constraints"],
                decision_id=record["policy_decision"]["decision_id"], approval_id=record["approval"]["approval_id"])
            permit_principal = replace(principal, workspace_id=request["workspace"]["binding_fingerprint"])
            permit = issue_permit(principal=permit_principal, authorization=claims, keys=self.keys, ttl_seconds=ttl, now=instant)
            record["permit"] = permit.to_dict()
            self._save(record, principal, "APPROVED")
            context = PermitVerificationContext(request_digest=record["request_digest"], principal=permit_principal, now=instant,
                is_revoked=lambda _: False, is_session_active=lambda candidate: replace(self.authenticate(token, principal.agent_id), workspace_id=request["workspace"]["binding_fingerprint"]) == candidate)
            self.ledger.register_permit(permit=permit, keys=self.keys, context=context, request_id=request_id,
                run_id=record["run_id"], proposal_id=record["proposal_id"], proposal_digest=record["proposal"]["proposal_digest"])
            authority = ValidatedExecutionAuthority(request=request, principal=principal,
                validate_live=lambda: self._live_execution(request_id, principal, token))
            try:
                result = self.service.execute_fixture_read(session_token=token, request=FixtureReadRequest(request_id, FIXTURE_ID),
                    permit=permit, authority=authority)
                record = self._read(request_id, principal)
                terminal = self.ledger.terminal_verification(result.attempt_id)
                if terminal is None:
                    raise LedgerError("terminal verification missing")
                record["receipt"] = {"receipt_id": terminal.receipt_id, "request_digest": terminal.request_digest,
                    "attempt_id": terminal.attempt_id, "permit_id": terminal.permit_id,
                    "status": terminal.receipt["status"],
                    "verification_state": terminal.verification_state, "verification_result_id": terminal.verification_result_id,
                    "observed_sha256": terminal.observed_output_sha256, "executor_output_sha256": terminal.executor_output_sha256,
                    "fixture_id": FIXTURE_ID, "synthetic": True, "output": result.output, "sandbox_receipt": terminal.receipt,
                    "persisted_at": _stamp(datetime.now(timezone.utc)),
                    "evidence_refs": ["ledger:terminal_receipts:" + terminal.receipt_id, "ledger:verification_results:" + terminal.verification_result_id],
                    "error_code": None if terminal.verification_state == "VERIFIED_SUCCESS" else "VERIFICATION_FAILED"}
                record["state"] = "SUCCEEDED" if terminal.verification_state == "VERIFIED_SUCCESS" else "FAILED"
                self._attach_full_receipt(record)
                self._save(record, principal, "RECEIPT_PERSISTED")
                verification = self._normative_verification(record)
                self.ledger.persist_runtime_verification(record, verification)
                record["receipt"]["gex_verification"] = verification
                self._save(record, principal, "RECEIPT_PERSISTED")
            except (StoreUnavailableError, OSError):
                raise ControlError("STORE_UNAVAILABLE_FAIL_CLOSED", 503, persisted=False) from None
            except ControlError as error:
                record = self._read(request_id, principal)
                state = self.ledger.permit_state(permit.permit_id)
                record["state"] = "RECONCILIATION_REQUIRED" if state and state["state"] == "CONSUMED" else "DENIED"
                record["error"] = {"code": error.code, "message": "La autoridad cambió antes de completar la operación."}
                self._save(record, principal, "CONTROL_FAILED")
                if record["state"] == "DENIED":
                    self._attach_denial(record, error.code)
                    self._save(record, principal, "RECEIPT_PERSISTED")
                raise ControlError(error.code, error.status, persisted=True, view=self.view(record, principal)) from None
            except Exception:
                record = self._read(request_id, principal)
                state = self.ledger.permit_state(permit.permit_id)
                record["state"] = "RECONCILIATION_REQUIRED" if state and state["state"] == "CONSUMED" else "DENIED"
                record["error"] = {"code": "EXECUTION_UNVERIFIED", "message": "La ejecución no tiene verificación durable completa."}
                self._save(record, principal, "CONTROL_FAILED")
                raise ControlError("EXECUTION_UNVERIFIED", 409, persisted=True, view=self.view(record, principal)) from None
            return self.view(record, principal)

    def get(self, request_id, principal):
        with self.lock:
            record = self._read(request_id, principal)
            if record["state"] == "AWAITING_APPROVAL" and datetime.now(timezone.utc) >= _parse_stamp(record["request"]["expires_at"]):
                record["state"] = "EXPIRED"
                self._save(record, principal, "EXPIRED")
                self._attach_denial(record, "REQUEST_EXPIRED")
                self._save(record, principal, "RECEIPT_PERSISTED")
            return self.view(record, principal)

    def view(self, record, principal):
        record = self._read(record["request_id"], principal)
        self._verify_proposal_artifacts(record)
        envelope = record["_proposal_envelope"]
        if envelope["principal_subject"] != principal.principal_id or envelope["agent_id"] != principal.agent_id:
            raise ControlError("PROPOSAL_INTEGRITY_INVALID", 409)
        integrity = {"request_digest_valid": None, "event_chain_valid": self.ledger.verify_event_chain(record["request_id"]),
            "approval_signature_valid": None, "permit_signature_valid": None, "receipt_verified": False}
        try:
            if record["request"] is not None:
                integrity["request_digest_valid"] = whole_request_digest(record["request"]) == record["request_digest"]
            if record["approval"] is not None:
                integrity["approval_signature_valid"] = self._verify_approval(record)
            if record["permit"] is not None:
                integrity["permit_signature_valid"] = self._verify_permit_signature(record)
            receipt = record["receipt"]
            if receipt is not None and not self._verify_full_receipt(record):
                record["error"] = {"code": "RECEIPT_INTEGRITY_INVALID", "message": "El recibo completo no satisface el contrato."}
            if receipt is not None and receipt["attempt_id"] is not None:
                terminal = self.ledger.terminal_verification(receipt["attempt_id"])
                integrity["receipt_verified"] = bool(terminal and terminal.verification_state == "VERIFIED_SUCCESS"
                    and receipt["status"] == "SUCCESS" and receipt["verification_state"] == "VERIFIED_SUCCESS"
                    and receipt["request_digest"] == record["request_digest"] == terminal.request_digest
                    and receipt["receipt_id"] == terminal.receipt_id and receipt["permit_id"] == terminal.permit_id == record["permit"]["permit_id"]
                    and receipt["verification_result_id"] == terminal.verification_result_id
                    and receipt["sandbox_receipt"] == terminal.receipt and isinstance(receipt["output"], str)
                    and hashlib.sha256(receipt["output"].encode("utf-8")).hexdigest() == receipt["executor_output_sha256"]
                    == receipt["observed_sha256"] == terminal.executor_output_sha256 == terminal.observed_output_sha256 == FIXTURE_SHA256
                    and integrity["request_digest_valid"] and integrity["event_chain_valid"]
                    and integrity["approval_signature_valid"] and integrity["permit_signature_valid"]
                    and self._verify_full_receipt(record) and self._verify_normative_verification(record))
        except (StoreUnavailableError, OSError):
            raise
        except Exception:
            if record["approval"] is not None and integrity["approval_signature_valid"] is None:
                integrity["approval_signature_valid"] = False
            if record["permit"] is not None and integrity["permit_signature_valid"] is None:
                integrity["permit_signature_valid"] = False
        if record["state"] == "SUCCEEDED" and not integrity["receipt_verified"]:
            record["state"] = "RECONCILIATION_REQUIRED"
            record["error"] = {"code": "RECEIPT_INTEGRITY_INVALID", "message": "El recibo no satisface la verificación completa."}
        public = {key: value for key, value in record.items() if not key.startswith("_")}
        public["proposal_envelope"] = record.get("_proposal_envelope")
        public["proposal_denial"] = record.get("_proposal_denial")
        return {**public, "integrity": integrity, "events": [
            {key: event.to_dict()[key] for key in ("event_id", "kind", "timestamp", "seq", "prev_hash", "event_digest", "request_id", "request_digest", "attempt_id", "permit_id", "payload_ref")}
            for event in self.ledger.events_for_request(record["request_id"])]}

    def _recover_controls(self):
        with self.ledger._connect() as db:
            rows = db.execute("SELECT * FROM control_records").fetchall()
        for row in rows:
            record = strict_json(row["record_json"])
            if record["state"] not in {"APPROVED", "RUNNING"}:
                continue
            record = self.ledger.read_control(row["request_id"], principal_id=row["principal_id"], workspace_id=row["workspace_id"], agent_id=row["agent_id"])
            record["state"] = "RECONCILIATION_REQUIRED"
            record["error"] = {"code": "RESTART_RECONCILIATION_REQUIRED", "message": "La operación pendiente no se reejecutó al reiniciar."}
            self.ledger.save_control(record, principal_id=row["principal_id"], workspace_id=row["workspace_id"], agent_id=row["agent_id"], kind="CONTROL_FAILED")
