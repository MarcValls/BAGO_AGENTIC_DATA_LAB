"""Run only this project's containers and bind receipts to the public context."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import time
from urllib.request import urlopen
from dev import preflight, compose_command

ROOT = Path(__file__).resolve().parent
EVIDENCE = ROOT / "evidence"
COMMANDS = []
ENVIRONMENT = None


def execute(label, arguments, timeout=1200):
    log = EVIDENCE / (label + ".log")
    start = datetime.now(timezone.utc).isoformat()
    print(json.dumps({"start": label, "command": arguments}), flush=True)
    with log.open("wb") as output:
        result = subprocess.run(arguments, cwd=ROOT, env=ENVIRONMENT, stdout=output, stderr=subprocess.STDOUT, timeout=timeout)
    row = {"label": label, "command": arguments, "started_at": start,
           "finished_at": datetime.now(timezone.utc).isoformat(), "returncode": result.returncode,
           "result": "PASS" if result.returncode == 0 else "FAIL", "log": log.relative_to(ROOT).as_posix(),
           "log_sha256": hashlib.sha256(log.read_bytes()).hexdigest()}
    COMMANDS.append(row)
    (EVIDENCE / "executions.json").write_text(json.dumps(COMMANDS, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"finish": label, "result": row["result"]}), flush=True)
    if result.returncode:
        raise SystemExit(result.returncode)
    return log.read_text(encoding="utf-8", errors="replace")


def main():
    global ENVIRONMENT
    EVIDENCE.mkdir(exist_ok=True)
    if (EVIDENCE / "executions.json").exists():
        raise SystemExit("Preserve prior executions: use a new evidence directory for a new validation run.")
    ENVIRONMENT, summary = preflight()
    print(json.dumps({"run_summary": summary}), flush=True)
    (EVIDENCE / "run-summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    compose = compose_command(summary)
    manifest = ROOT / "context-public/SOURCE_MANIFEST.json"
    source = json.loads(manifest.read_text(encoding="utf-8"))
    for item in source["files"]:
        assert hashlib.sha256((ROOT / "context-public/repository" / item["path"]).read_bytes()).hexdigest() == item["sha256"]
    execute("docker-version", ["docker", "version"])
    execute("compose-version", ["docker", "compose", "version"])
    before = execute("existing-containers-before", ["docker", "ps", "--format", "{{json .}}"])
    config = json.loads(execute("compose-config", compose + ["--profile", "*", "config", "--format", "json"]))
    for name, service in config["services"].items():
        assert not service.get("privileged") and service.get("network_mode") != "host"
        for port in service.get("ports", []):
            assert port["host_ip"] == "127.0.0.1"
        for mount in service.get("volumes", []):
            if mount["type"] == "bind":
                assert mount["read_only"] is True and mount["target"].startswith("/workspace/frontend/")
    execute("build", compose + ["--profile", "test", "build", "python-smoke", "frontend-test"])
    execute("python-smoke", compose + ["run", "--rm", "python-smoke"])
    execute("python-focused", compose + ["run", "--rm", "python-test"])
    execute("frontend-build-tests", compose + ["run", "--rm", "frontend-test"])
    execute("start-isolated-dev", compose + ["up", "-d", "--wait", "--wait-timeout", "90", "frontend", "api-isolated", "jaeger"])
    probes = []
    for label, url in [("frontend_html", "http://127.0.0.1:"+summary["ports"]["frontend"]+"/"),
                       ("isolated_api_health", "http://127.0.0.1:"+summary["ports"]["api"]+"/api/health"),
                       ("existing_host_api_through_vite", "http://127.0.0.1:"+summary["ports"]["frontend"]+"/api/health"),
                       ("jaeger_query", "http://127.0.0.1:"+summary["ports"]["jaeger"]+"/api/v3/services")]:
        with urlopen(url, timeout=10) as response:
            raw = response.read()
            assert response.status == 200
            if label == "frontend_html":
                assert b"/src/main.tsx" in raw
            probes.append({"label": label, "url": url, "http_status": response.status, "bytes": len(raw), "body_sha256": hashlib.sha256(raw).hexdigest()})
    execute("container-to-host-health", compose + ["exec", "-T", "frontend", "node", "-e", "fetch(process.env.BAGO_API_PROXY_TARGET+'/api/health').then(r=>{console.log(JSON.stringify({status:r.status,host:'host.docker.internal',effect:'health GET only'}));process.exit(r.ok?0:1)}).catch(e=>{console.error(e.message);process.exit(1)})"])
    execute("python-environment-lock", compose + ["run", "--rm", "python-smoke", "python", "-m", "pip", "freeze", "--all"])
    execute("image-identities", ["docker", "image", "inspect", "bago-dev-python:"+summary["candidate_id"]+"-rc1", "bago-dev-frontend:"+summary["candidate_id"]+"-rc1", "--format", "{{json .Id}} {{json .Config.User}}"])
    execute("task-containers", compose + ["ps", "--format", "json"])
    after = execute("existing-containers-after", ["docker", "ps", "--format", "{{json .}}"])
    before_ids = {json.loads(line)["ID"] for line in before.splitlines() if line.strip() and
                  ("com.docker.compose.project="+summary["project"]+",") not in (json.loads(line).get("Labels", "")+",")}
    after_ids = {json.loads(line)["ID"] for line in after.splitlines() if line.strip()}
    assert before_ids.issubset(after_ids), "An initially running unrelated container is no longer running; investigate without altering it"
    (EVIDENCE / "health-probes.json").write_text(json.dumps(probes, indent=2) + "\n", encoding="utf-8")
    (EVIDENCE / "RESULT.json").write_text(json.dumps({"result": "PASS", "source_manifest_sha256": hashlib.sha256(manifest.read_bytes()).hexdigest(),
        "commands": len(COMMANDS), "run_summary": summary, "health_probes": probes, "unrelated_running_container_ids_preserved": sorted(before_ids),
        "live_provider_inference": "NOT_RUN", "visible_browser_render": "NOT_RUN", "windows_oauth_whatsapp": "HOST_ADAPTER_REQUIRED",
        "containers_left_running": ["frontend", "api-isolated", "jaeger"], "real_messages_sent": 0}, indent=2) + "\n", encoding="utf-8")
    print("PASS: candidate-bound dev/test and health checks. Browser/provider effects remain NOT_RUN.", flush=True)


if __name__ == "__main__":
    main()
