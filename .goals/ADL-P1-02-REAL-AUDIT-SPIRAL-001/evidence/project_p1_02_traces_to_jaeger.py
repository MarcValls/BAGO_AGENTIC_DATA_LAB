"""Project the two completed audit LocalTraces to the local Jaeger collector."""

from __future__ import annotations

import hashlib
import json
import sys
import time
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import urlopen

REPOSITORY = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPOSITORY))

from src.observability.local_trace import LocalTrace, TraceEvent
from src.observability.otel_bridge import export_local_trace_to_otlp


TRACE_IDS = (
    "trace-263199de3de94db9",
    "trace-5928204206a14073",
)
OTLP_ENDPOINT = "http://127.0.0.1:4318/v1/traces"
JAEGER_BASE = "http://127.0.0.1:16686"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(64 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_jaeger_trace(trace_id: str) -> dict:
    url = f"{JAEGER_BASE}/api/traces/{trace_id}"
    last_error = ""
    for _ in range(10):
        try:
            with urlopen(url, timeout=5) as response:
                payload = json.load(response)
            if payload.get("data"):
                trace = payload["data"][0]
                return {
                    "http_status": 200,
                    "trace_id": trace.get("traceID"),
                    "span_count": len(trace.get("spans", [])),
                    "spans": [
                        {
                            "span_id": span.get("spanID"),
                            "operation": span.get("operationName"),
                            "process_id": span.get("processID"),
                            "service_name": trace.get("processes", {}).get(span.get("processID"), {}).get("serviceName"),
                            "tags": span.get("tags", []),
                        }
                        for span in trace.get("spans", [])
                    ],
                }
            last_error = "Trace not indexed yet"
        except (HTTPError, URLError, TimeoutError) as error:
            last_error = f"{type(error).__name__}: {error}"
        time.sleep(0.5)
    raise RuntimeError(last_error)


def main() -> None:
    repository = REPOSITORY
    receipts = []
    for trace_id in TRACE_IDS:
        path = repository / ".bago" / "traces" / "agent-chat" / f"{trace_id}.json"
        source_hash_before = sha256(path)
        data = json.loads(path.read_text(encoding="utf-8"))
        events = tuple(
            TraceEvent(
                event_id=event["event_id"],
                trace_id=event["trace_id"],
                sequence=event["sequence"],
                name=event["name"],
                kind=event["kind"],
                status=event["status"],
                parent_event_id=event.get("parent_event_id"),
                attributes=event.get("attributes", {}),
                evidence_refs=tuple(event.get("evidence_refs", [])),
                start_time_unix_nano=event.get("start_time_unix_nano"),
                end_time_unix_nano=event.get("end_time_unix_nano"),
            )
            for event in data["events"]
        )
        local_trace = LocalTrace(
            trace_id=data["trace_id"],
            run_id=data["run_id"],
            events=events,
            cost_usd=data.get("cost_usd", 0.0),
        )
        receipt = export_local_trace_to_otlp(
            local_trace,
            endpoint=OTLP_ENDPOINT,
            service_name="bago-agentic-data-lab",
            timeout=10,
        ).to_dict()
        if not receipt["exported"] or not receipt.get("jaeger_trace_id"):
            raise RuntimeError(f"OTLP export failed for {trace_id}: {receipt}")
        jaeger = read_jaeger_trace(receipt["jaeger_trace_id"])
        source_hash_after = sha256(path)
        if source_hash_before != source_hash_after:
            raise RuntimeError(f"Source LocalTrace changed during export: {trace_id}")
        receipts.append({
            "local_trace_path": str(path.relative_to(repository)).replace("\\", "/"),
            "local_trace_sha256": source_hash_before,
            "source_unchanged_after_projection": True,
            "export": receipt,
            "jaeger_readback": jaeger,
        })
    result = {
        "endpoint": OTLP_ENDPOINT,
        "service_name": "bago-agentic-data-lab",
        "method": "post-run projection of persisted LocalTrace; no agent/model request",
        "traces": receipts,
    }
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
