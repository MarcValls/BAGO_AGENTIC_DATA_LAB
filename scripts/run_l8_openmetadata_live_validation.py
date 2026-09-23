"""Run a bounded, local-only L8 validation against a real OpenMetadata server.

The script creates a uniquely named temporary catalog fixture, exercises the
governed adapter over HTTP, records receipts, and removes only the resources it
created. Credentials are read from the environment and are never written to
the evidence artifact.
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
import subprocess
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Optional
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request as URLRequest
from urllib.request import urlopen

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from adapters.openmetadata_adapter import (  # noqa: E402
    GovernedOpenMetadataAdapter,
    OpenMetadataCatalogPolicy,
    QualityRule,
)


API_BASE_URL = os.environ.get("OPENMETADATA_BASE_URL", "http://localhost:8585/api").rstrip("/")
HEALTH_URL = os.environ.get("OPENMETADATA_HEALTH_URL", "http://localhost:8586/healthcheck")
USERNAME = os.environ.get("OPENMETADATA_USERNAME", "admin@open-metadata.org")
PASSWORD = os.environ.get("OPENMETADATA_PASSWORD", "admin")
COMPOSE_VERSION = os.environ.get("OPENMETADATA_VERSION", "1.12.6")
EVIDENCE_PATH = REPO_ROOT / "evidence" / "l8_openmetadata_live.md"
COMPOSE_PATH = REPO_ROOT / "infra" / "openmetadata" / "docker-compose.yml"
ADAPTER_PATH = REPO_ROOT / "src" / "adapters" / "openmetadata_adapter.py"
HEALTH_TIMEOUT_SECONDS = float(os.environ.get("OPENMETADATA_HEALTH_TIMEOUT_SECONDS", "180"))


class LiveValidationError(RuntimeError):
    """Expected failure from the local OpenMetadata HTTP contract."""


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _git_identity() -> tuple[str, bool]:
    try:
        head = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=REPO_ROOT,
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
        status = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=REPO_ROOT,
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
        return head, bool(status)
    except (OSError, subprocess.CalledProcessError):
        return "UNAVAILABLE", True


def _redact(message: str, token: Optional[str] = None) -> str:
    clean = str(message)
    if token:
        clean = clean.replace(token, "[REDACTED]")
    return clean[:500]


def _request_json(
    method: str,
    url: str,
    *,
    token: Optional[str] = None,
    body: Any = None,
    params: Optional[Mapping[str, Any]] = None,
    timeout: float = 15.0,
) -> tuple[int, Mapping[str, Any]]:
    query = urlencode({key: value for key, value in (params or {}).items() if value is not None})
    target = f"{url}?{query}" if query else url
    payload = None if body is None else json.dumps(body, sort_keys=True).encode("utf-8")
    headers = {"Accept": "application/json"}
    if body is not None:
        headers["Content-Type"] = "application/json"
    if token:
        headers["Authorization"] = f"Bearer {token}"
    request = URLRequest(target, data=payload, method=method.upper(), headers=headers)
    try:
        with urlopen(request, timeout=timeout) as response:
            raw = response.read().decode("utf-8")
            if not raw.strip():
                return int(response.status), {}
            decoded = json.loads(raw)
            return int(response.status), decoded if isinstance(decoded, Mapping) else {"data": decoded}
    except HTTPError as error:
        message = error.read().decode("utf-8", errors="replace")[:500]
        raise LiveValidationError(f"HTTP {error.code}: {message}") from error
    except (URLError, TimeoutError) as error:
        raise LiveValidationError(str(error)) from error


def _login() -> str:
    encoded_password = base64.b64encode(PASSWORD.encode("utf-8")).decode("ascii")
    _, response = _request_json(
        "POST",
        f"{API_BASE_URL}/v1/auth/login",
        body={"email": USERNAME, "password": encoded_password},
    )
    token = response.get("accessToken")
    if not isinstance(token, str) or not token:
        raise LiveValidationError("OpenMetadata login did not return accessToken")
    return token


def _wait_for_healthy() -> Mapping[str, Any]:
    """Wait for the freshly started local server without weakening fail-closed behavior."""
    deadline = time.monotonic() + HEALTH_TIMEOUT_SECONDS
    last_error = "no health response"
    while True:
        try:
            status, health = _request_json("GET", HEALTH_URL)
            if status == 200 and health.get("OpenMetadataServerHealthCheck", {}).get("healthy"):
                return health
            last_error = f"HTTP {status}: health response is not healthy"
        except (LiveValidationError, OSError) as error:
            last_error = _redact(str(error))
        if time.monotonic() >= deadline:
            raise LiveValidationError(
                f"OpenMetadata healthcheck did not become healthy within "
                f"{HEALTH_TIMEOUT_SECONDS:g}s: {last_error}"
            )
        time.sleep(2)


def _create_entity(token: str, path: str, body: Mapping[str, Any]) -> dict[str, Any]:
    status, response = _request_json("POST", f"{API_BASE_URL}{path}", token=token, body=body)
    if status not in {200, 201}:
        raise LiveValidationError(f"unexpected create status {status} for {path}")
    return dict(response)


def _delete_entity(token: str, path: str, *, params: Optional[Mapping[str, Any]] = None) -> None:
    _request_json(
        "DELETE",
        f"{API_BASE_URL}{path}",
        token=token,
        params={"hardDelete": "true", "recursive": "true", **dict(params or {})},
    )


def _run_adapter(
    adapter: GovernedOpenMetadataAdapter,
    operation: str,
    evidence_path: str,
    **parameters: Any,
):
    request = adapter.build_request(
        operation,
        proposed_by="l8-live-validation",
        context_revision="local-openmetadata-1.12.6",
        evidence_refs=(evidence_path,),
        **parameters,
    )
    return getattr(adapter, operation)(request, adapter.authorize(request))


def _receipt_row(label: str, result: Any) -> dict[str, Any]:
    receipt = result.receipt.to_dict()
    return {
        "label": label,
        "receipt_id": receipt["receipt_id"],
        "operation": receipt["operation"],
        "decision": receipt["decision"],
        "outcome": receipt["execution_outcome"],
        "result_count": receipt["result_count"],
        "error_kind": receipt["error_kind"],
        "path": receipt["actual_effect"].get("path"),
    }


def _write_evidence(result: Mapping[str, Any]) -> None:
    head, dirty = _git_identity()
    evidence_lines = [
        "# L8 · OpenMetadata local live evidence",
        "",
        f"Generated: {datetime.now(timezone.utc).isoformat()}",
        "",
        "> Scope: real OpenMetadata server started locally with the pinned Docker Compose deployment.",
        "> Temporary service, database, schema, tables and quality definition were created for the run.",
        "> The script removes only those resource IDs after validation unless `--keep-data` is used.",
        "> No AWS account, cloud credential or paid service was used.",
        "",
        f"- OpenMetadata image version: `{COMPOSE_VERSION}`",
        f"- Compose SHA256: `{_sha256(COMPOSE_PATH) if COMPOSE_PATH.exists() else 'UNAVAILABLE'}`",
        f"- Adapter SHA256: `{_sha256(ADAPTER_PATH) if ADAPTER_PATH.exists() else 'UNAVAILABLE'}`",
        f"- Git HEAD observed: `{head}`",
        f"- Worktree dirty at execution: `{dirty}`",
        f"- Overall result: **{result.get('status', 'FAIL')}**",
        "",
        "## Acceptance checks",
        "",
        "| Check | Result | Detail |",
        "|---|---:|---|",
    ]
    for check in result.get("checks", []):
        evidence_lines.append(
            f"| {check['name']} | {check['status']} | {check.get('detail', '')} |"
        )
    evidence_lines.extend(["", "## Governed receipts", "", "| Label | Decision | Outcome | Results | Path | Receipt |", "|---|---|---|---:|---|---|"])
    for receipt in result.get("receipts", []):
        evidence_lines.append(
            f"| {receipt['label']} | {receipt['decision']} | {receipt['outcome']} | "
            f"{receipt['result_count']} | `{receipt.get('path') or '-'}` | `{receipt['receipt_id']}` |"
        )
    evidence_lines.extend(
        [
            "",
            "## Resource lifecycle",
            "",
            f"- Cleanup requested: `{result.get('cleanup_requested')}`",
            f"- Cleanup result: `{result.get('cleanup_status')}`",
            "- Resource names are run-scoped and are not treated as persistent project data.",
            "",
            "## Boundary",
            "",
            "This evidence proves the local Docker server, authenticated HTTP transport, "
            "real search, lineage write/read, table JSON Patch ownership/schema operations, "
            "quality-definition creation and pre-transport governance denial through the "
            "BAGO adapter. It does not prove AWS, a remote OpenMetadata deployment, OS-level "
            "sandbox isolation or production readiness.",
        ]
    )
    if result.get("error"):
        evidence_lines.extend(["", "## Failure detail", "", f"`{result['error']}`"])
    EVIDENCE_PATH.write_text("\n".join(evidence_lines) + "\n", encoding="utf-8")


def run(*, keep_data: bool = False, write_evidence: bool = True) -> dict[str, Any]:
    checks: list[dict[str, str]] = []
    receipts: list[dict[str, Any]] = []
    resources: dict[str, dict[str, Any]] = {}
    token: Optional[str] = None
    prefix = f"bago_l8_live_{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}_{uuid.uuid4().hex[:6]}"
    result: dict[str, Any] = {
        "status": "FAIL",
        "checks": checks,
        "receipts": receipts,
        "cleanup_requested": not keep_data,
        "cleanup_status": "NOT_RUN",
        "error": None,
    }

    try:
        _wait_for_healthy()
        checks.append({"name": "server health", "status": "PASS", "detail": "HTTP 200; server/database/deadlocks healthy"})

        token = _login()
        checks.append({"name": "JWT authentication", "status": "PASS", "detail": "local login returned a bearer token; token omitted from evidence"})

        service = _create_entity(
            token,
            "/v1/services/databaseServices",
            {
                "name": f"{prefix}_service",
                "serviceType": "CustomDatabase",
                "description": "temporary BAGO L8 live validation service",
            },
        )
        resources["service"] = service
        database = _create_entity(
            token,
            "/v1/databases",
            {
                "name": f"{prefix}_database",
                "service": service["fullyQualifiedName"],
                "description": "temporary BAGO L8 live validation database",
            },
        )
        resources["database"] = database
        schema = _create_entity(
            token,
            "/v1/databaseSchemas",
            {
                "name": f"{prefix}_schema",
                "database": database["fullyQualifiedName"],
                "description": "temporary BAGO L8 live validation schema",
            },
        )
        resources["schema"] = schema
        tables = []
        for role in ("source", "target"):
            table = _create_entity(
                token,
                "/v1/tables",
                {
                    "name": f"{prefix}_{role}",
                    "tableType": "Regular",
                    "columns": [{"name": "content", "dataType": "STRING", "description": "BAGO content"}],
                    "databaseSchema": schema["fullyQualifiedName"],
                    "description": f"temporary BAGO L8 live validation {role}",
                },
            )
            tables.append(table)
        resources["source"] = tables[0]
        resources["target"] = tables[1]

        evidence_ref = "evidence/l8_openmetadata_live.md"
        adapter = GovernedOpenMetadataAdapter(
            policy=OpenMetadataCatalogPolicy(
                base_url=API_BASE_URL,
                auth_token=token,
                timeout_seconds=15,
                max_attempts=2,
            )
        )

        search_result = None
        for _ in range(10):
            search_result = _run_adapter(
                adapter,
                "search",
                evidence_ref,
                resource=prefix,
                entity_type="table",
                query=prefix,
                page_size=10,
            )
            if search_result.entities:
                break
            time.sleep(0.5)
        if search_result is None or not search_result.entities:
            raise LiveValidationError("authenticated search returned no run-scoped table after indexing wait")
        receipts.append(_receipt_row("search", search_result))
        checks.append({"name": "authenticated adapter search", "status": "PASS", "detail": f"{len(search_result.entities)} live entities"})

        lineage_result = _run_adapter(
            adapter,
            "add_lineage",
            evidence_ref,
            resource=resources["target"]["id"],
            entity_type="table",
            from_entity={"id": resources["source"]["id"], "type": "table"},
            to_entity={"id": resources["target"]["id"], "type": "table"},
            evidence_ref=evidence_ref,
        )
        if lineage_result.receipt.execution_outcome.value != "SUCCESS":
            raise LiveValidationError(f"lineage write failed: {lineage_result.receipt.error_message}")
        receipts.append(_receipt_row("add_lineage", lineage_result))

        graph_result = _run_adapter(
            adapter,
            "get_lineage",
            evidence_ref,
            resource=resources["target"]["id"],
            entity_type="table",
            upstream_depth=2,
            downstream_depth=2,
        )
        if not graph_result.lineage:
            raise LiveValidationError("lineage read returned no edge after live write")
        receipts.append(_receipt_row("get_lineage", graph_result))
        checks.append({"name": "lineage write/read", "status": "PASS", "detail": f"{len(graph_result.lineage)} live edge(s)"})

        users_status, users_response = _request_json(
            "GET", f"{API_BASE_URL}/v1/users", token=token, params={"limit": 100}
        )
        if users_status != 200:
            raise LiveValidationError("could not list local users for ownership validation")
        admin = next((item for item in users_response.get("data", []) if item.get("email") == USERNAME), None)
        if not isinstance(admin, Mapping):
            raise LiveValidationError("local admin user was not found for ownership validation")
        owner_result = _run_adapter(
            adapter,
            "assign_ownership",
            evidence_ref,
            resource=resources["target"]["id"],
            entity_type="table",
            owner_id=admin["id"],
            owner_name=admin.get("name", "admin"),
            owner_type="user",
        )
        if owner_result.receipt.execution_outcome.value != "SUCCESS":
            raise LiveValidationError(f"ownership patch failed: {owner_result.receipt.error_message}")
        receipts.append(_receipt_row("assign_ownership", owner_result))
        checks.append({"name": "ownership JSON Patch", "status": "PASS", "detail": "table owner updated through /v1/tables"})

        schema_result = _run_adapter(
            adapter,
            "register_schema_version",
            evidence_ref,
            resource=resources["target"]["id"],
            entity_type="table",
            version="2.0",
            schema={"fields": ["content"]},
        )
        if schema_result.receipt.execution_outcome.value != "SUCCESS":
            raise LiveValidationError(f"schema patch failed: {schema_result.receipt.error_message}")
        receipts.append(_receipt_row("register_schema_version", schema_result))
        checks.append({"name": "schema revision JSON Patch", "status": "PASS", "detail": "native schemaDefinition updated"})

        quality_rule = QualityRule(
            name=f"{prefix}_content_present",
            entity_fqn=resources["target"]["fullyQualifiedName"],
            severity="HIGH",
            parameters={"column": "content"},
        )
        quality_result = _run_adapter(
            adapter,
            "create_quality_rule",
            evidence_ref,
            quality_rule=quality_rule,
        )
        if quality_result.receipt.execution_outcome.value != "SUCCESS":
            raise LiveValidationError(f"quality definition failed: {quality_result.receipt.error_message}")
        resources["quality"] = dict(quality_result.raw_response)
        receipts.append(_receipt_row("create_quality_rule", quality_result))
        checks.append({"name": "quality definition", "status": "PASS", "detail": "real test definition created"})

        class NoCallClient:
            def request(self, *args: Any, **kwargs: Any) -> Mapping[str, Any]:
                raise AssertionError("denied request reached transport")

        restricted = GovernedOpenMetadataAdapter(
            policy=OpenMetadataCatalogPolicy(
                base_url=API_BASE_URL,
                auth_token=token,
                auto_allow_external_api=False,
            ),
            client=NoCallClient(),
        )
        denied = _run_adapter(
            restricted,
            "search",
            evidence_ref,
            resource=prefix,
            entity_type="table",
            query=prefix,
        )
        receipts.append(_receipt_row("pre-transport denial", denied))
        if denied.receipt.decision.value != "REQUIRE_HUMAN" or denied.receipt.execution_outcome.value != "FAILURE":
            raise LiveValidationError("governance denial did not fail closed before transport")
        checks.append({"name": "pre-transport governance denial", "status": "PASS", "detail": "REQUIRE_HUMAN stopped transport"})
        result["status"] = "PASS"
    except Exception as error:  # evidence must be written even when a live contract fails
        result["error"] = _redact(str(error), token)
    finally:
        if keep_data or token is None:
            result["cleanup_status"] = "SKIPPED" if keep_data else "NOT_RUN"
        else:
            cleanup_errors: list[str] = []
            cleanup_actions = [
                ("lineage", f"/v1/lineage/table/{resources.get('source', {}).get('id', '')}/table/{resources.get('target', {}).get('id', '')}", None),
                ("target", f"/v1/tables/{resources.get('target', {}).get('id', '')}", None),
                ("source", f"/v1/tables/{resources.get('source', {}).get('id', '')}", None),
                ("quality", f"/v1/dataQuality/testDefinitions/{resources.get('quality', {}).get('id', '')}", None),
                ("schema", f"/v1/databaseSchemas/{resources.get('schema', {}).get('id', '')}", None),
                ("database", f"/v1/databases/{resources.get('database', {}).get('id', '')}", None),
                ("service", f"/v1/services/databaseServices/{resources.get('service', {}).get('id', '')}", None),
            ]
            for label, path, params in cleanup_actions:
                if path.endswith("/") or path.endswith("//") or path.rsplit("/", 1)[-1] == "":
                    continue
                try:
                    _delete_entity(token, path, params=params)
                except Exception as error:
                    if "HTTP 404" not in str(error):
                        cleanup_errors.append(f"{label}: {_redact(error, token)}")
            result["cleanup_status"] = "PASS" if not cleanup_errors else "PARTIAL"
            if cleanup_errors:
                result["cleanup_errors"] = cleanup_errors
    if write_evidence:
        _write_evidence(result)
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--keep-data",
        action="store_true",
        help="keep the temporary OpenMetadata resources for manual inspection",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="run the live validation and cleanup without rewriting the evidence file",
    )
    args = parser.parse_args()
    result = run(keep_data=args.keep_data, write_evidence=not args.check)
    print(json.dumps({key: value for key, value in result.items() if key != "error"}, sort_keys=True))
    if result.get("error"):
        print(f"ERROR: {result['error']}", file=sys.stderr)
    evidence_target = "NOT_WRITTEN (--check)" if args.check else str(EVIDENCE_PATH)
    print(f"Evidence: {evidence_target}")
    return 0 if result.get("status") == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
