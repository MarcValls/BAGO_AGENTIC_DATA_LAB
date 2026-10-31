"""Full-toolchain container check; all earlier attempts remain immutable."""
from pathlib import Path
import hashlib
import io
import json
import os
import subprocess
import tarfile
import uuid
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[4]
OUT = Path(__file__).resolve().parent
ATTEMPT = OUT / 'docker-attempt5'

JOB = r'''
from pathlib import Path
import datetime,hashlib,json,os,re,shutil,subprocess,sys,xml.etree.ElementTree as ET
root=Path('/workspace')
subprocess.run(['git','init','--quiet',str(root)],check=True)
with (root/'check-candidate.pack').open('rb') as stream:subprocess.run(['git','index-pack','--stdin'],cwd=root,stdin=stream,check=True,capture_output=True)
sha='8065906f4560f4f0b0951cc445b673ecad7ce175'
subprocess.run(['git','update-ref','refs/heads/codex/nearest-goals-close-20261031',sha],cwd=root,check=True)
subprocess.run(['git','symbolic-ref','HEAD','refs/heads/codex/nearest-goals-close-20261031'],cwd=root,check=True)
(root/'.git/shallow').write_text(sha+'\n')
subprocess.run(['git','read-tree','HEAD'],cwd=root,check=True)
subprocess.run(['git','remote','add','origin','https://github.com/MarcValls/BAGO_AGENTIC_DATA_LAB.git'],cwd=root,check=True)
assert subprocess.check_output(['git','rev-parse','HEAD'],cwd=root,text=True).strip()==sha
out=root/'check-results';out.mkdir()
temp=root/'check-temp';temp.mkdir()
env=os.environ.copy()
for name in ('BAGO_DATA_ROOT','BAGO_APP_ROOT','BAGO_CONVERSATION_DB_PATH','PYTEST_ADDOPTS'):
    env.pop(name,None)
env.update(TMPDIR=str(temp),TEMP=str(temp),TMP=str(temp),PYTHONDONTWRITEBYTECODE='1',PYTHONUTF8='1')
selection=json.loads((root/'check-selection.json').read_text())
steps=[('tools',[sys.executable,'-c',"import shutil,pytest,fastapi,pydantic; assert all(shutil.which(x) for x in ('git','node','ffmpeg')); print(pytest.__version__,fastapi.__version__,pydantic.__version__)"]),
       ('dom',['node','-e',"const{JSDOM}=require('./frontend/node_modules/jsdom');console.log(process.version,new JSDOM('<p>fixture</p>').window.document.querySelector('p').textContent)"]),
       ('triage',[sys.executable,'-B','-m','pytest','-q',*selection]),
       ('generate',[sys.executable,'-B','scripts/generate_dynamic_readme.py']),
       ('consistency',[sys.executable,'-B','scripts/generate_dynamic_readme.py','--check','--skip-tests'])]
results=[]
for label,argv in steps:
    current=dict(env,PYTEST_ADDOPTS=f'--basetemp={temp/label} --junitxml={out/(label+".xml")}')
    started=datetime.datetime.now(datetime.timezone.utc).isoformat()
    with (out/(label+'.stdout.log')).open('wb') as stdout,(out/(label+'.stderr.log')).open('wb') as stderr:
        p=subprocess.run(argv,cwd=root,env=current,stdout=stdout,stderr=stderr,timeout=1500)
    entry=dict(label=label,argv=argv,returncode=p.returncode,started_at=started,finished_at=datetime.datetime.now(datetime.timezone.utc).isoformat())
    xml=out/(label+'.xml')
    if xml.exists():
        tree=ET.parse(xml).getroot();suites=[tree] if tree.tag=='testsuite' else list(tree)
        entry['junit_counts_including_subtests']={k:sum(int(s.get(k,0)) for s in suites) for k in ('tests','failures','errors','skipped')}
    message=(out/(label+'.stdout.log')).read_text(errors='replace')
    match=re.search(r'README generado tras (\d+) tests pasados',message)
    if match:entry['main_pytest_passed']=int(match.group(1))
    entry['files']={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in out.glob(label+'.*')}
    results.append(entry)
    (out/'progress.json').write_text(json.dumps(results,indent=2)+'\n')
    print(label,p.returncode,entry.get('junit_counts_including_subtests',{}),flush=True)
    if p.returncode:break
ok=len(results)==len(steps) and all(x['returncode']==0 for x in results)
result=dict(status='PASS' if ok else 'FAIL',commands=results,python=sys.version,network='none',instrumentation='none; original tests and source files',windows_full_suite='FAIL retained separately')
(out/'inner-result.json').write_text(json.dumps(result,indent=2)+'\n')
shutil.copytree(out,'/results',dirs_exist_ok=True)
if ok:
    for name in ('README.md','README_DETAILS.md'):shutil.copyfile(root/name,Path('/results')/(name+'.generated'))
raise SystemExit(0 if ok else 1)
'''

BOOTSTRAP = r'''
from pathlib import Path
import os,sys,tarfile
root=Path('/workspace');root.mkdir(exist_ok=True)
with tarfile.open(fileobj=sys.stdin.buffer,mode='r|') as archive:archive.extractall(root,filter='data')
os.chdir(root)
exec((root/'check-job.py').read_text())
'''


def main():
    ATTEMPT.mkdir(exist_ok=False)
    image = subprocess.check_output(['docker', 'image', 'inspect', 'bago-nearest-goals-tests:20261031', '--format', '{{.Id}}'], text=True).strip()
    head = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip()
    selection = []
    for name in ('attempt1/generate.xml', 'docker-attempt3/generate.xml'):
        for case in ET.parse(OUT / name).getroot().iter('testcase'):
            if case.find('failure') is not None or case.find('error') is not None:
                file = case.attrib['classname'].replace('.', '/') + '.py'
                assert (ROOT / file).is_file(), file
                node = file + '::' + case.attrib['name']
                if node not in selection: selection.append(node)
    archive_path = ROOT / 'output/ng-complete-v2.tar'
    with archive_path.open('wb') as stream:
        subprocess.run(['git', 'archive', '--format=tar', head], cwd=ROOT, stdout=stream, check=True)
    object_ids = subprocess.check_output(['git','rev-list','--objects','--no-object-names','--no-walk=unsorted',head],cwd=ROOT)
    pack_path = ROOT / 'output/ng-candidate-objects.pack'
    with pack_path.open('wb') as stream:
        subprocess.run(['git','pack-objects','--stdout'],cwd=ROOT,input=object_ids,stdout=stream,check=True)
    dependency_inventory = []
    with tarfile.open(archive_path, 'a') as archive:
        info=tarfile.TarInfo('check-candidate.pack');info.size=pack_path.stat().st_size;info.mode=0o644
        with pack_path.open('rb') as stream:archive.addfile(info,stream)

        for name, content in [('check-job.py', JOB.encode()), ('check-selection.json', json.dumps(selection).encode())]:
            info = tarfile.TarInfo(name);info.size=len(content);info.mode=0o644
            archive.addfile(info, io.BytesIO(content))
        modules = ROOT / 'frontend/node_modules'
        for directory, dirs, files in os.walk(modules, followlinks=False):
            dirs[:] = sorted(x for x in dirs if x not in {'.cache', '.vite', '.bin'})
            for name in sorted(files):
                source = Path(directory) / name
                assert not source.is_symlink(), source
                data = source.read_bytes()
                relative = source.relative_to(ROOT).as_posix()
                info = tarfile.TarInfo(relative);info.size=len(data);info.mode=0o644
                archive.addfile(info, io.BytesIO(data))
                dependency_inventory.append(dict(path=relative,sha256=hashlib.sha256(data).hexdigest()))
    (ATTEMPT / 'dependency-inventory.json').write_text(json.dumps(dependency_inventory,indent=2)+'\n',encoding='utf-8')
    name='bago-near-complete-'+uuid.uuid4().hex[:10]
    argv=['docker','run','--rm','-i','--name',name,'--network','none','--mount',f'type=bind,source={ATTEMPT},target=/results','--entrypoint','python',image,'-B','-c',BOOTSTRAP]
    (ATTEMPT / 'launch.json').write_text(json.dumps(dict(image_id=image,candidate_head=head,argv=argv,archive_sha256=hashlib.sha256(archive_path.read_bytes()).hexdigest(),selection_count=len(selection),dependency_files=len(dependency_inventory),dependencies='existing npm ci with unchanged lock; excludes transient .cache/.vite and Windows .bin shims'),indent=2)+'\n',encoding='utf-8')
    try:
        with archive_path.open('rb') as stdin:process=subprocess.run(argv,cwd=ROOT,stdin=stdin,timeout=2000)
        code=process.returncode
    except subprocess.TimeoutExpired:
        subprocess.run(['docker','stop','--time','5',name],capture_output=True,timeout=30);code=124
    exists=subprocess.check_output(['docker','ps','-aq','--filter','name=^/'+name+'$'],text=True).strip()
    if code==0:
        for file in ('README.md','README_DETAILS.md'):(ROOT/file).write_bytes((ATTEMPT/(file+'.generated')).read_bytes())
    result=dict(status='PASS' if code==0 and not exists else 'FAIL',returncode=code,candidate_head=head,image_id=image,container_removed=not bool(exists),inner_sha256=hashlib.sha256((ATTEMPT/'inner-result.json').read_bytes()).hexdigest() if (ATTEMPT/'inner-result.json').exists() else None,windows_full_suite='FAIL preserved')
    (ATTEMPT/'result.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(result))
    return 0 if result['status']=='PASS' else 1


if __name__=='__main__':
    raise SystemExit(main())
