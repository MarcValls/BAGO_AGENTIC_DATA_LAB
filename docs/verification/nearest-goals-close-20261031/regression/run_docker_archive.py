"""Stage a Git candidate in Linux storage; export only this run's results."""
from pathlib import Path
import hashlib
import io
import json
import subprocess
import sys
import tarfile
import uuid

ROOT = Path(__file__).resolve().parents[4]
OUT = Path(__file__).resolve().parent
ATTEMPT = OUT / 'docker-attempt2'

BOOTSTRAP = r'''
from pathlib import Path
import runpy,shutil,sys,tarfile
root=Path('/workspace'); root.mkdir(exist_ok=True)
with tarfile.open(fileobj=sys.stdin.buffer,mode='r|') as archive:
    archive.extractall(root,filter='data')
import os
os.chdir(root)
scope='docs/verification/nearest-goals-close-20261031/regression'
module=runpy.run_path(str(root/scope/'run_docker_backend.py'))
inner=module['inner']; out=root/scope/'docker-attempt2';out.mkdir(parents=True)
inner.__globals__['ATTEMPT']=out
code=inner()
shutil.copytree(out,'/results',dirs_exist_ok=True)
if code==0:
    for name in ('README.md','README_DETAILS.md'):
        shutil.copyfile(root/name,Path('/results')/(name+'.generated'))
raise SystemExit(code)
'''


def main():
    ATTEMPT.mkdir(exist_ok=False)
    image = subprocess.check_output(['docker', 'image', 'inspect', 'bago-adl-trixie-baseline:20261027', '--format', '{{.Id}}'], text=True).strip()
    head = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip()
    archive_path = ROOT / 'output' / 'ng-candidate.tar'
    with archive_path.open('wb') as stream:
        subprocess.run(['git', 'archive', '--format=tar', head], cwd=ROOT, stdout=stream, check=True)
    with tarfile.open(archive_path, 'a') as archive:
        for rel in ('run_docker_backend.py', 'attempt1/generate.xml'):
            source = OUT / rel
            content = source.read_bytes()
            info = tarfile.TarInfo(source.relative_to(ROOT).as_posix())
            info.size = len(content)
            info.mode = 0o644
            archive.addfile(info, io.BytesIO(content))
    name = 'bago-near-archive-' + uuid.uuid4().hex[:10]
    argv = ['docker', 'run', '--rm', '-i', '--name', name, '--network', 'none',
            '--mount', f'type=bind,source={ATTEMPT},target=/results', '--entrypoint', 'python',
            image, '-B', '-c', BOOTSTRAP]
    launch = dict(image_id=image, candidate_head=head, archive_sha256=hashlib.sha256(archive_path.read_bytes()).hexdigest(),
                  source='git archive HEAD plus unchanged check script and failed-selection XML; Linux checkout bytes',
                  argv=argv, network='none', temporary_storage='container writable layer; result export in project only')
    (ATTEMPT / 'launch.json').write_text(json.dumps(launch, indent=2) + '\n', encoding='utf-8')
    try:
        with archive_path.open('rb') as stdin:
            process = subprocess.run(argv, stdin=stdin, cwd=ROOT, timeout=2000)
        code = process.returncode
    except subprocess.TimeoutExpired:
        subprocess.run(['docker', 'stop', '--time', '5', name], capture_output=True, timeout=30)
        code = 124
    exists = subprocess.check_output(['docker', 'ps', '-aq', '--filter', 'name=^/' + name + '$'], text=True).strip()
    if code == 0:
        for file in ('README.md', 'README_DETAILS.md'):
            (ROOT / file).write_bytes((ATTEMPT / (file + '.generated')).read_bytes())
    result = dict(status='PASS' if code == 0 and not exists else 'FAIL', returncode=code,
                  image_id=image, candidate_head=head, container_removed=not bool(exists),
                  inner_result_sha256=hashlib.sha256((ATTEMPT / 'inner-result.json').read_bytes()).hexdigest()
                  if (ATTEMPT / 'inner-result.json').exists() else None,
                  windows_full_suite='FAIL preserved; not reclassified as PASS')
    (ATTEMPT / 'result.json').write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(result))
    return 0 if result['status'] == 'PASS' else 1


if __name__ == '__main__':
    raise SystemExit(main())
