"""Run a bounded, explicit AWS Bedrock live validation.

The default mode performs only an STS identity preflight. ``--execute`` opts
into exactly one Bedrock Converse call with a model-scoped permit, a small
output budget and no SDK retries. Credentials and response text are never
written to the evidence artifact.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Optional

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from adapters.bedrock_provider_adapter import (  # noqa: E402
    BedrockProviderAdapter,
    BedrockProviderPolicy,
)


DEFAULT_MODEL_ID = "amazon.nova-lite-v1:0"
DEFAULT_REGION = "us-east-1"
DEFAULT_MAX_TOKENS = 32
EVIDENCE_PATH = REPO_ROOT / "evidence" / "l6_aws_live.md"


def _redact(value: Any) -> str:
    text = str(value)
    text = re.sub(r"(?:AKIA|ASIA)[A-Z0-9]{16}", "[REDACTED]", text)
    return text[:500]


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
        dirty = bool(
            subprocess.run(
                ["git", "status", "--porcelain"],
                cwd=REPO_ROOT,
                check=True,
                capture_output=True,
                text=True,
            ).stdout.strip()
        )
        return head, dirty
    except (OSError, subprocess.CalledProcessError):
        return "UNAVAILABLE", True


def _mask_account(account: Any) -> str:
    value = str(account or "")
    if len(value) >= 6:
        return f"{value[:4]}…{value[-2:]}"
    return "UNAVAILABLE"


def _arn_kind(arn: Any) -> str:
    value = str(arn or "")
    resource = value.split(":", 5)[-1] if value.startswith("arn:") else ""
    return resource.split("/", 1)[0] if resource else "UNAVAILABLE"


def _region_from_args(value: Optional[str]) -> str:
    return (
        value
        or os.environ.get("AWS_REGION")
        or os.environ.get("AWS_DEFAULT_REGION")
        or DEFAULT_REGION
    )


def _session(*, profile: Optional[str], region: str) -> Any:
    try:
        import boto3  # type: ignore[import-not-found]
    except ImportError as error:
        raise RuntimeError("boto3 is required; install it with `python -m pip install boto3`") from error

    kwargs: dict[str, Any] = {"region_name": region}
    if profile:
        kwargs["profile_name"] = profile
    return boto3.Session(**kwargs)


def _write_evidence(result: Mapping[str, Any]) -> None:
    head, dirty = _git_identity()
    receipt = dict(result.get("receipt") or {})
    error_message = _redact(receipt.get("error_message")) if receipt.get("error_message") else ""
    lines = [
        "# L6 · AWS Bedrock live evidence",
        "",
        f"Generated: {datetime.now(timezone.utc).isoformat()}",
        "",
        "> Scope: one explicit Amazon Bedrock Converse call through the governed BAGO adapter.",
        "> The runner uses a model allowlist, one call, maxTokens <= 64 and SDK retries disabled.",
        "> Credentials, tokens and response text are not written to this artifact.",
        "",
        f"- Region: `{result.get('region', 'UNAVAILABLE')}`",
        f"- Model ID: `{result.get('model_id', 'UNAVAILABLE')}`",
        f"- AWS account: `{result.get('account_masked', 'UNAVAILABLE')}`",
        f"- Principal kind: `{result.get('principal_kind', 'UNAVAILABLE')}`",
        f"- Git HEAD observed: `{head}`",
        f"- Worktree dirty at execution: `{dirty}`",
        f"- boto3 version: `{result.get('boto3_version', 'UNAVAILABLE')}`",
        "- Free-tier/billing status: `AWS account credit or billing state is not returned by Bedrock; verify it in AWS Billing`",
        f"- Overall result: **{result.get('status', 'FAIL')}**",
        "",
        "## Acceptance checks",
        "",
        "| Check | Result | Detail |",
        "|---|---:|---|",
    ]
    for check in result.get("checks", []):
        lines.append(f"| {check['name']} | {check['status']} | {check.get('detail', '')} |")
    lines.extend(
        [
            "",
            "## Governed receipt",
            "",
            "```json",
            json.dumps(receipt, ensure_ascii=False, indent=2, sort_keys=True),
            "```",
        ]
    )
    if error_message:
        lines.extend(["", "## Failure detail", "", f"`{error_message}`"])
    lines.extend(
        [
            "",
            "## Boundary",
            "",
            "This proves one live Bedrock call for the configured account, region and model "
            "scope. It does not prove zero billing, free-tier eligibility after the call, "
            "streaming, Knowledge Bases, production latency or production readiness.",
        ]
    )
    EVIDENCE_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def run(
    *,
    execute: bool,
    profile: Optional[str],
    region: str,
    model_id: str,
    max_tokens: int,
    prompt: str,
    write_evidence: bool,
) -> dict[str, Any]:
    result: dict[str, Any] = {
        "status": "BLOCKED",
        "region": region,
        "model_id": model_id,
        "checks": [],
        "receipt": {},
        "error": None,
    }

    if not model_id.strip():
        result["error"] = "model ID is required"
        return result
    if max_tokens < 1 or max_tokens > 64:
        result["error"] = "max_tokens must be between 1 and 64"
        return result
    if not prompt.strip():
        result["error"] = "prompt is required"
        return result

    try:
        session = _session(profile=profile, region=region)
        identity = session.client("sts", region_name=region).get_caller_identity()
        result["account_masked"] = _mask_account(identity.get("Account"))
        result["principal_kind"] = _arn_kind(identity.get("Arn"))
        result["checks"].append(
            {
                "name": "AWS credential resolution",
                "status": "PASS",
                "detail": f"STS identity resolved for account {result['account_masked']}",
            }
        )
    except Exception as error:
        result["error"] = _redact(f"{type(error).__name__}: {error}")
        result["checks"].append(
            {
                "name": "AWS credential resolution",
                "status": "BLOCKED",
                "detail": "STS identity could not be resolved; no Bedrock call was attempted",
            }
        )
        return result

    if not execute:
        result["status"] = "PREFLIGHT_PASS"
        result["checks"].append(
            {
                "name": "Bedrock inference",
                "status": "NOT_RUN",
                "detail": "preflight mode; pass --execute for exactly one call",
            }
        )
        return result

    try:
        from botocore.config import Config  # type: ignore[import-not-found]

        client = session.client(
            "bedrock-runtime",
            region_name=region,
            config=Config(
                connect_timeout=10,
                read_timeout=30,
                retries={"mode": "standard", "max_attempts": 0},
            ),
        )
        policy = BedrockProviderPolicy(
            region_name=region,
            allowed_model_ids=frozenset({model_id}),
            timeout_seconds=30,
            max_attempts=1,
            max_calls_per_window=1,
            input_cost_per_1k_tokens=0.0,
            output_cost_per_1k_tokens=0.0,
        )
        adapter = BedrockProviderAdapter(client=client, policy=policy)
        request = adapter.build_execution_request(
            model_id,
            [{"role": "user", "content": [{"text": prompt}]}],
            proposed_by="bago.aws-live-validation",
            context_revision="aws-free-tier-live-v1",
            inference_config={"maxTokens": max_tokens, "temperature": 0.0},
        )
        permit = adapter.authorize(request)
        live_result = adapter.converse(request, permit)
        result["receipt"] = live_result.receipt.to_dict()
        result["boto3_version"] = getattr(__import__("boto3"), "__version__", "UNAVAILABLE")
        if live_result.receipt.execution_outcome.value == "SUCCESS":
            result["status"] = "PASS"
            result["checks"].append(
                {
                    "name": "Bedrock Converse",
                    "status": "PASS",
                    "detail": f"one live call; {live_result.usage.total_tokens} total tokens",
                }
            )
        else:
            result["status"] = "FAIL"
            result["checks"].append(
                {
                    "name": "Bedrock Converse",
                    "status": "FAIL",
                    "detail": _redact(live_result.receipt.error_message or "live call failed"),
                }
            )
    except Exception as error:
        result["status"] = "FAIL"
        result["error"] = _redact(f"{type(error).__name__}: {error}")
        result["checks"].append(
            {
                "name": "Bedrock Converse",
                "status": "FAIL",
                "detail": result["error"],
            }
        )

    if write_evidence:
        _write_evidence(result)
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--execute", action="store_true", help="perform exactly one live Bedrock call")
    parser.add_argument("--no-evidence", action="store_true", help="do not write the evidence artifact")
    parser.add_argument("--profile", default=os.environ.get("AWS_PROFILE"))
    parser.add_argument("--region", default=None)
    parser.add_argument("--model-id", default=os.environ.get("BAGO_BEDROCK_MODEL_ID", DEFAULT_MODEL_ID))
    parser.add_argument("--max-tokens", type=int, default=DEFAULT_MAX_TOKENS)
    parser.add_argument(
        "--prompt",
        default="Reply with exactly: BAGO AWS LIVE PASS",
        help="bounded prompt; response text is never written to evidence",
    )
    args = parser.parse_args()
    result = run(
        execute=args.execute,
        profile=args.profile,
        region=_region_from_args(args.region),
        model_id=args.model_id,
        max_tokens=args.max_tokens,
        prompt=args.prompt,
        write_evidence=args.execute and not args.no_evidence,
    )
    output = {key: value for key, value in result.items() if key != "receipt"}
    output["receipt_id"] = result.get("receipt", {}).get("receipt_id")
    print(json.dumps(output, ensure_ascii=False, sort_keys=True))
    if args.execute:
        print(f"Evidence: {'NOT_WRITTEN' if args.no_evidence else EVIDENCE_PATH}")
    return 0 if result["status"] in {"PASS", "PREFLIGHT_PASS"} else 2


if __name__ == "__main__":
    raise SystemExit(main())
