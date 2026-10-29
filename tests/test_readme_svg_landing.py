"""Navigable SVG README coverage and trust boundaries."""
import json
from pathlib import Path
import sys
import xml.etree.ElementTree as ET

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import generate_dynamic_readme as generator  # noqa: E402


def test_minimal_landing_preserves_navigation_and_complete_reference():
    visual = generator.render_svg_landing()
    full = (ROOT / "README_DETAILS.md").read_text(encoding="utf-8")
    manifest = json.loads((ROOT / "docs/readme_svg_manifest.json").read_text(encoding="utf-8"))
    assert manifest["schema"] == "bago.readme.svg.landing.v3"
    assert visual.startswith("# BAGO Agentic Data Lab\n")
    assert "<details" not in visual.lower() and "<summary" not in visual.lower()
    assert "00-hero.svg" not in visual and "01-map.svg" not in visual
    for item in manifest["navigation"]:
        assert f'[{item["label"]}]({item["target"]})' in visual
        assert (ROOT / item["target"].split("#", 1)[0]).is_file()
    for heading in (
        "## El laboratorio", "## La aplicación frontend", "## Datos y conocimiento",
        "## Tests y verificación", "## Estado y roadmap",
    ):
        assert heading in full
    assert "model_registration_mismatch" in full
    assert "ese tramo no se declara PASS" in full
    assert "actions_executed" in full


def test_svg_panels_are_self_contained_and_preserve_visual_identity():
    panels = json.loads((ROOT / "docs/readme_svg_manifest.json").read_text(encoding="utf-8"))["panels"]
    for item in panels:
        content = (ROOT / item["asset"]).read_text(encoding="utf-8")
        svg = ET.fromstring(content)
        assert svg.tag == "{http://www.w3.org/2000/svg}svg"
        assert svg.attrib["viewBox"].startswith("0 0 1200 ")
        assert "#447b9d" in content.lower() and "#f2efea" in content.lower()
        assert "<rect" in content and "<text" in content
        for element in svg.iter():
            tag = element.tag.rsplit("}", 1)[-1]
            assert tag not in {"script", "foreignObject", "image", "iframe", "animate", "set"}
            for key, value in element.attrib.items():
                name = key.rsplit("}", 1)[-1]
                assert not name.startswith("on")
                if name == "href":
                    assert value.startswith("#")
        assert (ROOT / item["target"].split("#")[0]).is_file()


@pytest.mark.parametrize(
    "mutation",
    ["escape", "external", "no_alt", "nav_escape", "nav_external", "nav_bad_label"],
)
def test_vector_manifest_rejects_bad_paths_and_inaccessible_panels(tmp_path, monkeypatch, mutation):
    original = json.loads((ROOT / "docs/readme_svg_manifest.json").read_text(encoding="utf-8"))
    item = original["panels"][0] if not mutation.startswith("nav_") else original["navigation"][0]
    if mutation == "escape":
        item["asset"] = "docs/assets/readme-banner/../../unsafe.svg"
    elif mutation == "external":
        item["target"] = "https://attacker.example"
    elif mutation == "no_alt":
        item["alt"] = ""
    elif mutation == "nav_escape":
        item["target"] = "docs/../README_DETAILS.md"
    elif mutation == "nav_external":
        item["target"] = "https://attacker.example"
    else:
        item["label"] = "[external link](https://attacker.example)"
    path = tmp_path / "manifest.json"
    path.write_text(json.dumps(original), encoding="utf-8")
    monkeypatch.setattr(generator, "SVG_LANDING_MANIFEST_PATH", path)
    with pytest.raises((ValueError, FileNotFoundError)):
        generator.render_svg_landing()
