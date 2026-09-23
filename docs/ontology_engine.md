# L10 · Governed Ontology Engine

L10 adds a reasoning boundary after governed retrieval:

```text
question
  → GovernedRAG (eligible chunks + citations)
  → OntologyEngine (RDF graph + SPARQL + inference)
  → paths, supersession, dependencies, contradictions and constraints
  → evidence-bearing context
  → optional LLM generation
```

The engine is local and dependency-free. It is intentionally a bounded
portfolio implementation, not a claim that this repository contains a complete
RDF database or a complete W3C SPARQL implementation.

## Contract

`OntologyEngine.from_knowledge_graph()` materializes the existing L3
`KnowledgeGraph` into `RDFGraph` triples. Asset provenance becomes evidence on
the generated triples; relation endpoints remain governed by the L3 graph.

The engine then applies deterministic rules:

- inverse: `supersedes → supersededBy`, `validates → validatedBy`, and the
  other declared relation inverses;
- transitive closure: `derivedFrom`, `supersedes` and `requires`;
- symmetric closure: `contradicts` and `conflictsWith`;
- constraints: broken endpoints, missing relation evidence and explicit
  contradictions.

The input graph is not mutated. Inferred triples are marked with their rule and
carry the union of the evidence references that supported the inference.

## Local SPARQL subset

`OntologyEngine.select()` supports:

- `PREFIX` declarations;
- `SELECT` and `SELECT DISTINCT` projections;
- triple-pattern joins;
- `FILTER regex(str(?variable), "pattern", "i")`;
- `FILTER (?variable = term)`;
- `LIMIT`.

Example:

```sparql
PREFIX bago: <https://bago.local/ontology/>
SELECT ?current ?previous
WHERE {
  ?current bago:supersedes ?previous .
}
LIMIT 20
```

The supported subset is deliberately visible in the receipt and can later be
replaced by an adapter for a real local triplestore without changing the BAGO
evidence boundary.

## Agent boundary

When an `OntologyEngine` is injected into `GovernedKnowledgeAgent`, retrieval
seeds the graph with chunk/entity identity and citations. The resulting paths,
constraints, receipt and evidence references are appended to the governed LLM
context. A constraint with severity `ERROR` changes the agent run to
`CONSTRAINT_VIOLATION`; the LLM output is not promoted to a clean completion.

## Reproduction

```bash
python -m pytest tests/test_l10_ontology_engine.py -q
python scripts/generate_l10_ontology_evidence.py
```

The generated receipt is `evidence/l10_ontology_engine.md`. This L10 run uses
an injected Bedrock-shaped fixture solely to prove that the graph result reaches
the provider context; AWS remains `NOT_RUN`, while the separate local
OpenMetadata validation is recorded in `evidence/l8_openmetadata_live.md`.
OpenMetadata remote validation remains `NOT_RUN`.
