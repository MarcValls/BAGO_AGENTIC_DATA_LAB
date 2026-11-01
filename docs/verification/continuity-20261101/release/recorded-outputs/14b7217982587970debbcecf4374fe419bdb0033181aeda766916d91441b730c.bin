from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path


SCRIPT = Path(__file__).resolve()
COORD = SCRIPT.parents[1]
CANDIDATE = SCRIPT.parents[4]
PROJECT = CANDIDATE.parent.parent


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


issues: list[str] = []
counts: dict[str, int] = {}
index_path = COORD / "PUBLICATION_INDEX.json"
handoff_path = COORD / ".bago/team/runtime/handoffs/EXPORT.json"
index_bytes = index_path.read_bytes()
handoff_bytes = handoff_path.read_bytes()
index = json.loads(index_bytes)
handoff = json.loads(handoff_bytes)

if handoff.get("status") != "DONE" or handoff.get("work_id") != "EXPORT":
    issues.append("export handoff status/work identity mismatch")
if handoff.get("mission_id") != "BAGO_CONTINUITY_PUBLICATION_20261101":
    issues.append("export handoff mission identity mismatch")
if handoff.get("candidate_id") != "9bdf09833dd28ab922485c21a23e0f645efb5cb812712150dd3c1b07d4f8fada":
    issues.append("export handoff candidate mismatch")
if index.get("schema") != "bago.continuity.public-projection.v1":
    issues.append("publication index schema mismatch")
if index.get("publication_base") != "ed0efc83cc39a40aac231d9aa0da77a5d30a91e7":
    issues.append("publication base mismatch")
if index.get("source_normalization") != []:
    issues.append("index declares source normalization")

seen_output: set[str] = set()
for row in handoff.get("outputs", []):
    rel = row.get("path", "")
    if not rel or rel in seen_output:
        issues.append(f"duplicate or empty handoff output path: {rel!r}")
        continue
    seen_output.add(rel)
    p = COORD / rel
    if not p.is_file():
        issues.append(f"handoff output missing: {rel}")
    elif sha(p) != row.get("sha256"):
        issues.append(f"handoff output hash mismatch: {rel}")
counts["handoff_outputs"] = len(seen_output)

raw_ok = 0
source_ok = 0
for row in index.get("files", []):
    published = row.get("published", "")
    digest = row.get("sha256", "")
    if not re.fullmatch(r"[0-9a-f]{64}", digest):
        issues.append(f"invalid digest in index for {published}")
        continue
    payload = COORD / published
    if not payload.is_file() or sha(payload) != digest:
        issues.append(f"payload digest mismatch: {published}")
        continue
    raw_ok += 1
    if published != f"raw-objects/{digest}.bin":
        issues.append(f"payload path not content-addressed: {published}")
    src = PROJECT / row.get("source", "")
    if src.is_file():
        if sha(src) != digest or src.stat().st_size != row.get("bytes"):
            issues.append(f"source/published bytes differ: {row.get('source')}")
        else:
            source_ok += 1
counts["index_entries"] = len(index.get("files", []))
counts["payloads_hash_matched"] = raw_ok
counts["available_sources_hash_matched"] = source_ok

if len(index.get("excluded_private_files", [])) < 1:
    issues.append("private exclusions are not recorded")
excluded_sources = {x.get("source_path") for x in index.get("excluded_private_files", [])}
published_sources = {x.get("source") for x in index.get("files", [])}
if excluded_sources & published_sources:
    issues.append("an explicitly excluded private source is also published")

status_path = COORD / "STATUS.md"
status = status_path.read_text(encoding="utf-8")
required_status_phrases = [
    "ni constituye una nueva ejecución de Brave",
    "La selección GOV es un subconjunto público",
    "gesto de barra de herramientas y vídeo",
    "NOT_RUN",
    "No se ha autorizado integrar en main",
]
for phrase in required_status_phrases:
    if phrase.casefold() not in status.casefold():
        issues.append(f"STATUS lacks required limitation: {phrase}")
if "availability remote" not in status.casefold() and "disponibilidad remota" not in status.casefold():
    issues.append("STATUS does not distinguish remote availability")

readme_receipts = {}
for name in ("readme-generate", "readme-check", "portable-evidence"):
    p = COORD / "checks" / f"{name}.json"
    if not p.is_file():
        issues.append(f"check artifact missing: {name}")
        continue
    data = read_json(p)
    if data.get("status") != "PASS" or data.get("check_id") != name:
        issues.append(f"check artifact not PASS/expected id: {name}")
    readme_receipts[name] = sha(p)
counts["check_artifacts_pass"] = len(readme_receipts)

result = {
    "status": "PASS" if not issues else "FAIL",
    "scope": "independent read-only verification of exported evidence bytes and status claims",
    "mission_id": "BAGO_CONTINUITY_PUBLICATION_20261101",
    "candidate_id": handoff.get("candidate_id"),
    "export_handoff_sha256": sha(handoff_path),
    "publication_index_sha256": sha(index_path),
    "counts": counts,
    "checks_sha256": readme_receipts,
    "limits": [
        "This check establishes local projection integrity and status consistency only.",
        "It does not establish GitHub remote availability, product validation, or native /goal resume.",
        "GOV grant/control stores and private TaskStore/lease/token/reasoning records are intentionally omitted.",
    ],
    "issues": issues,
}
out = COORD / "review/RESULT.json"
out.parent.mkdir(parents=True, exist_ok=True)
out.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
print(json.dumps(result, ensure_ascii=False, indent=2))
raise SystemExit(0 if not issues else 1)
