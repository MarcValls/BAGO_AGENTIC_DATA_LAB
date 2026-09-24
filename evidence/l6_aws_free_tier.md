# L6 · AWS Free Tier account coverage evidence

Generated: 2026-09-24T00:13:08.299947+00:00

> Scope: read-only AWS Free Tier account-plan and usage inspection.
> No resource was created, no model was invoked and Cost Explorer was not queried.
> Credentials, account IDs and pagination tokens are not written to this artifact.

- Region: `us-east-1`
- AWS account: `6100…13`
- Git HEAD observed: `36f2641475467c27ce6f343ce493e54bf8076bcf`
- Worktree dirty at execution: `True`
- Account plan: `FREE`
- Account plan status: `ACTIVE`
- Remaining plan credits: `100.0 USD`
- Plan expiration: `2027-03-23T23:38:39.486000+00:00`
- Free Tier usage rows returned: `0`
- Cost Explorer query: `NOT_RUN`
- Coverage conclusion: **FREE_PLAN_ACTIVE**
- Zero-billing conclusion: **NOT_PROVEN**
- Overall result: **PASS**

## Acceptance checks

| Check | Result | Detail |
|---|---:|---|
| AWS credential resolution | PASS | STS identity resolved for account 6100…13 |
| Free account plan state | PASS | FREE / ACTIVE with 100.0 USD remaining |
| Free Tier API read | PASS | read 0 usage row(s); pagination token present: False |

## Boundary

This proves that the observed account had an active AWS Free account plan and remaining credits at validation time. An empty Free Tier usage list is an observation, not proof that all usage is free. It does not prove that the Bedrock call generated a zero-dollar invoice; billing data can settle later. Cost Explorer was intentionally not called because its API is priced per request.

References: [AWS Free Tier API](https://docs.aws.amazon.com/awsaccountbilling/latest/aboutv2/using-free-tier-api.html); [AWS Cost Explorer pricing](https://aws.amazon.com/aws-cost-management/aws-cost-explorer/pricing/).

## Stable summary

```json
{
  "account_masked": "6100…13",
  "account_plan": {
    "expiration": "2027-03-23T23:38:39.486000+00:00",
    "remaining_credits_amount": 100.0,
    "remaining_credits_unit": "USD",
    "status": "ACTIVE",
    "type": "FREE"
  },
  "checks": [
    {
      "detail": "STS identity resolved for account 6100…13",
      "name": "AWS credential resolution",
      "status": "PASS"
    },
    {
      "detail": "FREE / ACTIVE with 100.0 USD remaining",
      "name": "Free account plan state",
      "status": "PASS"
    },
    {
      "detail": "read 0 usage row(s); pagination token present: False",
      "name": "Free Tier API read",
      "status": "PASS"
    }
  ],
  "cost_explorer": "NOT_RUN",
  "coverage_status": "FREE_PLAN_ACTIVE",
  "error": null,
  "free_tier_usage_count": 0,
  "free_tier_usage_paginated": false,
  "free_tier_usage_services": [],
  "region": "us-east-1",
  "status": "PASS",
  "zero_billing_status": "NOT_PROVEN"
}
```
