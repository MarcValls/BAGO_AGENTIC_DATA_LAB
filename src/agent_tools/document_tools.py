"""ADL assignments and scoped grants around the independently installable toolkit.

Source bytes: tools/document-toolkit. No model-supplied extraction bundle is trusted.
Authorization follows the existing workspace read owner/conversation/revision pattern.
"""
from __future__ import annotations

from pathlib import Path
import copy
import hashlib
import importlib.util
import json
import os
import secrets
import sys
import threading
import time
import uuid
from urllib.parse import quote

PACKAGE = Path(__file__).resolve().parents[2] / "tools/document-toolkit/document_toolkit"
_load_lock = threading.Lock()


def toolkit():
    """Load the shipped package by a fixed path; no dependency on test sys.path."""
    with _load_lock:
        existing = sys.modules.get("document_toolkit")
        if existing is not None and Path(existing.__file__).resolve() == PACKAGE / "__init__.py":
            return existing
        spec = importlib.util.spec_from_file_location("document_toolkit", PACKAGE / "__init__.py",
                                                     submodule_search_locations=[str(PACKAGE)])
        module = importlib.util.module_from_spec(spec)
        sys.modules["document_toolkit"] = module
        spec.loader.exec_module(module)
        return module


TOOL_SPECS = {
    "document_inventory": ("inventory", "Inventariar documentos", "Inventory documents", "READ",
                           {"cursor": {"type": "string"}}),
    "document_extract": ("extract", "Leer documentos y citar fuentes", "Read documents with sources", "READ",
                         {"paths": {"type": "array", "items": {"type": "string"}, "minItems": 1, "maxItems": 10}}),
    "document_relate": ("relate", "Relacionar documentos para revisión", "Relate documents for review", "READ",
                        {"bundle_id": {"type": "string"}}),
    "document_plan_rename": ("plan-rename", "Proponer nombres de documentos", "Propose document filenames", "PROPOSE",
                             {"entries": {"type": "array", "maxItems": 100, "items": {"type": "object", "required": ["path", "destination", "expected_sha256"], "properties": {"path": {"type": "string"}, "destination": {"type": "string"}, "expected_sha256": {"type": "string"}}, "additionalProperties": False}}}),
    "document_export": ("export", "Crear informe documental", "Create document report", "WRITE_OUTPUT",
                        {"bundle_id": {"type": "string"}, "format": {"type": "string", "enum": ["json", "csv"]}}),
}
DOCUMENT_TOOL_IDS = frozenset(TOOL_SPECS)


def descriptors():
    observed = toolkit().capabilities()
    return [{"id": name, "name": spec[1], "name_en": spec[2], "provider": "Local document toolkit",
             "effect": spec[3], "status": "AVAILABLE", "integration": "CONNECTED",
             "summary": "Carpeta autorizada; formatos disponibles según dependencias. Las relaciones requieren revisión.",
             "assignable": True, "formats": observed["formats"],
             "limits": {"requires_user_opt_in": True, "max_corpus_files": 10000, "inventory_batch": 100,
                        "extract_batch": 10, "source_writes": False, "requires_output_opt_in": name == "document_export"},
             "source_paths": ["src/agent_tools/document_tools.py", "tools/document-toolkit/document_toolkit/core.py", "tools/document-toolkit/document_toolkit/parsers.py"]}
            for name, spec in TOOL_SPECS.items()]


class DocumentAccessError(ValueError):
    def __init__(self, code):
        self.code = code
        super().__init__(code)


def _safe_root(value):
    from document_toolkit.core import _root
    return _root(value)


def allowed_roots(workspace):
    toolkit()
    roots = [str(Path(workspace).resolve())]
    roots.extend(p for p in os.getenv("BAGO_DOCUMENT_ALLOWED_ROOTS", "").split(os.pathsep) if p)
    result = []
    for raw in roots:
        try:
            path = _safe_root(raw)
            if path not in result:
                result.append(path)
        except (ValueError, OSError):
            continue
    return result


def checked_directory(value, workspace):
    path = _safe_root(value)
    bound=Path(workspace).resolve()
    if path.is_relative_to(bound) and any(part.startswith('.') or part in {'node_modules','venv','__pycache__'} for part in path.relative_to(bound).parts):
        raise DocumentAccessError('INTERNAL_ROOT_REJECTED')
    if not any(path.is_relative_to(root) for root in allowed_roots(workspace)):
        raise DocumentAccessError("DOCUMENT_ROOT_NOT_ALLOWED")
    return path


def output_directory():
    return Path(os.getenv("BAGO_DOCUMENT_OUTPUT_ROOT", str(Path(os.getenv("LOCALAPPDATA", str(Path.home()/'.local/share')))/'BAGO/AgenticDataLab/document-exports'))).absolute()


def browse(value, workspace):
    roots = allowed_roots(workspace)
    if value is None:
        return {"roots": [{"path": str(p), "name": p.name or str(p)} for p in roots], "directories": [], "output_directory": str(output_directory())}
    directory = checked_directory(value, workspace)
    containing = max((p for p in roots if directory.is_relative_to(p)), key=lambda p: len(p.parts))
    folders = []
    with os.scandir(directory) as entries:
        for entry in entries:
            if len(folders) >= 500:
                raise DocumentAccessError("DIRECTORY_LIST_LIMIT")
            if entry.name.startswith(".") or entry.name in {"node_modules", "__pycache__"}:
                continue
            if entry.is_dir(follow_symlinks=False):
                try:
                    checked_directory(entry.path, workspace)
                    folders.append({"path": entry.path, "name": entry.name})
                except (OSError, ValueError):
                    continue
    return {"roots": [{"path": str(p), "name": p.name or str(p)} for p in roots], "path": str(directory),
            "parent": str(directory.parent) if directory != containing else None,
            "output_directory": str(output_directory()),
            "directories": sorted(folders, key=lambda x: x["name"].casefold())}


def _manifest(root):
    """Metadata-only corpus snapshot; content hashes are produced by actual tools."""
    from document_toolkit.core import _no_links
    rows = []
    started = time.monotonic()
    for directory, folders, files in os.walk(root, followlinks=False):
        if time.monotonic()-started > 10:
            raise DocumentAccessError("CORPUS_METADATA_TIME_LIMIT")
        safe = []
        for name in sorted(folders):
            if name.startswith(".") or name in {"node_modules", "__pycache__", "venv"}:
                continue
            try:
                _no_links(Path(directory)/name); safe.append(name)
            except (OSError, ValueError):
                raise DocumentAccessError("CORPUS_LINK_REJECTED") from None
        folders[:] = safe
        for name in sorted(files):
            path = Path(directory)/name
            if name.startswith("."):
                continue
            if len(rows) >= 10000:
                raise DocumentAccessError("CORPUS_FILE_COUNT_LIMIT")
            _no_links(path)
            info = path.stat()
            if not path.is_file():
                raise DocumentAccessError("CORPUS_NON_REGULAR_FILE")
            rows.append({"path": path.relative_to(root).as_posix(), "bytes": info.st_size,
                         "mtime_ns": info.st_mtime_ns, "inode": info.st_ino})
    return rows


class DocumentAuthorizations:
    def __init__(self):
        self.lock = threading.RLock()
        self.grants = {}
        self.sessions = {}

    def issue(self, *, workspace, owner_id, conversation_id, revision, root, assigned, confirmed,
              allow_export=False, expected_output_directory=None, evidence_root=None,communications=None,
              review_work_id=None,review_candidate_id=None,review_scope_sha256=None,contact_id=None,allow_draft=False):
        from src.agent_tools.agent_services import SERVICE_TOOL_IDS,AgentServiceSession,DELIVERY_TOOL_IDS
        if confirmed is not True or not (DOCUMENT_TOOL_IDS|SERVICE_TOOL_IDS).intersection(assigned):
            raise DocumentAccessError("DOCUMENT_CONSENT_OR_ASSIGNMENT_REQUIRED")
        if allow_export and expected_output_directory != str(output_directory()):
            raise DocumentAccessError("DOCUMENT_OUTPUT_SCOPE_NOT_CONFIRMED")
        if allow_export and "document_export" not in assigned:
            raise DocumentAccessError("DOCUMENT_OUTPUT_TOOL_NOT_ASSIGNED")
        directory = checked_directory(root, workspace)
        from src.agent_tools.filesystem_tools import FS_TOOL_IDS
        manifest = _manifest(directory) if (DOCUMENT_TOOL_IDS|FS_TOOL_IDS).intersection(assigned) else []
        fingerprint = hashlib.sha256(json.dumps(manifest, sort_keys=True).encode()).hexdigest()
        identity = (owner_id, conversation_id, str(directory), fingerprint, str(output_directory()))
        if allow_draft and 'delivery_prepare_draft' not in assigned:raise DocumentAccessError('DRAFT_TOOL_NOT_ASSIGNED')
        if review_work_id:
            if not DELIVERY_TOOL_IDS.intersection(assigned):raise DocumentAccessError('REVIEW_TOOL_NOT_ASSIGNED')
            from src.services.agent_producers import ProducerStore
            try:selected=ProducerStore(workspace).load_registered(review_work_id)
            except (ValueError,OSError,KeyError):raise DocumentAccessError('REVIEW_WORK_UNAVAILABLE') from None
            if selected['candidate_id']!=review_candidate_id or selected['scope_sha256']!=review_scope_sha256:raise DocumentAccessError('REVIEW_CANDIDATE_SCOPE_NOT_CONFIRMED')
        if contact_id and (communications is None or not any(c['id']==contact_id for c in communications.contacts())):raise DocumentAccessError('REVIEW_CONTACT_NOT_FOUND')
        services=AgentServiceSession(workspace=workspace,root=directory,owner_id=owner_id,
            conversation_id=conversation_id,communications=communications,review_work_id=review_work_id,contact_id=contact_id,allow_draft=allow_draft)
        with self.lock:
            now = time.time()
            self.grants = {k: v for k, v in self.grants.items() if v["expires_at"] > now}
            self.sessions = {k: v for k, v in self.sessions.items() if v.expires_at > now}
            if len(self.grants) >= 128 or len(self.sessions) >= 64:
                raise DocumentAccessError("DOCUMENT_SESSION_LIMIT")
            session = self.sessions.get(identity)
            if session is None:
                session = DocumentSession(directory, manifest, fingerprint, evidence_root)
                self.sessions[identity] = session
            token = secrets.token_urlsafe(32)
            self.grants[token] = {"owner_id": owner_id, "conversation_id": conversation_id, "revision": revision,
                                  "workspace": str(Path(workspace).resolve()), "expires_at": now+300,
                                  "session": session, "assigned": frozenset(assigned), "allow_export": bool(allow_export),"services":services}
        return {"authorization_id": token, "root": str(directory), "files": len(manifest),
                "manifest_sha256": fingerprint, "expires_in_seconds": 300, "allow_export": bool(allow_export),
                "formats": toolkit().capabilities()["formats"], "output_directory": str(session.output_directory)}

    def consume(self, token, *, owner_id, conversation_id, revision, workspace, assigned):
        with self.lock:
            grant = self.grants.get(token)
            if grant is None:
                raise DocumentAccessError("DOCUMENT_AUTHORIZATION_REQUIRED")
            if grant["expires_at"] <= time.time():
                self.grants.pop(token, None)
                raise DocumentAccessError("DOCUMENT_AUTHORIZATION_EXPIRED")
            if (grant["owner_id"], grant["conversation_id"], grant["revision"], grant["workspace"]) != (
                    owner_id, conversation_id, revision, str(Path(workspace).resolve())):
                raise DocumentAccessError("DOCUMENT_AUTHORIZATION_SCOPE_MISMATCH")
            grant = self.grants.pop(token)
            checked_directory(grant["session"].root, workspace)
            grant["assigned"] = grant["assigned"].intersection(assigned)
            return grant

    def report(self, receipt_id, *, owner_id, conversation_id):
        from document_toolkit.core import _no_links
        with self.lock:
            for identity, session in self.sessions.items():
                if identity[:2] != (owner_id, conversation_id) or session.expires_at <= time.time():
                    continue
                output = session.outputs.get(receipt_id)
                if output is not None:
                    path = Path(output["path"])
                    _no_links(path)
                    if not path.resolve().is_relative_to(session.output_directory.resolve()) or hashlib.sha256(path.read_bytes()).hexdigest() != output["sha256"]:
                        raise DocumentAccessError("DOCUMENT_REPORT_INTEGRITY_FAILED")
                    return path
        raise DocumentAccessError("DOCUMENT_REPORT_NOT_FOUND")


class DocumentSession:
    def __init__(self, root, manifest, fingerprint, evidence_root):
        self.root = root
        self.manifest = manifest
        self.fingerprint = fingerprint
        self.paths = {r["path"] for r in manifest}
        self.bundles = {}
        self.cursors = {}
        self.outputs = {}
        self.expires_at = time.time()+3600
        self.evidence_root = Path(evidence_root) if evidence_root else None
        self.output_directory = output_directory()

    def tool_schemas(self, grant):
        result = []
        for name in sorted(grant["assigned"].intersection(DOCUMENT_TOOL_IDS)):
            spec = TOOL_SPECS[name]
            if name == "document_export" and not grant["allow_export"]:
                continue
            required = ["paths"] if name == "document_extract" else ["bundle_id"] if name in {"document_relate", "document_export"} else ["entries"] if name == "document_plan_rename" else []
            result.append({"type": "function", "function": {"name": name,
                "description": spec[2]+". Only the authorized corpus. Inventory returns next_cursor until complete. Extract returns bundle_id for later relation/export. Never claim payment or rename execution.",
                "parameters": {"type": "object", "properties": spec[4], "required": required, "additionalProperties": False}}})
        return result

    def invoke(self, name, arguments, grant):
        receipt = {"kind": "document_tool", "tool_name": name, "decision": "DENY", "path": str(self.root),
                   "manifest_sha256": self.fingerprint, "receipt_id": "document_"+uuid.uuid4().hex,
                   "executed": False, "source_writes": False}
        try:
            if name not in DOCUMENT_TOOL_IDS or name not in grant["assigned"]:
                raise DocumentAccessError("DOCUMENT_TOOL_NOT_ASSIGNED")
            args = json.loads(arguments) if isinstance(arguments, str) else arguments
            if not isinstance(args, dict) or set(args)-set(TOOL_SPECS[name][4]):
                raise DocumentAccessError("INVALID_DOCUMENT_ARGUMENTS")
            if time.time() >= self.expires_at:
                raise DocumentAccessError("DOCUMENT_SESSION_EXPIRED")
            if _manifest(self.root) != self.manifest:
                raise DocumentAccessError("DOCUMENT_SNAPSHOT_CHANGED")
            operation = TOOL_SPECS[name][0]
            fields = copy.deepcopy(args)
            next_cursor = None
            if operation == "inventory":
                cursor = args.get("cursor")
                if cursor is not None and cursor not in self.cursors:
                    raise DocumentAccessError("INVALID_DOCUMENT_CURSOR")
                offset = self.cursors.get(cursor, 0)
                selected = [r["path"] for r in self.manifest[offset:offset+100]]
                if not selected:
                    return {"state": "EXECUTED", "records": [], "coverage": {"total": len(self.manifest), "offset": offset, "complete": True}, "next_cursor": None}, {**receipt, "decision": "ALLOW", "executed": True}
                fields = {"paths": selected}
                if offset+len(selected) < len(self.manifest):
                    next_cursor = secrets.token_urlsafe(18)
                    self.cursors[next_cursor] = offset+len(selected)
            elif operation == "extract":
                selected = args.get("paths")
                if not isinstance(selected, list) or not 1 <= len(selected) <= 10 or any(p not in self.paths for p in selected):
                    raise DocumentAccessError("DOCUMENT_PATH_NOT_AUTHORIZED")
            elif operation in {"relate", "export"}:
                bundle_id = fields.pop("bundle_id", None)
                if bundle_id not in self.bundles:
                    raise DocumentAccessError("DOCUMENT_BUNDLE_NOT_FOUND")
                fields["bundle"] = self.bundles[bundle_id]
                if operation == "export":
                    if not grant["allow_export"]:
                        raise DocumentAccessError("DOCUMENT_OUTPUT_CONSENT_REQUIRED")
                    fmt = fields.get("format", "json")
                    if fmt not in {"json", "csv"}:
                        raise DocumentAccessError("INVALID_DOCUMENT_FORMAT")
                    if self.output_directory.resolve().is_relative_to(self.root):
                        raise DocumentAccessError("DOCUMENT_OUTPUT_WITHIN_SOURCE_REJECTED")
                    self.output_directory.mkdir(parents=True, exist_ok=True)
                    fields["destination"] = str(self.output_directory/('documents_'+uuid.uuid4().hex+'.'+fmt))
            elif operation == "plan-rename":
                if not isinstance(args.get("entries"), list) or any(e.get("path") not in self.paths for e in args["entries"] if isinstance(e, dict)):
                    raise DocumentAccessError("DOCUMENT_PATH_NOT_AUTHORIZED")
            limits = toolkit().Limits(max_files=100, max_chars=12000, max_seconds=30)
            result = toolkit().execute(operation, self.root, fields, limits=limits)
            receipt.update(executed=True, decision="FAIL" if result["state"] == "FAILED" else "ALLOW",
                           outcome=result["state"],
                           reason_code=result["errors"][0]["code"] if result["errors"] else None)
            if operation == "inventory":
                result.update(next_cursor=next_cursor, corpus_coverage={"total": len(self.manifest), "offset": offset,
                              "batch_selected": len(selected), "complete": next_cursor is None and not result["errors"]})
            if operation == "extract" and result["records"]:
                if len(self.bundles) >= 20:
                    self.bundles.pop(next(iter(self.bundles)))
                bid = "bundle_"+uuid.uuid4().hex
                self.bundles[bid] = copy.deepcopy(result)
                result["bundle_id"] = bid
            if operation == "export" and result.get("output"):
                self.outputs[receipt["receipt_id"]] = result["output"]
                result["output"]["download_url"] = '/api/document-tools/reports/'+receipt["receipt_id"]+'?owner_id='+quote(grant["owner_id"],safe='')+'&conversation_id='+quote(grant["conversation_id"],safe='')
            for key in ("next_cursor", "corpus_coverage", "bundle_id", "output"):
                if key in result:
                    receipt[key] = result[key]
            receipt["result_sha256"] = hashlib.sha256(json.dumps(result, sort_keys=True).encode()).hexdigest()
            if self.evidence_root is not None:
                self.evidence_root.mkdir(parents=True, exist_ok=True)
                target = self.evidence_root/(receipt["receipt_id"]+'.json')
                payload = json.dumps({"receipt": receipt, "result": result}, ensure_ascii=False, sort_keys=True).encode('utf8')
                with target.open('xb') as output:
                    output.write(payload);output.flush();os.fsync(output.fileno())
                if target.read_bytes() != payload:
                    raise DocumentAccessError("DOCUMENT_RECEIPT_READBACK_FAILED")
                receipt.update(evidence_path=str(target), evidence_sha256=hashlib.sha256(payload).hexdigest())
            return result, receipt
        except (ValueError, OSError, TypeError, KeyError) as error:
            receipt["reason_code"] = getattr(error, "code", "DOCUMENT_EXECUTION_FAILED")
            if receipt["executed"]:
                receipt["decision"] = "FAIL"
            return {"ok": False, "state": "FAILED", "reason_code": receipt["reason_code"]}, receipt


DOCUMENT_AUTHORIZATIONS = DocumentAuthorizations()
