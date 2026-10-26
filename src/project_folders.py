"""Confirmed, missing-only initialization of an exact user-selected project root."""
from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import threading
import time
import uuid

from src.workspace_sdk.workspace_service import CONTEXT, MAX, SECRET, API, ServiceError, Workspace, WorkspaceService, checked_name

DIRECTORIES = (".bago", ".bago/context", ".bago/state", ".bago/runtime", ".workspace-service", ".workspace-service/trash", ".workspace-service/hooks")
MANIFEST = ".workspace-service/manifest.json"
PLAN_ID = re.compile(r"project-plan_[0-9a-f]{32}\Z")
WORKSPACE_ID = re.compile(r"workspace_[0-9a-f]{32}\Z")
DIGEST = re.compile(r"[0-9a-f]{64}\Z")
_LOCK = threading.RLock()


def _encoded(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False).encode("utf-8")


def _sha(raw):
    return hashlib.sha256(raw).hexdigest()


def _utc(seconds):
    return datetime.fromtimestamp(seconds, timezone.utc).isoformat()


class ProjectFolderError(ValueError):
    def __init__(self, code, message, status=409, receipt=None):
        super().__init__(message)
        self.code, self.status, self.receipt = code, status, receipt


def _stat(path, directory):
    value = path.lstat()
    if (stat.S_ISLNK(value.st_mode) or getattr(value, "st_file_attributes", 0) & 0x400
            or not (stat.S_ISDIR(value.st_mode) if directory else stat.S_ISREG(value.st_mode))
            or not directory and value.st_nlink != 1):
        raise ProjectFolderError("unsafe_path", "La ruta contiene enlaces o un tipo de archivo incompatible.")
    return value


def _ancestors(path):
    result = []
    for item in reversed((path, *path.parents)):
        info = _stat(item, True)
        result.append([str(item), info.st_dev, info.st_ino])
    return result


def _directory(value):
    if not isinstance(value, (str, Path)) or not str(value) or len(str(value)) > 1024 or any(ord(c) < 32 for c in str(value)):
        raise ProjectFolderError("invalid_path", "Elige una carpeta absoluta existente.", 422)
    path = Path(value)
    if not path.is_absolute() or ".." in path.parts:
        raise ProjectFolderError("invalid_path", "Elige una carpeta absoluta existente.", 422)
    try:
        _ancestors(path)
        return path.resolve(strict=True)
    except FileNotFoundError:
        raise ProjectFolderError("folder_not_found", "La carpeta indicada ya no existe.", 422) from None


def _file(path):
    before = _stat(path, False)
    if before.st_size > MAX:
        raise ProjectFolderError("file_too_large", "Un archivo de contexto supera el límite de 1 MiB.", 422)
    flags = os.O_RDONLY | getattr(os, "O_BINARY", 0) | getattr(os, "O_NOFOLLOW", 0)
    with os.fdopen(os.open(path, flags), "rb") as stream:
        opened = os.fstat(stream.fileno())
        if (opened.st_dev, opened.st_ino, opened.st_nlink) != (before.st_dev, before.st_ino, 1):
            raise ProjectFolderError("path_changed", "La identidad de un archivo ha cambiado.")
        raw = stream.read(MAX + 1)
    after = _stat(path, False)
    signature = lambda s: [s.st_dev, s.st_ino, s.st_size, s.st_mtime_ns]
    if len(raw) > MAX or signature(before) != signature(after):
        raise ProjectFolderError("path_changed", "Un archivo ha cambiado durante la lectura.")
    return raw, signature(after) + [_sha(raw)]


def binding_identity(config_path, workspace_root):
    """Readonly identity; atomic config replacement detects A -> B -> A."""
    path = Path(config_path)
    try:
        _ancestors(path.parent)
        raw, identity = _file(path)
    except FileNotFoundError:
        identity = None
    return {"workspace_root": str(workspace_root), "config_identity": identity}


def _snapshot(target):
    values = {}
    for relative in (*DIRECTORIES, *CONTEXT, MANIFEST):
        path = target / relative
        try:
            if relative in DIRECTORIES:
                item = _stat(path, True)
                values[relative] = [item.st_dev, item.st_ino]
            else:
                values[relative] = _file(path)[1]
        except FileNotFoundError:
            values[relative] = None
    return values


def _atomic_json(path, value):
    _ancestors(path.parent)
    raw = _encoded(value)
    temporary = path.with_name(path.name + ".tmp-" + uuid.uuid4().hex)
    with temporary.open("xb") as stream:
        stream.write(raw)
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temporary, path)


class ProjectFolders:
    def __init__(self, *, state_directory, workspace_root, set_workspace_root, pick_directory,
                 binding_identity, legacy_parent=lambda: None, binding_lock=None, clock=time.time, ttl=300):
        self.state = Path(state_directory).absolute()
        self.workspace_root, self.set_workspace_root, self.pick_directory = workspace_root, set_workspace_root, pick_directory
        self.binding_identity, self.legacy_parent = binding_identity, legacy_parent
        self.binding_lock = binding_lock or threading.RLock()
        self.clock, self.ttl, self.plans = clock, ttl, {}

    def config(self):
        return {"workspace_root": str(self.workspace_root()), "scope": "global_workspace"}

    def browse(self):
        selected = self.pick_directory(Path(self.workspace_root()))
        return {"path": str(selected) if selected else None, "cancelled": not bool(selected)}

    def _registry(self):
        path = self.state / "registry.json"
        try:
            _ancestors(self.state)
            value = json.loads(_file(path)[0])
        except FileNotFoundError:
            return {}
        except (ValueError, UnicodeError):
            raise ProjectFolderError("registry_invalid", "El registro de carpetas requiere revisión.") from None
        if (not isinstance(value, dict) or value.get("schema") != "project-folder-registry.v1"
                or not isinstance(value.get("roots"), dict) or len(value["roots"]) > 1000
                or value.get("sha256") != _sha(_encoded(value["roots"]))):
            raise ProjectFolderError("registry_invalid", "El registro de carpetas requiere revisión.")
        if any(not WORKSPACE_ID.fullmatch(identity) or not isinstance(row, dict)
               or not isinstance(row.get("root"), str) or not Path(row["root"]).is_absolute()
               or not isinstance(row.get("ancestors"), list)
               or not isinstance(row.get("manifest_sha256"), str) or not DIGEST.fullmatch(row["manifest_sha256"])
               for identity, row in value["roots"].items()):
            raise ProjectFolderError("registry_invalid", "El registro de carpetas requiere revisión.")
        return value["roots"]

    def _save_registry(self, roots):
        value = {"schema": "project-folder-registry.v1", "roots": roots, "sha256": _sha(_encoded(roots))}
        if len(roots) > 1000 or len(_encoded(value)) > MAX:
            raise ProjectFolderError("registry_capacity", "El registro alcanzó su límite; se conserva la versión anterior.")
        _atomic_json(self.state / "registry.json", value)

    def prepare(self, *, mode, path, name, title, expected_workspace_root):
        if mode not in {"existing", "create_child"}:
            raise ProjectFolderError("invalid_mode", "Elige carpeta existente o crear subcarpeta.", 422)
        parent = _directory(path)
        with _LOCK, self.binding_lock:
            binding = self.binding_identity()
            if expected_workspace_root != str(self.workspace_root()):
                raise ProjectFolderError("workspace_changed", "La carpeta activa cambió. Actualiza la vista.")
            if mode == "create_child":
                checked_name(name)
                target = parent / name
                if target.exists() or target.is_symlink():
                    raise ProjectFolderError("target_exists", "La subcarpeta ya existe; no se adoptará automáticamente.")
            else:
                target = parent
                name = name or target.name or "Proyecto"
                if not isinstance(name, str) or len(name) > 200 or any(c in name for c in "/\\") or any(ord(c) < 32 for c in name):
                    raise ProjectFolderError("invalid_name", "El nombre del proyecto no es válido.", 422)
            title = title or name
            if not isinstance(title, str) or not title.strip() or len(title) > 200 or any(ord(c) < 32 for c in title) or SECRET.search(title):
                raise ProjectFolderError("invalid_title", "Indica un título breve de una sola línea.", 422)
            snapshots = _snapshot(target) if mode == "existing" else dict.fromkeys((*DIRECTORIES, *CONTEXT, MANIFEST))
            workspace_id = "workspace_" + uuid.uuid4().hex
            if snapshots[".workspace-service"] is not None:
                if snapshots[MANIFEST] is None:
                    raise ProjectFolderError("foreign_service_state", "Los metadatos existentes de esta carpeta no tienen una identidad válida.")
                try:
                    existing = json.loads(_file(target / MANIFEST)[0].decode("utf-8"))
                    if (not WORKSPACE_ID.fullmatch(existing.get("id", "")) or existing.get("root") != str(target)
                            or not all(isinstance(existing.get(key), str) for key in ("name", "title", "revision", "created_at"))):
                        raise ValueError()
                    if (not existing["name"].strip() or len(existing["name"]) > 200 or any(c in existing["name"] for c in "/\\")
                            or not existing["title"].strip() or len(existing["title"]) > 200
                            or any(ord(c) < 32 for c in existing["name"] + existing["title"]) or SECRET.search(existing["title"])):
                        raise ValueError()
                    workspace_id = existing["id"]
                    # This operation adopts an existing SDK identity; it never renames it.
                    name, title = existing["name"], existing["title"]
                except (ValueError, TypeError, AttributeError, UnicodeError):
                    raise ProjectFolderError("foreign_service_state", "Los metadatos existentes no pertenecen a esta carpeta.") from None
            for relative in CONTEXT:
                if snapshots[relative] is not None:
                    try:
                        text = _file(target / relative)[0].decode("utf-8")
                        if "\0" in text or SECRET.search(text):
                            raise ValueError()
                    except (UnicodeError, ValueError):
                        raise ProjectFolderError("unsupported_context", "Un contexto existente no es compatible con el SDK; se conserva sin cambios.", 422) from None
            roots = self._registry()
            if workspace_id in roots and roots[workspace_id]["root"] != str(target):
                raise ProjectFolderError("registry_conflict", "La identidad ya pertenece a otra carpeta.")
            plan_id = "project-plan_" + uuid.uuid4().hex
            expires = self.clock() + self.ttl
            files = [{"path": relative, "action": "preserve" if snapshots[relative] is not None else "create"} for relative in (*CONTEXT, MANIFEST)]
            directories = ([{"path": ".", "action": "create"}] if mode == "create_child" else []) + [
                {"path": relative, "action": "preserve" if snapshots[relative] is not None else "create"} for relative in DIRECTORIES]
            public = {"plan_id": plan_id, "mode": mode, "path": str(parent), "name": name, "title": title,
                      "target_root": str(target), "expected_workspace_root": expected_workspace_root,
                      "files": files, "directories": directories, "expires_at": _utc(expires)}
            proof = {"public": public, "binding": binding, "ancestors": _ancestors(parent), "snapshot": snapshots,
                     "workspace_id": workspace_id, "expires": expires}
            public["plan_sha256"] = _sha(_encoded(proof))
            self.plans[plan_id] = json.loads(json.dumps(proof))
            return json.loads(json.dumps(public))

    @contextmanager
    def _state_lock(self):
        # Called only after exact confirmation and all readonly stale checks.
        missing = []
        ancestor = self.state
        while not ancestor.exists() and not ancestor.is_symlink():
            missing.append(ancestor)
            ancestor = ancestor.parent
        _ancestors(ancestor)
        for directory in reversed(missing):
            directory.mkdir(exist_ok=False)
            _stat(directory, True)
        _ancestors(self.state)
        lock = self.state / "lock"
        descriptor = os.open(lock, os.O_RDWR | os.O_CREAT | getattr(os, "O_BINARY", 0) | getattr(os, "O_NOFOLLOW", 0), 0o600)
        stream = os.fdopen(descriptor, "r+b")
        try:
            expected, opened = _stat(lock, False), os.fstat(stream.fileno())
            if (expected.st_dev, expected.st_ino, expected.st_nlink) != (opened.st_dev, opened.st_ino, 1):
                raise ProjectFolderError("path_changed", "La identidad del bloqueo ha cambiado.")
            if os.fstat(stream.fileno()).st_size == 0:
                stream.write(b"0"); stream.flush()
            stream.seek(0)
            if os.name == "nt":
                import msvcrt
                msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except ProjectFolderError:
            stream.close()
            raise
        except OSError:
            stream.close()
            raise ProjectFolderError("busy", "Otra operación está usando el registro.") from None
        try:
            yield
        finally:
            stream.seek(0)
            if os.name == "nt":
                import msvcrt
                msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                import fcntl
                fcntl.flock(stream.fileno(), fcntl.LOCK_UN)
            stream.close()

    def _receipt_path(self, plan_id):
        return self.state / (plan_id + ".json")

    def _stored(self, plan_id, digest):
        try:
            _ancestors(self.state)
            value = json.loads(_file(self._receipt_path(plan_id))[0])
        except FileNotFoundError:
            return None
        except (ValueError, UnicodeError):
            raise ProjectFolderError("receipt_invalid", "El intento anterior requiere revisión; no se repetirá.", 503) from None
        if (not isinstance(value, dict) or value.get("plan_id") != plan_id
                or value.get("status") not in {"APPLIED", "PARTIAL_FAILED", "INCONCLUSIVE"}
                or not isinstance(value.get("workspace_id"), str) or not WORKSPACE_ID.fullmatch(value["workspace_id"])):
            raise ProjectFolderError("receipt_invalid", "El intento anterior requiere revisión; no se repetirá.", 503)
        if value.get("plan_sha256") != digest:
            raise ProjectFolderError("plan_hash_conflict", "El hash no coincide con el intento registrado.")
        if value.get("status") == "APPLIED":
            workspace = self._open_registered(value["workspace_id"]).info()
            return {"workspace_root": str(self.workspace_root()), "workspace": workspace, "receipt": value}
        raise ProjectFolderError("project_folder_incomplete", "El intento anterior quedó incompleto; no se repetirá automáticamente.", 503, value)

    def _save_receipt(self, receipt):
        _atomic_json(self._receipt_path(receipt["plan_id"]), receipt)

    def _create_file(self, target, relative, raw):
        path = target / relative
        _ancestors(path.parent)
        flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_BINARY", 0) | getattr(os, "O_NOFOLLOW", 0)
        with os.fdopen(os.open(path, flags, 0o600), "wb") as stream:
            stream.write(raw); stream.flush(); os.fsync(stream.fileno())

    def _validate_plan(self, plan):
        public = plan["public"]
        target, parent = Path(public["target_root"]), Path(public["path"])
        if self.clock() >= plan["expires"]:
            raise ProjectFolderError("plan_expired", "El plan ha caducado; vuelve a prepararlo.")
        if self.binding_identity() != plan["binding"] or str(self.workspace_root()) != public["expected_workspace_root"]:
            raise ProjectFolderError("workspace_changed", "La carpeta activa cambió; vuelve a preparar el plan.")
        if _ancestors(parent) != plan["ancestors"]:
            raise ProjectFolderError("folder_changed", "La identidad de la carpeta ha cambiado.")
        if public["mode"] == "create_child":
            if target.exists() or target.is_symlink():
                raise ProjectFolderError("target_exists", "La subcarpeta apareció después de preparar el plan.")
        elif _snapshot(target) != plan["snapshot"]:
            raise ProjectFolderError("files_changed", "Los archivos o directorios previstos han cambiado.")

    def apply(self, plan_id, *, plan_sha256, confirmed):
        if not isinstance(plan_id, str) or not PLAN_ID.fullmatch(plan_id) or not isinstance(plan_sha256, str) or not DIGEST.fullmatch(plan_sha256):
            raise ProjectFolderError("invalid_plan", "El plan no es válido.", 422)
        if confirmed is not True:
            raise ProjectFolderError("confirmation_required", "Confirma el plan exacto antes de aplicar.", 422)
        with _LOCK, self.binding_lock:
            replay = self._stored(plan_id, plan_sha256)
            if replay is not None:
                return replay
            plan = self.plans.get(plan_id)
            if plan is None or plan["public"]["plan_sha256"] != plan_sha256:
                raise ProjectFolderError("plan_changed", "El plan no existe o su hash ha cambiado.")
            public = plan["public"]
            target, parent = Path(public["target_root"]), Path(public["path"])
            self._validate_plan(plan)
            receipt = {"receipt_id": "project-folder-receipt_" + uuid.uuid4().hex, "plan_id": plan_id,
                       "plan_sha256": plan_sha256, "status": "INCONCLUSIVE", "target_root": str(target),
                       "created_files": [], "created_directories": [], "registry_applied": False,
                       "binding_applied": False, "actual_workspace_root": str(self.workspace_root()), "error_code": None,
                       "workspace_id": plan["workspace_id"]}
            with self._state_lock():
                # Another process may have finished between the readonly check
                # and lock acquisition. Revalidate before admitting target effects.
                self._validate_plan(plan)
                # Exclusive durable admission means crash/replay never redispatches effects.
                try:
                    with self._receipt_path(plan_id).open("xb") as stream:
                        stream.write(_encoded(receipt)); stream.flush(); os.fsync(stream.fileno())
                except FileExistsError:
                    return self._stored(plan_id, plan_sha256)
                try:
                    if public["mode"] == "create_child":
                        target.mkdir(exist_ok=False)
                        receipt["created_directories"].append(".")
                    seed = {
                        CONTEXT[0]: f"# {public['title']}\n\nAlcance y decisiones pendientes de definir por el usuario.\n".encode(),
                        CONTEXT[1]: json.dumps({"project_id": plan["workspace_id"], "state": "PREPARED", "updated_at": _utc(self.clock()), "verification": "NOT_RUN", "pending": ["Define project acceptance criteria"]}, indent=2).encode() + b"\n",
                        CONTEXT[2]: f"# Continuidad — {public['title']}\n\nCarpeta seleccionada. No se ha ejecutado ni validado un producto.\n".encode(),
                        MANIFEST: _encoded({"id": plan["workspace_id"], "root": str(target), "name": public["name"], "title": public["title"], "revision": uuid.uuid4().hex, "created_at": _utc(self.clock())}),
                    }
                    for item in public["files"]:
                        if item["action"] == "preserve":
                            continue
                        destination = target / item["path"]
                        for directory in reversed(destination.parent.relative_to(target).parents):
                            if str(directory) == ".":
                                continue
                            self._mkdir(target, directory.as_posix(), receipt)
                        self._mkdir(target, destination.parent.relative_to(target).as_posix(), receipt)
                        self._create_file(target, item["path"], seed[item["path"]])
                        receipt["created_files"].append(item["path"])
                        self._save_receipt(receipt)
                    for item in public["directories"]:
                        if item["path"] != ".":
                            self._mkdir(target, item["path"], receipt)
                    workspace = Workspace(target, target.parent)
                    info = workspace.info()
                    roots = self._registry()
                    if workspace.id in roots and roots[workspace.id]["root"] != str(target):
                        raise ProjectFolderError("registry_conflict", "La identidad pertenece a otra carpeta.")
                    roots[workspace.id] = {"root": str(target), "ancestors": _ancestors(target), "manifest_sha256": _file(target / MANIFEST)[1][-1]}
                    self._save_registry(roots)
                    receipt["registry_applied"] = True
                    self._save_receipt(receipt)
                    if self.binding_identity() != plan["binding"]:
                        raise ProjectFolderError("workspace_changed", "La carpeta activa cambió durante la operación.")
                    receipt["binding_applied"] = None
                    self._save_receipt(receipt)
                    self.set_workspace_root(target)
                    if str(self.workspace_root()) != str(target):
                        raise ProjectFolderError("binding_not_confirmed", "No se pudo confirmar la carpeta activa.")
                    receipt["binding_applied"] = True
                    receipt["actual_workspace_root"] = str(self.workspace_root())
                    receipt["status"] = "APPLIED"
                    self._save_receipt(receipt)
                    return {"workspace_root": str(target), "workspace": info, "receipt": receipt}
                except Exception as error:
                    receipt["status"] = "PARTIAL_FAILED"
                    receipt["error_code"] = getattr(error, "code", "initialization_failed")
                    try:
                        receipt["actual_workspace_root"] = str(self.workspace_root())
                    except Exception:
                        receipt["actual_workspace_root"] = None
                    try:
                        self._save_receipt(receipt)
                    except OSError:
                        receipt["status"] = "INCONCLUSIVE"
                    raise ProjectFolderError("project_folder_incomplete", "La operación quedó incompleta. Revisa el recibo; no se repetirá automáticamente.", 503, receipt) from None

    @staticmethod
    def _mkdir(target, relative, receipt):
        if relative == ".":
            return
        path = target / relative
        _ancestors(path.parent)
        if path.exists() or path.is_symlink():
            _stat(path, True)
        else:
            path.mkdir(exist_ok=False)
            receipt["created_directories"].append(relative)

    def _open_registered(self, workspace_id):
        if not isinstance(workspace_id, str) or not WORKSPACE_ID.fullmatch(workspace_id):
            raise ProjectFolderError("invalid_workspace", "La identidad del proyecto no es válida.", 422)
        row = self._registry().get(workspace_id)
        if row is None:
            configured = self.legacy_parent()
            if configured:
                return WorkspaceService(Path(configured)).open(workspace_id)
            raise ProjectFolderError("workspace_not_found", "Este proyecto no está registrado.", 404)
        root = Path(row["root"])
        if _ancestors(root) != row["ancestors"] or _file(root / MANIFEST)[1][-1] != row["manifest_sha256"]:
            raise ProjectFolderError("registered_root_changed", "La identidad de la carpeta registrada ha cambiado.")
        workspace = Workspace(root, root.parent)
        if workspace.id != workspace_id:
            raise ProjectFolderError("registered_root_changed", "La identidad del proyecto ha cambiado.")
        return workspace

    def workspaces(self):
        results = {}
        configured = self.legacy_parent()
        if configured:
            for item in WorkspaceService(Path(configured)).list()["workspaces"]:
                results[item["id"]] = item
        for identity in self._registry():
            info = self._open_registered(identity).info()
            if identity in results and results[identity]["root"] != info["root"]:
                raise ProjectFolderError("registry_conflict", "La identidad aparece en dos carpetas.")
            results[identity] = info
        return {"workspaces": list(results.values())}

    def active_project(self):
        """Return the registered project identity for the bound folder, if any."""
        root = Path(self.workspace_root()).resolve()
        for identity, record in self._registry().items():
            if Path(record["root"]).resolve() == root:
                item = self._open_registered(identity).info()
                return {"project_id": item["id"], "name": item["name"], "title": item["title"],
                        "root": str(root), "scope": "project"}
        if self.legacy_parent():
            try:
                manifest = json.loads(_file(root / MANIFEST)[0].decode("utf-8"))
                identity = manifest.get("id")
                if WORKSPACE_ID.fullmatch(identity or "") and Path(manifest.get("root", "")).resolve() == root:
                    item = self._open_registered(identity).info()
                    return {"project_id": item["id"], "name": item["name"], "title": item["title"],
                            "root": str(root), "scope": "project"}
            except (OSError, ValueError, TypeError, UnicodeError, ProjectFolderError, ServiceError):
                pass
        return {"project_id": None, "name": root.name, "title": root.name,
                "root": str(root), "scope": "unregistered_workspace"}

    def action(self, workspace_id, body):
        owner = self
        class OwnedAdapter:
            def open(self, identity):
                return owner._open_registered(identity)
        return API(OwnedAdapter()).dispatch("POST", f"/api/workspaces/v1/workspaces/{workspace_id}/actions", body)
