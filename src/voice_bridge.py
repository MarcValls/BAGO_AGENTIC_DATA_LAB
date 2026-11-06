"""Bounded loopback bridge to the separate local Kokoro voice project."""
from __future__ import annotations

import atexit
import json
import http.client
import os
import socket
import struct
import subprocess
import threading
import time
from pathlib import Path

from src.storage.portable import data_path
from src.voice_windows_job import OwnedVoiceJob


MAX_AUDIO_BYTES = 12 * 1024 * 1024
DEFAULT_PORT = 8766
VOICE_CONFIG = data_path("voice", "integration.json")
VOICE_TOKEN = data_path("voice", "receiver.token")


class VoiceBridgeError(RuntimeError):
    def __init__(self, code: str, status: int = 503):
        super().__init__(code)
        self.code = code
        self.status = status


class VoiceBridge:
    """Starts only its own configured voice process and never adopts/kills strangers."""

    def __init__(self, config_path: Path = VOICE_CONFIG, token_path: Path = VOICE_TOKEN):
        self.config_path = config_path
        self.token_path = token_path
        self._lock = threading.RLock()
        self._process: subprocess.Popen | None = None
        self._job: OwnedVoiceJob | None = None
        self._root: Path | None = None
        self._python: Path | None = None
        self._script: Path | None = None
        self._port = DEFAULT_PORT
        self._config_error: VoiceBridgeError | None = None
        try:
            self._load_config()
        except VoiceBridgeError as exc:
            # Voice configuration must fail closed for voice routes without
            # preventing the unrelated ADL application from starting.
            self._config_error = exc
        atexit.register(self.close)

    def _load_config(self) -> None:
        try:
            config = json.loads(self.config_path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            return
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            raise VoiceBridgeError("voice_config_invalid", 503) from exc
        if not isinstance(config, dict) or config.get("schema") != "bago.voice.integration.v1":
            raise VoiceBridgeError("voice_config_invalid", 503)
        root_value = config.get("project_root")
        port = config.get("port", DEFAULT_PORT)
        if not isinstance(root_value, str) or not root_value or not Path(root_value).is_absolute():
            raise VoiceBridgeError("voice_config_invalid", 503)
        if isinstance(port, bool) or not isinstance(port, int) or not 1024 <= port <= 65535:
            raise VoiceBridgeError("voice_config_invalid", 503)
        root = Path(root_value).resolve(strict=False)
        python = root / ".venv" / "Scripts" / "python.exe"
        script = root / "voz_local.py"
        self._root, self._python, self._script, self._port = root, python, script, port

    def _ensure_config_valid(self) -> None:
        if self._config_error is not None:
            raise VoiceBridgeError(self._config_error.code, self._config_error.status)

    @property
    def configured(self) -> bool:
        return bool(self._root and self._python and self._python.is_file() and self._script and self._script.is_file())

    def _base(self) -> str:
        self._ensure_config_valid()
        if not self.configured:
            raise VoiceBridgeError("voice_runtime_unavailable", 503)
        return f"http://127.0.0.1:{self._port}"

    def _owned_http(self, method: str, path: str, body: bytes | None = None, headers: dict | None = None, timeout: float = 4) -> dict:
        connection = http.client.HTTPConnection("127.0.0.1", self._port, timeout=timeout)
        try:
            connection.connect()
            peer = connection.sock
            job = self._job
            if peer is None or job is None or not job.owns_connection(peer):
                raise VoiceBridgeError("voice_peer_unverified", 503)
            # No reconnection: the checked socket is the one used for the request.
            connection.auto_open = 0
            connection.request(method, path, body=body, headers=headers or {})
            response = connection.getresponse()
            if response.status >= 400:
                code = {401: "voice_token_rejected", 404: "voice_request_not_found", 413: "voice_audio_too_large", 415: "voice_audio_format_unsupported", 422: "voice_request_invalid", 429: "voice_busy"}.get(response.status, "voice_request_failed")
                raise VoiceBridgeError(code, 503 if response.status >= 500 else response.status)
            raw = response.read(32769)
            if len(raw) > 32768:
                raise VoiceBridgeError("voice_response_invalid", 502)
            result = json.loads(raw.decode("utf-8"))
            if not isinstance(result, dict):
                raise VoiceBridgeError("voice_response_invalid", 502)
            return result
        except VoiceBridgeError:
            raise
        except (OSError, http.client.HTTPException, ValueError, UnicodeError) as exc:
            raise VoiceBridgeError("voice_request_failed", 503) from exc
        finally:
            connection.close()

    def _health(self) -> dict | None:
        process = self._process
        if process is None or process.poll() is not None or self._job is None:
            return None
        try:
            payload = self._owned_http("GET", "/health", timeout=1.0)
        except VoiceBridgeError:
            return None
        return payload if payload.get("app") == "Voz Local Receptor" else None

    @staticmethod
    def _listener_process_ids(port: int) -> set[int] | None:
        """Return PIDs listening on an IPv4 port, or None when identity is unavailable."""
        if os.name != "nt":
            return None
        try:
            import ctypes
            from ctypes import wintypes

            get_table = ctypes.WinDLL("iphlpapi").GetExtendedTcpTable
            get_table.argtypes = [ctypes.c_void_p, ctypes.POINTER(wintypes.ULONG), wintypes.BOOL,
                                  wintypes.ULONG, wintypes.ULONG, wintypes.ULONG]
            get_table.restype = wintypes.ULONG
            size = wintypes.ULONG(0)
            # AF_INET, TCP_TABLE_OWNER_PID_LISTENER, ERROR_INSUFFICIENT_BUFFER
            result = get_table(None, ctypes.byref(size), False, 2, 3, 0)
            if result not in (0, 122) or size.value < 4:
                return None
            table = ctypes.create_string_buffer(size.value)
            result = get_table(table, ctypes.byref(size), False, 2, 3, 0)
            if result != 0:
                return None
            count = struct.unpack_from("<I", table.raw, 0)[0]
            owners: set[int] = set()
            for index in range(count):
                offset = 4 + index * 24
                state, _, local_port, _, _, pid = struct.unpack_from("<IIIIII", table.raw, offset)
                if state == 2 and socket.ntohs(local_port & 0xFFFF) == port:
                    owners.add(pid)
            return owners
        except (AttributeError, OSError, ValueError, struct.error):
            return None

    def _port_has_listener(self) -> bool:
        try:
            with socket.create_connection(("127.0.0.1", self._port), timeout=0.2):
                return True
        except OSError:
            return False

    def status(self) -> dict:
        self._ensure_config_valid()
        ready = self._health()
        if ready:
            return {"configured": True, "available": self.token_path.is_file(), "state": "READY" if self.token_path.is_file() else "TOKEN_MISSING", "version": ready.get("version"), "port": self._port}
        process = self._process
        if process is not None and process.poll() is None:
            return {"configured": self.configured, "available": False, "state": "STARTING", "port": self._port}
        if self._port_has_listener():
            return {"configured": self.configured, "available": False, "state": "PORT_IN_USE", "port": self._port}
        return {"configured": self.configured, "available": False, "state": "STOPPED" if self.configured else "UNCONFIGURED", "port": self._port}

    def _ensure_ready(self) -> str:
        self._ensure_config_valid()
        with self._lock:
            if self._health():
                try:
                    token = self.token_path.read_text(encoding="utf-8").strip()
                except OSError as exc:
                    raise VoiceBridgeError("voice_token_unavailable", 503) from exc
                if len(token) < 32:
                    raise VoiceBridgeError("voice_token_invalid", 503)
                return token
            if not self.configured or not self._python or not self._script or not self._root:
                raise VoiceBridgeError("voice_runtime_unavailable", 503)
            process = self._process
            if process is None or process.poll() is not None:
                if self._port_has_listener():
                    raise VoiceBridgeError("voice_port_in_use", 409)
                self.token_path.parent.mkdir(parents=True, exist_ok=True)
                env = os.environ.copy()
                if self._job is not None:
                    if not self._job.terminate() or not self._job.is_empty() or not self._job.close():
                        raise VoiceBridgeError("voice_cleanup_failed", 503)
                    self._job = None
                try:
                    job = OwnedVoiceJob()
                    self._job = job
                    self._process = job.launch(
                        [str(self._python), str(self._script), "servidor", "--puerto", str(self._port), "--token-file", str(self.token_path)],
                        cwd=str(self._root), env=env,
                    )
                except OSError as exc:
                    if self._job is not None:
                        if self._job.terminate() and self._job.is_empty() and self._job.close():
                            self._job = None
                        else:
                            raise VoiceBridgeError("voice_cleanup_failed", 503) from exc
                    raise VoiceBridgeError("voice_process_start_failed", 503) from exc
            deadline = time.monotonic() + 12
            while time.monotonic() < deadline:
                if self._health():
                    try:
                        token = self.token_path.read_text(encoding="utf-8").strip()
                    except OSError:
                        time.sleep(0.1)
                        continue
                    if len(token) >= 32:
                        return token
                if self._process.poll() is not None:
                    raise VoiceBridgeError("voice_process_start_failed", 503)
                time.sleep(0.1)
            raise VoiceBridgeError("voice_start_timeout", 503)

    def _request(self, path: str, body: bytes, content_type: str) -> dict:
        token = self._ensure_ready()
        return self._owned_http("POST", path, body, {"Content-Type": content_type, "X-Voz-Token": token}, timeout=180)

    def speak(self, text: str, voice: str = "alex", speed: float = 0.95) -> dict:
        try:
            payload = json.dumps({"text": text, "voice": voice, "speed": speed}, ensure_ascii=False).encode("utf-8")
        except UnicodeEncodeError as exc:
            raise VoiceBridgeError("voice_request_invalid", 422) from exc
        return self._request("/speak", payload, "application/json; charset=utf-8")

    def transcribe(self, audio: bytes, content_type: str) -> dict:
        if not audio or len(audio) > MAX_AUDIO_BYTES:
            raise VoiceBridgeError("voice_audio_too_large" if audio else "voice_audio_empty", 413 if audio else 400)
        return self._request("/transcribe", audio, content_type)

    def request_status(self, request_id: str) -> dict:
        if len(request_id) != 32 or any(ch not in "0123456789abcdef" for ch in request_id):
            raise VoiceBridgeError("voice_request_not_found", 404)
        token = self._ensure_ready()
        return self._owned_http("GET", f"/status/{request_id}", headers={"X-Voz-Token": token})

    def close(self) -> bool:
        with self._lock:
            job, process = self._job, self._process
            if job is None:
                return True
            # Terminate the entire owned tree even if the wrapper has exited.
            terminated = job.terminate()
            if process is not None:
                try:
                    process.wait(timeout=5)
                except (OSError, subprocess.TimeoutExpired):
                    pass
            exited = process is None or process.poll() is not None
            if terminated and exited and job.is_empty() and job.close():
                self._job = None
                self._process = None
                return True
            return False
