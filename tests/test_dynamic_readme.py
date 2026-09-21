"""Tests for the non-destructive README metrics updater."""

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

from generate_dynamic_readme import update_readme  # noqa: E402


def test_update_readme_preserves_manual_content_and_updates_metrics():
    source = """# README\n\n[![Tests](https://img.shields.io/badge/tests-11%2F11%20passing-brightgreen)]()\n[![Commits](https://img.shields.io/badge/commits-6-orange)]()\n| **Tests Passing** | 11/11 ✅ |\n✅ **Testing CRIT P0** - 11 tests passing\nÚltima actualización: 2026-09-21\nGenerado: 2026-09-21\n"""

    updated = update_readme(source, tests=29, commits=7, generated="2026-09-21 22:00:00")

    assert "# README" in updated
    assert "tests-29%2F29%20passing" in updated
    assert "| **Tests Passing** | 29/29 ✅ |" in updated
    assert "Testing CRIT P0** - 29 tests passing" in updated
    assert "commits-7-orange" in updated
    assert "Generado: 2026-09-21 22:00:00" in updated
