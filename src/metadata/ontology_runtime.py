"""Bounded local proposal, approval and evidence-backed ontology runtime."""
from __future__ import annotations

import hashlib
import json
import os
import sqlite3
import uuid
from dataclasses import asdict
from pathlib import Path, PurePosixPath
from typing import Any

from src.agent_tools.workspace_read import MAX_FILE_BYTES, _blocked_path_parts, normalize_workspace_path
from src.metadata.ontology import KnowledgeGraph, OntologyRelation, RelationType
from src.metadata.ontology_engine import OntologyEngine
from src.metadata.ontology_generator import OntologyGenerator, OntologyValidator
from src.metadata.schema import AuthorityLevel, KnowledgeAsset, Source


class OntologyRuntimeError(ValueError):
    """A bounded ontology operation failed closed."""


def _db_path() -> Path:
    override = os.environ.get("ADL_ONTOLOGY_DB")
    if override:
        return Path(override).expanduser().resolve()
    from src.storage.portable import configured_path
    return configured_path("ADL_ONTOLOGY_DB", "knowledge", "ontology.sqlite3")


def _trace_dir() -> Path:
    override = os.environ.get("ADL_ONTOLOGY_TRACE_DIR")
    if override:
        return Path(override).expanduser().resolve()
    from src.storage.portable import configured_path
    return configured_path("ADL_ONTOLOGY_TRACE_DIR", "traces", "ontology")


def _connect() -> sqlite3.Connection:
    db = _db_path()
    db.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(db, timeout=5)
    connection.row_factory = sqlite3.Row
    connection.executescript("""
      CREATE TABLE IF NOT EXISTS ontology_proposals(
        proposal_id TEXT PRIMARY KEY, source_path TEXT NOT NULL, source_sha256 TEXT NOT NULL,
        payload TEXT NOT NULL, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP);
      CREATE TABLE IF NOT EXISTS ontology_accepted(
        proposal_id TEXT PRIMARY KEY, source_path TEXT NOT NULL, source_sha256 TEXT NOT NULL,
        payload TEXT NOT NULL, approval_receipt_id TEXT NOT NULL, accepted_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP);
      CREATE TABLE IF NOT EXISTS ontology_receipts(
        receipt_id TEXT PRIMARY KEY, kind TEXT NOT NULL, payload TEXT NOT NULL);
    """)
    return connection


def _read_source(workspace_root: Path, requested: str) -> tuple[str, bytes]:
    relative = normalize_workspace_path(requested)
    if relative is None:
        raise OntologyRuntimeError("path must be one workspace-relative file")
    parts = tuple(PurePosixPath(relative).parts)
    if _blocked_path_parts(parts) or Path(relative).suffix.casefold() not in {".md", ".txt"}:
        raise OntologyRuntimeError("only a workspace-relative Markdown or text file is accepted")
    root = workspace_root.resolve()
    path = root / Path(*parts)
    cursor = root
    try:
        for part in parts:
            cursor = cursor / part
            if cursor.is_symlink():
                raise OntologyRuntimeError("symlink paths are not accepted")
        target = path.resolve(strict=True)
        if not target.is_relative_to(root) or not target.is_file():
            raise OntologyRuntimeError("source must be a regular file inside the workspace")
        before = target.stat()
        if before.st_size > MAX_FILE_BYTES:
            raise OntologyRuntimeError("source exceeds the workspace read limit")
        with target.open("rb") as stream:
            opened = os.fstat(stream.fileno())
            raw = stream.read(MAX_FILE_BYTES + 1)
        after = target.stat()
        if len(raw) > MAX_FILE_BYTES or any((before.st_dev, before.st_ino, before.st_mtime_ns) != (item.st_dev, item.st_ino, item.st_mtime_ns) for item in (opened, after)):
            raise OntologyRuntimeError("source changed during read")
        raw.decode("utf-8")
    except (OSError, UnicodeDecodeError) as error:
        raise OntologyRuntimeError("source must be a readable UTF-8 file") from error
    if not raw.strip():
        raise OntologyRuntimeError("empty source is not accepted")
    return target.relative_to(root).as_posix(), raw


def _write_trace(kind: str, payload: dict[str, Any], *, trace_id: str | None = None) -> dict[str, str]:
    directory = _trace_dir()
    directory.mkdir(parents=True, exist_ok=True)
    trace_id = trace_id or "ontology_trace_" + uuid.uuid4().hex
    record = {"trace_id": trace_id, "kind": kind, **payload}
    raw = (json.dumps(record, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode("utf-8")
    path = directory / f"{trace_id}.json"
    try:
        with path.open("xb") as stream:
            stream.write(raw)
    except OSError as error:
        raise OntologyRuntimeError("trace persistence failed") from error
    return {"trace_id": trace_id, "path": str(path), "sha256": hashlib.sha256(raw).hexdigest()}


def propose(workspace_root: Path, requested: str) -> dict[str, Any]:
    path, raw = _read_source(workspace_root, requested)
    content = raw.decode("utf-8")
    source_hash = hashlib.sha256(raw).hexdigest()
    proposal = OntologyGenerator().generate([(path, content)])
    report = OntologyValidator().validate(proposal)
    valid = {item.proposal_id: item for item in report.accepted}
    rejected = {item.proposal_id: item for item in report.rejected}
    entities = [{"id": item.asset_id, "label": item.title} for item in sorted(proposal.graph.assets.values(), key=lambda item: item.asset_id)]
    lines = content.splitlines()
    relations: list[dict[str, Any]] = []
    for candidate in proposal.relation_proposals:
        evidence_line = candidate.evidence_ref.rstrip("\r")
        line_number = next((index for index, line in enumerate(lines, 1) if line == evidence_line), None)
        status = "PASS" if candidate.proposal_id in valid else "FAIL"
        reason = None if status == "PASS" else rejected[candidate.proposal_id].rejection_reason
        payload = {
            "proposal_id": candidate.proposal_id, "type": candidate.relation.relation_type.value,
            "source_id": candidate.relation.source_id, "target_id": candidate.relation.target_id,
            "evidence": {"source_path": path, "source_sha256": source_hash, "line_number": line_number, "line": evidence_line},
            "validator": {"status": status, "reason": reason},
            "relation_id": candidate.relation.relation_id,
        }
        relations.append(payload)
    proposal_id = "ontology_proposal_" + uuid.uuid4().hex
    batch = {"proposal_id": proposal_id, "source_path": path, "source_sha256": source_hash, "entities": entities, "relations": relations}
    receipt_id = "ontology_receipt_" + uuid.uuid4().hex
    receipt_payload = {"receipt_id": receipt_id, "kind": "proposal", "proposal_id": proposal_id, "source_path": path, "source_sha256": source_hash, "candidate_count": len(relations)}
    try:
        with _connect() as conn:
            conn.execute("INSERT INTO ontology_proposals(proposal_id,source_path,source_sha256,payload) VALUES(?,?,?,?)", (proposal_id, path, source_hash, json.dumps(batch, sort_keys=True)))
            conn.execute("INSERT INTO ontology_receipts(receipt_id,kind,payload) VALUES(?,?,?)", (receipt_id, "proposal", json.dumps(receipt_payload, sort_keys=True)))
    except sqlite3.Error as error:
        raise OntologyRuntimeError("proposal persistence failed") from error
    trace = _write_trace("proposal", {**receipt_payload, "candidate_ids": [item["proposal_id"] for item in relations]})
    return {**batch, "source": {"path": path, "sha256": source_hash}, "receipt": {"receipt_id": receipt_id}, "trace": trace}


def approve(workspace_root: Path, proposal_id: str, selected_ids: list[str]) -> dict[str, Any]:
    if not selected_ids or len(selected_ids) != len(set(selected_ids)):
        raise OntologyRuntimeError("proposal_ids must be a non-empty unique list")
    with _connect() as conn:
        row = conn.execute("SELECT * FROM ontology_proposals WHERE proposal_id=?", (proposal_id,)).fetchone()
        if row is None:
            raise OntologyRuntimeError("unknown proposal batch")
        batch = json.loads(row["payload"])
        path, raw = _read_source(workspace_root, row["source_path"])
        if path != row["source_path"] or hashlib.sha256(raw).hexdigest() != row["source_sha256"]:
            raise OntologyRuntimeError("source revision is stale; generate proposals again")
        relation_by_id = {item["proposal_id"]: item for item in batch["relations"]}
        if any(item not in relation_by_id for item in selected_ids):
            raise OntologyRuntimeError("approval contains an unknown proposal ID")
        selected = [relation_by_id[item] for item in selected_ids]
        if any(item["validator"]["status"] != "PASS" for item in selected):
            raise OntologyRuntimeError("only validator-passing proposals may be approved")
        receipt_id = "ontology_receipt_" + uuid.uuid4().hex
        approval_trace_id = "ontology_trace_" + uuid.uuid4().hex
        accepted_payloads = {
            item["proposal_id"]: {
                **item,
                "entities": batch["entities"],
                "approval_receipt_id": receipt_id,
                "approval_trace_id": approval_trace_id,
            }
            for item in selected
        }
        fingerprint = _graph_fingerprint([
            (item["proposal_id"], path, row["source_sha256"], json.dumps(accepted_payloads[item["proposal_id"]], sort_keys=True))
            for item in selected
        ])
        trace = _write_trace(
            "approval",
            {"receipt_id": receipt_id, "proposal_id": proposal_id, "accepted_ids": selected_ids, "graph_fingerprint": fingerprint},
            trace_id=approval_trace_id,
        )
        receipt_payload = {
            "receipt_id": receipt_id,
            "trace_id": trace["trace_id"],
            "kind": "approval",
            "proposal_id": proposal_id,
            "accepted_ids": selected_ids,
            "graph_fingerprint": fingerprint,
        }
        try:
            conn.execute("BEGIN IMMEDIATE")
            for relation in selected:
                accepted_payload = accepted_payloads[relation["proposal_id"]]
                conn.execute("INSERT INTO ontology_accepted(proposal_id,source_path,source_sha256,payload,approval_receipt_id) VALUES(?,?,?,?,?)", (relation["proposal_id"], path, row["source_sha256"], json.dumps(accepted_payload, sort_keys=True), receipt_id))
            conn.execute("INSERT INTO ontology_receipts(receipt_id,kind,payload) VALUES(?,?,?)", (receipt_id, "approval", json.dumps(receipt_payload, sort_keys=True)))
            conn.commit()
        except sqlite3.Error as error:
            conn.rollback()
            raise OntologyRuntimeError("accepted graph persistence failed") from error
    return {"accepted_ids": selected_ids, "graph_fingerprint": fingerprint, "receipt": {"receipt_id": receipt_id}, "trace": trace}


def _graph_fingerprint(extra: list[tuple[str, str, str, str]] | None = None) -> str:
    with _connect() as conn:
        rows = conn.execute("SELECT proposal_id,source_path,source_sha256,payload FROM ontology_accepted ORDER BY proposal_id").fetchall()
    items = [(row["proposal_id"], row["source_path"], row["source_sha256"], row["payload"]) for row in rows]
    items.extend(extra or [])
    serialized = "\n".join("|".join(item) for item in sorted(items, key=lambda item: item[0]))
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def query(text: str) -> dict[str, Any]:
    if not text.strip() or len(text) > 2000:
        raise OntologyRuntimeError("query must contain 1 to 2000 characters")
    with _connect() as conn:
        rows = conn.execute("SELECT * FROM ontology_accepted ORDER BY proposal_id").fetchall()
    graph = KnowledgeGraph()
    source_ids: dict[tuple[str, str], str] = {}
    evidence_by_ref: dict[str, dict[str, Any]] = {}
    for row in rows:
        item = json.loads(row["payload"])
        source_key = (row["source_path"], row["source_sha256"])
        source_id = source_ids.get(source_key)
        if source_id is None:
            source_id = "source_" + hashlib.sha256((row["source_path"] + row["source_sha256"]).encode()).hexdigest()[:12]
            source_ids[source_key] = source_id
            graph.sources[source_id] = Source(source_id, row["source_path"], "FILE", metadata={"content_hash": row["source_sha256"]})
        for entity in item["entities"]:
            graph.assets.setdefault(entity["id"], KnowledgeAsset(entity["id"], entity["label"], "Concept extracted from a user-selected source", "CONCEPT", source_id, version=row["source_sha256"], authority=AuthorityLevel.PROPOSED, metadata={"provenance": row["source_path"], "content_hash": row["source_sha256"]}))
        ref = f"{row['source_path']}#sha256={row['source_sha256']}#line={item['evidence']['line_number']}"
        rel = OntologyRelation(item["relation_id"], RelationType(item["type"]), item["source_id"], item["target_id"], 0.95, metadata={"evidence": item["evidence"]["line"], "evidence_refs": [ref]})
        graph.relations.append(rel)
        evidence_by_ref[ref] = {
            **item["evidence"],
            "proposal_id": row["proposal_id"],
            "receipt_id": item.get("approval_receipt_id", row["approval_receipt_id"]),
            "trace_ref": item.get("approval_trace_id"),
        }
    engine = OntologyEngine.from_knowledge_graph(graph)
    result = engine.reason(text, max_hops=3)
    fingerprint = _graph_fingerprint()
    paths = [{"nodes": list(path.nodes), "triples": [asdict(edge) for edge in path.triples], "evidence_refs": list(path.evidence_refs)} for path in result.paths]
    inferred = [asdict(edge) for edge in result.inferred_triples]
    contradictions = [{"code": item.code, "message": item.message, "evidence_refs": list(item.evidence_refs)} for item in result.violations if item.code == "CONTRADICTION"]
    refs = sorted(set(result.evidence_refs) | {ref for path in result.paths for ref in path.evidence_refs})
    receipt_id = "ontology_receipt_" + uuid.uuid4().hex
    receipt_payload = {"receipt_id": receipt_id, "kind": "query", "query": text, "graph_fingerprint": fingerprint, "evidence_refs": refs}
    try:
        with _connect() as conn:
            conn.execute("INSERT INTO ontology_receipts(receipt_id,kind,payload) VALUES(?,?,?)", (receipt_id, "query", json.dumps(receipt_payload, sort_keys=True)))
    except sqlite3.Error as error:
        raise OntologyRuntimeError("query receipt persistence failed") from error
    trace = _write_trace("query", {**receipt_payload, "paths": paths, "inferred": inferred, "contradictions": contradictions})
    return {"query": text, "paths": paths, "inferred": inferred, "contradictions": contradictions, "evidence_refs": [evidence_by_ref[ref] for ref in refs if ref in evidence_by_ref], "graph_fingerprint": fingerprint, "receipt": {"receipt_id": receipt_id}, "trace": trace}


__all__ = ["OntologyRuntimeError", "approve", "propose", "query"]
