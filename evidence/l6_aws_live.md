# L6 · AWS Bedrock live evidence

Generated: 2026-09-23T23:49:32.379193+00:00

> Scope: one explicit Amazon Bedrock Converse call through the governed BAGO adapter.
> The runner uses a model allowlist, one call, maxTokens <= 64 and SDK retries disabled.
> Credentials, tokens and response text are not written to this artifact.

- Region: `us-east-1`
- Model ID: `amazon.nova-lite-v1:0`
- AWS account: `6100…13`
- Principal kind: `root`
- Git HEAD observed: `2f9f7efcfbb2edcc8deebc7bdfac5cf86a015a91`
- Worktree dirty at execution: `False`
- boto3 version: `1.43.101`
- Free-tier/billing status: `AWS account credit or billing state is not returned by Bedrock; verify it in AWS Billing`
- Overall result: **PASS**

## Acceptance checks

| Check | Result | Detail |
|---|---:|---|
| AWS credential resolution | PASS | STS identity resolved for account 6100…13 |
| Bedrock Converse | PASS | one live call; 41 total tokens |

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
  "duration_ms": 1153,
  "error_kind": null,
  "error_message": null,
  "evidence_refs": [
    "bedrock://us-east-1/amazon.nova-lite-v1:0/converse#request=bedrock_req_02c0a6633f6deb09"
  ],
  "execution_outcome": "SUCCESS",
  "model_id": "amazon.nova-lite-v1:0",
  "operation": "converse",
  "permit_id": "bedrock_permit_234cb562d5c39041",
  "receipt_id": "bedrock_receipt_6bd83e150030f5ec",
  "request_id": "bedrock_req_02c0a6633f6deb09",
  "usage": {
    "input_tokens": 9,
    "output_tokens": 32,
    "total_tokens": 41
  }
}
```

## Boundary

This proves one live Bedrock call for the configured account, region and model scope. It does not prove zero billing, free-tier eligibility after the call, streaming, Knowledge Bases, production latency or production readiness.
