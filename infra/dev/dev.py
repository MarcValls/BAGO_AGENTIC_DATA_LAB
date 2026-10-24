"""Standalone guarded Docker CLI. Same snapshot, explicit candidate and host API."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parent


def preflight(environment=None, allow_stale=False):
    env = dict(os.environ if environment is None else environment)
    manifest_path = ROOT / "context-public/SOURCE_MANIFEST.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    identity = json.loads((ROOT / "context-public/EXPORT_IDENTITY.json").read_text(encoding="utf-8"))
    manifest_hash = hashlib.sha256(manifest_path.read_bytes()).hexdigest()
    candidate = env.get("BAGO_DEV_CANDIDATE", "20261023")
    if not re.fullmatch(r"[a-z0-9][a-z0-9-]{0,47}", candidate) or identity.get("candidate_id") != candidate or identity.get("source_manifest_sha256") != manifest_hash:
        raise ValueError("Candidate ID differs from export manifest. Create an identified new export/config; do not relabel another frontend.")
    source = (ROOT / "context-public/repository").resolve()
    mounted = Path(env.get("BAGO_DEV_SOURCE") or source).resolve()
    source_issues = []
    if mounted != source:
        source_issues.append("BAGO_DEV_SOURCE differs from this export")
    expected_paths = {item["path"] for item in manifest["files"]}
    if source.is_dir():
        for path in source.rglob("*"):
            relative = path.relative_to(source).as_posix()
            if path.is_symlink():
                source_issues.append("unexpected link: " + relative)
            elif path.is_file() and relative not in expected_paths:
                source_issues.append("unmanifested file: " + relative)
    for item in manifest["files"]:
        path = source / item["path"]
        try:
            valid = path.resolve().is_relative_to(source) and not path.is_symlink() and hashlib.sha256(path.read_bytes()).hexdigest() == item["sha256"]
        except OSError:
            valid = False
        if not valid:
            source_issues.append(item["path"])
    if source_issues and not allow_stale:
        raise ValueError("Source fingerprint/pair changed; create an identified new export/config. Previous verification is stale: " + ", ".join(source_issues[:3]))
    target = env.get("BAGO_API_PROXY_TARGET", "http://host.docker.internal:8080")
    parsed = urlsplit(target)
    if parsed.scheme not in ("http", "https") or parsed.hostname != "host.docker.internal" or parsed.username or parsed.password or parsed.path not in ("", "/") or parsed.query or parsed.fragment:
        raise ValueError("Proxy must identify the existing host API without embedded credentials")
    ports = {"frontend": env.get("BAGO_DEV_FRONTEND_PORT", "5173"), "api": env.get("BAGO_DEV_API_PORT", "8089"),
             "jaeger": env.get("BAGO_DEV_JAEGER_PORT", "16689"), "otlp": env.get("BAGO_DEV_OTLP_PORT", "4329")}
    if any(not str(port).isdigit() or not 1024 <= int(port) <= 65535 for port in ports.values()) or len({int(port) for port in ports.values()}) != 4:
        raise ValueError("Choose four different unprivileged loopback ports")
    env.update(BAGO_DEV_CANDIDATE=candidate, BAGO_DEV_SOURCE=str(source), BAGO_API_PROXY_TARGET=target)
    for key in ("COMPOSE_PROJECT_NAME", "COMPOSE_FILE", "COMPOSE_ENV_FILES", "COMPOSE_PROFILES"):
        env.pop(key, None)
    suffix = env.get("BAGO_DEV_INSTANCE_SUFFIX", "")
    if suffix and not re.fullmatch(r"-[a-z0-9][a-z0-9-]{0,20}", suffix):
        raise ValueError("Instance suffix must be empty or an explicit -lowercase-name")
    summary = {"candidate_id": candidate, "project": "bago-dev-" + candidate + suffix, "checkout": manifest["source"], "head": manifest["head"],
               "mounted_source": str(source), "manifest_sha256": manifest_hash,
               "host_api_target": target, "ports": ports, "source_files": len(manifest["files"]),
               "fingerprint_state": "STALE" if source_issues else "MATCH", "source_issues": source_issues}
    return env, summary


def compose_command(summary):
    project = summary["project"]
    if not re.fullmatch(r"bago-dev-[a-z0-9][a-z0-9-]{0,80}", project):
        raise ValueError("Invalid validated project identity")
    return ["docker", "compose", "--project-name", project, "--project-directory", str(ROOT), "--file", str(ROOT / "compose.yaml")]


def run_action(action, environment=None):
    try:
        env, summary = preflight(environment, allow_stale=action in ("stop", "ps"))
    except (OSError, ValueError, KeyError) as error:
        print(json.dumps({"result": "FAIL", "message": str(error)}))
        return 2
    print(json.dumps(summary), flush=True)
    actions = {"config": ["--profile", "*", "config"], "build": ["--profile", "test", "build", "python-smoke", "frontend-test"],
               "up": ["up", "-d", "--wait", "frontend"], "stop": ["stop", "frontend", "api-isolated", "jaeger"], "ps": ["ps"]}
    if action == "test":
        for service in ("python-smoke", "python-test", "frontend-test"):
            result = subprocess.run(compose_command(summary) + ["run", "--rm", service], cwd=ROOT, env=env)
            if result.returncode:
                return result.returncode
    elif action != "preflight":
        return subprocess.run(compose_command(summary) + actions[action], cwd=ROOT, env=env).returncode
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["preflight", "config", "build", "up", "stop", "ps", "test"])
    raise SystemExit(run_action(parser.parse_args().action))
