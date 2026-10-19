"""Verified, explicit-lifecycle client for the bundled BAGO Embedded Runtime.

Constructing a client is inert. The caller must invoke ``start`` before making
requests and must obtain human approval before calling ``approve``.
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import secrets
import shutil
import subprocess
import sys
import tempfile
import threading
from typing import Any
import zipfile

from .compatibility import legacy_compatible_operation


BER_VERSION = "0.1.0"
PROTOCOL_VERSION = "bago.ber.ipc/v1"
SOURCE_COMMIT = "5fb6f2f0c57f29de1b42bbb2efb4a57c86aa032d"
ARTIFACT_SHA256 = "da7960e83bd7dd8b16c7518e8019d52280b381bdf2f2fd4eb71cd74d38650f22"
MAX_RESPONSE_BYTES = 1_048_576


class BerRuntimeError(RuntimeError):
    """A startup, protocol, or BAGO runtime error with stable code."""

    def __init__(self, message: str, *, code: str = "ber_client_error") -> None:
        super().__init__(message)
        self.code = code


class BerClient:
    """Own one private stdio BER child process and its extracted package."""

    def __init__(
        self,
        *,
        workspace: str | os.PathLike[str],
        artifact: str | os.PathLike[str] | None = None,
        lockfile: str | os.PathLike[str] | None = None,
        python: str | os.PathLike[str] | None = None,
        request_timeout: float = 15.0,
    ) -> None:
        repo_root = Path(__file__).resolve().parents[3]
        bundle_dir = repo_root / "runtime" / "ber"
        self.artifact = Path(artifact or bundle_dir / f"bago-embedded-runtime-{BER_VERSION}.zip").resolve()
        self.lockfile = Path(lockfile or bundle_dir / "BER.lock.json").resolve()
        self.workspace = Path(workspace).expanduser().resolve(strict=True)
        if not self.workspace.is_dir():
            raise ValueError("workspace must be an existing directory")
        self.python = str(python or sys.executable)
        self.request_timeout = max(0.1, float(request_timeout))
        self._process: subprocess.Popen[str] | None = None
        self._temp: tempfile.TemporaryDirectory[str] | None = None
        self._backend: Path | None = None
        self._state_root: Path | None = None
        self._lock = threading.RLock()
        self._sequence = 0
        self._identity: dict[str, Any] | None = None

    @property
    def running(self) -> bool:
        return self._process is not None and self._process.poll() is None

    def _read_and_verify_bundle(self) -> tuple[dict[str, Any], Path]:
        try:
            identity = json.loads(self.lockfile.read_text(encoding="utf-8"))
            artifact_bytes = self.artifact.read_bytes()
        except (OSError, json.JSONDecodeError) as exc:
            raise BerRuntimeError(f"BER package or lockfile is unavailable: {exc}", code="ber_package_unavailable") from exc
        digest = hashlib.sha256(artifact_bytes).hexdigest()
        if digest != ARTIFACT_SHA256 or identity.get("artifact_sha256") != ARTIFACT_SHA256 or digest != identity.get("artifact_sha256"):
            raise BerRuntimeError("BER package does not match the ADL pinned SHA-256", code="ber_package_integrity_failed")
        if identity.get("ber_version") != BER_VERSION or identity.get("source_commit") != SOURCE_COMMIT or identity.get("protocol_version") != PROTOCOL_VERSION:
            raise BerRuntimeError("BER package identity is not supported by this ADL client", code="ber_package_identity_mismatch")
        source_hashes = identity.get("source_files_sha256")
        if not isinstance(source_hashes, dict) or not source_hashes:
            raise BerRuntimeError("BER source manifest is missing", code="ber_package_manifest_invalid")
        self._temp = tempfile.TemporaryDirectory(prefix="adl-ber-")
        package_root = Path(self._temp.name).resolve()
        try:
            with zipfile.ZipFile(self.artifact) as package:
                names = set(package.namelist())
                for relative, expected_hash in source_hashes.items():
                    member = PurePosixPath(relative)
                    if member.is_absolute() or ".." in member.parts or "\\" in relative or ":" in relative or relative not in names:
                        raise BerRuntimeError("BER archive contains an invalid source path", code="ber_package_manifest_invalid")
                    if hashlib.sha256(package.read(relative)).hexdigest() != expected_hash:
                        raise BerRuntimeError(f"BER source hash mismatch: {relative}", code="ber_package_integrity_failed")
                for name in names:
                    member = PurePosixPath(name)
                    info = package.getinfo(name)
                    if member.is_absolute() or ".." in member.parts or "\\" in name or ":" in name or (info.external_attr >> 16) & 0o170000 == 0o120000:
                        raise BerRuntimeError("BER archive path escapes its extraction root", code="ber_package_manifest_invalid")
                embedded_manifest = json.loads(package.read("backend/bago_core/embedded/ber-manifest.json"))
                if embedded_manifest.get("source_files_sha256") != source_hashes or embedded_manifest.get("source_commit") != SOURCE_COMMIT or embedded_manifest.get("ber_version") != BER_VERSION:
                    raise BerRuntimeError("BER embedded manifest does not match its ADL lock", code="ber_package_manifest_invalid")
                package.extractall(package_root)
        except BerRuntimeError:
            self._temp.cleanup()
            self._temp = None
            raise
        except (OSError, zipfile.BadZipFile, KeyError, json.JSONDecodeError) as exc:
            self._temp.cleanup()
            self._temp = None
            raise BerRuntimeError(f"BER archive verification failed: {exc}", code="ber_package_integrity_failed") from exc
        backend = package_root / "backend"
        if not (backend / "bago_core" / "embedded" / "stdio_server.py").is_file():
            raise BerRuntimeError("BER entry point is missing", code="ber_package_manifest_invalid")
        self._identity = identity
        self._backend = backend
        self._state_root = package_root / "state"
        return identity, package_root

    def start(self) -> dict[str, Any]:
        """Verify the pinned package and explicitly start its private process."""
        with self._lock:
            if self.running:
                return self.status()
            identity, package_root = self._read_and_verify_bundle()
            assert self._backend is not None and self._state_root is not None
            env = dict(os.environ)
            env["PYTHONPATH"] = str(self._backend) + (os.pathsep + env["PYTHONPATH"] if env.get("PYTHONPATH") else "")
            env["PYTHONDONTWRITEBYTECODE"] = "1"
            env["BAGO_BER_ARTIFACT_SHA256"] = identity["artifact_sha256"]
            try:
                self._process = subprocess.Popen(
                    [self.python, "-m", "bago_core.embedded.stdio_server", "--workspace", str(self.workspace), "--state-root", str(self._state_root), "--runtime-root", str(self._backend)],
                    cwd=package_root,
                    env=env,
                    stdin=subprocess.PIPE,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    encoding="utf-8",
                    bufsize=1,
                )
            except OSError as exc:
                self.close()
                raise BerRuntimeError(f"Could not start BER: {exc}", code="ber_start_failed") from exc
            try:
                return self._request("health")
            except Exception:
                self.close()
                raise

    def _request(self, action: str, **payload: Any) -> dict[str, Any]:
        with self._lock:
            process = self._process
            if process is None or process.poll() is not None or process.stdin is None or process.stdout is None:
                raise BerRuntimeError("BER is not running", code="ber_not_running")
            self._sequence += 1
            request_id = f"adl-ber-{self._sequence}-{secrets.token_hex(4)}"
            message = {"protocol_version": PROTOCOL_VERSION, "request_id": request_id, "action": action, **payload}
            encoded = json.dumps(message, ensure_ascii=False, separators=(",", ":"))
            try:
                process.stdin.write(encoded + "\n")
                process.stdin.flush()
            except (OSError, BrokenPipeError) as exc:
                raise BerRuntimeError(f"BER IPC failed: {exc}", code="ber_ipc_failed") from exc
            read_done = threading.Event()
            read_result: list[str | BaseException] = []

            def read_response() -> None:
                try:
                    read_result.append(process.stdout.readline(MAX_RESPONSE_BYTES + 2))
                except BaseException as exc:  # pass the pipe error to this caller
                    read_result.append(exc)
                finally:
                    read_done.set()

            threading.Thread(target=read_response, name="adl-ber-ipc-reader", daemon=True).start()
            if not read_done.wait(self.request_timeout):
                process.kill()
                raise BerRuntimeError("BER response timed out; its private process was stopped", code="ber_ipc_timeout")
            if not read_result or isinstance(read_result[0], BaseException):
                raise BerRuntimeError(f"BER IPC failed: {read_result[0] if read_result else 'empty response'}", code="ber_ipc_failed")
            response_line = read_result[0]
        if not response_line or len(response_line.encode("utf-8")) > MAX_RESPONSE_BYTES or not response_line.endswith("\n"):
            raise BerRuntimeError("BER returned an empty or oversized response", code="ber_protocol_response_invalid")
        try:
            response = json.loads(response_line)
        except json.JSONDecodeError as exc:
            raise BerRuntimeError("BER returned invalid JSON", code="ber_protocol_response_invalid") from exc
        if response.get("protocol_version") != PROTOCOL_VERSION or response.get("request_id") != request_id:
            raise BerRuntimeError("BER response identity does not match the request", code="ber_protocol_response_mismatch")
        if response.get("ok") is not True:
            error = response.get("error") if isinstance(response.get("error"), dict) else {}
            raise BerRuntimeError(str(error.get("message") or "BER rejected the request"), code=str(error.get("code") or "ber_request_denied"))
        result = response.get("result")
        if not isinstance(result, dict):
            raise BerRuntimeError("BER result must be a JSON object", code="ber_protocol_response_invalid")
        return result

    def status(self) -> dict[str, Any]:
        return self._request("health")

    def prepare(self, operation: dict[str, Any]) -> dict[str, Any]:
        return self._request("prepare", operation=operation)

    def prepare_legacy_compatible(self, operation: dict[str, Any]) -> dict[str, Any]:
        """Prepare an existing ADL effect using its legacy text semantics."""
        return self.prepare(legacy_compatible_operation(operation))

    def approve(self, challenge_id: str, *, channel: str = "desktop") -> dict[str, Any]:
        if channel not in {"desktop", "ui-react"}:
            raise ValueError("unsupported BER approval channel")
        return self._request("approve", challenge_id=challenge_id, channel=channel)

    def execute(self, challenge_id: str) -> dict[str, Any]:
        return self._request("execute", challenge_id=challenge_id)

    def close(self) -> None:
        """Gracefully stop the child and remove its temporary package copy."""
        with self._lock:
            process = self._process
            self._process = None
            if process is not None:
                if process.poll() is None and process.stdin is not None:
                    try:
                        self._sequence += 1
                        request_id = f"adl-ber-stop-{self._sequence}"
                        message = {"protocol_version": PROTOCOL_VERSION, "request_id": request_id, "action": "shutdown"}
                        process.stdin.write(json.dumps(message, separators=(",", ":")) + "\n")
                        process.stdin.flush()
                        if process.stdout is not None:
                            process.stdout.readline(MAX_RESPONSE_BYTES + 2)
                    except (OSError, BrokenPipeError):
                        pass
                try:
                    process.wait(timeout=self.request_timeout)
                except subprocess.TimeoutExpired:
                    process.terminate()
                    try:
                        process.wait(timeout=2)
                    except subprocess.TimeoutExpired:
                        process.kill()
                        process.wait(timeout=2)
                for stream in (process.stdin, process.stdout, process.stderr):
                    if stream is not None:
                        stream.close()
            if self._temp is not None:
                self._temp.cleanup()
                self._temp = None
            self._backend = None
            self._state_root = None

    def __enter__(self) -> "BerClient":
        self.start()
        return self

    def __exit__(self, *_exc: object) -> None:
        self.close()


__all__ = ["BerClient", "BerRuntimeError", "BER_VERSION", "PROTOCOL_VERSION", "SOURCE_COMMIT", "ARTIFACT_SHA256"]
