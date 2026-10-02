"""Run the local one-command governed knowledge-agent demo.

From the repository root, install ``requirements.txt`` and run:

    python demo.py

The command uses deterministic local fixtures only (no credentials, network,
Docker, or paid services) and writes five JSON artifacts to ``demo_output/``.
Use ``--output-dir PATH`` to choose another output directory.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts"))

from scripts.run_public_e2e_demo import QUERY, run_demo, summary as make_summary  # noqa: E402

ARTIFACT_NAMES = (
    "summary.json",
    "agent_run.json",
    "receipts.json",
    "trace.json",
    "evaluation.json",
)


def _json_default(value: Any) -> Any:
    if hasattr(value, "value"):
        return value.value
    if isinstance(value, Path):
        return str(value)
    raise TypeError(f"Object of type {type(value).__name__} is not JSON serializable")


def _write_json(path: Path, payload: Any) -> None:
    """Write one JSON artifact atomically in its destination directory."""
    encoded = json.dumps(
        payload,
        ensure_ascii=False,
        indent=2,
        sort_keys=True,
        default=_json_default,
    ) + "\n"
    fd, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as stream:
            stream.write(encoded)
        os.replace(temporary_name, path)
    except BaseException:
        try:
            os.unlink(temporary_name)
        except OSError:
            pass
        raise


def artifact_payloads(result: dict[str, Any]) -> dict[str, Any]:
    """Serialize one successful E2E run using existing component serializers."""
    agent_run = result["agent_run"]
    trace = result["trace"]
    evaluation = result["evaluation"]
    ontology = result["ontology"]
    sandbox = result["sandbox"]
    report = make_summary(result)
    report.update(
        {
            "query": agent_run.query,
            "answer": agent_run.answer,
            "run_id": agent_run.run_id,
            "trace_id": trace.trace_id,
            "evaluation_id": evaluation.evaluation_id,
            "artifacts": list(ARTIFACT_NAMES),
        }
    )

    receipts = {
        "run_id": agent_run.run_id,
        "trace_id": trace.trace_id,
        "agent_decision_receipts": [r.to_dict() for r in agent_run.decision_receipts],
        "mcp_receipts": [r.to_dict() for r in agent_run.mcp_receipts],
        "provider_receipt": (
            agent_run.provider_result.receipt.to_dict()
            if agent_run.provider_result is not None
            else None
        ),
        "ontology_receipt": ontology.receipt.to_dict(),
        "sandbox_receipts": [sandbox.receipt.to_dict()],
    }
    return {
        "summary.json": report,
        "agent_run.json": agent_run.to_dict(),
        "receipts.json": receipts,
        "trace.json": trace.to_dict(),
        "evaluation.json": evaluation.to_dict(),
    }


def run(output_dir: Path) -> dict[str, Any]:
    """Execute the public demo and persist its five linked artifacts."""
    result = run_demo()
    payloads = artifact_payloads(result)
    summary_payload = payloads["summary.json"]
    summary_payload["output_directory"] = (
        output_dir.relative_to(ROOT).as_posix() if output_dir.is_relative_to(ROOT) else str(output_dir)
    )
    output_dir.mkdir(parents=True, exist_ok=True)
    for name in ARTIFACT_NAMES:
        _write_json(output_dir / name, payloads[name])
    return payloads["summary.json"]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=ROOT / "demo_output",
        help="directory for the five JSON artifacts (default: ./demo_output)",
    )
    args = parser.parse_args(argv)
    output_dir = args.output_dir if args.output_dir.is_absolute() else ROOT / args.output_dir
    try:
        report = run(output_dir)
    except Exception as exc:
        print(
            json.dumps(
                {"status": "FAIL", "error_type": type(exc).__name__, "error": str(exc)},
                ensure_ascii=False,
                indent=2,
            ),
            file=sys.stderr,
        )
        return 1
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    print(f"Artifacts: {output_dir.relative_to(ROOT) if output_dir.is_relative_to(ROOT) else output_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())