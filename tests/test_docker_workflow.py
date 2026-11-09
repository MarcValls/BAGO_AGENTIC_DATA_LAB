"""Regression tests for the Docker workflow."""

from pathlib import Path
import fnmatch
import re
import shlex
import subprocess
import textwrap

import pytest


ROOT = Path(__file__).parent.parent


def test_image_defaults_to_container_interface_and_compose_publishes_loopback():
    dockerfile = (ROOT / 'Dockerfile.ui').read_text(encoding='utf-8')
    compose = (ROOT / 'docker-compose.ui.yml').read_text(encoding='utf-8')
    assert 'BAGO_RUNTIME_MODE=container' in dockerfile
    assert 'BAGO_API_HOST=0.0.0.0' in dockerfile
    assert '127.0.0.1:8080:8080' in compose


def test_python_builder_copies_every_included_requirements_file():
    pending = ["requirements.txt"]
    required = set()
    while pending:
        name = pending.pop()
        if name in required:
            continue
        required.add(name)
        for line in (ROOT / name).read_text(encoding="utf-8").splitlines():
            match = re.match(r"^-r\s*(\S+)", line.strip())
            if match:
                pending.append((Path(name).parent / match[1]).as_posix())
    builder = (ROOT / "Dockerfile.ui").read_text(encoding="utf-8").split("# Build frontend", 1)[0]
    copies = []
    for line in builder.splitlines():
        if line.startswith("COPY "):
            copies.extend(shlex.split(line)[1:-1])
    missing = sorted(name for name in required if not any(fnmatch.fnmatch(name, source) for source in copies))
    assert not missing, f"Python builder lacks recursively included requirements files: {missing}"


def test_image_sha_tag_uses_event_independent_default_prefix():
    workflow = (ROOT / ".github" / "workflows" / "docker-build.yml").read_text(
        encoding="utf-8"
    )

    assert "            type=sha\n" in workflow
    assert "prefix={{branch}}" not in workflow


def test_pull_request_build_does_not_export_registry_cache():
    workflow = (ROOT / ".github" / "workflows" / "docker-build.yml").read_text(
        encoding="utf-8"
    )
    build, _ = workflow.split("  security-scan:\n", 1)

    assert (
        "          cache-to: ${{ github.event_name != 'pull_request' && "
        "format('type=registry,ref={0}/{1}:buildcache,mode=max', env.REGISTRY, "
        "steps.normalize_image.outputs.image_name) || '' }}\n"
    ) in build
    assert "          push: ${{ github.event_name != 'pull_request' }}" in build


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


def test_ui_image_includes_pinned_ber_artifact_and_lock():
    dockerfile = (ROOT / "Dockerfile.ui").read_text(encoding="utf-8")

    assert "COPY frontend/ui-kit-preview.html ./" in dockerfile
    assert "COPY frontend/packages ./packages" in dockerfile
    assert "COPY runtime/ber runtime/ber/" in dockerfile
    assert "COPY scripts/ber_effect_demo.py scripts/ber_effect_demo.py" in dockerfile
    assert (ROOT / "runtime" / "ber" / "bago-embedded-runtime-0.1.0.zip").is_file()
    assert (ROOT / "runtime" / "ber" / "BER.lock.json").is_file()


@pytest.mark.parametrize(
    ("success_on", "attempts", "returncode"),
    [(1, 1, 0), (3, 3, 0), (4, 3, 1)],
)
def test_openmetadata_image_pull_retries_are_bounded(success_on, attempts, returncode):
    workflow = (ROOT / ".github" / "workflows" / "ci.yml").read_text(
        encoding="utf-8"
    )
    pull_step, start_step = workflow.split(
        "      - name: Pull local OpenMetadata images\n", 1
    )[1].split("      - name: Start local OpenMetadata\n", 1)
    script = textwrap.dedent(pull_step.split("        run: |\n", 1)[1])
    stubs = f"""
    calls=0
    docker() {{
      calls=$((calls + 1))
      echo "docker $*"
      [ "$calls" -ge {success_on} ]
    }}
    sleep() {{ echo "sleep $*"; }}
    """
    result = subprocess.run(
        ["bash", "-e", "-s"],
        input=(textwrap.dedent(stubs) + script).encode('utf-8'),
        capture_output=True,
        timeout=5,
    )

    assert result.returncode == returncode, result.stderr.decode('utf-8', errors='replace')
    command = "compose -p bago-openmetadata -f infra/openmetadata/docker-compose.yml"
    stdout = result.stdout.decode('utf-8').replace('\r\n', '\n')
    assert stdout.count(f"docker {command} pull\n") == attempts
    assert [
        line for line in stdout.splitlines() if line.startswith("sleep ")
    ] == [f"sleep {attempt * 10}" for attempt in range(1, attempts)]
    assert ("failed after 3 attempts" in stdout) == (returncode != 0)
    assert f"run: docker {command} up -d --pull never\n" in start_step
    assert "continue-on-error" not in pull_step
