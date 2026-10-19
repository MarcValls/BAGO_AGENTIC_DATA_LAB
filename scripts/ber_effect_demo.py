#!/usr/bin/env python3
"""Interactively execute one bounded BAGO Embedded Runtime effect.

The CLI is an explicit ADL demonstration path, not Agent Runner. It prints a
JSON record containing BAGO's receipt and ADL's LocalTrace/evaluation. Effect
arguments, including file contents, are never copied into the trace.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from evaluation.local_evals import LocalTraceEvaluator  # noqa: E402
from observability.ber_effect_trace import local_trace_from_ber_effect  # noqa: E402
from runtime.ber import BerClient, BerRuntimeError  # noqa: E402
from runtime.ber.client import ARTIFACT_SHA256, BER_VERSION, PROTOCOL_VERSION, SOURCE_COMMIT  # noqa: E402


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", required=True, type=Path, help="existing workspace root for this bounded effect")
    parser.add_argument("--effect", required=True, choices=("filesystem.read", "filesystem.write", "process.inspect", "process.execute"))
    parser.add_argument("--path", help="workspace-relative file path for filesystem effects")
    parser.add_argument("--content", help="UTF-8 content for filesystem.write; omitted content is an empty string")
    parser.add_argument("--expected-sha256", help="required existing-file digest for a modify; omit to create a new file")
    parser.add_argument("--executable", help="allowlisted executable for process effects")
    parser.add_argument("--cwd", help="process cwd within the workspace; defaults to the workspace root")
    parser.add_argument("--argv", nargs=argparse.REMAINDER, default=[], help="typed argv for process effects; no shell is used (put this option last)")
    return parser


def _operation(args: argparse.Namespace) -> dict[str, Any]:
    if args.effect.startswith("filesystem."):
        if not args.path:
            raise ValueError("--path is required for filesystem effects")
        arguments: dict[str, Any] = {}
        if args.effect == "filesystem.write":
            arguments = {
                "content": args.content or "",
                "expected_exists": bool(args.expected_sha256),
            }
            if args.expected_sha256:
                arguments["expected_sha256"] = args.expected_sha256.lower()
        return {"effect_id": args.effect, "target": {"path": args.path}, "arguments": arguments}

    if not args.executable:
        raise ValueError("--executable is required for process effects")
    return {
        "effect_id": args.effect,
        "target": {"executable": args.executable, "cwd": args.cwd or str(args.workspace)},
        "arguments": {"argv": args.argv},
    }


def _emit(record: dict[str, Any]) -> None:
    print(json.dumps(record, ensure_ascii=False, indent=2, sort_keys=True, default=str))


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        workspace = args.workspace.expanduser().resolve(strict=True)
        if not workspace.is_dir():
            raise ValueError("--workspace must name an existing directory")
        operation = _operation(args)
    except (OSError, ValueError) as exc:
        _emit({"schema": "bago.ber.effect-demo.v1", "status": "INVALID_REQUEST", "error": str(exc)})
        return 2

    client = BerClient(workspace=workspace)
    try:
        identity = client.start()
        prepared = client.prepare(operation)
        approval: dict[str, Any] | None = None
        if prepared.get("approval_required") is True:
            print(
                "Efecto preparado por BAGO BER:\n"
                + json.dumps({
                    "effect_id": prepared.get("effect_id"),
                    "request_id": prepared.get("request_id"),
                    "target": prepared.get("target"),
                    "arguments_digest": prepared.get("arguments_digest"),
                    "world_state_digest": prepared.get("world_state_digest"),
                    "expires_at": prepared.get("expires_at"),
                }, ensure_ascii=False, indent=2, sort_keys=True)
                + f"\nEscribe APROBAR {prepared.get('effect_id')} para continuar: ",
                file=sys.stderr,
                end="",
                flush=True,
            )
            try:
                confirmation = input().strip()
            except EOFError:
                confirmation = ""
            if confirmation != f"APROBAR {prepared.get('effect_id')}":
                _emit({
                    "schema": "bago.ber.effect-demo.v1",
                    "status": "NOT_EXECUTED",
                    "ber": {"version": BER_VERSION, "protocol_version": PROTOCOL_VERSION, "source_commit": SOURCE_COMMIT, "artifact_sha256": ARTIFACT_SHA256},
                    "prepared": prepared,
                    "approval": None,
                    "execution": None,
                    "trace": None,
                    "evaluation": None,
                })
                return 3
            approval = client.approve(prepared["challenge_id"], channel="desktop")

        execution = client.execute(prepared["challenge_id"])
        trace = local_trace_from_ber_effect(prepared, approval, execution, artifact_sha256=ARTIFACT_SHA256)
        evaluation = LocalTraceEvaluator().evaluate_ber_effect(trace)
        _emit({
            "schema": "bago.ber.effect-demo.v1",
            "status": evaluation.status.value,
            "ber": {
                "version": BER_VERSION,
                "protocol_version": PROTOCOL_VERSION,
                "source_commit": SOURCE_COMMIT,
                "artifact_sha256": ARTIFACT_SHA256,
                "health": identity,
            },
            "prepared": prepared,
            "approval": approval,
            "execution": execution,
            "trace": trace.to_dict(),
            "evaluation": evaluation.to_dict(),
        })
        return 0 if evaluation.status.value == "PASS" else 1
    except (BerRuntimeError, OSError, ValueError, KeyError) as exc:
        _emit({
            "schema": "bago.ber.effect-demo.v1",
            "status": "FAILED",
            "error": {"code": getattr(exc, "code", "ber_effect_demo_failed"), "message": str(exc)},
        })
        return 1
    finally:
        client.close()


if __name__ == "__main__":
    raise SystemExit(main())
