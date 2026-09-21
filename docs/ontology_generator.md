# Ontology generator — governed induction

The LAB now distinguishes the ontology model from the generator that proposes
an ontology from documentation.

```text
documents
  → metadata generator       (L1: fields and concepts)
  → relation extractor       (L2: explicit relation proposals)
  → ontology validator       (L3: endpoints, confidence, duplicates, cycles)
  → human/contract decision
  → accepted ontology graph
```

The current implementation is deterministic and rule-based. It does not call
an LLM. That is deliberate: an eventual LLM-assisted extractor must enter at
the same `RelationProposal` boundary and cannot write directly to the accepted
`KnowledgeGraph`.

## Levels

### L1 — metadata generator

`MetadataGenerator` creates stable `Source` and `KnowledgeAsset` records from
UTF-8 Markdown/text. It extracts title, version, explicit authority markers,
classification, provenance, content hash, and known domain concepts.

Authority is conservative: a generic mention of “evidence” does not promote a
document. `CANONICAL` and `VERIFIED` require explicit metadata markers.

### L2 — relation extractor

`RelationExtractor` recognizes explicit Spanish and English statements such as:

```text
Contract IMPLEMENTS Component
Permiso AUTORIZA Ejecución
Execution GENERATES Evidence
Provider SERVES Model
```

Each result is a `RelationProposal` with confidence, evidence text, and
`PROPOSED` status. A proposal is not an accepted relation.

### L3 — ontology validator

`OntologyValidator` checks that endpoints exist, confidence is sufficient,
relations are not duplicated, and `DERIVED_FROM` cycles are rejected. Only an
explicit call to `accept()` builds a graph containing the accepted relations;
the CLI below stops before persistence so a human or contract-level decision
can review the proposal first.

## Commands

Generate a review artifact from the lab's design documents:

```bash
python scripts/generate_ontology_proposal.py
```

Use selected documents and an explicit output path:

```bash
python scripts/generate_ontology_proposal.py \
  LAB_CONTRACT.md ARCHITECTURE.md \
  --output evidence/ontology_proposal.md
```

The resulting Markdown reports candidate entities, explicit relation
proposals, rule-pass/rejection results, and the governance boundary. It does
not silently promote proposals into the canonical graph.
