"""Bounded, read-only runtime metadata and process-local ASGI activity."""
from __future__ import annotations

import asyncio
from collections import OrderedDict
from copy import deepcopy
from datetime import datetime, timezone
import inspect
import json
import os
from pathlib import Path
import re
import stat
import threading
import time

from fastapi import APIRouter
from fastapi.responses import JSONResponse

JSON_LIMIT = 256 * 1024
MODEL = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:/-]{0,127}\Z")
LABELS = {"ollama-cloud": "Ollama", "codex": "OpenAI Codex", "openai-platform": "OpenAI Platform", "github-copilot": "GitHub Copilot"}
MODES = {"ollama-cloud": {"api_key", "local_cli"}, "codex": {"codex_cli"}, "openai-platform": {"api_key"}, "github-copilot": {"copilot_cli", "token"}}
PROVIDER_STATES = {"ready", "configured_unverified", "not_configured", "needs_authentication", "error", "unsupported_runtime"}


def utc_now():
    return datetime.now(timezone.utc).isoformat()


class MetadataError(ValueError):
    pass


class ActivityTracker:
    """Only requests executing through one process' installed ASGI middleware."""
    def __init__(self):
        self._lock, self._active = threading.Lock(), 0

    def begin(self):
        with self._lock:
            self._active += 1

    def end(self):
        with self._lock:
            self._active -= 1

    def snapshot(self):
        with self._lock:
            count = self._active
        return {"state": "active" if count else "idle", "active_requests": count,
                "scope": "current_process_http_api_requests", "background_activity": "not_observed"}


class RuntimeActivityMiddleware:
    def __init__(self, app, *, tracker):
        self.app, self.tracker = app, tracker

    async def __call__(self, scope, receive, send):
        path = scope.get("path", "").rstrip("/")
        tracked = scope.get("type") == "http" and path.startswith("/api/") and path not in {"/api/runtime/status", "/api/health"}
        if not tracked:
            return await self.app(scope, receive, send)
        self.tracker.begin()
        try:
            await self.app(scope, receive, send)
        finally:
            self.tracker.end()


def _read_json(path):
    """Fixed metadata files only. No constructors, keyring, imports or recovery."""
    if path is None:
        return None
    path = Path(path)
    try:
        before = path.lstat()
    except FileNotFoundError:
        return None
    if (not stat.S_ISREG(before.st_mode) or before.st_nlink != 1 or before.st_size > JSON_LIMIT
            or getattr(before, "st_file_attributes", 0) & 0x400):
        raise MetadataError("metadata_file_invalid")
    with os.fdopen(os.open(path, os.O_RDONLY | getattr(os, "O_BINARY", 0) | getattr(os, "O_NOFOLLOW", 0)), "rb") as stream:
        opened = os.fstat(stream.fileno())
        raw = stream.read(JSON_LIMIT + 1)
    after = path.lstat()
    identity = lambda item: (item.st_dev, item.st_ino, item.st_size, item.st_mtime_ns)
    if len(raw) > JSON_LIMIT or identity(before) != identity(opened) or identity(opened) != identity(after):
        raise MetadataError("metadata_changed")
    value = json.loads(raw.decode("utf-8"))
    if not isinstance(value, dict):
        raise MetadataError("metadata_object_required")
    return value


def _model(value):
    return value if isinstance(value, str) and MODEL.fullmatch(value) and "://" not in value else None


class ProviderSelectionMetadata:
    """Pure projection of persisted registration, never provider availability."""
    def __init__(self, *, selection_path, policy_path, registry_path, ollama_path, runtime_mode="host"):
        self.selection_path, self.policy_path = selection_path, policy_path
        self.registry_path, self.ollama_path, self.runtime_mode = registry_path, ollama_path, runtime_mode

    def __call__(self):
        policy = _read_json(self.policy_path)
        if policy is not None:
            main, models = policy.get("main_chat"), policy.get("models")
            if not isinstance(models, list) or len(models) > 500:
                raise MetadataError("invalid_policy")
            if not isinstance(main, str) or main.count("|") != 1:
                return {"state": "not_configured", "provider_id": None, "model_id": None}
            provider, model = main.split("|", 1)
            eligible = any(isinstance(item, dict) and item.get("provider_id") == provider and item.get("model_id") == model
                           and item.get("orchestrator", item.get("chat")) is True for item in models)
            if not eligible:
                return {"state": "not_configured", "provider_id": None, "model_id": None}
        else:
            selection = _read_json(self.selection_path) or {}
            provider, model = selection.get("provider_id", "ollama-cloud"), selection.get("model_id")
        if provider not in LABELS:
            raise MetadataError("provider_not_integrated")
        if provider == "ollama-cloud":
            registration = _read_json(self.ollama_path) or {}
        else:
            registry = _read_json(self.registry_path) or {}
            providers = registry.get("providers", {})
            if not isinstance(providers, dict):
                raise MetadataError("invalid_registry")
            registration = providers.get(provider, {})
        if not isinstance(registration, dict):
            raise MetadataError("invalid_registration")
        model = _model(model or registration.get("model_id"))
        state = "not_configured"
        selection_matches = policy is not None or model == registration.get("model_id")
        if model and selection_matches and registration.get("auth_mode") in MODES[provider]:
            state = "configured_unverified"
            # This is historical registration evidence, never a new probe.
            if provider != "ollama-cloud" and registration.get("model_id") == model and registration.get("last_verified_model_id") == model:
                state = "ready"
            elif registration.get("last_error_state") == "needs_authentication":
                state = "needs_authentication"
        if provider == "ollama-cloud" and self.runtime_mode == "container":
            state = "unsupported_runtime"
        return {"state": state, "provider_id": provider, "model_id": model}


class GitMetadata:
    """Local metadata only; root-keyed TTL cache and bounded subprocess output."""
    def __init__(self, *, executable="git", ttl=5.0, timeout=1.0, clock=time.monotonic, wall_clock=utc_now):
        self.executable, self.ttl = executable, max(0.0, min(float(ttl), 30.0))
        self.timeout, self.clock, self.wall_clock = min(max(float(timeout), 0.01), 1.0), clock, wall_clock
        self._cache, self._lock = OrderedDict(), asyncio.Lock()

    async def _run(self, root, arguments, *, capture=True):
        env = {key: value for key, value in os.environ.items() if not key.startswith("GIT_")}
        env.update(GIT_OPTIONAL_LOCKS="0", GIT_TERMINAL_PROMPT="0", GIT_CONFIG_NOSYSTEM="1",
                   GIT_CONFIG_GLOBAL=os.devnull, GIT_CEILING_DIRECTORIES=str(root.parent))
        process = None
        try:
            async with asyncio.timeout(self.timeout):
                process = await asyncio.create_subprocess_exec(self.executable, "--no-optional-locks", "--no-pager", "-C", str(root),
                    *arguments, stdin=asyncio.subprocess.DEVNULL,
                    stdout=asyncio.subprocess.PIPE if capture else asyncio.subprocess.DEVNULL,
                    stderr=asyncio.subprocess.DEVNULL, env=env, limit=4096,
                    **({"creationflags": 0x08000000} if os.name == "nt" else {}))
                output = bytearray()
                if capture:
                    while True:
                        chunk = await process.stdout.read(4097 - len(output))
                        output.extend(chunk)
                        if len(output) > 4096:
                            raise MetadataError("git_output_limit")
                        if not chunk:
                            break
                code = await process.wait()
                return code, bytes(output)
        finally:
            if process is not None and process.returncode is None:
                try:
                    process.kill()
                except ProcessLookupError:
                    pass
                await process.wait()

    async def _probe(self, root):
        result = {"state": "not_repository", "repo_detected": False, "branch": None, "detached": None,
                  "remote_configured": None, "remote_verification": "not_checked", "error_code": None}
        try:
            if not root.is_absolute():
                raise MetadataError("invalid_root")
            details = root.lstat()
            if (not stat.S_ISDIR(details.st_mode) or stat.S_ISLNK(details.st_mode)
                    or getattr(details, "st_file_attributes", 0) & 0x400):
                raise MetadataError("invalid_root")
        except FileNotFoundError:
            raise MetadataError("root_unavailable") from None
        try:
            marker = (root / ".git").lstat()
        except FileNotFoundError:
            return result
        if (stat.S_ISLNK(marker.st_mode) or getattr(marker, "st_file_attributes", 0) & 0x400
                or not (stat.S_ISDIR(marker.st_mode) or stat.S_ISREG(marker.st_mode))):
            raise MetadataError("git_marker_invalid")
        code, raw = await self._run(root, ["rev-parse", "--show-toplevel"])
        if code or os.path.normcase(os.path.abspath(raw.decode("utf-8").strip())) != os.path.normcase(os.path.abspath(root)):
            raise MetadataError("git_root_unverified")
        result.update(state="repository", repo_detected=True)
        code, raw = await self._run(root, ["symbolic-ref", "--quiet", "--short", "HEAD"])
        if code == 0:
            branch = raw.decode("utf-8").strip()
            if not branch or len(branch) > 256 or any(ord(character) < 32 for character in branch):
                raise MetadataError("git_branch_invalid")
            result.update(branch=branch, detached=False)
        elif code == 1:
            result["detached"] = True
        else:
            raise MetadataError("git_branch_unavailable")
        # The URL is discarded by the OS; it never enters Python or the response.
        code, _ = await self._run(root, ["config", "--local", "--no-includes", "--get", "remote.origin.url"], capture=False)
        if code not in (0, 1):
            raise MetadataError("git_remote_metadata_unavailable")
        result["remote_configured"] = code == 0
        return result

    async def status(self, root):
        root = Path(root)
        key = os.path.normcase(os.path.abspath(root))
        async with self._lock:
            cached = self._cache.get(key)
            if cached is not None and self.clock() < cached[0]:
                return {**deepcopy(cached[1]), "cached": True}
            checked_at = self.wall_clock()
            try:
                result = await self._probe(root)
            except Exception:
                result = {"state": "unavailable", "repo_detected": None, "branch": None, "detached": None,
                          "remote_configured": None, "remote_verification": "not_checked", "error_code": "git_metadata_unavailable"}
            result.update(checked_at=checked_at, cached=False, cache_ttl_seconds=self.ttl)
            self._cache[key] = (self.clock() + self.ttl, deepcopy(result))
            self._cache.move_to_end(key)
            while len(self._cache) > 8:
                self._cache.popitem(last=False)
            return result


async def _callback(function):
    result = function() if inspect.iscoroutinefunction(function) else await asyncio.to_thread(function)
    return await result if inspect.isawaitable(result) else result


class RuntimeStatus:
    def __init__(self, *, workspace_root, context_metadata, provider_selection, tracker, git=None, callback_timeout=1.0):
        self.workspace_root, self.context_metadata, self.provider_selection = workspace_root, context_metadata, provider_selection
        self.tracker, self.git, self.callback_timeout = tracker, git or GitMetadata(), callback_timeout

    async def _memory(self):
        try:
            context = await asyncio.wait_for(_callback(self.context_metadata), self.callback_timeout)
            memory = context["memory"]
            if memory["kind"] != "conversation_history" or memory["state"] not in {"present", "absent"}:
                raise MetadataError("unknown_memory")
            return {"state": "available", "history": {"kind": "conversation_history", "state": memory["state"], "proof": "metadata_presence_only"},
                    "general": {"state": "disconnected"}, "checked_at": utc_now(), "error_code": None}
        except Exception:
            return {"state": "unavailable", "history": {"kind": "conversation_history", "state": "unknown"},
                    "general": {"state": "not_observed"}, "checked_at": utc_now(), "error_code": "memory_metadata_unavailable"}

    async def _provider(self):
        try:
            selection = await asyncio.wait_for(_callback(self.provider_selection), self.callback_timeout)
            state, provider = selection["state"], selection.get("provider_id")
            if state not in PROVIDER_STATES or provider is not None and provider not in LABELS:
                raise MetadataError("unknown_provider")
            model = _model(selection.get("model_id"))
            if state in {"ready", "configured_unverified"} and (provider is None or model is None):
                raise MetadataError("invalid_selected_model")
            return {"state": state, "label": LABELS.get(provider), "model": model,
                    "observation": "registration_metadata", "response_verified": False,
                    "checked_at": utc_now(), "error_code": None}
        except Exception:
            return {"state": "unavailable", "label": None, "model": None, "observation": "registration_metadata",
                    "response_verified": False, "checked_at": utc_now(), "error_code": "provider_metadata_unavailable"}

    async def _git(self):
        try:
            root = await asyncio.wait_for(_callback(self.workspace_root), self.callback_timeout)
            return await self.git.status(root)
        except Exception:
            return {"state": "unavailable", "repo_detected": None, "branch": None, "detached": None,
                    "remote_configured": None, "remote_verification": "not_checked", "error_code": "git_metadata_unavailable",
                    "checked_at": utc_now(), "cached": False, "cache_ttl_seconds": self.git.ttl}

    async def snapshot(self):
        memory, provider, git = await asyncio.gather(self._memory(), self._provider(), self._git())
        return {"schema": "runtime-status.v1", "checked_at": utc_now(), "backend": {"responding": True},
                "activity": self.tracker.snapshot(), "memory": memory, "provider": provider, "git": git}


def create_runtime_status_router(service):
    router = APIRouter()

    @router.get("/api/runtime/status")
    async def runtime_status():
        return JSONResponse(await service.snapshot(), headers={"Cache-Control": "no-store"})

    return router
