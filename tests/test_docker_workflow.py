"""Regression tests for the Docker workflow."""

from pathlib import Path


ROOT = Path(__file__).parent.parent


def test_security_scan_has_job_scoped_sarif_upload_permissions():
    workflow = (ROOT / ".github" / "workflows" / "docker-build.yml").read_text(
        encoding="utf-8"
    )
    before_scan, security_scan = workflow.split("  security-scan:\n", 1)

    assert "security-events: write" not in before_scan
    assert (
        "    permissions:\n"
        "      contents: read\n"
        "      security-events: write\n"
    ) in security_scan
    assert "uses: github/codeql-action/upload-sarif@" in security_scan
