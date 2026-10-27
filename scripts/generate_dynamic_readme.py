"""Render README.md from repository state and a small canonical manifest.

README.md is an output artifact. Human-maintained project decisions live in
the manifest and the project documents; repository facts are discovered from
the checkout every time this script runs.
"""

from __future__ import annotations

import argparse
import ast
import json
import re
import subprocess
import sys
from datetime import date
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
README_PATH = REPO_ROOT / "README.md"
MANIFEST_PATH = REPO_ROOT / "docs" / "readme_manifest.json"
INLINE = chr(96)
FENCE = INLINE * 3


def _run(command: list[str], *, check: bool = True) -> str:
    result = subprocess.run(
        command,
        cwd=REPO_ROOT,
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    if check and result.returncode != 0:
        details = (result.stdout + result.stderr).strip()
        raise RuntimeError(
            f"Command failed ({result.returncode}): {' '.join(command)}\n{details}"
        )
    return (result.stdout + result.stderr).strip()


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _relative(path: Path) -> str:
    return path.relative_to(REPO_ROOT).as_posix()


def _matches(pattern: str) -> list[str]:
    return sorted(
        {
            _relative(path)
            for path in REPO_ROOT.glob(pattern)
            if path.is_file()
        }
    )


def _matches_many(patterns: list[str]) -> list[str]:
    result: set[str] = set()
    for pattern in patterns:
        result.update(_matches(pattern))
    return sorted(result)


def _test_function_count(path: Path) -> int:
    """Count test functions for the generator's compatibility tests."""
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"))
    except (OSError, SyntaxError):
        return 0

    def is_pytest_fixture(node: ast.AST) -> bool:
        for decorator in getattr(node, "decorator_list", []):
            target = decorator.func if isinstance(decorator, ast.Call) else decorator
            if isinstance(target, ast.Name) and target.id == "fixture":
                return True
            if isinstance(target, ast.Attribute) and target.attr == "fixture":
                return True
        return False

    return sum(
        isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and node.name.startswith("test_")
        and not is_pytest_fixture(node)
        for node in ast.walk(tree)
    )


def collected_test_count() -> int:
    """Count pytest cases, including parametrized cases, without executing them."""
    output = _run(
        [
            sys.executable,
            "-m",
            "pytest",
            "tests",
            "--collect-only",
            "-q",
            "--disable-warnings",
        ]
    )
    match = re.search(r"\b(?P<count>\d+)\s+tests? collected\b", output)
    if not match:
        raise RuntimeError("pytest collection completed without a parseable case count")
    return int(match.group("count"))


def executed_test_count() -> int:
    """Run the complete suite and return its passing count."""
    output = _run(
        [
            sys.executable,
            "-m",
            "pytest",
            "tests",
            "-q",
            "--disable-warnings",
        ]
    )
    match = re.search(r"(?P<count>\d+)\s+passed\b", output)
    if not match:
        raise RuntimeError("pytest completed without a parseable passing count")
    return int(match.group("count"))


def parse_state() -> dict[str, str]:
    """Read the current, top-level state block from .bago/canon/STATE.md."""
    text = (REPO_ROOT / ".bago/canon/STATE.md").read_text(encoding="utf-8")

    def field(name: str) -> str:
        pattern = rf"^\*\*{re.escape(name)}:\*\*\s*(.*?)(?=^\*\*|\Z)"
        match = re.search(pattern, text, flags=re.MULTILINE | re.DOTALL)
        return " ".join(match.group(1).split()) if match else "NOT_DECLARED"

    status = field("Status")
    status_match = re.search(
        r"\b(PROPOSED|PREPARED|EXECUTED|VERIFIED|VALIDATED|NOT_RUN)\b",
        status,
    )
    return {
        "updated": field("Updated"),
        "current_phase": field("Current phase"),
        "status": status,
        "status_label": status_match.group(1) if status_match else "NOT_DECLARED",
        "tests": field("Latest CI full-suite record"),
        "next_phase": field("Next phase"),
    }


def parse_roles() -> list[list[str]]:
    """Extract the current target-role table from .bago/canon/LAB_CONTRACT.md."""
    text = (REPO_ROOT / ".bago/canon/LAB_CONTRACT.md").read_text(encoding="utf-8")
    start = text.find("### Vacantes Prioritarias Identificadas")
    if start < 0:
        return []
    end = text.find("\n## ", start)
    section = text[start : end if end >= 0 else None]
    rows: list[list[str]] = []
    for line in section.splitlines():
        if not re.match(r"^\|\s*\*\*", line):
            continue
        cells = [
            cell.strip().replace("**", "")
            for cell in line.strip().strip("|").split("|")
        ]
        if len(cells) == 5:
            rows.append(cells)
    return rows


def _is_table_separator(line: str) -> bool:
    cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
    return bool(cells) and all(re.fullmatch(r":?-{3,}:?", cell) for cell in cells)


def parse_skills() -> list[list[str]]:
    """Extract the technical skill table from .bago/canon/JOB_SKILL_MATRIX.md."""
    text = (REPO_ROOT / ".bago/canon/JOB_SKILL_MATRIX.md").read_text(encoding="utf-8")
    start = text.find("### Technical Skills")
    end = text.find("### Soft Skills", start)
    section = text[start : end if end >= 0 else None]
    rows: list[list[str]] = []
    for line in section.splitlines():
        if (
            not line.startswith("|")
            or _is_table_separator(line)
            or line.startswith("| Skill")
        ):
            continue
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        if len(cells) == 6:
            rows.append(cells)
    return rows


def parse_skill_matrix_convention() -> str:
    """Read the technical skill matrix's symbol convention from its canon."""
    text = (REPO_ROOT / ".bago/canon/JOB_SKILL_MATRIX.md").read_text(encoding="utf-8")
    for line in text.splitlines():
        if line.startswith("**Matrix convention:**"):
            return line
    raise ValueError("Technical skill matrix convention is missing")


def parse_soft_skills() -> list[list[str]]:
    """Extract the strategic/soft skill table from .bago/canon/JOB_SKILL_MATRIX.md."""
    text = (REPO_ROOT / ".bago/canon/JOB_SKILL_MATRIX.md").read_text(encoding="utf-8")
    start = text.find("### Soft Skills")
    if start < 0:
        return []
    section = text[start:]
    rows: list[list[str]] = []
    for line in section.splitlines():
        if (
            not line.startswith("|")
            or _is_table_separator(line)
            or line.startswith("| Skill")
        ):
            continue
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        if len(cells) == 4:
            rows.append(cells)
    return rows


def phase_inventory(
    manifest: dict[str, Any], state: dict[str, str]
) -> list[dict[str, Any]]:
    """Attach real artifact presence and current lifecycle status to each phase."""
    current_id = state["current_phase"].split(" ", maxsplit=1)[0]
    phases: list[dict[str, Any]] = []
    for phase in manifest["phases"]:
        checks: list[dict[str, Any]] = []
        for check in phase.get("checks", []):
            patterns = list(check.get("patterns", []))
            matches = _matches_many(patterns)
            missing = [pattern for pattern in patterns if not _matches(pattern)]
            checks.append(
                {
                    "kind": check["kind"],
                    "patterns": patterns,
                    "matches": matches,
                    "missing": missing,
                }
            )
        status = phase["status"]
        if phase["id"] == current_id:
            scope = re.search(r"(\s*\([^)]*\))$", str(status))
            status = state["status_label"] + (scope.group(1) if scope else "")
        if any(check["missing"] for check in checks):
            status = f"{status}; ARTIFACT GAP"
        phases.append(
            {
                **phase,
                "status": status,
                "checks": checks,
            }
        )
    return phases


def _cell(value: Any) -> str:
    return str(value).replace("|", r"\|").replace("\n", " ")


def _inline(value: Any) -> str:
    return f"{INLINE}{value}{INLINE}"


def _markdown_list(paths: list[str]) -> str:
    if not paths:
        return "- Ninguno detectado."
    return "\n".join(f"- {_inline(path)}" for path in paths)


def _files_under(
    directory: str,
    pattern: str = "*",
    *,
    excluded_dirs: tuple[str, ...] = (),
) -> list[str]:
    root = REPO_ROOT / directory
    if not root.exists():
        return []
    return sorted(
        _relative(path)
        for path in root.rglob(pattern)
        if path.is_file()
        and not any(directory_name in path.parts for directory_name in excluded_dirs)
        and "__pycache__" not in path.parts
        and path.suffix != ".pyc"
    )


def _render_phase_table(phases: list[dict[str, Any]]) -> str:
    lines = [
        "| Fase | Estado declarado | Objetivo | Área |",
        "|---|---|---|---|",
    ]
    for phase in phases:
        lines.append(
            f"| {_cell(phase['id'])} | {_cell(phase['status'])} | "
            f"{_cell(phase.get('target', '-'))} | {_cell(phase['name'])} |"
        )
    return "\n".join(lines)


def _links(paths: list[str], *, limit: int | None = None) -> str:
    selected = paths if limit is None else paths[:limit]
    if not selected:
        return "—"
    links = " · ".join(f"[{_inline(path)}]({path})" for path in selected)
    remainder = len(paths) - len(selected)
    return links + (f" · (+{remainder} archivos)" if remainder else "")


def _render_phase_evidence(phases: list[dict[str, Any]]) -> str:
    """Render phase evidence as readable Markdown groups without wide tables."""
    sections: list[str] = []
    for phase in phases:
        by_kind = {check["kind"]: check for check in phase.get("checks", [])}
        code = by_kind.get("code", {}).get("matches", [])
        tests = by_kind.get("tests", {}).get("matches", [])
        evidence = by_kind.get("evidence", {}).get("matches", [])
        missing = [
            pattern
            for check in phase.get("checks", [])
            for pattern in check.get("missing", [])
        ]
        sections.append(
            "\n".join(
                [
                    f"### {_cell(phase['id'])} — {_cell(phase['name'])}",
                    f"**Estado:** {_cell(phase['status'])}",
                    "",
                    f"**Código localizado:** {_links(code, limit=3)}",
                    f"**Tests:** {_links(tests, limit=3)}",
                    f"**Evidencia:** {_links(evidence, limit=4)}",
                    f"**Patrones sin resolver:** {_inline(', '.join(missing) if missing else 'ninguno')}",
                ]
            )
        )
    return "\n\n".join(sections)


def _render_business_demo(manifest: dict[str, Any]) -> str:
    """Render the app-produced fictional Bruma order cases and provenance."""
    config = manifest.get("business_demo", {})
    required = (
        "guide", "orders", "decisions", "run_evidence", "input_orders",
        "policy", "qa", "profiles", "video", "subtitles", "hash_manifest",
    )
    missing = [key for key in required if not config.get(key)]
    if missing:
        raise ValueError("Business demo metadata is missing: " + ", ".join(missing))
    absent = [path for path in config.values() if not (REPO_ROOT / path).is_file()]
    if absent:
        raise FileNotFoundError("Business demo artifacts missing: " + ", ".join(absent))

    orders_data = _read_json(REPO_ROOT / config["orders"])
    decisions_data = _read_json(REPO_ROOT / config["decisions"])
    run_data = _read_json(REPO_ROOT / config["run_evidence"])
    orders = {item["order_id"]: item for item in orders_data.get("orders", [])}
    lines = [
        "| Pedido | Envío | Retraso | Decisión registrada | Importe de envío elegible |",
        "|---|---|---:|---|---:|",
    ]
    for item in decisions_data.get("decisions", []):
        order = orders.get(item["order_id"], {})
        delay = order.get("delay_hours")
        delay_text = f"{delay} h" if delay is not None else "sin dato"
        amount = item.get("refund_shipping_fee_eur")
        amount_text = f"€{amount:.2f} (solo envío)" if amount is not None else "—"
        lines.append(
            f"| {item['order_id']} | {_cell(order.get('shipping_method', 'desconocido'))} | "
            f"{delay_text} | `{item['decision']}` | {amount_text} |"
        )

    runs = run_data.get("runs", [])
    trace_ids = [
        run.get("trace", {}).get("trace_id", "")
        for run in runs
        if run.get("trace", {}).get("trace_id")
    ]
    sources = [source for run in run_data.get("runs", []) for source in run.get("sources", [])]
    source_ids = sorted({source.get("file_sha256", "") for source in sources if source.get("file_sha256")})
    order_hash = next(
        (source.get("file_sha256") for source in sources if source.get("path") == config["input_orders"]),
        "NOT_RECORDED",
    )
    no_actions = not decisions_data.get("actions_executed", [])
    validation = run_data.get("validation", {})
    status = run_data.get("status", "NOT_DECLARED")
    return "\n".join(
        [
            "## Recorrido comercial de la app: Bruma Market",
            "",
            "Este tutorial usa pedidos y políticas totalmente ficticios. Documenta dos conversaciones de agentes ejecutadas en la app: un extractor produce JSON y un revisor aplica la política con evidencia autorizada. No son pedidos ni clientes reales.",
            "",
            *lines,
            "",
            f"**Ejecución registrada:** `{status}`; cuatro casos QA: `{', '.join(validation.get('decisions', []))}`; `actions_executed` vacío: `{no_actions}`. Ningún reembolso se ejecutó.",
            f"**Trazas de las conversaciones:** {', '.join(_inline(trace_id) for trace_id in trace_ids) or 'sin ID registrado'} (`local_only`; no Jaeger export). SHA-256 del CSV autorizado: `{order_hash}`. SHA distintos presentes en recibos: {len(source_ids)}.",
            "",
            "La regla estricta solo cubre envíos EXPRESS con más de 24 h de retraso y devuelve únicamente la tarifa de envío. Exactamente 24 h no cumple; STANDARD no entra en la regla; sin hora de entrega queda pendiente.",
            "",
            f"**Revisa el tutorial:** [guía paso a paso]({config['guide']}) · [vídeo MP4]({config['video']}) · [subtítulos]({config['subtitles']}) · [hash manifest]({config['hash_manifest']}). Entradas: [CSV de pedidos]({config['input_orders']}), [política]({config['policy']}) y [QA esperado]({config['qa']}). Resultados y receipts: [extracción JSON]({config['orders']}), [decisiones]({config['decisions']}), [recibos de lectura y trazas]({config['run_evidence']}) y [perfiles/runs guardados]({config['profiles']}).",
            "",
            "**Límite del conjunto:** solo contiene pedidos sintéticos, política, QA y recibos de lectura. No aporta directorio de clientes, facturas ni albaranes; esos casos requieren datos y escenarios propios antes de afirmar que están demostrados.",
            "",
        ]
    )

def _render_canonical_documents(manifest: dict[str, Any]) -> str:
    groups: dict[str, list[tuple[str, str, str]]] = {
        "Gobierno del proyecto": [],
        "Demo y portfolio": [],
        "Versionado": [],
    }
    for document in manifest.get("canonical_documents", []):
        path = str(document["path"])
        state = "PRESENTE" if (REPO_ROOT / path).is_file() else "FALTA"
        if path.startswith(".bago/canon/"):
            group = "Gobierno del proyecto"
        elif path == "VERSION":
            group = "Versionado"
        else:
            group = "Demo y portfolio"
        groups[group].append((path, str(document["role"]), state))
    if not any(groups.values()):
        return "No hay documentos canónicos declarados."

    coverage = {
        "Gobierno del proyecto": "Estado, contrato, arquitectura, roadmap, aprendizaje y skills",
        "Demo y portfolio": "Tutoriales, walkthrough, snapshot y notas de release",
        "Versionado": "Versión declarada del repositorio",
    }
    lines = ["| Área | Cobertura | Fuentes presentes / declaradas |", "|---|---|---|"]
    for group, documents in groups.items():
        if not documents:
            continue
        present = sum(state == "PRESENTE" for _, _, state in documents)
        result = f"{present}/{len(documents)} presentes"
        if present < len(documents):
            result += f"; {len(documents) - present} ausente(s)"
        lines.append(f"| {group} | {coverage[group]} | {result} |")
    lines.append("")
    for group, documents in groups.items():
        if not documents:
            continue
        lines.extend((f"**{group}:**", ""))
        lines.extend(
            f"- [{_inline(path)}]({path}) — {_cell(role)}"
            + (" — **FALTA en este checkout**" if state == "FALTA" else "")
            for path, role, state in documents
        )
        lines.append("")
    while lines and not lines[-1]:
        lines.pop()
    return "\n".join(lines)

def _render_one_command_demo(manifest: dict[str, Any]) -> str:
    config = manifest.get("one_command_demo", {})
    if not config:
        return ""
    artifacts = config.get("artifacts", [])
    artifact_lines = "\n".join(f"- `{name}`" for name in artifacts)
    return "\n".join(
        [
            "## One-Command Governed Knowledge Agent Demo",
            "",
            "A deterministic, credential-free local demonstration of the existing governed-agent path; it composes fixtures, typed execution, receipts, trace and structural evaluation without contacting external services.",
            "",
            "```text",
            "QUESTION → AGENT → GOVERNED RETRIEVAL → EXECUTION → RECEIPTS → TRACE → EVALUATION",
            "```",
            "",
            f"**Run:** `{config.get('command', 'python demo.py')}` (Python 3.11+, after `python -m pip install -r requirements.txt`).",
            "",
            f"Example question: {config.get('example_question', '')}",
            "",
            f"Expected fixture result: `{config.get('expected_result', 'PASS')}`; 2 retrieval hits, 15 trace events, evaluation score 1.0. Run-specific IDs/hashes may vary.",
            "",
            "Artifacts in `demo_output/`:",
            artifact_lines,
            "",
            f"Read the artifact contract, Windows setup, governance controls and limits in [`{config.get('documentation', 'docs/one_command_demo.md')}`]({config.get('documentation', 'docs/one_command_demo.md')}); use [`{config.get('walkthrough', 'docs/one_command_demo_walkthrough.md')}`]({config.get('walkthrough', 'docs/one_command_demo_walkthrough.md')}) for the 30-second, 90-second and 5-minute explanations.",
            "",
            "The injected provider is a fixture, not an AWS call; this local demo does not prove production answer quality or sandbox isolation. AWS and remote integrations remain scoped by `STATE.md`.",
            "",
        ]
    )


def _render_releases(manifest: dict[str, Any]) -> str:
    releases = manifest.get("releases", [])
    if not releases:
        return ""
    out: list[str] = ["## Releases congelados", ""]
    for release in releases:
        tag = str(release.get("tag", ""))
        repo = str(manifest.get("project", {}).get("repository", "")).rstrip("/")
        tag_url = f"{repo}/releases/tag/{tag}" if repo and tag else ""
        header = release.get("title", tag) or tag
        out.append(f"### `{tag}` — {release.get('date', '')}")
        out.append("")
        out.append(f"**{header}**")
        out.append("")
        if release.get("summary"):
            out.append(str(release["summary"]))
            out.append("")
        if tag_url:
            out.append(f"- Tag: <{tag_url}>")
        docs = release.get("docs", []) or []
        if docs:
            doc_links = ", ".join(_inline(d) for d in docs if d)
            out.append(f"- Docs: {doc_links}")
        if release.get("video"):
            duration = release.get("duration", "60-90s")
            sha = release.get("video_sha256") or ""
            fset = release.get("video_frame_set_sha256") or ""
            out.append(f"- Vídeo: {_inline(str(release['video']))} ({duration})")
            if sha:
                out.append(f"- SHA-256 sidecar: {_inline(str(sha))}")
            if fset:
                out.append(
                    "- Frame-set SHA-256 (deterministic): "
                    f"`{fset}` — byte-stable across encoder runs"
                )
        boundaries = release.get("boundaries", {}) or {}
        if boundaries:
            out.append("- Boundaries:")
            for key, value in boundaries.items():
                out.append(f"  - `{key}`: {value}")
        out.append("")
    return "\n".join(out)


def _render_sync_agent(manifest: dict[str, Any]) -> str:
    config = manifest.get("sync_agent", {})
    lines = [
        "| Componente | Estado | Función |",
        "|---|---|---|",
    ]
    labels = {
        "definition": "Definición del agente",
        "executor": "Ejecutor gobernado",
        "documentation": "Documentación",
    }
    roles = {
        "definition": "contrato operativo",
        "executor": "commit, push, PR y merge con receipts",
        "documentation": "uso y límites",
    }
    for key in ("definition", "executor", "documentation"):
        path = str(config.get(key, ""))
        if not path:
            continue
        state = "PRESENTE" if (REPO_ROOT / path).is_file() else "FALTA"
        lines.append(
            f"| {_inline(path)} | {_cell(state)} | "
            f"{_cell(labels[key] + ': ' + roles[key])} |"
        )
    return "\n".join(lines) or "No hay agente de sincronización declarado."


def _render_flowchart(phases: list[dict[str, Any]]) -> str:
    lines = [FENCE + "mermaid", "flowchart LR"]
    for phase in phases:
        label = f"{phase['id']} {phase['name']} ({phase['status']})"
        lines.append(f"    {phase['id']}[\"{_mermaid_label(label)}\"]")
    for left, right in zip(phases, phases[1:]):
        lines.append(f"    {left['id']} --> {right['id']}")
    lines.append(FENCE)
    return "\n".join(lines)


def _render_architecture(manifest: dict[str, Any]) -> str:
    architecture = manifest["architecture"]
    lines = [
        f"**Principio:** {architecture['principle']}",
        "",
        FENCE + "mermaid",
        "flowchart LR",
    ]
    nodes = [
        "RAG",
        "RDF",
        "SPARQL",
        "INFERENCE",
        "CONSTRAINTS",
        "LLM",
        "GATEWAY",
        "SANDBOX",
        "RECEIPT",
    ]
    labels = [
        "Governed RAG",
        "RDF/Turtle",
        "SPARQL local",
        "Inference",
        "Constraints",
        "LLM context",
        "ExecutionGateway",
        "SandboxManager",
        "Receipt",
    ]
    for node, label in zip(nodes, labels):
        lines.append(f"    {node}[\"{_mermaid_label(label)}\"]")
    for left, right in zip(nodes, nodes[1:]):
        lines.append(f"    {left} --> {right}")
    lines.extend([FENCE, "", "Pipeline actual:", ""])
    lines.extend(
        f"{index}. {step}" for index, step in enumerate(architecture["pipeline"], 1)
    )
    return "\n".join(lines)


def _mermaid_label(value: str) -> str:
    """Quote Mermaid labels and keep embedded quotes parser-safe."""
    return str(value).replace('"', "&quot;")


def _render_roles(rows: list[list[str]]) -> str:
    if not rows:
        return "No se pudo extraer la tabla de vacantes desde .bago/canon/LAB_CONTRACT.md."
    lines = [
        "| Empresa | Rol | Fit | Gap principal | Timeline |",
        "|---|---|---:|---|---|",
    ]
    lines.extend("| " + " | ".join(_cell(cell) for cell in row) + " |" for row in rows)
    return "\n".join(lines)


def _render_skills(rows: list[list[str]], convention: str) -> str:
    if not rows:
        return "No se pudo extraer la tabla técnica desde .bago/canon/JOB_SKILL_MATRIX.md."
    lines = [
        convention,
        "",
        "| Skill | Demanda | Nivel actual | Nivel objetivo | Primera evidencia | Entrevista |",
        "|---|---|---|---|---|---|",
    ]
    for skill, demand, current, target, evidence, interview in rows:
        lines.append(
            f"| {_cell(skill)} | {_cell(demand)} | {_cell(current)} | "
            f"{_cell(target)} | {_cell(evidence)} | {_cell(interview)} |"
        )
    return "\n".join(lines)


def _render_soft_skills(rows: list[list[str]]) -> str:
    if not rows:
        return "No se pudo extraer la tabla estratégica desde .bago/canon/JOB_SKILL_MATRIX.md."
    lines = [
        "| Skill | Nivel actual | Nivel objetivo | Evidencia |",
        "|---|---|---|---|",
    ]
    lines.extend(
        "| " + " | ".join(_cell(cell) for cell in row) + " |"
        for row in rows
    )
    return "\n".join(lines)


def _render_agent_catalog() -> str:
    """Render the committed reference-only agent catalog by responsibility."""
    manifest_path = REPO_ROOT / "agents" / "CATALOG_MANIFEST.json"
    if not manifest_path.is_file():
        return "No hay catálogo de agentes comprometido en este checkout."
    catalog = _read_json(manifest_path)
    lines = [
        f"Alcance: `{catalog.get('scope', 'NOT_DECLARED')}` · "
        f"activación: `{catalog.get('activation', 'NOT_DECLARED')}`.",
        "El catálogo es de referencia; la definición operativa sigue en `.github/agents`.",
        "",
        "| Grupo | Archivos | Responsabilidad |",
        "|---|---:|---|",
    ]
    for group, responsibility in catalog.get("groups", {}).items():
        count = len(_files_under(f"agents/{group}"))
        lines.append(f"| {_inline(group)} | {count} | {_cell(responsibility)} |")
    return "\n".join(lines)


def render_first_user_tutorial(manifest: dict[str, Any]) -> str:
    """Render and validate the first-user tutorial declared in the manifest."""
    tutorial = manifest.get("first_user_tutorial")
    if not tutorial:
        return "No hay un videotutorial de primer uso declarado."

    if tutorial.get("evidence_mode") == "synthetic_ui_capture":
        required_files = ("video", "subtitles", "guide", "historical_video", "historical_subtitles", "historical_trace", "historical_input")
        missing_keys = [key for key in required_files if not tutorial.get(key)]
        if missing_keys:
            raise ValueError("Tutorial metadata is missing: " + ", ".join(missing_keys))
        missing_files = [key for key in required_files if not (REPO_ROOT / tutorial[key]).is_file()]
        if missing_files:
            paths = ", ".join(tutorial[key] for key in missing_files)
            raise FileNotFoundError("Tutorial artifacts missing: " + paths)
        return "\n".join([
            "Recorrido narrado en español sobre la UI actual, grabado con Playwright y respuestas API sintéticas en un contexto aislado.",
            "No muestra consultas reales, respuestas de proveedor, agentes guardados ni trabajos ejecutados.",
            "La sesión real anterior permanece separada como evidencia histórica; su traza acredita solo el alcance que contiene.",
            "",
            f"- Vídeo actual: [{_inline('MP4')}]({tutorial['video']})",
            f"- Subtítulos actuales: [{_inline('SRT')}]({tutorial['subtitles']})",
            f"- Guía: [{_inline(Path(tutorial['guide']).name)}]({tutorial['guide']})",
            f"- Vídeo histórico: [{_inline('MP4 2026-10-10')}]({tutorial['historical_video']})",
            f"- Subtítulos históricos: [{_inline('SRT 2026-10-10')}]({tutorial['historical_subtitles']})",
            f"- LocalTrace histórica: [{_inline(Path(tutorial['historical_trace']).name)}]({tutorial['historical_trace']})",
            f"- Archivo leído en la sesión histórica: [{_inline(Path(tutorial['historical_input']).name)}]({tutorial['historical_input']})",
        ])

    required_files = ("video", "subtitles", "guide", "trace", "input")
    required_values = ("provider", "global_model", "agent_model", "credential_redaction")
    missing_keys = [key for key in required_files + required_values if not tutorial.get(key)]
    if missing_keys:
        raise ValueError("Tutorial metadata is missing: " + ", ".join(missing_keys))
    missing_files = [
        tutorial[key]
        for key in required_files
        if not (REPO_ROOT / tutorial[key]).is_file()
    ]
    if missing_files:
        raise FileNotFoundError("Tutorial artifacts missing: " + ", ".join(missing_files))

    return "\n".join(
        [
            "Guía visual narrada en español para recorrer el chat, los agentes y los ajustes del proveedor.",
            f"La pantalla completa de configuración se conserva; el campo de {tutorial['credential_redaction']} aparece censurado.",
            f"La guía distingue el modelo global del asistente ({_inline(tutorial['global_model'])}) del modelo fijado al agente lector ({_inline(tutorial['agent_model'])}).",
            f"La traza enlazada registra una lectura acotada y respuesta real de {tutorial['provider']}; no acredita una auditoría del código ni ejecución de trabajos.",
            "",
            f"- Vídeo: [{_inline('MP4')}]({tutorial['video']})",
            f"- Subtítulos: [{_inline('SRT')}]({tutorial['subtitles']})",
            f"- Guía y límites: [{_inline(Path(tutorial['guide']).name)}]({tutorial['guide']})",
            f"- LocalTrace: [{_inline(Path(tutorial['trace']).name)}]({tutorial['trace']})",
            f"- Archivo de ejemplo: [{_inline(Path(tutorial['input']).name)}]({tutorial['input']})",
        ]
    )


def _render_frontend(manifest: dict[str, Any]) -> list[str]:
    """Describe the actual app entrypoints, not inferred provider availability."""
    config = manifest["frontend"]
    paths = [config[key] for key in ("entry", "package", "api", "setup_guide", "launcher")]
    paths.extend(path for layer in config["layers"] for path in layer["sources"])
    missing = [path for path in paths if not (REPO_ROOT / path).is_file()]
    if missing:
        raise FileNotFoundError("Frontend sources missing: " + ", ".join(missing))
    package = _read_json(REPO_ROOT / config["package"])
    for name in ("dev", "build", "test", "test:ui", "test:contracts"):
        if not package.get("scripts", {}).get(name):
            raise ValueError("Frontend script is missing: " + name)
    lines = [
        "## La aplicación frontend", "",
        f"La app [React + TypeScript + Vite]({config['package']}) permite trabajar con agentes y datos, y abrir una capa de inspección para revisar las observaciones que devuelve la [API FastAPI]({config['api']}).", "",
        "| Capa | Qué contiene | Fuente |", "|---|---|---|",
    ]
    for layer in config["layers"]:
        links = " · ".join(
            f"[{Path(path).parent.name if Path(path).stem == 'index' else Path(path).stem}]({path})"
            for path in layer["sources"][:2]
        )
        if len(layer["sources"]) > 2:
            links += f" (+{len(layer['sources']) - 2} fuentes en el manifiesto)"
        lines.append(f"| {_cell(layer['name'])} | {_cell(layer['description'])} | {links} |")
    lines.extend([
        "", "Chat y borradores, tareas y ejecuciones tienen recorridos distintos. La disponibilidad de un modelo, proveedor o motor BER se comprueba en su recorrido; ver una pantalla no acredita que una acción se haya ejecutado.", "",
        "**Arranque desde la raíz del repositorio**, con Python 3.11+, Node.js 22 y el entorno Python activado. `requirements-test.txt` fija las dependencias de la app y sus pruebas, incluida la API:", "",
        FENCE + "bash", *config["start_commands"], FENCE, "",
        "Abre <http://127.0.0.1:8080>. La API sirve `frontend/dist` después del build; la configuración de proveedores se realiza en Settings. Estos comandos describen el arranque, no una sesión iniciada por este README.", "",
        f"En Windows, el [lanzador local]({config['launcher']}) construye la UI y selecciona un puerto libre; consulta sus [requisitos y límites]({config['setup_guide']}). Para desarrollo, `npm run dev --prefix frontend` usa Vite con proxy hacia la API local.", "",
    ])
    return lines


def _verification_record(manifest: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    """Read the local identity-bound record selected by the canonical manifest."""
    path = manifest["verification_record"]
    relative = Path(path)
    if relative.is_absolute() or ".." in relative.parts:
        raise ValueError("Verification record must be repository-relative")
    record = _read_json(REPO_ROOT / relative)
    if record.get("schema") != "bago.readme.verification.v1":
        raise ValueError("Unsupported README verification record schema")
    if not record.get("recorded_at"):
        raise ValueError("README verification record requires its observation date")
    ci = record.get("ci", {})
    for key in ("candidate", "completed_at", "run_url", "scope", "checks"):
        if not ci.get(key):
            raise ValueError("README CI record is missing " + key)
    if not re.fullmatch(r"[a-f0-9]{40}", ci["candidate"]):
        raise ValueError("README CI record requires an exact commit SHA")
    for check in ci["checks"]:
        for key in ("name", "command", "result", "summary", "evidence_url"):
            if not check.get(key):
                raise ValueError("README CI check is missing " + key)
        if check["result"] not in ("PASS", "FAIL", "NOT_RUN", "SKIPPED"):
            raise ValueError("Unsupported README check result")
    return path, record


def _render_verification(manifest: dict[str, Any]) -> list[str]:
    path, record = _verification_record(manifest)
    ci = record["ci"]
    lines = [
        "## Tests y verificación", "",
        f"**Snapshot de CI:** [{ci['completed_at']}]({ci['run_url']}) · candidata `{ci['candidate']}`.",
        f"**Alcance:** {_cell(ci['scope'])}",
        f"Registro versionado observado el {_cell(record['recorded_at'])}: [{path}]({path}). No es una consulta en vivo ni cubre cambios posteriores a esa candidata.", "",
        "| Batería | Resultado registrado | Evidencia |", "|---|---|---|",
    ]
    for check in ci["checks"]:
        lines.append(f"| {_cell(check['name'])} | `{check['result']}` · {_cell(check['summary'])} | [{_inline(check['command'])}]({check['evidence_url']}) |")
    lines.extend([
        "", "<details>", "<summary>Repetir las comprobaciones en tu checkout</summary>", "",
        FENCE + "bash", "python -m pytest tests -q", "npm test --prefix frontend",
        "npm run test:ui --prefix frontend", "npm run test:contracts --prefix frontend",
        "npm run build --prefix frontend", "python scripts/generate_dynamic_readme.py --check --skip-tests", FENCE, "",
        "La colección de pytest no es una ejecución: `--check --skip-tests` informa `NOT_RUN`. El conteo de una ejecución local se imprime en terminal; no sustituye ni modifica el snapshot versionado de CI.", "", "</details>", "",
    ])
    historical = record.get("historical", [])
    if historical:
        lines.extend(["<details>", "<summary>Resultados locales e históricos, con alcance propio</summary>", ""])
        for item in historical:
            for key in ("label", "candidate", "observed_at", "scope", "summary", "evidence_url"):
                if not item.get(key):
                    raise ValueError("Historical verification record is missing " + key)
            summary = _cell(item["summary"]).rstrip(".")
            scope = _cell(item["scope"]).rstrip(".")
            lines.append(f"- [{_cell(item['label'])}]({item['evidence_url']}) · {_cell(item['observed_at'])} · candidata `{item['candidate']}`: {summary}. Alcance: {scope}.")
        lines.extend(["", "</details>", ""])
    return lines


def _details(summary: str, content: list[str]) -> list[str]:
    return ["<details>", f"<summary>{summary}</summary>", "", *content, "", "</details>", ""]


def _render_current_captures(manifest: dict[str, Any]) -> list[str]:
    """Publish explicitly declared captures with date-bound provenance."""
    presentation = manifest["presentation"]
    capture_date = presentation.get("capture_date")
    try:
        parsed_capture_date = date.fromisoformat(capture_date)
    except (TypeError, ValueError) as exc:
        raise ValueError("Current capture date must be an ISO calendar date") from exc
    carousel_path = presentation.get("carousel_gif")
    viewer_path = presentation.get("carousel_html")
    if not carousel_path or not viewer_path:
        raise ValueError("Current presentation needs an animated carousel and an HTML viewer")
    required = [
        presentation["banner"], presentation["frontend_guide"],
        presentation["capture_guide"], carousel_path, viewer_path,
    ]
    required.extend(item["path"] for item in presentation["captures"])
    for path in required:
        relative = Path(path)
        if relative.is_absolute() or ".." in relative.parts:
            raise ValueError("Presentation artifact must be repository-relative")
        if not (REPO_ROOT / relative).is_file():
            raise FileNotFoundError("Presentation artifact missing: " + path)
    gif_bytes = (REPO_ROOT / carousel_path).read_bytes()
    if not gif_bytes.startswith((b"GIF87a", b"GIF89a")):
        raise ValueError("Current screenshot carousel must be a valid GIF")
    guide_text = (REPO_ROOT / presentation["capture_guide"]).read_text(encoding="utf-8")
    month_names = (
        "enero", "febrero", "marzo", "abril", "mayo", "junio",
        "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre",
    )
    documented_date = (
        f"{parsed_capture_date.day} de {month_names[parsed_capture_date.month - 1]} "
        f"de {parsed_capture_date.year}"
    )
    if capture_date not in guide_text and documented_date not in guide_text:
        raise ValueError("Current capture date must appear in its provenance guide")
    lines = [
        "## La aplicación en pantalla", "",
        f"**Capturas del recorrido documentado el {capture_date} · aplicación local en Brave visible.** Las imágenes se capturaron desde el navegador visible; las observaciones y su procedencia están descritas en la guía enlazada.", "",
        f"El carrusel cambia de captura automáticamente. Puedes abrir el [visor HTML con controles de anterior, siguiente y pausa]({viewer_path}) o desplegar una imagen original para leerla a tamaño completo.", "",
        f"![Carrusel de capturas actuales de BAGO ADL]({carousel_path})", "",
    ]
    for index, item in enumerate(presentation["captures"], start=1):
        if not item.get("alt") or not item.get("caption"):
            raise ValueError("Current capture needs alt text and an observation caption")
        lines.extend([
            "<details>",
            f"<summary>Captura {index:02d} · {item['caption']}</summary>",
            "",
            f"![{item['alt']}]({item['path']})",
            "",
            f"**{item['caption']}**",
            "",
            "</details>",
            "",
        ])
    lines.extend([
        f"**Profundizar:** [cómo se tomaron, identidad del servidor, observaciones y hashes]({presentation['capture_guide']}) · [guía del frontend]({presentation['frontend_guide']}).", "",
    ])
    return lines


# BEGIN BAGO_VISUAL_README_V1 — additive presentation layer.
BAGO_VISUAL_MANIFEST = REPO_ROOT / "docs" / "readme_visual_manifest.json"


def _render_bago_visual_section(key: str) -> list[str]:
    """Render only local linked assets; each click is handled by Markdown."""
    manifest = _read_json(BAGO_VISUAL_MANIFEST)
    if manifest.get("schema") != "bago.readme.visual.v1":
        raise ValueError("Invalid visual README manifest schema")
    if key not in manifest["sections"]:
        raise ValueError(f"Unknown visual section: {key}")
    info = manifest["sections"][key]
    entries = info.get("entries", [])
    for entry in entries:
        asset = entry["asset"]
        if not asset.startswith("docs/assets/readme-visual/") or ".." in asset:
            raise ValueError(f"Untrusted visual asset path: {asset}")
        if not (REPO_ROOT / asset).is_file():
            raise FileNotFoundError(f"Missing visual asset: {asset}")
        target = entry["target"]
        if not target.startswith(("#", "docs/", ".bago/")):
            raise ValueError(f"Untrusted visual link target: {target}")
    if key == "nav":
        cards = entries
        if len(cards) != 6:
            raise ValueError("Expected 6 navigation cards")
        cells = [f"[![{c['alt']}]({c['asset']})]({c['target']})" for c in cards]
        def nav_label(card: dict[str, str]) -> str:
            label = card["alt"].split(": ", 1)[-1]
            return label[:1].upper() + label[1:]

        text_links = " · ".join(
            f"[{nav_label(c)}]({c['target']})" for c in cards
        )
        return [
            "### Explorar el laboratorio", "",
            f"**Accesos rápidos:** {text_links}", "",
            "| | | |", "|:---:|:---:|:---:|",
            "| " + " | ".join(cells[:3]) + " |",
            "| " + " | ".join(cells[3:]) + " |", "",
        ]
    result = []
    for entry in entries:
        result.extend([
            f"[![{entry['alt']}]({entry['asset']})]({entry['target']})", "",
            entry["caption"], "",
        ])
    return result
# END BAGO_VISUAL_README_V1

def render_readme(
    *,
    manifest: dict[str, Any],
    state: dict[str, str],
    passing_tests: int,
) -> str:
    # Public compatibility argument: collection and local test totals never
    # change the identity-bound, versioned verification snapshot.
    project = manifest["project"]
    phases = phase_inventory(manifest, state)
    presentation = manifest["presentation"]
    repository = project["repository"].rstrip("/")
    _render_frontend(manifest)  # Validate real app/package entrypoints.
    render_first_user_tutorial(manifest)  # Preserve historic artifact validation.
    current_captures = _render_current_captures(manifest)
    guide = presentation["frontend_guide"]
    lines = [
        f"![BAGO · Agentic Data Lab · agentes, datos y ejecución gobernada]({presentation['banner']})", "",
        f"# {project['title']}", "",
        f"[![CI]({repository}/actions/workflows/{project['ci_workflow']}/badge.svg)]({repository}/actions/workflows/{project['ci_workflow']})",
        f"[![README consistency]({repository}/actions/workflows/readme-consistency.yml/badge.svg)]({repository}/actions/workflows/readme-consistency.yml)",
        f"[![License](https://img.shields.io/badge/license-{project['license']}-447B9D)](LICENSE)", "",
        "> **Tu espacio de trabajo, desde el chat.** Expresa la intención, revisa la propuesta y consulta el resultado con su evidencia.", "",
        project["description"], "",
        "**Entrada principal: Chat.** Workspace, Agent Builder, Inspect y Settings amplían la conversación para preparar datos, configurar perfiles, revisar autorizaciones y profundizar en resultados. La cobertura conversacional actual se describe abajo; los pasos que necesitan una vista específica siguen indicados.", "",
        "[Conocer el producto](#el-laboratorio) · [Ver la aplicación](#la-aplicación-en-pantalla) · [Instalar y arrancar](#instalación-y-operación) · [Revisar tests](#tests-y-verificación)", "",
        "---", "",
        "**EN ESTA PÁGINA**", "",
        "| Producto | Plataforma | Operación |", "|---|---|---|",
        "| [01 · El laboratorio](#el-laboratorio) | [05 · Agentes y tareas](#agentes-tareas-y-evaluación) | [10 · Tests y verificación](#tests-y-verificación) |",
        "| [02 · Chat y frontend](#la-aplicación-frontend) | [06 · Proveedores y modelos](#proveedores-y-modelos) | [11 · Instalación](#instalación-y-operación) |",
        "| [03 · Capturas actuales](#la-aplicación-en-pantalla) | [07 · Ejecución gobernada](#bago-ber-y-ejecución-gobernada) | [12 · Observabilidad](#observabilidad-e-inspección) |",
        "| [04 · Datos y conocimiento](#datos-y-conocimiento) | [08 · Arquitectura](#arquitectura-de-un-vistazo) | [13 · Estado y roadmap](#estado-y-roadmap) |",
        "| [Guía del frontend](docs/readme_frontend.md) | [09 · Casos y demos](#casos-y-demos) | [14 · Documentación](#documentación-y-aprendizaje) |", "",
        *_render_bago_visual_section("nav"),
        "## El laboratorio", "",
        *_render_bago_visual_section("overview"),
        "BAGO Agentic Data Lab reúne una aplicación de trabajo y un laboratorio de AI Engineering. Permite conversar con el asistente, preparar agentes y datos, y recorrer controles de ejecución, recuperación, trazabilidad y evaluación con contratos explícitos.", "",
        "El producto organiza la experiencia alrededor de una intención del usuario. La evidencia permite distinguir una respuesta del modelo, una propuesta, una autorización y un efecto comprobado. Cada integración conserva su entorno y sus límites de validación.", "",
        "| Necesidad | Recorrido | Resultado que se puede inspeccionar |", "|---|---|---|",
        "| Orientarse y pedir ayuda | Chat del asistente y accesos a vistas | Conversación persistida, propuesta de navegación y contexto |",
        "| Preparar un agente | Borrador conversacional y Agent Builder | Perfil guardado con modelo y configuración explícitos |",
        "| Consultar conocimiento | Ingesta, recuperación gobernada y ontología | Fuentes, citas, relaciones y decisiones de metadata |",
        "| Revisar una operación | Perfil de ejecución aplicable y autorización | Solicitud, decisión, permiso y recibo, cuando existen |",
        "| Evaluar y diagnosticar | Evaluation Lab, Inspect y trazas | Comprobaciones declaradas, historial y evidencia enlazada |", "",
        "**Profundizar:** [contrato del laboratorio](.bago/canon/LAB_CONTRACT.md) · [arquitectura de referencia](.bago/canon/ARCHITECTURE.md).", "",
        "## La aplicación frontend", "",
        "La interfaz **React + TypeScript + Vite** sitúa Chat como entrada principal. El asistente puede ayudar, listar agentes/capacidades, preparar un borrador de agente y proponer navegación. Agent Builder puede aparecer dentro de la conversación; el cambio a otra pantalla requiere la decisión visible del usuario.", "",
        "```mermaid", "flowchart LR",
        '    CHAT["Chat · intención y contexto"] --> PROPOSAL["Respuesta o propuesta"]',
        '    PROPOSAL --> REVIEW["Revisión y autorización aplicables"]',
        '    REVIEW --> RESULT["Resultado observado"]',
        '    RESULT --> INSPECT["Inspect · evidencia y procedencia"]',
        '    PROPOSAL --> VIEWS["Workspace · Builder · Settings"]',
        '    VIEWS --> CHAT', "```", "",
        "| Desde el chat | Apoyo de las vistas | Cobertura actual |", "|---|---|---|",
        "| Conversar, pedir ayuda y listar agentes | Settings configura proveedor/modelo y cognición | Depende del proveedor efectivo; una selección guardada no prueba inferencia |",
        "| Pedir un borrador de agente | Builder integrado o pantalla completa | El perfil se revisa y guarda; guardarlo no ejecuta sus herramientas |",
        "| Solicitar navegación | Workspace, Agent Runs, Inspect y otras vistas existentes | La navegación propuesta se confirma; no implica completar la operación de destino |",
        "| Autorizar lecturas acotadas de proyecto y revisar resultados compatibles | Controles de lectura y revisión del workspace | Rutas explícitas y autorización propia; disponer de contexto no concede acceso general |",
        "| Consultar historial y resultados disponibles | Inspect, tareas y evaluación | Algunos recorridos requieren pasos manuales en su vista; no se afirma cobertura total desde Chat |", "",
        "| Área del producto | Función |", "|---|---|",
    ]
    for layer in manifest["frontend"]["layers"]:
        lines.append(f"| {_cell(layer['name'])} | {_cell(layer['description'])} |")
    lines.extend([
        "", f"**Profundizar:** [guía del frontend y alcance conversacional]({guide}) · [entrada de la app]({manifest['frontend']['entry']}) · [API FastAPI]({manifest['frontend']['api']}).", "",
        *current_captures,
        "## Datos y conocimiento", "",
        *_render_bago_visual_section("knowledge"),
        "El contexto del workspace, los documentos recuperados y las relaciones de una ontología aportan información a la tarea. Los recorridos gobernados mantienen la identidad y la elegibilidad de las fuentes para que una cita o una relación pueda revisarse después.", "",
        "| Capacidad | Aportación | Qué revisar |", "|---|---|---|",
        "| Ingesta y consulta | Preparar conocimiento y recuperar fragmentos con citas | Fuente, metadata permitida y evidencia devuelta |",
        "| RAG híbrido y vectores locales | Recuperación léxica/semántica con SQLite persistente | Backend utilizado, fingerprint del índice y gate de metadata |",
        "| Ontology Engine | RDF/Turtle, SPARQL acotado, inferencias y constraints | Relaciones derivadas, evidencia y contradicciones |",
        "| Calidad de catálogo | Revisión de activos y metadata | Alcance local o remoto de cada comprobación |",
        "| Conexiones y MCP | Adaptadores y registro de capacidades | Disponibilidad, autorización y recibos de cada invocación |", "",
        "**Profundizar:** [Governed RAG](docs/governed_rag.md) · [vector store local](docs/local_vector_store.md) · [ontología](docs/ontology_engine.md) · [catálogo](docs/openmetadata_catalog.md) · [MCP gobernado](docs/mcp_governance.md).", "",
        "## Agentes, tareas y evaluación", "",
        "Un agente guardado es un perfil reutilizable. Las tareas conservan su petición y estado; las ejecuciones y evaluaciones aportan resultados solo cuando se recorre su contrato efectivo. El modelo asignado al asistente y el del agente se resuelven por separado.", "",
        "```mermaid", "flowchart LR",
        '    INTENT["Petición en Chat"] --> DRAFT["Borrador revisable"]',
        '    DRAFT --> PROFILE["Perfil guardado"]',
        '    PROFILE --> TASK["Tarea y recorrido aplicable"]',
        '    TASK --> OBS["Resultado y observación"]',
        '    OBS --> EVAL["Evaluación con criterio declarado"]', "```", "",
        "| Espacio | Trabajo principal | Límite de la afirmación |", "|---|---|---|",
        "| Agent Builder | Preparar nombre, prompt, modelo y herramientas declaradas | Una herramienta seleccionada no queda autorizada por el perfil |",
        "| Tareas de agentes | Guardar y revisar tareas asociadas a perfiles | Una tarea guardada no equivale a una ejecución completa |",
        "| Agent Runs | Acceder al recorrido de ejecución disponible | Runtime, proveedor, permisos y perfil determinan la disponibilidad |",
        "| Agent Evaluation Lab | Suites versionadas y snapshots de runs en SQLite | Sus checks de texto deterministas no miden calidad general del modelo |",
        "| Job History e Inspect | Consultar historial, estados y artefactos disponibles | Se necesita evidencia del efecto, además del estado mostrado |", "",
        "**Profundizar:** [guía frontend: agentes y tareas](docs/readme_frontend.md#agentes-tareas-y-resultados) · [Agent Builder](docs/agent_builder_ui.md) · [contrato de Evaluation Lab](docs/agent_evaluation_lab.md).", "",
        "## Proveedores y modelos", "",
        "Settings separa configuración, catálogo de modelos y selección. El registro del adaptador, una credencial reconocida, la pertenencia al catálogo y una respuesta real son comprobaciones diferentes. La app muestra y aplica los estados que devuelve el backend.", "",
        "| Modalidad | Configuración y uso | Evidencia necesaria para declararla operativa |", "|---|---|---|",
        "| Ollama y adaptadores locales | Servicio/modelo local y disponibilidad reportada | Dispatch y respuesta real del modelo seleccionado |",
        "| OpenAI Platform y otros proveedores por API | Credencial y adaptador propios del servicio | Autenticación, modelo elegible y respuesta del proveedor |",
        "| Codex CLI / sesión del host | Integración de sesión y protocolo del host correspondiente | Respuesta efectiva en ese recorrido; no se deduce de una API key de Platform |",
        "| GitHub Copilot | Integración y elegibilidad propias | Estado del servicio y respuesta en su adaptador |",
        "| AWS Bedrock | Adaptador gobernado, región y modelo explícitos | Recibo de la llamada y alcance/fecha; cuota y facturación tienen evidencia separada |", "",
        "En la demostración nueva se verificó la selección de Codex gpt-6-luna en Settings y se obtuvo una respuesta real del agente con ese modelo. El primer guardado había fallado con `model_registration_mismatch`; el error quedó visible. Esa observación pertenece a esta sesión y no declara operativos todos los proveedores de la tabla.", "",
        "**Profundizar:** [proveedores y modelos en el frontend](docs/readme_frontend.md#proveedores-y-modelos) · [pantalla de configuración](docs/provider-models-screen.md) · [setup Bedrock](docs/aws_bedrock_setup.md).", "",
        "## BAGO, BER y ejecución gobernada", "",
        *_render_bago_visual_section("governance"),
        "BAGO aporta contratos y control de ejecución. El modelo produce propuestas; la autorización y la comprobación del efecto pertenecen al recorrido de ejecución. ADL presenta la revisión humana y la evidencia disponible en la interfaz.", "",
        "```mermaid", "flowchart LR",
        '    P["Propuesta sin autoridad implícita"] --> A["Autorización y aprobación aplicables"]',
        '    A --> PERMIT["Permiso ligado a la solicitud"]',
        '    PERMIT --> EFFECT["Operación tipada"]',
        '    EFFECT --> RECEIPT["Recibo persistido"]',
        '    RECEIPT --> VERIFY["Observación y postcondición"]', "```", "",
        "| Recorrido | Alcance | Condición de lectura |", "|---|---|---|",
        "| Laboratorio local histórico | Graph, ExecutionGateway y SandboxManager con fixtures y controles acotados | Mantiene su evidencia de fase; no representa el kernel de un sistema nuevo |",
        "| Perfil GEX RUNTIME_FIXTURE | Lectura de un fixture sintético, solicitud exacta, aprobación y recuperación durable | Su contrato mantiene las rutas genéricas no habilitadas en ese perfil como `UNAVAILABLE / FAIL_CLOSED` |",
        "| Agent Runner sobre BER | Adaptación al runtime fijado, workspace ligado y efectos tipados registrados | Requiere disponibilidad efectiva del host/proveedor; el gateway heredado no es fallback |",
        "| BER Effect Record | Inspección del registro y del efecto declarado | Una vista del registro requiere su propia evidencia para acreditar el efecto |", "",
        "**Profundizar:** [contrato normativo GEX](docs/governed-execution/GEX_V1_NORMATIVE_CONTRACT.md) · [perfil de lectura sintética](docs/governed-execution/RUNTIME_FIXTURE_PROFILE.md) · [alcance BER Agent Runner](docs/ber/AGENT_RUNNER_SCOPE.md) · [BER Effect Inspector](docs/ber/BER_EFFECT_INSPECTOR.md).", "",
        "## Arquitectura de un vistazo", "",
        *_render_bago_visual_section("architecture"),
        "La aplicación conecta experiencia de usuario, API y servicios especializados. El control de efectos conserva sus fronteras; LocalTrace enlaza eventos y artefactos, mientras que la proyección OpenTelemetry facilita su observación externa.", "",
        "```mermaid", "flowchart TB",
        '    UI["React · Chat y vistas de profundización"] --> API["FastAPI · contratos y endpoints"]',
        '    API --> ORCH["Orquestación y proveedores"]',
        '    API --> DATA["Workspace · conocimiento · tareas"]',
        '    ORCH --> GOV["Control gobernado según perfil"]',
        '    GOV --> ADAPTER["Adaptadores y efectos tipados"]',
        '    DATA --> TRACE["LocalTrace · recibos · evaluación"]',
        '    ADAPTER --> TRACE',
        '    TRACE --> OTEL["OpenTelemetry / Jaeger · proyección"]', "```", "",
        "| Capa | Responsabilidad | Fuente de profundización |", "|---|---|---|",
        "| Frontend | Conversación, configuración y revisión | [App React](frontend/src/App.tsx) |",
        "| API | Identidad de recursos, validación y conexión de recorridos | [Servidor](src/api/server.py) |",
        "| Datos | Metadata, recuperación, ontología y persistencia | [Arquitectura canónica](.bago/canon/ARCHITECTURE.md) |",
        "| Gobierno | Propuesta, elegibilidad, aprobación y límites de efecto | [GEX normativo](docs/governed-execution/GEX_V1_NORMATIVE_CONTRACT.md) |",
        "| Evidencia | Recibos, traza local y evaluación | [Observabilidad](docs/observability_evals.md) |", "",
        "**Profundizar:** [arquitectura completa](.bago/canon/ARCHITECTURE.md) · [pipeline del laboratorio](docs/one_command_demo_walkthrough.md) · [frontera de sandbox local](docs/sandbox_manager.md).", "",
        "## Casos y demos", "",
        *_render_bago_visual_section("demonstrability"),
        "Cada demo tiene entradas y alcance propios. Las fixtures permiten repetir controles sin credenciales. Los tutoriales con datos ficticios ayudan a entender el producto y conservan los recibos que realmente produjeron.", "",
        "| Recorrido | Entrada | Resultado y artefactos | Alcance |", "|---|---|---|---|",
        "| Chat real · 22 de octubre | Agente nuevo, workspace nuevo y lectura explícita de `DEMO.md` | Respuesta con citas y LocalTrace `trace-496fac766f384348` | Una lectura autorizada y dos pedidos ficticios; Inspect no quedó vinculado automáticamente |",
        "| Demo de una orden | `python demo.py` | `summary.json`, `agent_run.json`, `receipts.json`, `trace.json`, `evaluation.json` | Determinista y local; sin servicio externo |",
        "| Lectura GEX | Workspace sintético, operador y agente autorizados | Solicitud, decisión, permiso, recibo y verificación persistidos | Solo fixture registrado de ese perfil |",
        "| Bruma Market | Pedidos y política ficticios | Extracción JSON, decisiones, trazas y recibos de lectura | Tutorial histórico; ningún reembolso ejecutado |", "",
        "### Demostración nueva desde Chat", "",
        "El **2026-10-22**, en Brave visible sobre la app local del puerto 8080, se creó a las **18:40:34 UTC** el agente **BAGO Demo Chat 20261022** desde un borrador inline: Preview y Save Agent. Tras el error inicial `model_registration_mismatch`, Settings guardó y verificó Codex `gpt-6-luna`; el segundo guardado funcionó. Se abrió una conversación nueva y se autorizó expresamente la lectura del fixture `DEMO.md` del workspace nuevo; la respuesta se registró a las **18:44:10 UTC**.", "",
        "| Caso ficticio | Dato observado | Respuesta del agente |", "|---|---|---|",
        "| DEMO-001 | 30 h de retraso | 6 EUR de tarifa de envío elegible, con citas a líneas 7 y 12 |",
        "| DEMO-002 | 12 h de retraso | Sin reembolso de envío, con citas a líneas 8 y 13 |", "",
        "**Resultado observado:** traza `trace-496fac766f384348`, decisión `ALLOW`, una lectura, estado `COMPLETED`, modelo `gpt-6-luna`, 14,6 s. Se demostró lectura autorizada y respuesta; no se ejecutó un reembolso ni una herramienta genérica. SHA-256 del archivo completo: `7fdbb3379f3abc59ef1d3c9fa5c9ffb4c7c2abc5de93a9c038e3ca8c25716677`. El hash de la UI corresponde al excerpt numerado de líneas 1–16 y no debe confundirse con el hash del archivo completo.", "",
        "**Hallazgo abierto:** al abrir Inspect se mostró la traza histórica de Bruma `trace-5b385699ffda0529`, distinta de la traza nueva. La navegación funcionó, pero no se observó vinculación automática de Inspect con esta conversación; ese tramo no se declara PASS. [Captura, pasos, identidad y evidencia de la sesión](docs/assets/readme-20261022/README.md).", "",
        "### Ejecutar la demo local", "",
        "```bash", "python -m pip install -r requirements.txt", "python demo.py", "```", "",
        "La demo compone recuperación con citas, ejecución tipada, recibos, LocalTrace y evaluación estructural. El resultado esperado del fixture es `PASS`; la orden escrita aquí no acredita una ejecución nueva. Los artefactos se escriben en `demo_output/`.", "",
        "**Profundizar:** [demo y requisitos](docs/one_command_demo.md) · [lectura de sus artefactos](docs/one_command_demo_walkthrough.md) · [GEX fixture](docs/governed-execution/RUNTIME_FIXTURE_PROFILE.md) · [tutorial Bruma](output/playwright/bruma-market-tutorial/README.md).", "",
        *_render_verification(manifest),
        *_render_bago_visual_section("verification"),
        "**Profundizar:** [registro versionado de resultados](" + manifest["verification_record"] + ") · [contrato de generación y comprobaciones](docs/readme_generation.md) · [integridad teamctl](docs/verification/teamctl-integrity-20261022/README.md).", "",
        "## Instalación y operación", "",
        *_render_bago_visual_section("portability"),
        "La aplicación completa necesita Python 3.11+, Node.js 22 y un entorno Python activado. Desde la raíz del checkout, instala las dependencias declaradas, construye el frontend y arranca la API que sirve `frontend/dist`.", "",
        "```bash", *manifest["frontend"]["start_commands"], "```", "",
        "Abre <http://127.0.0.1:8080>. Los comandos describen el arranque, no una sesión iniciada por este README. Configura después el proveedor/modelo en Settings; su disponibilidad se comprueba por separado.", "",
        "| Modo | Entrada | Uso |", "|---|---|---|",
        "| App local compilada | `python -m src.api.server` después del build | API y frontend distribuido desde el mismo proceso |",
        "| Desarrollo frontend | `npm run dev --prefix frontend` con API local | Vite y proxy a la API |",
        "| Windows | `INICIAR_APP.cmd` o launcher documentado | Build y puerto libre según el contrato del launcher |",
        "| Demo offline | `python demo.py` | Recorrido determinista sin configurar un proveedor |", "",
        f"**Profundizar:** [instalación local]({manifest['frontend']['setup_guide']}) · [launcher PowerShell]({manifest['frontend']['launcher']}) · [guía frontend]({guide}#arranque-y-comprobaciones) · [demo portable](docs/one_command_demo.md).", "",
        "## Observabilidad e inspección", "",
        "Inspect permite revisar el resultado declarado junto a claims, evidencia, procedencia y artefactos disponibles. Job History, Trace y Evaluation complementan esa lectura con identidad, secuencia y comprobaciones del recorrido.", "",
        "| Recurso | Qué permite revisar | Frontera |", "|---|---|---|",
        "| LocalTrace | Pasos, IDs y enlaces de ejecución | Fuente local de evidencia; conservar su identidad y alcance |",
        "| Recibo y observador | Efecto declarado y postcondición | La presencia de un recibo no sustituye su integridad y validación |",
        "| Decision / BER Inspector | Conclusión, evidencia, autorización y registro de efecto | Presentación de los artefactos recibidos; no prueba independiente por sí sola |",
        "| Evaluation Lab | Casos, respuestas acotadas y checks declarados | No establece calidad general, seguridad ni facturación |",
        "| OpenTelemetry / Jaeger | Proyección de la traza y relaciones entre spans | No concede autoridad; requiere exportación/observación efectivas |", "",
        "**Observación actual del 22 de octubre:** la nueva conversación produjo `trace-496fac766f384348`, pero abrir Inspect mostró `trace-5b385699ffda0529` de Bruma. La continuidad Chat → Inspect necesita enlazar y comprobar la traza exacta de la conversación. El recorrido nuevo de lectura/respuesta y este hallazgo de inspección se conservan por separado.", "",
        "La evidencia L15 del **2026-10-08** registró 15 spans proyectados y observados y 13 operaciones con `PASS`. Se conserva como ejecución histórica local. Las capturas nuevas de esta página no se presentan como una nueva validación de Jaeger.", "",
        "**Profundizar:** [observabilidad y evaluación](docs/observability_evals.md) · [OpenTelemetry y Jaeger](docs/otel_jaeger.md) · [informe L15](evidence/l15_otel_jaeger_live.md) · [alcance del frontend](docs/readme_frontend.md#inspeccionar-la-evidencia).", "",
        "## Estado y roadmap", "",
        *_render_bago_visual_section("status"),
        f"**Estado canónico fechado:** {_cell(state['updated'])} · **fase declarada:** {_cell(state['current_phase'])}.", "",
        "El estado de una capacidad pertenece a su evidencia y entorno. Reorganizar esta portada conserva las capacidades documentadas, sin renovar automáticamente su fecha ni promover integraciones externas.", "",
        "| Capacidad | Estado y alcance documentados | Qué falta para una afirmación más amplia |", "|---|---|---|",
        "| Recuperación, ontología, sandbox y trazas locales | Estados de fases L1–L15 con evidencia específica | Repetir puertas afectadas para otra candidata/entorno |",
        "| Frontend de ADL | Fuentes, baterías fechadas y capturas actuales enlazadas | Comprobar cada efecto real y cada integración en su runtime |",
        "| Perfil GEX y BER | Contratos y límites propios enlazados arriba | Gate del perfil, host y proveedor efectivos |",
        "| AWS Bedrock Converse | Éxito histórico acotado; intentos posteriores con cuota agotada | Identidad, cuota y llamada nueva con recibo; coste real separado |",
        "| Bedrock KB, OpenMetadata remoto, commercetools live | `NOT_RUN` en el canon citado | Servicio, credenciales, datos y aceptación específicos |", "",
        "**Profundizar:** [STATE fechado](.bago/canon/STATE.md) · [roadmap](.bago/canon/ROADMAP.md) · [aprendizaje y evidencia](.bago/canon/LEARNING_LEDGER.md) · [inventario histórico por fase](#apéndices-y-evidencia-histórica).", "",
        "## Documentación y aprendizaje", "",
        "La documentación se organiza para pasar de una vista de conjunto al contrato, el procedimiento y la evidencia del recorrido que interesa. Cada sección de esta página tiene su propio acceso de profundización.", "",
        "| Quiero… | Empezar por… |", "|---|---|",
        "| Usar la aplicación desde Chat | [Guía del frontend](docs/readme_frontend.md) |",
        "| Instalar y arrancar | [Local setup](docs/agent-chat-control/LOCAL_SETUP.md) |",
        "| Entender una demo sin credenciales | [One-command demo](docs/one_command_demo.md) |",
        "| Revisar autorización y efectos | [GEX](docs/governed-execution/GEX_V1_NORMATIVE_CONTRACT.md) y [BER](docs/ber/AGENT_RUNNER_SCOPE.md) |",
        "| Desarrollar y revisar contexto | [Índice BAGO](.bago/INDEX.md) y [arquitectura](.bago/canon/ARCHITECTURE.md) |",
        "| Relacionar aprendizaje con evidencias | [Learning ledger](.bago/canon/LEARNING_LEDGER.md) y [skills](.bago/canon/JOB_SKILL_MATRIX.md) |",
        "| Contribuir a esta portada | [Contrato de generación](docs/readme_generation.md) y [manifiesto](docs/readme_manifest.json) |", "",
        "Las matrices de skills y roles conservan las estimaciones de planificación del proyecto. El catálogo de agentes es de referencia; las definiciones operativas y sus permisos se revisan en su contexto efectivo.", "",
        "**Profundizar:** [fuentes canónicas](.bago/INDEX.md) · [catálogo de agentes](agents/CATALOG_MANIFEST.json) · [agente de sincronización](docs/bago-sync-agent.md) · [licencia MIT](LICENSE).", "",
        "## Apéndices y evidencia histórica", "",
        "El detalle histórico conserva trazabilidad y procedencia. Las imágenes de tutoriales anteriores siguen en sus documentos originales; la galería de esta portada contiene únicamente capturas nuevas.", "",
        f"[Tutorial histórico de primer uso](docs/agent-chat-control/TUTORIAL_PRIMER_USO.md): conserva el recorrido de UI del 2026-10-19 con respuestas API sintéticas y sus referencias a la sesión histórica del 2026-10-10. No es evidencia de una ejecución nueva ni sustituye las capturas actuales del {manifest['presentation']['capture_date']}.", "",
        *_details("Fases L0–L15: estados declarados y archivos de evidencia", [
            "### Roadmap y evidencia por fase", "",
            "Los patrones resueltos identifican archivos del checkout; su presencia no implica repetir la ejecución.", "",
            _render_phase_table(phases), "", _render_flowchart(phases), "", _render_phase_evidence(phases),
        ]),
        *_details("Estado canónico y observaciones externas con su fecha", [
            f"**Alcance declarado:** {_cell(state['status'])}", "",
            f"**Siguiente bloque declarado:** {_cell(state['next_phase'])}", "",
            f"**Registro histórico de CI conservado en STATE.md:** {_cell(state['tests'])}", "",
            "Las observaciones históricas de crédito AWS no son un saldo vigente ni una comprobación actual de disponibilidad/facturación.", "",
            "[Free Tier histórico](evidence/l6_aws_free_tier.md) · [recibo Bedrock](evidence/l6_aws_live.md) · [intento Nova Lite](evidence/aws-live-attempts/20261018_nova_lite_throttled.md) · [intento Nova Micro](evidence/aws-live-attempts/20261018_nova_micro_throttled.md).",
        ]),
        *_details("Bruma Market: decisiones ficticias y recibos históricos", [
            _render_business_demo(manifest).replace("## Recorrido", "### Recorrido", 1),
        ]),
        *_details("Skills, roles y catálogo de referencia", [
            "Estimaciones históricas del proyecto; no evaluaciones independientes ni ofertas vigentes.", "",
            "### Roles objetivo", "", _render_roles(parse_roles()), "",
            "### Skills técnicas", "", _render_skills(parse_skills(), parse_skill_matrix_convention()), "",
            "### Skills estratégicas y personales", "", _render_soft_skills(parse_soft_skills()), "",
            _render_agent_catalog(), "", _render_sync_agent(manifest),
        ]),
        *_details("Fuentes canónicas y releases preservadas", [
            _render_canonical_documents(manifest), "", _render_releases(manifest),
        ]),
        "### Contrato de generación del README", "",
        "`README.md` es un artefacto generado. No lo edites manualmente: actualiza las fuentes canónicas y ejecuta el generador. La colección de pruebas y `--check --skip-tests` permanecen `NOT_RUN`; los resultados publicados proceden del registro de verificación versionado.", "",
        "[Contrato y revisión](docs/readme_generation.md) · [manifiesto](docs/readme_manifest.json) · [generador](scripts/generate_dynamic_readme.py).", "",
        "---", "", "**BAGO · Agentic Data Lab** · MIT License · [LICENSE](LICENSE)", "",
    ])
    return "\n".join(lines)

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check",
        action="store_true",
        help="fail if README.md is not identical to the generated output",
    )
    parser.add_argument(
        "--skip-tests",
        action="store_true",
        help="collect pytest cases without executing them or recording a pass result",
    )
    args = parser.parse_args(argv)

    test_count = collected_test_count() if args.skip_tests else executed_test_count()
    manifest = _read_json(MANIFEST_PATH)
    state = parse_state()
    rendered = render_readme(
        manifest=manifest,
        state=state,
        passing_tests=test_count,
    )
    current = README_PATH.read_text(encoding="utf-8") if README_PATH.exists() else ""
    if args.check:
        if current != rendered:
            print("README desactualizado: ejecuta python scripts/generate_dynamic_readme.py")
            return 1
        print(f"README verificado; suite NOT_RUN ({test_count} casos recogidos)" if args.skip_tests else f"README verificado; {test_count} tests pasaron")
        return 0
    README_PATH.write_text(rendered, encoding="utf-8", newline="\n")
    print(f"README generado; suite NOT_RUN ({test_count} casos recogidos)" if args.skip_tests else f"README generado tras {test_count} tests pasados")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
