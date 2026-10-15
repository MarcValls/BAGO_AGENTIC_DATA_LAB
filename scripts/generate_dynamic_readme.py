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
            or line.startswith("|---")
            or line.startswith("| Skill")
        ):
            continue
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        if len(cells) == 6:
            rows.append(cells)
    return rows


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
            or line.startswith("|---")
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

def _render_canonical_documents(manifest: dict[str, Any]) -> str:
    lines = [
        "| Documento | Función | Estado en este checkout |",
        "|---|---|---|",
    ]
    for document in manifest.get("canonical_documents", []):
        path = str(document["path"])
        state = "PRESENTE" if (REPO_ROOT / path).is_file() else "FALTA"
        lines.append(
            f"| [{_inline(path)}]({path}) | {_cell(document['role'])} | {_cell(state)} |"
        )
    return "\n".join(lines) or "No hay documentos canónicos declarados."

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


def _render_skills(rows: list[list[str]]) -> str:
    if not rows:
        return "No se pudo extraer la tabla técnica desde .bago/canon/JOB_SKILL_MATRIX.md."
    lines = [
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


def render_readme(
    *,
    manifest: dict[str, Any],
    state: dict[str, str],
    passing_tests: int,
) -> str:
    # Kept in the public helper signature for existing callers. Test outcomes
    # come from the exact CI record in STATE.md, never from test collection.
    project = manifest["project"]
    phases = phase_inventory(manifest, state)
    branch = project["default_branch"]
    branch_badge = branch.replace("/", "-")
    repository = project["repository"].rstrip("/")
    ci_workflow = project.get("ci_workflow", ".github/workflows/readme-consistency.yml")
    current_phase_id = state["current_phase"].split(" ", 1)[0]
    current_phase = next((phase for phase in phases if phase["id"] == current_phase_id), None)
    current_status = current_phase["status"] if current_phase else state["status_label"]
    tutorial = manifest.get("first_user_tutorial", {})
    guide = tutorial.get("guide", "docs/agent-chat-control/TUTORIAL_PRIMER_USO.md")
    video = tutorial.get("video", "docs/agent-chat-control/assets/ADL_videotutorial_primer_usuario.mp4")
    subtitles = tutorial.get("subtitles", "docs/agent-chat-control/assets/ADL_videotutorial_primer_usuario.es.srt")
    trace = tutorial.get("trace", "docs/agent-chat-control/assets/trace-c7ec5fcc40284a42.json")
    input_file = tutorial.get("input", "output/tutorial/sample-note.txt")
    render_first_user_tutorial(manifest)  # Fail closed if a declared artifact is missing.

    lines = [
        f"# {project['emoji']} {project['title']}",
        "",
        f"[![CI]({repository}/actions/workflows/{ci_workflow}/badge.svg)]({repository}/actions/workflows/{ci_workflow})",
        f"[![README consistency]({repository}/actions/workflows/readme-consistency.yml/badge.svg)]({repository}/actions/workflows/readme-consistency.yml)",
        f"[![Branch](https://img.shields.io/badge/branch-{branch_badge}-green)]({repository}/tree/{branch})",
        f"[![License](https://img.shields.io/badge/license-{project['license']}-blue)](LICENSE)",
        "",
        f"> {project['description']}",
        "> README generado desde fuentes canónicas y artefactos del checkout.",
        "",
        "## Qué es",
        "",
        "Un laboratorio para construir agentes cuya evidencia, permisos y efectos puedan inspeccionarse. Una respuesta del modelo, por sí sola, no demuestra autorización ni ejecución.",
        "",
        "## Demo local",
        "",
        "La demo principal usa fixtures locales y no llama a AWS ni a otros proveedores externos.",
        "",
        FENCE + "bash",
        "python -m pip install -r requirements.txt",
        "python demo.py",
        FENCE,
        "",
        "La guía explica la instalación en Windows y POSIX, los artefactos y sus límites: [demo de una orden](docs/one_command_demo.md) · [recorrido de artefactos](docs/one_command_demo_walkthrough.md).",
        "",
        "## Estado del proyecto",
        "",
        "| Campo | Valor |",
        "|---|---|",
        f"| Rama pública | {_inline(branch)} |",
        f"| Resumen actualizado | {_cell(state['updated'])} |",
        f"| Fase actual | **{_cell(state['current_phase'])}** · {_cell(current_status)} |",
        f"| Siguiente bloque declarado | {_cell(state['next_phase'])} |",
        f"| Último resultado completo de CI registrado | {_cell(state['tests'])} |",
        "",
        f"**Alcance declarado:** {_cell(state['status'])}",
        "",
        "La fecha corresponde a la actualización del resumen. Cada observación externa conserva la fecha y el alcance de su evidencia; este README no representa una consulta en vivo.",
        "",
        "## Arquitectura y fases",
        "",
        f"**Principio:** {manifest['architecture']['principle']}",
        "",
        _render_flowchart(phases),
        "",
        "La tabla muestra estados declarados en el manifiesto del proyecto; consulta las fuentes canónicas para conocer el alcance comprobado.",
        "",
        _render_phase_table(phases),
        "",
        "## Evidencia y límites",
        "",
        "- [Verificación L15 con Jaeger local](evidence/l15_otel_jaeger_live.md): resultado fechado del 2026-10-08; es evidencia histórica local, no disponibilidad actual del servicio.",
        f"- [Último resultado completo de CI]({repository}/actions/runs/38665463586): estado y SHA del commit verificados en `STATE.md`; no cubre cambios posteriores.",
        "- [Límites operativos actuales](.bago/canon/STATE.md): AWS, OpenMetadata remoto y commercetools mantienen su alcance `NOT_RUN` o `NOT_PROVEN` donde corresponde.",
        "",
        "La demo local evalúa trazas y controles estructurales; no prueba calidad general de respuestas, aislamiento de producción ni integraciones cloud en vivo.",
        "",
        "## Tutorial de interfaz",
        "",
        f"- [Guía y límites]({guide})",
        f"- [Vídeo narrado]({video}) · [subtítulos]({subtitles})",
        f"- [Traza de la sesión documentada]({trace}) · [archivo de ejemplo]({input_file})",
        "",
        "La grabación acredita la lectura y respuesta acotadas descritas en la guía; no una auditoría del código ni ejecución de trabajos.",
        "",
        "## Fuentes canónicas",
        "",
        _render_canonical_documents(manifest),
        "",
        "- [Índice de contexto BAGO](.bago/INDEX.md)",
        "- [Contrato del laboratorio y estimaciones de planificación](.bago/canon/LAB_CONTRACT.md)",
        "- [Matriz de skills](.bago/canon/JOB_SKILL_MATRIX.md); sus porcentajes son estimaciones del proyecto, no evaluaciones independientes.",
        "- [Catálogo de agentes](agents/CATALOG_MANIFEST.json), de referencia; las definiciones operativas están en `.github/agents/`.",
        "- [Agente de sincronización: documentación](docs/bago-sync-agent.md) · [definición](.github/agents/bago-sync-agent.agent.md)",
        "",
        "## Reproducción y CI",
        "",
        FENCE + "bash",
        "python -m pytest tests -q",
        "python scripts/generate_dynamic_readme.py --check --skip-tests",
        "python scripts/run_public_e2e_demo.py --check",
        FENCE,
        "",
        "La CI completa ejecuta la suite, valida este README y comprueba las demos y servicios locales. `--check --skip-tests` solo comprueba el render y recoge casos; informa `NOT_RUN` y no acredita que pasen.",
        "",
        "La regla de coste cero sigue vigente: el README no propone ejecutar comprobaciones AWS. Las comprobaciones locales que escriben evidencia o arrancan Docker se describen en sus guías específicas.",
        "",
        "## Generación",
        "",
        "`README.md` es un artefacto generado. No lo edites manualmente; modifica las fuentes canónicas y ejecuta el generador.",
        "",
        "- [Contrato de generación y revisión](docs/readme_generation.md)",
        "- Manifiesto de contenido: `docs/readme_manifest.json`",
        "- [Registro congelado portfolio-demo-v1](docs/cv_linkedin/portfolio-demo-v1.md)",
        "",
        "MIT License · [LICENSE](LICENSE)",
        "",
    ]
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
