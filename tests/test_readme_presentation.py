"""Reader order and evidence boundaries for the generated README."""
import copy
from datetime import date
import hashlib
import importlib
import json
from pathlib import Path
import re
import sys
import xml.etree.ElementTree as ET
from urllib.parse import unquote

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
generator = importlib.import_module("generate_dynamic_readme")


def manifest():
    return json.loads((ROOT / "docs/readme_manifest.json").read_text(encoding="utf-8"))


def record():
    return json.loads((ROOT / manifest()["verification_record"]).read_text(encoding="utf-8"))


def render(passing_tests=0):
    return generator.render_readme(
        manifest=manifest(), state=generator.parse_state(), passing_tests=passing_tests
    )


PRINCIPAL_SECTIONS = [
    "El laboratorio", "La aplicación frontend", "La aplicación en pantalla",
    "Datos y conocimiento", "Agentes, tareas y evaluación", "Proveedores y modelos",
    "BAGO, BER y ejecución gobernada", "Arquitectura de un vistazo", "Casos y demos",
    "Tests y verificación", "Instalación y operación", "Observabilidad e inspección",
    "Estado y roadmap", "Documentación y aprendizaje",
]


def visible_markdown(text):
    return re.sub(r"<details>.*?</details>", "", text, flags=re.DOTALL)


def sections(text):
    parts = re.split(r"^## (.+)$", text, flags=re.MULTILINE)
    return dict(zip(parts[1::2], parts[2::2]))


def test_corporate_overview_exposes_all_principal_sections_and_chat_entry():
    text = render()
    visible = visible_markdown(text)
    headings = re.findall(r"^## (.+)$", visible, re.MULTILINE)
    assert headings[:14] == PRINCIPAL_SECTIONS
    assert "**Entrada principal: Chat.**" in visible.split("## El laboratorio", 1)[0]
    assert "**EN ESTA PÁGINA**" in visible
    assert "[Revisar tests](#tests-y-verificación)" in visible
    assert text.count("<details>") == text.count("</details>")
    for heading in PRINCIPAL_SECTIONS:
        body = sections(visible)[heading]
        assert len(body.split()) >= 30, heading
        assert "**Profundizar:**" in body, heading
        assert "|" in body or "![" in body or "```mermaid" in body, heading


def test_each_principal_section_links_to_existing_deeper_material():
    for heading, body in sections(visible_markdown(render())).items():
        if heading not in PRINCIPAL_SECTIONS:
            continue
        deep = body.split("**Profundizar:**", 1)[1]
        links = re.findall(r"\[[^\]]+\]\(([^)]+)\)", deep)
        assert links, heading
        for link in links:
            if link.startswith(("http:", "https:", "#")):
                continue
            target, _, anchor = unquote(link).partition("#")
            path = (ROOT / target).resolve()
            assert path.is_relative_to(ROOT.resolve()), link
            assert path.is_file(), link
            if anchor and path.suffix == ".md":
                headings = re.findall(r"^#{1,6} (.+)$", path.read_text(encoding="utf-8"), re.MULTILINE)
                anchors = {re.sub(r"[^\w\- ]", "", h.lower()).replace(" ", "-") for h in headings}
                assert anchor in anchors, link


def test_corporate_banner_is_self_contained_and_has_accessible_image_text():
    presentation = manifest()["presentation"]
    banner = ROOT / presentation["banner"]
    source = banner.read_text(encoding="utf-8")
    svg = ET.fromstring(source)
    assert svg.tag == "{http://www.w3.org/2000/svg}svg"
    assert svg.attrib.get("viewBox")
    assert "447b9d" in source.lower() and "f2efea" in source.lower()
    assert "<path" in source  # Existing BAGO vector identity, not plain title text.
    for node in svg.iter():
        assert node.tag.rsplit("}", 1)[-1] not in {"script", "foreignObject"}
        for key, value in node.attrib.items():
            if key.rsplit("}", 1)[-1] == "href":
                assert value.startswith("#"), value
    assert re.search(r"!\[[^\]]+\]\(" + re.escape(presentation["banner"]) + r"\)", render())


def test_gallery_uses_new_observed_captures_with_provenance_and_limits():
    presentation = manifest()["presentation"]
    capture_date = date.fromisoformat(presentation["capture_date"])
    month_names = (
        "enero", "febrero", "marzo", "abril", "mayo", "junio",
        "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre",
    )
    gallery = sections(render())["La aplicación en pantalla"]
    assert "Brave visible" in gallery and presentation["capture_date"] in gallery
    assert "guía enlazada" in gallery
    assert "Capturas del recorrido documentado" in gallery
    assert "traza anterior de Bruma" not in gallery
    assert f"![Carrusel de capturas actuales de BAGO ADL]({presentation['carousel_gif']})" in gallery
    assert f"[visor HTML con controles de anterior, siguiente y pausa]({presentation['carousel_html']})" in gallery
    gif = ROOT / presentation["carousel_gif"]
    assert gif.read_bytes().startswith((b"GIF87a", b"GIF89a"))
    viewer = (ROOT / presentation["carousel_html"]).read_text(encoding="utf-8")
    for control in ('id="prev"', 'id="next"', 'id="play"', "ArrowLeft", "ArrowRight"):
        assert control in viewer
    assert len(presentation["captures"]) >= 5
    paths = [item["path"] for item in presentation["captures"]]
    assert len(paths) == len(set(paths))
    provenance = ROOT / presentation["capture_guide"]
    assert provenance.is_file()
    guide_text = provenance.read_text(encoding="utf-8")
    documented_date = (
        f"{capture_date.day} de {month_names[capture_date.month - 1]} "
        f"de {capture_date.year}"
    )
    assert documented_date in guide_text
    assert presentation["capture_guide"] == "docs/verification/readme-captures-20261025.md"
    for item in presentation["captures"]:
        relative_path = Path(item["path"])
        assert not relative_path.is_absolute() and ".." not in relative_path.parts
        assert relative_path.suffix.lower() == ".png"
        path = (ROOT / relative_path).resolve()
        assert path.is_relative_to(ROOT.resolve()) and path.is_file()
        assert item["alt"].strip() and item["caption"].strip()
        assert path.read_bytes().startswith(b"\x89PNG\r\n\x1a\n")
        assert f"![{item['alt']}]({item['path']})" in gallery
        assert item["caption"] in gallery
        assert relative_path.name in guide_text
    assert presentation["capture_guide"] in gallery


def test_current_chat_evidence_keeps_the_unlinked_inspect_finding_open():
    demo = ROOT / "docs/verification/readme-corporate-20261022/demo"
    result = json.loads((demo / "RESULT.json").read_text(encoding="utf-8"))
    trace = json.loads((demo / f"{result['trace_id']}.json").read_text(encoding="utf-8"))
    assert result["schema"] == "bago.readme.chat-demonstration.v1"
    assert result["checks"]["new_agent_chat_response"] == "PASS"
    assert result["checks"]["authorized_file_read"] == "PASS"
    assert result["checks"]["automatic_current_chat_trace_in_inspect"] == "FAIL"
    assert trace["trace_id"] == result["trace_id"]
    workflow = next(event for event in trace["events"] if event["name"] == "agent.chat")
    read = next(event for event in trace["events"] if event["name"] == "workspace.read")
    assert workflow["attributes"]["agent_id"] == result["agent_id"]
    assert workflow["attributes"]["outcome"] == "response_received"
    assert workflow["attributes"]["model_id"] == result["model"]
    assert workflow["attributes"]["provider_id"] == result["provider"]
    assert workflow["attributes"]["cost_status"] == "not_reported"
    assert read["attributes"]["decision"] == "ALLOW"
    assert read["attributes"]["file_sha256"] == result["file_sha256"]
    assert read["attributes"]["content_sha256"] == result["numbered_excerpt_sha256"]
    for name, digest in result["artifacts"].items():
        path = (demo / name).resolve()
        assert path.is_relative_to(demo.resolve())
        assert hashlib.sha256(path.read_bytes()).hexdigest() == digest
    body = sections(visible_markdown(render()))["Casos y demos"]
    assert result["trace_id"] in body and result["file_sha256"] in body
    assert "trace-5b385699ffda0529" in body
    assert "ese tramo no se declara PASS" in body
    assert "no se ejecutó un reembolso ni una herramienta genérica" in body


def test_dated_ci_snapshot_matches_its_preserved_evidence_and_separate_batteries():
    data = record()
    ci = data["ci"]
    evidence = json.loads((ROOT / ci["evidence_path"]).read_text(encoding="utf-8"))
    assert data["schema"] == "bago.readme.verification.v1"
    assert evidence["conclusion"] == "success"
    for key in ("candidate", "completed_at", "run_url"):
        assert ci[key] == evidence[key]
    assert re.fullmatch(r"[a-f0-9]{64}", evidence["source_log_sha256"])
    assert re.fullmatch(r"[a-f0-9]{64}", evidence["source_metadata_sha256"])
    checks = {check["name"]: check for check in ci["checks"]}
    # These are dated predecessor results, never the current collected count.
    assert ci["candidate"] == "64a88fbc30bb1b2c0a4cd516281c71be1f65748b"
    for name in ("Backend Python", "Frontend Vitest", "Frontend UI Node", "Contratos TypeScript"):
        assert checks[name]["counts"]["passed"] > 0
        assert checks[name]["result"] == "PASS"
        assert checks[name]["counts"]["failed"] == checks[name]["counts"]["skipped"] == 0
    passed = checks["Backend Python"]["counts"]["passed"]
    assert f"{passed} passed" in "\n".join(evidence["summary_lines"])
    text = render()
    for value in (ci["candidate"], ci["completed_at"], ci["run_url"], data["recorded_at"]):
        assert value in text
    for check in ci["checks"]:
        for key in ("name", "command", "summary", "evidence_url"):
            assert check[key] in text
    assert ci["scope"] in text
    assert "ni cubre cambios posteriores" in text
    for old in data["historical"]:
        assert old["candidate"] in text and old["scope"] in text
        assert old["summary"] in text and old["evidence_url"] in text


def test_collection_argument_cannot_change_the_published_results():
    assert render(0) == render(987654321)
    assert "987654321" not in render(987654321)


def test_frontend_instructions_point_to_real_sources_and_keep_demo_distinct():
    bodies = sections(visible_markdown(render()))
    app = bodies["La aplicación frontend"]
    install = bodies["Instalación y operación"]
    config = manifest()["frontend"]
    for key in ("entry", "package", "api", "setup_guide", "launcher"):
        assert (ROOT / config[key]).is_file()
    for command in config["start_commands"]:
        assert command in install
    assert "npm ci --prefix frontend" in install
    assert "npm run build --prefix frontend" in install
    assert "python -m src.api.server" in install
    assert config["launcher"] in install and config["setup_guide"] in install
    assert "no una sesión iniciada" in install
    assert "python demo.py" not in app
    assert "Chat como entrada principal" in app
    assert "no se afirma cobertura total desde Chat" in app
    assert manifest()["presentation"]["frontend_guide"] in app


@pytest.mark.parametrize("mutation", [
    "missing_candidate", "missing_evidence", "collection_as_result",
    "unsupported_schema", "path_escape",
])
def test_incomplete_or_nonexecution_records_cannot_be_promoted(mutation, monkeypatch):
    data = copy.deepcopy(record())
    specification = manifest()
    if mutation == "missing_candidate":
        data["ci"].pop("candidate")
    elif mutation == "missing_evidence":
        data["ci"]["checks"][0].pop("evidence_url")
    elif mutation == "collection_as_result":
        data["ci"]["checks"][0]["result"] = "COLLECTED"
    elif mutation == "unsupported_schema":
        data["schema"] = "unsupported"
    else:
        specification["verification_record"] = "../outside.json"
    monkeypatch.setattr(generator, "_read_json", lambda path: data)
    with pytest.raises(ValueError):
        generator._render_verification(specification)


def test_recorded_not_run_is_rendered_without_inventing_a_pass(monkeypatch):
    data = copy.deepcopy(record())
    data["historical"] = []
    data["ci"]["checks"] = [{
        "name": "Collection only", "command": "pytest --collect-only",
        "result": "NOT_RUN", "summary": "321 casos recogidos; ejecución pendiente",
        "counts": {}, "evidence_url": data["ci"]["run_url"],
    }]
    monkeypatch.setattr(generator, "_read_json", lambda path: data)
    text = "\n".join(generator._render_verification(manifest()))
    assert "`NOT_RUN`" in text and "321 casos recogidos" in text
    assert "PASS" not in text


def test_check_skip_collects_without_execution_or_rewriting_readme(tmp_path, monkeypatch, capsys):
    expected = render()
    path = tmp_path / "README.md"
    path.write_text(expected, encoding="utf-8")
    before = path.read_bytes()
    monkeypatch.setattr(generator, "README_PATH", path)
    monkeypatch.setattr(generator, "collected_test_count", lambda: 987654321)
    def forbidden_execution():
        pytest.fail("--check --skip-tests executed the test suite")
    monkeypatch.setattr(generator, "executed_test_count", forbidden_execution)
    assert generator.main(["--check", "--skip-tests"]) == 0
    assert path.read_bytes() == before
    output = capsys.readouterr().out
    assert "NOT_RUN" in output and "987654321" in output
    assert "tests pasaron" not in output
