# L6 · AWS Bedrock live evidence

Generated: 2026-10-17T23:05:20.283811+00:00

> Scope: one explicit Amazon Bedrock Converse call through the governed BAGO adapter.
> The runner uses a model allowlist, one call, maxTokens <= 64 and SDK retries disabled.
> Credentials, tokens and response text are not written to this artifact.

- Region: `us-east-1`
- Model ID: `amazon.nova-lite-v1:0`
- AWS account: `6100…13`
- Principal kind: `root`
- Git HEAD observed: `7fc350044df596a0e3eff751c62b423f70885e16`
- Worktree dirty at execution: `True`
- boto3 version: `1.43.101`
- Free-tier/billing status: `AWS account credit or billing state is not returned by Bedrock; verify it in AWS Billing`
- Overall result: **FAIL**

## Acceptance checks

| Check | Result | Detail |
|---|---:|---|
| AWS credential resolution | PASS | STS identity resolved for account 6100…13 |
| Bedrock Converse | FAIL | ThrottlingException: An error occurred (ThrottlingException) when calling the Converse operation (reached max retries: 0): Too many tokens per day, please wait before trying again. |

## Governed receipt

```json
{
  "actual_effect": {
    "attempts": 1,
    "called": true,
    "model_id": "amazon.nova-lite-v1:0",
    "operation": "converse",
    "provider": "aws.bedrock"
  },
  "attempts": 1,
  "cost_usd": 0.0,
  "decision": "ALLOW",
  "duration_ms": 1050,
  "error_kind": "THROTTLE",
  "error_message": "ThrottlingException: An error occurred (ThrottlingException) when calling the Converse operation (reached max retries: 0): Too many tokens per day, please wait before trying again.",
  "evidence_refs": [
    "bedrock://us-east-1/amazon.nova-lite-v1:0/converse#request=bedrock_req_02c0a6633f6deb09"
  ],
  "execution_outcome": "FAILURE",
  "model_id": "amazon.nova-lite-v1:0",
  "operation": "converse",
  "permit_id": "bedrock_permit_234cb562d5c39041",
  "receipt_id": "bedrock_receipt_2713f1a932f5c4a6",
  "request_id": "bedrock_req_02c0a6633f6deb09",
  "usage": {
    "input_tokens": 0,
    "output_tokens": 0,
    "total_tokens": 0
  }
}
```

## Failure detail

`ThrottlingException: An error occurred (ThrottlingException) when calling the Converse operation (reached max retries: 0): Too many tokens per day, please wait before trying again.`

## Boundary

This proves one live Bedrock call for the configured account, region and model scope. It does not prove zero billing, free-tier eligibility after the call, streaming, Knowledge Bases, production latency or production readiness.
