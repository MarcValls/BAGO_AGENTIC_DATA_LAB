"""Run existing regression gates on this candidate; preserve every attempt."""
from pathlib import Path
import datetime
import hashlib
import json
import os
import subprocess
import sys
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[4]
OUT = Path(__file__).resolve().parent


def main():
    attempt = OUT / sys.argv[1]
    attempt.mkdir(exist_ok=False)
    temp = ROOT / 'output' / ('ng-' + sys.argv[1])
    temp.mkdir(parents=True, exist_ok=False)
    env = os.environ.copy()
    env.update(PYTHONUTF8='1', PYTHONDONTWRITEBYTECODE='1',
               BAGO_DATA_ROOT=str(temp / 'data'),
               TEMP=str(temp), TMP=str(temp))
    commands = [
        ('smoke', [sys.executable, '-B', '-m', 'pytest', '-q',
                   'tests/test_agent_chat_trace.py::test_real_agent_tool_loop_traces_allowed_and_denied_exact_file_reads',
                   'tests/test_provider_cognition_repair.py::test_help_uses_model_and_persists_focus_only_when_cognition_enabled',
                   'tests/test_workspace_read.py']),
        ('generate', [sys.executable, '-B', 'scripts/generate_dynamic_readme.py']),
        ('consistency', [sys.executable, '-B', 'scripts/generate_dynamic_readme.py', '--check', '--skip-tests']),
    ]
    results = []
    for name, argv in commands:
        xml = attempt / (name + '.xml')
        current_env = dict(env, PYTEST_ADDOPTS=f'--basetemp="{temp / name}" --junitxml="{xml}"')
        started = datetime.datetime.now(datetime.timezone.utc).isoformat()
        with (attempt / (name + '.stdout.log')).open('wb') as stdout, (attempt / (name + '.stderr.log')).open('wb') as stderr:
            process = subprocess.run(argv, cwd=ROOT, env=current_env, stdout=stdout, stderr=stderr, timeout=2400)
        entry = dict(label=name, argv=argv, returncode=process.returncode, started_at=started,
                     completed_at=datetime.datetime.now(datetime.timezone.utc).isoformat())
        if xml.exists():
            tree = ET.parse(xml).getroot()
            suites = [tree] if tree.tag == 'testsuite' else list(tree)
            entry['counts'] = {key: sum(int(s.attrib.get(key, 0)) for s in suites)
                               for key in ('tests', 'errors', 'failures', 'skipped')}
        entry['logs'] = {p.name: hashlib.sha256(p.read_bytes()).hexdigest()
                         for p in attempt.glob(name + '.*') if p.is_file()}
        results.append(entry)
        (attempt / 'progress.json').write_text(json.dumps(results, indent=2) + '\n', encoding='utf-8')
        print(name, process.returncode, entry.get('counts', {}), flush=True)
        if process.returncode:
            break
    report = dict(status='PASS' if len(results) == 3 and all(x['returncode'] == 0 for x in results) else 'FAIL',
                  candidate_head=subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
                  python=sys.executable, commands=results,
                  limits=['Historical checks remain unchanged.', 'No frontend/browser or external inference claim in this report.'])
    (attempt / 'result.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    return 0 if report['status'] == 'PASS' else 1


if __name__ == '__main__':
    raise SystemExit(main())
