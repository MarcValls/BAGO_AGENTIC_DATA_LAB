"""Execute the candidate's existing frontend commands without changing sources."""
from pathlib import Path
import datetime
import hashlib
import json
import os
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[4]
OUT = Path(__file__).resolve().parent


def main():
    attempt = OUT / sys.argv[1]
    attempt.mkdir(exist_ok=False)
    package = ROOT / 'frontend/package.json'
    lock = ROOT / 'frontend/package-lock.json'
    before = {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in (package, lock)}
    results = []
    npm = shutil.which('npm.cmd') or shutil.which('npm')
    for name in ('build', 'test', 'test:ui', 'test:contracts'):
        label = name.replace(':', '-')
        argv = [npm, 'run', name]
        started = datetime.datetime.now(datetime.timezone.utc).isoformat()
        with (attempt / (label + '.stdout.log')).open('wb') as stdout, (attempt / (label + '.stderr.log')).open('wb') as stderr:
            process = subprocess.run(argv, cwd=ROOT / 'frontend', stdout=stdout, stderr=stderr, timeout=900)
        results.append(dict(label=name, argv=argv, returncode=process.returncode, started_at=started,
                            completed_at=datetime.datetime.now(datetime.timezone.utc).isoformat(),
                            logs={p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in attempt.glob(label + '.*')}))
        (attempt / 'progress.json').write_text(json.dumps(results, indent=2) + '\n', encoding='utf-8')
        print(name, process.returncode, flush=True)
    after = {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in (package, lock)}
    report = dict(status='PASS' if before == after and all(x['returncode'] == 0 for x in results) else 'FAIL',
                  candidate_head=subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
                  commands=results, package_hashes_before=before, package_hashes_after=after,
                  browser='NOT_RUN_IN_THIS_CHECK')
    (attempt / 'result.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    return 0 if report['status'] == 'PASS' else 1


if __name__ == '__main__':
    raise SystemExit(main())
