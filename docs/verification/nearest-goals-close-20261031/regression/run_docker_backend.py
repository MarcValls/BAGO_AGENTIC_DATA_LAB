"""Run README gates in the existing local image with no external network."""
from pathlib import Path
import datetime
import hashlib
import json
import os
import subprocess
import sys
import uuid
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[4]
OUT = Path(__file__).resolve().parent
ATTEMPT = OUT / 'docker-attempt1'
IMAGE = 'bago-adl-trixie-baseline:20261027'


def inner():
    temp = ROOT / 'output' / 'ngd1'
    temp.mkdir(parents=True, exist_ok=True)
    env = os.environ.copy()
    for name in ('BAGO_DATA_ROOT', 'BAGO_APP_ROOT', 'PYTEST_ADDOPTS'):
        env.pop(name, None)
    env.update(PYTHONUTF8='1', PYTHONDONTWRITEBYTECODE='1', TMPDIR=str(temp), TEMP=str(temp), TMP=str(temp))
    failed = ET.parse(OUT / 'attempt1/generate.xml').getroot()
    nodes = []
    for case in failed.iter('testcase'):
        if case.find('failure') is not None or case.find('error') is not None:
            file = case.attrib['classname'].replace('.', '/') + '.py'
            assert (ROOT / file).is_file(), file
            nodes.append(file + '::' + case.attrib['name'])
    results = []
    for label, argv in [
        ('triage', [sys.executable, '-B', '-m', 'pytest', '-q', *nodes]),
        ('generate', [sys.executable, '-B', 'scripts/generate_dynamic_readme.py']),
        ('consistency', [sys.executable, '-B', 'scripts/generate_dynamic_readme.py', '--check', '--skip-tests']),
    ]:
        xml = ATTEMPT / (label + '.xml')
        current_env = dict(env, PYTEST_ADDOPTS=f'--basetemp={temp / label} --junitxml={xml}')
        started = datetime.datetime.now(datetime.timezone.utc).isoformat()
        with (ATTEMPT / (label + '.stdout.log')).open('wb') as stdout, (ATTEMPT / (label + '.stderr.log')).open('wb') as stderr:
            process = subprocess.run(argv, cwd=ROOT, env=current_env, stdout=stdout, stderr=stderr, timeout=1800)
        entry = dict(label=label, argv=argv, returncode=process.returncode, started_at=started,
                     finished_at=datetime.datetime.now(datetime.timezone.utc).isoformat())
        if xml.exists():
            tree = ET.parse(xml).getroot()
            suites = [tree] if tree.tag == 'testsuite' else list(tree)
            entry['counts'] = {key: sum(int(s.attrib.get(key, 0)) for s in suites)
                               for key in ('tests', 'failures', 'errors', 'skipped')}
        entry['logs'] = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in ATTEMPT.glob(label + '.*')}
        results.append(entry)
        (ATTEMPT / 'progress.json').write_text(json.dumps(results, indent=2) + '\n', encoding='utf-8')
        print(label, process.returncode, entry.get('counts'), flush=True)
        if process.returncode:
            break
    result = dict(status='PASS' if len(results) == 3 and all(x['returncode'] == 0 for x in results) else 'FAIL',
                  python=sys.version, commands=results, network='none',
                  windows_full_suite='FAIL retained in attempt1; this run validates Linux container only')
    (ATTEMPT / 'inner-result.json').write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
    return 0 if result['status'] == 'PASS' else 1


def host():
    ATTEMPT.mkdir(exist_ok=False)
    name = 'bago-near-goals-' + uuid.uuid4().hex[:10]
    image_id = subprocess.check_output(['docker', 'image', 'inspect', IMAGE, '--format', '{{.Id}}'], text=True).strip()
    head = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip()
    argv = ['docker', 'run', '--rm', '--name', name, '--network', 'none',
            '--mount', f'type=bind,source={ROOT},target=/workspace', '--workdir', '/workspace',
            '--env', 'PYTHONDONTWRITEBYTECODE=1', '--entrypoint', 'python', image_id,
            '-B', 'docs/verification/nearest-goals-close-20261031/regression/run_docker_backend.py', 'inner']
    (ATTEMPT / 'launch.json').write_text(json.dumps(dict(image=image_id, candidate_head=head, argv=argv,
        script_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()), indent=2) + '\n', encoding='utf-8')
    try:
        process = subprocess.run(argv, cwd=ROOT, timeout=2000)
        code = process.returncode
    except subprocess.TimeoutExpired:
        subprocess.run(['docker', 'stop', '--time', '5', name], capture_output=True, timeout=30)
        code = 124
    exists = subprocess.check_output(['docker', 'ps', '-aq', '--filter', 'name=^/' + name + '$'], text=True).strip()
    report = dict(status='PASS' if code == 0 and not exists else 'FAIL', returncode=code,
                  container_name=name, container_removed=not bool(exists), image_id=image_id, candidate_head=head,
                  inner_sha256=hashlib.sha256((ATTEMPT / 'inner-result.json').read_bytes()).hexdigest()
                  if (ATTEMPT / 'inner-result.json').exists() else None)
    (ATTEMPT / 'result.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    return 0 if report['status'] == 'PASS' else 1


if __name__ == '__main__':
    raise SystemExit(inner() if len(sys.argv) > 1 and sys.argv[1] == 'inner' else host())
