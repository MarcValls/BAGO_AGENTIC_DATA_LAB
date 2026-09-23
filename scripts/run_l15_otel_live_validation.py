"""Run the public E2E trace through a local OpenTelemetry Collector/Jaeger."""

from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = REPO_ROOT / "src"
EVIDENCE_PATH = REPO_ROOT / "evidence" / "l15_otel_jaeger_live.md"
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from observability.otel_bridge import (  # noqa: E402
    DEFAULT_OTLP_HTTP_ENDPOINT,
    DEFAULT_SERVICE_NAME,
    export_local_trace_to_otlp,
)
from scripts.run_public_e2e_demo import run_demo  # noqa: E402


DEFAULT_JAEGER_QUERY = "http://localhost:16686"
EXPECTED_OPERATIONS = {"agent.run", "retrieval", "permit"}


def _json_get(url: str, *, timeout: float = 5.0) -> dict[str, Any]:
    request = Request(url, headers={"Accept": "application/json"})
    with urlopen(request, timeout=timeout) as response:  # nosec B310 - explicit local URL input
        payload = json.loads(response.read().decode("utf-8"))
    if not isinstance(payload, dict):
        raise RuntimeError(f"Expected JSON object from {url}")
    return payload


def _wait_for_query(base_url: str, timeout: float) -> None:
    deadline = time.monotonic() + timeout
    last_error = ""
    while time.monotonic() < deadline:
        try:
            _json_get(f"{base_url.rstrip('/')}/api/services", timeout=2.0)
            return
        except (HTTPError, URLError, TimeoutError, OSError, json.JSONDecodeError) as exc:
            last_error = f"{type(exc).__name__}: {exc}"
            time.sleep(0.5)
    raise RuntimeError(f"Jaeger query API did not become ready: {last_error}")


def _query_trace(base_url: str, service_name: str) -> list[dict[str, Any]]:
    payload = _json_get(
        f"{base_url.rstrip('/')}/api/traces?service={quote(service_name)}&limit=20"
    )
    traces = payload.get("data", [])
    return [trace for trace in traces if isinstance(trace, dict)]


def _operations(traces: list[dict[str, Any]]) -> set[str]:
    return {
        str(span.get("operationName"))
        for trace in traces
        for span in trace.get("spans", [])
        if isinstance(span, dict) and span.get("operationName")
    }


def _belongs_to_local_trace(trace: dict[str, Any], local_trace_id: str) -> bool:
    return any(
        tag.get("key") == "bago.trace_id" and tag.get("value") == local_trace_id
        for span in trace.get("spans", [])
        if isinstance(span, dict)
        for tag in span.get("tags", [])
        if isinstance(tag, dict)
    )


def _latest_trace(traces: list[dict[str, Any]]) -> dict[str, Any] | None:
    if not traces:
        return None
    return max(
        traces,
        key=lambda trace: max(
            (int(span.get("startTime", 0)) for span in trace.get("spans", []) if isinstance(span, dict)),
            default=0,
        ),
    )


def run_validation(
    *,
    otlp_endpoint: str = DEFAULT_OTLP_HTTP_ENDPOINT,
    jaeger_query: str = DEFAULT_JAEGER_QUERY,
    service_name: str = DEFAULT_SERVICE_NAME,
    timeout: float = 30.0,
) -> dict[str, Any]:
    _wait_for_query(jaeger_query, timeout)
    result = run_demo()
    local_trace = result["trace"]
    export_receipt = export_local_trace_to_otlp(
        local_trace,
        endpoint=otlp_endpoint,
        service_name=service_name,
        timeout=min(timeout, 10.0),
    )
    if not export_receipt.exported:
        raise RuntimeError(f"OpenTelemetry export failed: {export_receipt.to_dict()}")

    deadline = time.monotonic() + timeout
    traces: list[dict[str, Any]] = []
    observed: set[str] = set()
    while time.monotonic() < deadline:
        candidates = [
            trace
            for trace in _query_trace(jaeger_query, service_name)
            if _belongs_to_local_trace(trace, local_trace.trace_id)
        ]
        latest = _latest_trace(candidates)
        traces = [latest] if latest is not None else []
        observed = _operations(traces)
        if EXPECTED_OPERATIONS.issubset(observed):
            break
        time.sleep(0.5)

    missing = sorted(EXPECTED_OPERATIONS - observed)
    if missing:
        raise RuntimeError(
            "Jaeger did not expose the expected BAGO operations: " + ", ".join(missing)
        )

    matching_trace_ids = [
        str(trace.get("traceID"))
        for trace in traces
        if trace.get("spans")
    ]
    return {
        "status": "PASS",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "scope": "local-opentelemetry-jaeger-public-e2e",
        "cost_usd": 0.0,
        "service_name": service_name,
        "otlp_endpoint": export_receipt.endpoint,
        "jaeger_query": jaeger_query,
        "local_trace_id": local_trace.trace_id,
        "spans_projected": export_receipt.span_count,
        "spans_observed": sum(len(trace.get("spans", [])) for trace in traces),
        "observed_operations": sorted(observed),
        "expected_operations": sorted(EXPECTED_OPERATIONS),
        "matching_trace_ids": matching_trace_ids,
        "trace_found": bool(matching_trace_ids),
        "public_e2e_status": result["status"],
        "aws_live": "NOT_RUN",
        "remote_collector": "NOT_RUN",
    }


def render_evidence(result: dict[str, Any]) -> str:
    encoded = json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True)
    return f"""# L15 · OpenTelemetry + Jaeger local live validation

Generated at: `{result['generated_at']}`

This validation projects the existing BAGO `LocalTrace` into OpenTelemetry
spans and verifies that Jaeger receives and indexes the public E2E operations:

```text
public E2E LocalTrace
  → OTLP/HTTP exporter
  → Jaeger all-in-one local Docker service
  → Jaeger query API
  → observed operation evidence
```

## Result

- Status: `{result['status']}`
- Service: `{result['service_name']}`
- Spans projected: `{result['spans_projected']}`
- Spans observed: `{result['spans_observed']}`
- Trace found: `{result['trace_found']}`
- Operations: `{', '.join(result['observed_operations'])}`
- Cost: `{result['cost_usd']:.1f} USD`
- AWS live: `{result['aws_live']}`
- Remote collector: `{result['remote_collector']}`

## Reproduce

```bash
docker compose -p bago-otel -f infra/observability/docker-compose.yml up -d
python scripts/run_l15_otel_live_validation.py --check
python scripts/run_l15_otel_live_validation.py --write-evidence
docker compose -p bago-otel -f infra/observability/docker-compose.yml down
```

## Boundary

The BAGO `LocalTrace` remains the source of evidence and authority. OpenTelemetry
is a projection/transport layer only; it cannot authorize or execute an action.
Jaeger is a local Docker backend, not production telemetry, AWS, SaaS
observability or an external collector validation.

## Stable summary

```json
{encoded}
```
"""


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="fail unless live gates pass")
    parser.add_argument("--write-evidence", action="store_true")
    parser.add_argument("--otlp-endpoint", default=DEFAULT_OTLP_HTTP_ENDPOINT)
    parser.add_argument("--jaeger-query", default=DEFAULT_JAEGER_QUERY)
    parser.add_argument("--service-name", default=DEFAULT_SERVICE_NAME)
    parser.add_argument("--timeout", type=float, default=30.0)
    args = parser.parse_args(argv)
    result = run_validation(
        otlp_endpoint=args.otlp_endpoint,
        jaeger_query=args.jaeger_query,
        service_name=args.service_name,
        timeout=args.timeout,
    )
    if args.write_evidence:
        EVIDENCE_PATH.parent.mkdir(parents=True, exist_ok=True)
        EVIDENCE_PATH.write_text(render_evidence(result), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    if args.write_evidence:
        print(f"Evidence: {EVIDENCE_PATH.relative_to(REPO_ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
