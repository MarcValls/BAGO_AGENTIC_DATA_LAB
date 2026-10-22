"""Loopback-only bridge to the repository's bounded live OpenMetadata check."""
from __future__ import annotations

import ipaddress
import os
import subprocess
import sys
import uuid
from pathlib import Path
from urllib.request import urlopen
from urllib.parse import urlsplit


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "run_l8_openmetadata_live_validation.py"


class OpenMetadataRuntimeError(ValueError):
    pass


def _loopback_url(name: str, default: str) -> str:
    value = os.environ.get(name, default).strip()
    try:
        parsed = urlsplit(value)
        host = parsed.hostname
        if parsed.scheme not in {"http", "https"} or not host or parsed.username or parsed.password:
            raise ValueError
        try:
            allowed = ipaddress.ip_address(host).is_loopback
        except ValueError:
            allowed = host.lower() == "localhost"
        if not allowed:
            raise ValueError
        return value.rstrip("/")
    except (ValueError, TypeError):
        raise OpenMetadataRuntimeError("OpenMetadata endpoint must use a loopback URL.") from None


def configured_urls() -> tuple[str, str]:
    return (
        _loopback_url("OPENMETADATA_BASE_URL", "http://localhost:8585/api"),
        _loopback_url("OPENMETADATA_HEALTH_URL", "http://localhost:8586/healthcheck"),
    )


def status() -> dict:
    try:
        _, health_url = configured_urls()
    except OpenMetadataRuntimeError:
        return {"state": "unavailable", "configured": False, "healthy": False, "service_kind": "local_openmetadata"}
    try:
        with urlopen(health_url, timeout=2) as response:
            import json
            payload = json.loads(response.read().decode("utf-8"))
            healthy = response.status == 200 and bool(payload.get("OpenMetadataServerHealthCheck", {}).get("healthy"))
        return {"state": "healthy" if healthy else "unavailable", "configured": True, "healthy": healthy, "service_kind": "local_openmetadata"}
    except Exception:
        return {"state": "unavailable", "configured": True, "healthy": False, "service_kind": "local_openmetadata"}


def run_live_validation() -> dict:
    api_url, health_url = configured_urls()  # Preflight before importing/calling transport code.
    if not os.environ.get("OPENMETADATA_USERNAME") or not os.environ.get("OPENMETADATA_PASSWORD"):
        raise OpenMetadataRuntimeError("Local OpenMetadata credentials are not configured in the process environment.")
    env = os.environ.copy()
    env["OPENMETADATA_BASE_URL"] = api_url
    env["OPENMETADATA_HEALTH_URL"] = health_url
    try:
        completed = subprocess.run(
            [sys.executable, str(SCRIPT), "--check"], cwd=ROOT, env=env,
            capture_output=True, text=True, timeout=900, check=False,
        )
        # --check JSON is produced by the canonical runner; stderr is intentionally discarded.
        line = next((line for line in reversed(completed.stdout.splitlines()) if line.lstrip().startswith("{")), None)
        if line is None:
            raise OpenMetadataRuntimeError("Local OpenMetadata validation did not return a result.")
        import json
        result = json.loads(line)
    except (OSError, subprocess.TimeoutExpired, ValueError):
        raise OpenMetadataRuntimeError("Local OpenMetadata validation could not be completed safely.") from None
    cleanup = result.get("cleanup_status", "NOT_RUN")
    status_value = "PASS" if result.get("status") == "PASS" and cleanup == "PASS" else "FAIL"
    # Explicit allowlist: never forward exception strings, arbitrary server data or credentials.
    checks = [{"name": str(c.get("name", ""))[:100], "status": c.get("status") if c.get("status") in {"PASS", "FAIL"} else "FAIL", "detail": str(c.get("detail", ""))[:240]} for c in result.get("checks", [])]
    receipts = [{key: row.get(key) for key in ("label", "receipt_id", "operation", "decision", "outcome", "result_count", "error_kind", "path")} for row in result.get("receipts", [])]
    return {
        "run_id": uuid.uuid4().hex,
        "status": status_value,
        "checks": checks,
        "receipts": receipts,
        "cleanup_requested": True,
        "cleanup_status": cleanup,
        "service_kind": "local_openmetadata",
        "error": None if status_value == "PASS" else "Live validation failed; inspect local service status and cleanup outcome.",
    }
