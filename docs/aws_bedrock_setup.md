# AWS Bedrock Provider (L6)

This lab uses an adapter boundary around the Amazon Bedrock Runtime `Converse`
and `ConverseStream` operations.  Bedrock provides the inference capability;
BAGO remains responsible for the request, permit, execution and receipt.

The implementation is intentionally optional: importing the adapter does not
require `boto3`, and all repository tests inject a client double. One bounded
live `Converse` call is now recorded in
[`evidence/l6_aws_live.md`](../evidence/l6_aws_live.md). A separate read-only
Free Tier account-plan check is recorded in
[`evidence/l6_aws_free_tier.md`](../evidence/l6_aws_free_tier.md); streaming,
managed Knowledge Bases and invoice-level billing remain separate scopes.

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

With AWS CLI 2.32 or newer, the local-development login flow can use the
existing AWS Management Console session and issue temporary credentials
without asking for a long-lived access key.  The installed CLI in the
reference environment is 2.37.0:

```powershell
$env:AWS_REGION = "us-east-1"
& "C:\Program Files\Amazon\AWSCLIV2\aws.exe" login --profile bago-free --region $env:AWS_REGION
& "C:\Program Files\Amazon\AWSCLIV2\aws.exe" sts get-caller-identity --profile bago-free --no-cli-pager
$env:AWS_PROFILE = "bago-free"
```

The first command opens a browser for the account holder to authenticate.
It requires an existing AWS account; it does not create a free-tier account
or prove that the next inference is bill-free.  If the account uses IAM
Identity Center, use `aws configure sso` followed by `aws sso login` instead.
See the [AWS CLI local-development login guide](https://docs.aws.amazon.com/cli/latest/userguide/cli-configure-sign-in.html).

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
python -m pip install "botocore[crt]" boto3
python scripts/run_l6_aws_live_validation.py --profile bago-free --region us-east-1
python scripts/run_l6_aws_live_validation.py --profile bago-free --execute --region us-east-1 --model-id amazon.nova-lite-v1:0
```

The preflight proves only that STS credentials resolve. The `--execute` command
is the real AWS call and must be treated as potentially billable. Account-plan
coverage is checked separately with the read-only Free Tier API; evidence is
written to `evidence/l6_aws_live.md` only after an explicit live attempt.

## Free Tier account coverage (read-only)

The checkout includes `scripts/run_l6_aws_free_tier_validation.py`. It performs
only STS identity resolution, `GetAccountPlanState` and one bounded
`GetFreeTierUsage` read. It does not create resources, invoke Bedrock or call
Cost Explorer. The latter is intentionally excluded because AWS prices each
Cost Explorer API request at USD 0.01.

```powershell
python scripts/run_l6_aws_free_tier_validation.py --profile bago-free --region us-east-1 --write-evidence
```

The current evidence observes an active `FREE` account plan with USD 100.00
remaining and zero returned Free Tier usage rows. That proves account-plan
coverage at the observation time, not a zero-dollar invoice for the earlier
Bedrock call; the latter remains `NOT_PROVEN` without a later billing record.

## Live validation checklist

The following is deliberately separate from the offline test result:

- [x] `boto3` and `botocore[crt]` installed in the target runtime
- [x] AWS region selected and model access enabled for `amazon.nova-lite-v1:0`
- [x] Short-lived credentials resolve for the intended profile or role
- [ ] IAM policy permits only the approved inference operation/model
- [x] One non-streaming `Converse` call produces a successful receipt
- [x] Read-only Free Tier API observes an active `FREE` plan with remaining credits
- [ ] One `ConverseStream` call produces a successful receipt
- [ ] A later billing record confirms a zero-dollar charge for the call
- [ ] Throttling/timeout behavior is observed against the real account without exceeding the budget
- [ ] Real latency and current price evidence is recorded separately from the fixture benchmark

L6 is now `VERIFIED` for the local governed adapter, the bounded live
`Converse` scope and the observed Free account-plan coverage. It is not
`VALIDATED` for AWS production connectivity, least-privilege IAM, streaming,
managed Knowledge Bases or zero billing.
