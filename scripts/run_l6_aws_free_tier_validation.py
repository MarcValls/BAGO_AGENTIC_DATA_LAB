"""Read AWS Free Tier account coverage without making a billable workload call.

This runner uses only the AWS Free Tier API and STS identity lookup. It does
not call Cost Explorer, create resources, or invoke a model. The result proves
the account-plan coverage visible at validation time; it deliberately does not
claim that a later invoice contains zero dollars.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Optional

REPO_ROOT = Path(__file__).resolve().parents[1]
EVIDENCE_PATH = REPO_ROOT / "evidence" / "l6_aws_free_tier.md"
DEFAULT_REGION = "us-east-1"
DEFAULT_MAX_RESULTS = 1000


def _redact(value: Any) -> str:
    text = str(value)
    text = re.sub(r"(?:AKIA|ASIA)[A-Z0-9]{16}", "[REDACTED]", text)
    return text[:500]


def _mask_account(account: Any) -> str:
    value = str(account or "")
    if len(value) >= 6:
        return f"{value[:4]}…{value[-2:]}"
    return "UNAVAILABLE"


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


def _region_from_args(value: Optional[str]) -> str:
    return (
        value
        or os.environ.get("AWS_REGION")
        or os.environ.get("AWS_DEFAULT_REGION")
        or DEFAULT_REGION
    )


def _serialize_datetime(value: Any) -> Any:
    return value.isoformat() if hasattr(value, "isoformat") else value


def _session(*, profile: Optional[str], region: str) -> Any:
    try:
        import boto3  # type: ignore[import-not-found]
    except ImportError as error:
        raise RuntimeError(
            "boto3 is required; install it with `python -m pip install boto3`"
        ) from error

    kwargs: dict[str, Any] = {"region_name": region}
    if profile:
        kwargs["profile_name"] = profile
    return boto3.Session(**kwargs)


def _write_evidence(result: Mapping[str, Any]) -> None:
    head, dirty = _git_identity()
    account_plan = result.get("account_plan") or {}
    checks = result.get("checks") or []
    lines = [
        "# L6 · AWS Free Tier account coverage evidence",
        "",
        f"Generated: {datetime.now(timezone.utc).isoformat()}",
        "",
        "> Scope: read-only AWS Free Tier account-plan and usage inspection.",
        "> No resource was created, no model was invoked and Cost Explorer was not queried.",
        "> Credentials, account IDs and pagination tokens are not written to this artifact.",
        "",
        f"- Region: `{result.get('region', 'UNAVAILABLE')}`",
        f"- AWS account: `{result.get('account_masked', 'UNAVAILABLE')}`",
        f"- Git HEAD observed: `{head}`",
        f"- Worktree dirty at execution: `{dirty}`",
        f"- Account plan: `{account_plan.get('type', 'UNAVAILABLE')}`",
        f"- Account plan status: `{account_plan.get('status', 'UNAVAILABLE')}`",
        f"- Remaining plan credits: `{account_plan.get('remaining_credits_amount', 'UNAVAILABLE')} {account_plan.get('remaining_credits_unit', '')}`",
        f"- Plan expiration: `{account_plan.get('expiration', 'UNAVAILABLE')}`",
        f"- Free Tier usage rows returned: `{result.get('free_tier_usage_count', 'UNAVAILABLE')}`",
        f"- Cost Explorer query: `{result.get('cost_explorer', 'NOT_RUN')}`",
        f"- Coverage conclusion: **{result.get('coverage_status', 'NOT_PROVEN')}**",
        f"- Zero-billing conclusion: **{result.get('zero_billing_status', 'NOT_PROVEN')}**",
        f"- Overall result: **{result.get('status', 'FAIL')}**",
        "",
        "## Acceptance checks",
        "",
        "| Check | Result | Detail |",
        "|---|---:|---|",
    ]
    for check in checks:
        lines.append(
            f"| {check['name']} | {check['status']} | {check.get('detail', '')} |"
        )
    lines.extend(
        [
            "",
            "## Boundary",
            "",
            "This proves that the observed account had an active AWS Free account plan "
            "and remaining credits at validation time. An empty Free Tier usage list "
            "is an observation, not proof that all usage is free. It does not prove "
            "that the Bedrock call generated a zero-dollar invoice; billing data can "
            "settle later. Cost Explorer was intentionally not called because its API "
            "is priced per request.",
            "",
            "References: [AWS Free Tier API](https://docs.aws.amazon.com/awsaccountbilling/latest/aboutv2/using-free-tier-api.html); "
            "[AWS Cost Explorer pricing](https://aws.amazon.com/aws-cost-management/aws-cost-explorer/pricing/).",
            "",
            "## Stable summary",
            "",
            "```json",
            json.dumps(dict(result), ensure_ascii=False, indent=2, sort_keys=True),
            "```",
        ]
    )
    EVIDENCE_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def run(
    *,
    profile: Optional[str],
    region: str,
    max_results: int = DEFAULT_MAX_RESULTS,
    write_evidence: bool = False,
) -> dict[str, Any]:
    result: dict[str, Any] = {
        "status": "BLOCKED",
        "region": region,
        "account_masked": "UNAVAILABLE",
        "account_plan": {},
        "free_tier_usage_count": 0,
        "free_tier_usage_services": [],
        "free_tier_usage_paginated": False,
        "cost_explorer": "NOT_RUN",
        "coverage_status": "NOT_PROVEN",
        "zero_billing_status": "NOT_PROVEN",
        "checks": [],
        "error": None,
    }

    if not 1 <= max_results <= 1000:
        result["error"] = "max_results must be between 1 and 1000"
        if write_evidence:
            _write_evidence(result)
        return result

    try:
        from botocore.config import Config  # type: ignore[import-not-found]

        session = _session(profile=profile, region=region)
        identity = session.client(
            "sts",
            region_name=region,
            config=Config(
                connect_timeout=10,
                read_timeout=30,
                retries={"mode": "standard", "max_attempts": 0},
            ),
        ).get_caller_identity()
        result["account_masked"] = _mask_account(identity.get("Account"))
        result["checks"].append(
            {
                "name": "AWS credential resolution",
                "status": "PASS",
                "detail": f"STS identity resolved for account {result['account_masked']}",
            }
        )

        client = session.client(
            "freetier",
            region_name=region,
            config=Config(
                connect_timeout=10,
                read_timeout=30,
                retries={"mode": "standard", "max_attempts": 0},
            ),
        )
        plan = client.get_account_plan_state()
        plan_credits = plan.get("accountPlanRemainingCredits") or {}
        remaining_amount = plan_credits.get("amount")
        try:
            remaining_numeric = float(remaining_amount)
        except (TypeError, ValueError):
            remaining_numeric = -1.0
        result["account_plan"] = {
            "type": plan.get("accountPlanType", "UNAVAILABLE"),
            "status": plan.get("accountPlanStatus", "UNAVAILABLE"),
            "remaining_credits_amount": remaining_amount,
            "remaining_credits_unit": plan_credits.get("unit", "UNAVAILABLE"),
            "expiration": _serialize_datetime(
                plan.get("accountPlanExpirationDate", "UNAVAILABLE")
            ),
        }
        plan_active = (
            result["account_plan"]["type"] == "FREE"
            and result["account_plan"]["status"] == "ACTIVE"
            and remaining_numeric > 0
        )
        result["checks"].append(
            {
                "name": "Free account plan state",
                "status": "PASS" if plan_active else "FAIL",
                "detail": (
                    f"{result['account_plan']['type']} / {result['account_plan']['status']} with "
                    f"{remaining_amount} {plan_credits.get('unit', '')} remaining"
                ),
            }
        )

        usage = client.get_free_tier_usage(maxResults=max_results)
        usage_rows = usage.get("freeTierUsages") or []
        result["free_tier_usage_count"] = len(usage_rows)
        result["free_tier_usage_services"] = sorted(
            {
                str(row.get("service"))
                for row in usage_rows
                if row.get("service")
            }
        )
        result["free_tier_usage_paginated"] = bool(usage.get("nextToken"))
        result["checks"].append(
            {
                "name": "Free Tier API read",
                "status": "PASS",
                "detail": (
                    f"read {len(usage_rows)} usage row(s); pagination token present: "
                    f"{bool(usage.get('nextToken'))}"
                ),
            }
        )
        result["coverage_status"] = "FREE_PLAN_ACTIVE" if plan_active else "NOT_PROVEN"
        result["status"] = "PASS" if plan_active and not usage.get("nextToken") else "FAIL"
    except Exception as error:
        result["error"] = _redact(f"{type(error).__name__}: {error}")
        result["checks"].append(
            {
                "name": "AWS Free Tier coverage",
                "status": "BLOCKED",
                "detail": result["error"],
            }
        )

    if write_evidence:
        _write_evidence(result)
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile", default=os.environ.get("AWS_PROFILE"))
    parser.add_argument("--region", default=None)
    parser.add_argument("--max-results", type=int, default=DEFAULT_MAX_RESULTS)
    parser.add_argument("--write-evidence", action="store_true")
    args = parser.parse_args()
    result = run(
        profile=args.profile,
        region=_region_from_args(args.region),
        max_results=args.max_results,
        write_evidence=args.write_evidence,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    if args.write_evidence:
        print(f"Evidence: {EVIDENCE_PATH}")
    return 0 if result["status"] == "PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
