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
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"))
    except (OSError, SyntaxError):
        return 0
    def is_pytest_fixture(node: ast.AST) -> bool:
        decorators = getattr(node, "decorator_list", [])
        for decorator in decorators:
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
    """Count test functions without importing project dependencies."""
    return sum(
        _test_function_count(path)
        for path in sorted((REPO_ROOT / "tests").glob("test_*.py"))
    )


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
    """Read the current, top-level state block from STATE.md."""
    text = (REPO_ROOT / "STATE.md").read_text(encoding="utf-8")

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
        "tests": field("Tests"),
        "next_phase": field("Next phase"),
    }


def parse_roles() -> list[list[str]]:
    """Extract the current target-role table from LAB_CONTRACT.md."""
    text = (REPO_ROOT / "LAB_CONTRACT.md").read_text(encoding="utf-8")
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
    """Extract the technical skill table from JOB_SKILL_MATRIX.md."""
    text = (REPO_ROOT / "JOB_SKILL_MATRIX.md").read_text(encoding="utf-8")
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
    """Extract the strategic/soft skill table from JOB_SKILL_MATRIX.md."""
    text = (REPO_ROOT / "JOB_SKILL_MATRIX.md").read_text(encoding="utf-8")
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
        "| Fase | Estado | Objetivo | Descripción | Tests | Evidencia/docs |",
        "|---|---|---|---|---:|---:|",
    ]
    for phase in phases:
        test_count = sum(
            _test_function_count(REPO_ROOT / match)
            for check in phase["checks"]
            if check["kind"] == "tests"
            for match in check["matches"]
        )
        evidence_count = sum(
            len(check["matches"])
            for check in phase["checks"]
            if check["kind"] in {"evidence", "contract"}
        )
        lines.append(
            f"| {_cell(phase['id'])} | {_cell(phase['status'])} | "
            f"{_cell(phase.get('target', '—'))} | {_cell(phase['name'])} | "
            f"{test_count} | {evidence_count} |"
        )
    return "\n".join(lines)


def _render_canonical_documents(manifest: dict[str, Any]) -> str:
    lines = [
        "| Documento | Función | Estado |",
        "|---|---|---|",
    ]
    for document in manifest.get("canonical_documents", []):
        path = str(document["path"])
        state = "PRESENTE" if (REPO_ROOT / path).is_file() else "FALTA"
        lines.append(
            f"| {_inline(path)} | {_cell(document['role'])} | {_cell(state)} |"
        )
    return "\n".join(lines) or "No hay documentos canónicos declarados."


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
        return "No se pudo extraer la tabla de vacantes desde LAB_CONTRACT.md."
    lines = [
        "| Empresa | Rol | Fit | Gap principal | Timeline |",
        "|---|---|---:|---|---|",
    ]
    lines.extend("| " + " | ".join(_cell(cell) for cell in row) + " |" for row in rows)
    return "\n".join(lines)


def _render_skills(rows: list[list[str]]) -> str:
    if not rows:
        return "No se pudo extraer la tabla técnica desde JOB_SKILL_MATRIX.md."
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
        return "No se pudo extraer la tabla estratégica desde JOB_SKILL_MATRIX.md."
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


def render_readme(
    *,
    manifest: dict[str, Any],
    state: dict[str, str],
    passing_tests: int,
) -> str:
    project = manifest["project"]
    phases = phase_inventory(manifest, state)
    total_tests = collected_test_count()
    test_badge = f"tests-{passing_tests}%2F{total_tests}%20passing"
    branch = project["default_branch"]
    branch_badge = branch.replace("/", "-")
    current_phase = next(
        (phase for phase in phases if phase["id"] == state["current_phase"].split(" ", 1)[0]),
        None,
    )
    current_status = current_phase["status"] if current_phase else state["status_label"]
    ci_workflow = project.get("ci_workflow", ".github/workflows/readme-consistency.yml")
    roles = parse_roles()
    skills = parse_skills()
    soft_skills = parse_soft_skills()
    test_files = _files_under("tests", "test_*.py")
    docs = _files_under("docs", "*.md")
    evidence = _files_under("evidence", "*")
    scripts = _files_under("scripts", "*.py")
    infrastructure = _files_under(
        "infra",
        "*",
        excluded_dirs=("docker-volume",),
    )
    source = _files_under("src", "*.py")

    lines = [
        f"# {project['emoji']} {project['title']}",
        "",
        f"[![CI]({project['repository']}/actions/workflows/{ci_workflow}/badge.svg)]({project['repository']}/actions/workflows/{ci_workflow})",
        f"[![GitHub]({project['repository']}/actions/workflows/readme-consistency.yml/badge.svg)]({project['repository']}/actions/workflows/readme-consistency.yml)",
        f"[![Branch](https://img.shields.io/badge/branch-{branch_badge}-green)]({project['repository']}/tree/{branch})",
        f"[![Tests](https://img.shields.io/badge/{test_badge}-brightgreen)]({project['repository']}/actions)",
        f"[![License](https://img.shields.io/badge/license-{project['license']}-blue)](LICENSE)",
        "",
        f"> {project['description']}",
        "> Este documento se genera desde el estado y los artefactos del repositorio.",
        "",
        "## Estado actual",
        "",
        "| Métrica | Valor |",
        "|---|---|",
        f"| Tests ejecutados | **{passing_tests}/{total_tests}** |",
        f"| Rama pública | {_inline(branch)} |",
        f"| Estado actualizado | {_cell(state['updated'])} |",
        f"| Fase actual | **{_cell(state['current_phase'])}** · {_cell(current_status)} |",
        f"| Siguiente bloque | {_cell(state['next_phase'])} |",
        f"| Estado declarado | {_cell(state['status'])} |",
        "",
        "El estado público se limita a lo que existe en el checkout y a la evidencia",
        "referenciada. AWS live, OpenMetadata live y otras integraciones externas",
        "no se presentan como verificadas si STATE.md las marca como NOT_RUN.",
        "El commit, push y merge de este snapshot son operaciones separadas.",
        "",
        "## Fuentes canónicas",
        "",
        "El README proyecta estos documentos; no los sustituye ni los edita.",
        "",
        _render_canonical_documents(manifest),
        "",
        "## Agente de sincronización",
        "",
        "La sincronización operativa está separada del catálogo de copias de referencia.",
        "",
        _render_sync_agent(manifest),
        "",
        "## Catálogo de agentes",
        "",
        "El catálogo organizado por responsabilidad se genera desde "
        "`agents/CATALOG_MANIFEST.json`.",
        "",
        _render_agent_catalog(),
        "",
        "## Roadmap detectado",
        "",
        _render_flowchart(phases),
        "",
        _render_phase_table(phases),
        "",
        "## Arquitectura actual",
        "",
        _render_architecture(manifest),
        "",
        "## Job market alignment",
        "",
        "La tabla se extrae de LAB_CONTRACT.md; no se duplica manualmente aquí.",
        "",
        _render_roles(roles),
        "",
        "## Skills evidenciadas",
        "",
        "La tabla se extrae de JOB_SKILL_MATRIX.md y se mantiene fuera del README.",
        "",
        _render_skills(skills),
        "",
        "## Skills estratégicas",
        "",
        "La tabla se extrae de JOB_SKILL_MATRIX.md y se mantiene fuera del README.",
        "",
        _render_soft_skills(soft_skills),
        "",
        "## Inventario real del checkout",
        "",
        "### Código fuente",
        "",
        _markdown_list(source),
        "",
        "### Tests",
        "",
        "\n".join(
            f"- {_inline(path)} ({_test_function_count(REPO_ROOT / path)} checks)"
            for path in test_files
        )
        or "- Ninguno detectado.",
        "",
        "### Evidencia",
        "",
        _markdown_list(evidence),
        "",
        "### Documentación",
        "",
        _markdown_list(docs),
        "",
        "### Scripts",
        "",
        _markdown_list(scripts),
        "",
        "### Infraestructura reproducible",
        "",
        _markdown_list(infrastructure),
        "",
        "### CI automática",
        "",
        f"- {_inline(f'.github/workflows/{ci_workflow}')} · suite, README, demo E2E y compile check",
        "",
        "## Comandos reproducibles",
        "",
        FENCE + "bash",
        "python -m pip install -r requirements.txt",
        "python -m pytest tests -q",
        "python scripts/generate_dynamic_readme.py",
        "python scripts/generate_dynamic_readme.py --check --skip-tests",
        "python scripts/run_public_e2e_demo.py --check",
        "python scripts/run_public_e2e_demo.py --write-evidence",
        "docker compose -p bago-openmetadata -f infra/openmetadata/docker-compose.yml up -d",
        "python scripts/run_l8_openmetadata_live_validation.py",
        "python scripts/run_sandbox_local_validation.py",
        FENCE,
        "",
        "Tests por fase:",
        "",
    ]
    for phase in phases:
        phase_tests = sorted(
            {
                match
                for check in phase["checks"]
                if check["kind"] == "tests"
                for match in check["matches"]
            }
        )
        if phase_tests:
            command = "python -m pytest " + " ".join(phase_tests) + " -q"
            lines.append(f"- {_inline(phase['id'])}: {_inline(command)}")
    lines.extend(
        [
            "",
            "## Contrato de generación",
            "",
            "README.md es un artefacto generado. No editarlo manualmente.",
            "Las decisiones estables viven en docs/readme_manifest.json y en los",
            "documentos canónicos enlazados arriba; los inventarios, métricas,",
            "métricas de tests y estado declarado se calculan al generar.",
            "",
            "- Generar: python scripts/generate_dynamic_readme.py",
            "- Comprobar deriva: python scripts/generate_dynamic_readme.py --check --skip-tests",
            "- Comprobar con la suite completa: python scripts/generate_dynamic_readme.py --check",
            "",
            f"Fuente de estado: {_inline('STATE.md')}; contrato: {_inline('LAB_CONTRACT.md')};",
            f"skills: {_inline('JOB_SKILL_MATRIX.md')}; manifiesto: {_inline('docs/readme_manifest.json')}.",
            "",
            "MIT License — ver [LICENSE](LICENSE).",
            "",
        ]
    )
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
        help="count test functions without executing pytest",
    )
    args = parser.parse_args(argv)

    passing_tests = collected_test_count() if args.skip_tests else executed_test_count()
    manifest = _read_json(MANIFEST_PATH)
    state = parse_state()
    rendered = render_readme(
        manifest=manifest,
        state=state,
        passing_tests=passing_tests,
    )
    current = README_PATH.read_text(encoding="utf-8") if README_PATH.exists() else ""
    if args.check:
        if current != rendered:
            print("README desactualizado: ejecuta python scripts/generate_dynamic_readme.py")
            return 1
        print(f"README verificado ({passing_tests} tests)")
        return 0
    README_PATH.write_text(rendered, encoding="utf-8", newline="\n")
    print(f"README generado: {passing_tests} tests")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
