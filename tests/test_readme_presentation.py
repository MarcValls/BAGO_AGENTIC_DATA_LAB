"""Reader order and evidence boundaries for the generated README."""
import copy
import importlib
import json
from pathlib import Path
import re
import sys

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


def test_reader_reaches_app_and_results_before_architecture_and_history():
    headings = re.findall(r"^## (.+)$", render(), re.MULTILINE)
    assert headings == [
        "El laboratorio", "La aplicación frontend", "Tests y verificación",
        "Ejecutar la demo local", "Arquitectura de un vistazo",
        "Historial y evidencia", "Documentación del proyecto",
        "Contrato de generación del README",
    ]


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
    for name, passed in (("Backend Python", 539), ("Frontend Vitest", 127),
                         ("Frontend UI Node", 49), ("Contratos TypeScript", 13)):
        assert checks[name]["counts"]["passed"] == passed
        assert checks[name]["counts"]["failed"] == checks[name]["counts"]["skipped"] == 0
    assert "539 passed" in "\n".join(evidence["summary_lines"])
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
    text = render()
    app = text.split("## La aplicación frontend", 1)[1].split("## Tests y verificación", 1)[0]
    config = manifest()["frontend"]
    for key in ("entry", "package", "api", "setup_guide", "launcher"):
        assert (ROOT / config[key]).is_file()
    for command in config["start_commands"]:
        assert command in app
    assert "npm ci --prefix frontend" in app
    assert "npm run build --prefix frontend" in app
    assert "python -m src.api.server" in app
    assert config["launcher"] in app and config["setup_guide"] in app
    assert "no una sesión iniciada" in app
    assert "python demo.py" not in app


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
