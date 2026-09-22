# Bedrock Knowledge Base (L7)

L7 studies the managed retrieval option for the Devoteam target while keeping
BAGO's local ETL/RAG path as the comparison baseline.

Amazon Bedrock Knowledge Bases expose two different application paths:

- `Retrieve` returns ranked source chunks/references. BAGO can assemble the
  context, apply its own authority rules and decide how to answer.
- `RetrieveAndGenerate` combines retrieval with model generation and returns
  citations. The generated answer is still an external provider result and
  must remain behind the BAGO permit/receipt boundary.

The adapter uses the `bedrock-agent-runtime` client. It is optional at import
time and accepts an injected client for offline tests.

## Contract

```text
query + knowledge_base_id
    → ExecutionRequest(effect=EXTERNAL_API)
    → KB allowlist + metadata filter + result/quota limits
    → Permit bound to request_id and knowledge_base_id
    → bedrock-agent-runtime.retrieve / retrieve_and_generate
    → normalized references/citations + BedrockKBReceipt
```

No query reaches the client when the permit is absent, expired, mismatched,
denied or outside the configured Knowledge Base allowlist.

## Local validation

```powershell
python -m pytest tests/test_bedrock_kb_adapter.py -v
python scripts/compare_bago_etl_vs_bedrock_kb.py
```

The comparison writes
[`evidence/bago_etl_vs_bedrock_kb_comparison.md`](../evidence/bago_etl_vs_bedrock_kb_comparison.md).
It uses one query through the 65-chunk local ETL/RAG corpus and an injected
Bedrock-shaped fixture built from the same labelled references. The overlap
proves citation normalization and the adapter contract; it is not a claim of
equal cloud ranking quality.

## AWS shape and data lifecycle

For a real Knowledge Base, the data must be available through a supported
connector, embeddings must be configured, and a vector store must be selected.
An ingestion job brings the source data into the Knowledge Base. A typical
operational sequence is:

```text
source connector / S3
    → ingestion job
    → embeddings + vector store
    → Retrieve or RetrieveAndGenerate
    → source citations
```

Metadata filters are sent as the Bedrock vector-search filter shape, for
example `equals`, `andAll` or `orAll`. The adapter preserves those fields and
records the returned source URI, metadata, score and stable chunk identifier.

## IAM boundary

There are two distinct IAM roles to configure:

1. The caller needs permission to query/manage the Knowledge Base, scoped to
   the intended Knowledge Base ARN.
2. The Bedrock Knowledge Base service role needs access to the data source,
   embedding model and vector store. For an S3 source this normally includes
   narrowly scoped `s3:ListBucket` and `s3:GetObject`, plus KMS permissions when
   encryption is used.

For a retrieval-only application, start with the smallest current
`bedrock:Retrieve` permission. Add the generation operation and foundation
model access only when using `RetrieveAndGenerate`. Management permissions
(`CreateKnowledgeBase`, ingestion-job operations and updates) belong to a
separate setup role, not to the runtime query principal.

AWS changes supported stores, managed Knowledge Base behavior and IAM action
details over time. Re-check the current AWS permission pages before applying
an account policy; do not use `bedrock:*` for this experiment.

## Configuration example

```python
from adapters.bedrock_kb_adapter import BedrockKnowledgeBaseAdapter
from adapters.bedrock_kb_adapter import BedrockKnowledgeBasePolicy

policy = BedrockKnowledgeBasePolicy(
    region_name="eu-west-1",
    knowledge_base_id="KB_ID_FROM_AWS",
    allowed_knowledge_base_ids=frozenset({"KB_ID_FROM_AWS"}),
    generation_model_arn="MODEL_ARN_FROM_AWS",
    max_results=5,
    default_search_type="HYBRID",
    max_attempts=3,
)
adapter = BedrockKnowledgeBaseAdapter(policy=policy)
request = adapter.build_request(
    "Which permits authorize external execution?",
    proposed_by="bago.agent",
    context_revision="ctx-v1",
    operation="retrieve_and_generate",
)
permit = adapter.authorize(request)
result = adapter.retrieve_and_generate(request, permit)
```

The result contains a normalized answer, source hits/citations and a receipt.
Cost is zero unless an approved local estimate is configured; the receipt is
not an AWS billing record.

## Live validation checklist

- [ ] AWS region selected and Knowledge Base created
- [ ] Source connector and vector store configured
- [ ] Ingestion job completed successfully
- [ ] Caller IAM policy scoped to the Knowledge Base and operation
- [ ] Bedrock service role can read the source and access embeddings/vector store
- [ ] Model access approved for `RetrieveAndGenerate`
- [ ] One real `Retrieve` call produces citations
- [ ] One real `RetrieveAndGenerate` call produces answer plus citations
- [ ] Metadata filter behavior and superseded-document policy are checked against the live corpus
- [ ] Cloud latency and current AWS pricing are recorded separately

Current L7 status is `VERIFIED` for the offline governed adapter and fixture
comparison. Live AWS Knowledge Base connectivity remains `NOT_RUN`.
