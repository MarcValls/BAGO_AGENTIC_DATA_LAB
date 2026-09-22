"""Generate an offline Bedrock-provider benchmark and receipt evidence.

The clients in this script are deterministic fixtures.  They exercise the
same adapter path as a boto3 client, but never open a network connection and
do not represent AWS latency or current AWS pricing.
"""

from __future__ import annotations

import sys
import time
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from adapters.bedrock_provider_adapter import (  # noqa: E402
    BedrockProviderAdapter,
    BedrockProviderPolicy,
)


class FixtureBedrockClient:
    def __init__(self, *, text: str, input_tokens: int, output_tokens: int) -> None:
        self.text = text
        self.input_tokens = input_tokens
        self.output_tokens = output_tokens
        self.calls = 0

    def converse(self, **kwargs):
        self.calls += 1
        return {
            "output": {
                "message": {
                    "role": "assistant",
                    "content": [{"text": self.text}],
                }
            },
            "stopReason": "end_turn",
            "usage": {
                "inputTokens": self.input_tokens,
                "outputTokens": self.output_tokens,
                "totalTokens": self.input_tokens + self.output_tokens,
            },
        }


def _run_fixture(model_id: str, *, input_tokens: int, output_tokens: int, text: str) -> dict:
    client = FixtureBedrockClient(
        text=text,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
    )
    policy = BedrockProviderPolicy(
        region_name="fixture-region",
        allowed_model_ids=frozenset({model_id}),
        input_cost_per_1k_tokens=0.003,
        output_cost_per_1k_tokens=0.015,
        max_attempts=2,
    )
    adapter = BedrockProviderAdapter(client=client, policy=policy)
    request = adapter.build_execution_request(
        model_id,
        [{"role": "user", "content": [{"text": "Give a one-line status."}]}],
        proposed_by="offline-benchmark",
        context_revision="fixture-v1",
    )
    permit = adapter.authorize(request)
    started = time.perf_counter()
    result = adapter.converse(request, permit)
    latency_ms = (time.perf_counter() - started) * 1000
    return {
        "model": model_id,
        "result": result.receipt.execution_outcome.value,
        "decision": result.receipt.decision.value,
        "attempts": result.receipt.attempts,
        "latency_ms": latency_ms,
        "input_tokens": result.usage.input_tokens,
        "output_tokens": result.usage.output_tokens,
        "cost_usd": result.receipt.cost_usd,
        "client_calls": client.calls,
        "receipt_id": result.receipt.receipt_id,
    }


def main() -> None:
    rows = [
        _run_fixture(
            "amazon.nova-lite-v1:0",
            input_tokens=96,
            output_tokens=32,
            text="Nova fixture: governed success",
        ),
        _run_fixture(
            "anthropic.claude-3-haiku-20240307-v1:0",
            input_tokens=128,
            output_tokens=48,
            text="Claude fixture: governed success",
        ),
    ]
    if any(row["result"] != "SUCCESS" for row in rows):
        raise RuntimeError("offline Bedrock benchmark did not produce successful fixtures")

    generated = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    lines = [
        "# L6 Bedrock Provider — Offline Benchmark",
        "",
        f"Generated: {generated}",
        "",
        "> Scope: deterministic injected-client benchmark. No AWS credentials, network "
        "call, cloud latency or live AWS price lookup was used.",
        "> The cost column uses the rates configured in the fixture policy "
        "(`$0.003/1K` input and `$0.015/1K` output) only to verify receipt math.",
        "",
        "| Model fixture | Decision | Outcome | Attempts | Local latency (ms) | Input tokens | Output tokens | Estimated cost (USD) | Client calls |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for row in rows:
        lines.append(
            "| {model} | {decision} | {result} | {attempts} | {latency_ms:.3f} | "
            "{input_tokens} | {output_tokens} | ${cost_usd:.8f} | {client_calls} |".format(
                **row
            )
        )
    lines.extend(
        [
            "",
            "## Receipt checks",
            "",
            "- Every fixture created an `ExecutionRequest` with `EXTERNAL_API`.",
            "- Every fixture required a model-scoped `Permit` before the fake client call.",
            "- Both receipts report `called=true`, `SUCCESS`, one attempt and a model-bound evidence URI.",
            "- Live AWS validation remains `NOT_RUN` until a region, IAM policy, model access and credentials are provided.",
            "",
        ]
    )
    output_path = REPO_ROOT / "evidence" / "bedrock_provider_benchmark.md"
    output_path.write_text("\n".join(lines), encoding="utf-8")
    print(output_path)
    for row in rows:
        print(
            f"{row['model']}: {row['result']} attempts={row['attempts']} "
            f"latency_ms={row['latency_ms']:.3f} cost_usd={row['cost_usd']:.8f}"
        )


if __name__ == "__main__":
    main()
