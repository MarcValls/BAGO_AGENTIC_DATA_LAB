"""Send a fresh synthetic context through the exact .dockerignore policy."""
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import tempfile

def main():
    root = Path(__file__).resolve().parent
    (root / "evidence").mkdir(exist_ok=True)
    positive = ["frontend/packages/bago-adl-ui-kit/tokens.css", "frontend/src/ui-kit-preview.tsx",
                "frontend/src/features/decision-inspector/evidence/EvidenceExplorer.tsx",
                "frontend/src/features/new/evidence/AnotherView.tsx"]
    negative = [".env", ".bago/providers/registry.json", "frontend/profiles/browser.json", "frontend/session-token.json",
                "frontend/src/private/credential.ts", "frontend/src/features/new/evidence/live.json"]
    with tempfile.TemporaryDirectory(prefix="bago-docker-context-policy-") as temporary:
        work = Path(temporary)
        shutil.copyfile(root / ".dockerignore", work / ".dockerignore")
        for name in positive + negative:
            target = work / "context-public/repository" / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text("SYNTHETIC_POLICY_FIXTURE_ONLY", encoding="utf-8")
        code = "const fs=require('fs');const yes=" + json.dumps(positive) + ";const no=" + json.dumps(negative) + ";for(const x of yes)if(!fs.existsSync('/probe/'+x))throw Error('public source omitted: '+x);for(const x of no)if(fs.existsSync('/probe/'+x))throw Error('private data included: '+x);console.log('PASS public source/private fixtures');"
        dockerfile = work / "docker/policy.Dockerfile"
        dockerfile.parent.mkdir()
        dockerfile.write_text("FROM node:22-bookworm-slim@sha256:de170b39439eb0e5a3444ad7d60b015614a381e10fecae2e30ec9e735122f38d\nCOPY context-public/repository/ /probe/\nRUN node -e " + __import__('shlex').quote(code) + "\n", encoding="utf-8")
        command = ["docker", "build", "-f", str(dockerfile), "-t", "bago-dev-context-policy:integrated-i04", str(work)]
        process = subprocess.run(command, capture_output=True, timeout=120)
        (root / "evidence/context-policy.log").write_bytes(process.stdout + process.stderr)
        (root / "evidence/context-policy.json").write_text(json.dumps({"returncode": process.returncode,
            "positive_public_paths": positive, "negative_synthetic_paths": negative,
            "dockerignore_sha256": hashlib.sha256((root / ".dockerignore").read_bytes()).hexdigest(),
            "command": command, "result": "PASS" if process.returncode == 0 else "FAIL", "real_credentials_used": False}, indent=2) + "\n", encoding="utf-8")
        print(json.dumps({"result": "PASS" if process.returncode == 0 else "FAIL", "returncode": process.returncode}))
        raise SystemExit(process.returncode)


if __name__ == "__main__":
    main()
