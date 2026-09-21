# L6 Bedrock Provider — Offline Benchmark

Generated: 2026-09-21 23:54:57 UTC

> Scope: deterministic injected-client benchmark. No AWS credentials, network call, cloud latency or live AWS price lookup was used.
> The cost column uses the rates configured in the fixture policy (`$0.003/1K` input and `$0.015/1K` output) only to verify receipt math.

| Model fixture | Decision | Outcome | Attempts | Local latency (ms) | Input tokens | Output tokens | Estimated cost (USD) | Client calls |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| amazon.nova-lite-v1:0 | ALLOW | SUCCESS | 1 | 0.071 | 96 | 32 | $0.00076800 | 1 |
| anthropic.claude-3-haiku-20240307-v1:0 | ALLOW | SUCCESS | 1 | 0.046 | 128 | 48 | $0.00110400 | 1 |

## Receipt checks

- Every fixture created an `ExecutionRequest` with `EXTERNAL_API`.
- Every fixture required a model-scoped `Permit` before the fake client call.
- Both receipts report `called=true`, `SUCCESS`, one attempt and a model-bound evidence URI.
- Live AWS validation remains `NOT_RUN` until a region, IAM policy, model access and credentials are provided.
