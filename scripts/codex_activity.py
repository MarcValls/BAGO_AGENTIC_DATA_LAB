"""ADL/Codex read-only activity observer CLI. See docs/observability/codex_activity.md."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
from observability.codex_activity_monitor import diagnostic_report, project_to_jaeger, serve  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="ADL Codex activity witness (no execution permissions)")
    parser.add_argument("action", choices=("serve", "report", "project"))
    parser.add_argument("--data-dir", type=Path, default=ROOT / ".bago/traces/codex-activity")
    parser.add_argument("--port", type=int, default=4319)
    parser.add_argument("--endpoint", default="http://127.0.0.1:4318/v1/traces")
    parser.add_argument("--slow-ms", type=int, default=30_000)
    parser.add_argument("--limit", type=int, default=500, help="Latest events in an explicit Jaeger snapshot")
    args = parser.parse_args()
    if args.action == "serve":
        serve(args.data_dir, port=args.port)
        return 0
    if args.action == "report":
        result = diagnostic_report(args.data_dir, slow_ms=args.slow_ms)
    else:
        result = project_to_jaeger(args.data_dir, endpoint=args.endpoint, max_events=args.limit)
    print(json.dumps(result, indent=2, ensure_ascii=False, sort_keys=True))
    if args.action == "project":
        return 0 if result.get("status") == "PASS" else 2
    return 1 if result["unreadable_records"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
