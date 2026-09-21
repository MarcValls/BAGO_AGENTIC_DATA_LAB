"""Update README metrics without replacing its hand-maintained content."""

from __future__ import annotations

import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
README_PATH = REPO_ROOT / "README.md"


def _run(command: list[str]) -> str:
    result = subprocess.run(
        command,
        cwd=REPO_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        details = (result.stdout + result.stderr).strip()
        raise RuntimeError(f"Command failed ({result.returncode}): {' '.join(command)}\n{details}")
    return result.stdout + result.stderr


def collected_test_count() -> int:
    """Run the repository suite and return its passing test count."""
    output = _run([sys.executable, "-m", "pytest", "tests", "-q", "--disable-warnings"])
    match = re.search(r"(?P<count>\d+) passed", output)
    if not match:
        raise RuntimeError("pytest completed without a parseable passing count")
    return int(match.group("count"))


def commit_count() -> int:
    """Return the number of commits reachable from the current HEAD."""
    return int(_run(["git", "rev-list", "--count", "HEAD"]).strip())


def update_readme(text: str, tests: int, commits: int, generated: str) -> str:
    """Update only dynamic counters and dates in the existing README."""
    replacements = [
        (
            r"tests-\d+%2F\d+%20passing",
            f"tests-{tests}%2F{tests}%20passing",
        ),
        (
            r"(\| \*\*Tests Passing\*\* \| )\d+/\d+( ✅ \|)",
            rf"\g<1>{tests}/{tests}\g<2>",
        ),
        (
            r"(\*\*Testing CRIT P0\*\* - )\d+ tests passing",
            rf"\g<1>{tests} tests passing",
        ),
        (
            r"commits-\d+-orange",
            f"commits-{commits}-orange",
        ),
        (
            r"(Última actualización: )\d{4}-\d{2}-\d{2}",
            rf"\g<1>{generated[:10]}",
        ),
        (
            r"(Generado: )\d{4}-\d{2}-\d{2}(?: \d{2}:\d{2}:\d{2})?",
            rf"\g<1>{generated}",
        ),
    ]
    updated = text
    for pattern, replacement in replacements:
        updated, count = re.subn(pattern, replacement, updated)
        if count == 0 and pattern.startswith("(\\| \\*\\*Tests"):
            raise RuntimeError("README does not contain the expected Tests Passing row")
    return updated


def main() -> None:
    tests = collected_test_count()
    commits = commit_count()
    generated = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    current = README_PATH.read_text(encoding="utf-8")
    updated = update_readme(current, tests, commits, generated)
    README_PATH.write_text(updated, encoding="utf-8")
    print(f"README actualizado: {tests} tests passing, {commits} commits, {generated}")


if __name__ == "__main__":
    main()
