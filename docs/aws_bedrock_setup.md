# AWS Bedrock Provider (L6)

This lab uses an adapter boundary around the Amazon Bedrock Runtime `Converse`
and `ConverseStream` operations.  Bedrock provides the inference capability;
BAGO remains responsible for the request, permit, execution and receipt.

The implementation is intentionally optional: importing the adapter does not
require `boto3`, and all repository tests inject a client double.  A live call
is a separate validation step and is currently `NOT_RUN` in this repository.

## Contract

```text
model/messages
    → ExecutionRequest(effect=EXTERNAL_API)
    → model allowlist + timeout/retry/quota policy
    → Permit bound to request_id and model_id
    → boto3 bedrock-runtime.converse/converse_stream
    → BedrockCallReceipt(usage, cost, attempts, error taxonomy)
```

`BedrockProviderAdapter` does not invoke a client when the permit is missing,
expired, mismatched, denied, or outside the configured model allowlist.

## Local/offline validation

No AWS dependency is needed for the tests:

```powershell
python -m pytest tests/test_bedrock_integration.py -v
python scripts/benchmark_bedrock_provider.py
```

The benchmark writes
[`evidence/bedrock_provider_benchmark.md`](../evidence/bedrock_provider_benchmark.md).
Its latency is local fixture latency and its cost uses explicit fixture rates;
neither is an AWS production measurement.

## Optional SDK setup

Install the provider SDK in the environment that will make the live call:

```powershell
python -m pip install boto3
$env:AWS_REGION = "eu-west-1"
$env:AWS_PROFILE = "your-profile"
```

Prefer short-lived role credentials, SSO or another standard AWS credential
provider.  Do not commit access keys, profiles, `.env` files or tokens.

The adapter creates a `bedrock-runtime` client with explicit connect/read
timeouts and disables SDK-level retry multiplication; the adapter owns the
bounded retry budget and classifies throttling, timeout, network,
authorization and validation failures.

## IAM and model access

Start with a customer-managed policy scoped to the models and region required
by the experiment.  For Converse, AWS documents the inference permission as
`bedrock:InvokeModel`; streaming also needs the corresponding streaming
inference permission.  A minimal starting shape is:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "ConverseOnlyForApprovedModels",
      "Effect": "Allow",
      "Action": [
        "bedrock:InvokeModel",
        "bedrock:InvokeModelWithResponseStream"
      ],
      "Resource": [
        "arn:aws:bedrock:eu-west-1::foundation-model/APPROVED_MODEL_ID"
      ]
    }
  ]
}
```

The exact resource form depends on the model or inference profile.  Confirm
model access is enabled in the target region and validate the policy against
the current AWS service authorization reference before granting it.  Avoid
`bedrock:*` for this provider test.

## Runtime policy

Configure an explicit `allowed_model_ids` set for production-like use:

```python
from adapters.bedrock_provider_adapter import (
    BedrockProviderAdapter,
    BedrockProviderPolicy,
)

policy = BedrockProviderPolicy(
    region_name="eu-west-1",
    allowed_model_ids=frozenset({"amazon.nova-lite-v1:0"}),
    timeout_seconds=30,
    max_attempts=3,
    max_calls_per_window=30,
    input_cost_per_1k_tokens=0.0,   # configure from an approved price source
    output_cost_per_1k_tokens=0.0,
)
adapter = BedrockProviderAdapter(policy=policy)
```

The local quota is a guardrail, not a replacement for AWS account/model
quotas.  Cost receipts are estimates based on the response `usage` fields and
the configured rates; they are not billing records.

## Bounded live runner

The checkout includes `scripts/run_l6_aws_live_validation.py`. It performs an
STS-only preflight by default. A real inference call requires the explicit
`--execute` flag and is bounded to one `Converse` request, one retry budget,
`maxTokens <= 64` and a model allowlist. The runner never writes credentials or
response text to evidence.

```powershell
python -m pip install boto3
python scripts/run_l6_aws_live_validation.py
python scripts/run_l6_aws_live_validation.py --execute --region us-east-1 --model-id amazon.nova-lite-v1:0
```

The preflight proves only that STS credentials resolve. The `--execute` command
is the real AWS call and must be treated as potentially billable; free-tier
credits/account state are checked separately in AWS Billing. Evidence is written
to `evidence/l6_aws_live.md` only after an explicit live attempt.

## Live validation checklist

The following is deliberately separate from the offline test result:

- [ ] `boto3` installed in the target runtime
- [ ] AWS region selected and model access enabled
- [ ] Short-lived credentials resolve for the intended profile or role
- [ ] IAM policy permits only the approved inference operation/model
- [ ] One non-streaming `Converse` call produces a successful receipt
- [ ] One `ConverseStream` call produces a successful receipt
- [ ] Throttling/timeout behavior is observed against the real account without exceeding the budget
- [ ] Real latency and current price evidence is recorded separately from the fixture benchmark

Until these checks are run, L6 is `VERIFIED` for the local governed adapter
scope, not `VALIDATED` for AWS production connectivity.
