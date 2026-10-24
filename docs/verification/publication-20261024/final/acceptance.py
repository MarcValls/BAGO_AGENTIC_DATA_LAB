"""Managed finite final admission; inherited suites are not rerun."""
from pathlib import Path
import hashlib,json,os,re,subprocess,sys
root=Path(__file__).resolve().parents[4];out=Path(__file__).resolve().parent
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
results=[];errors=[]
env=os.environ.copy();env['PYTEST_ADDOPTS']=''
for name,args in [('CONTROLS_FINAL',[str(out/'check_controls.py')]),('README_CHECK',['scripts/generate_dynamic_readme.py','--check','--skip-tests'])]:
 run=subprocess.run([sys.executable]+args,cwd=root,env=env,capture_output=True,text=True,timeout=120)
 log=out/(name+'.log');log.write_text(run.stdout+run.stderr,encoding='utf-8')
 results.append({'id':name,'result':'PASS' if run.returncode==0 else 'FAIL','returncode':run.returncode,'log':log.relative_to(root).as_posix(),'log_sha256':sha(log)})
 if run.returncode:errors.append(name+' failed')
admission=json.loads((out/'RC13_ADMISSION.json').read_text());assert admission['status']=='PASS'
snapshot=json.loads((out/'RC13_PUBLIC_SNAPSHOT.json').read_text())
for row in snapshot['files']:
 if row['path'].startswith('frontend/') and sha(root/row['path'])!=row['sha256']:errors.append('RC13 mismatch '+row['path'])
for name,key in [('DOCKER_TEST.log','log_sha256'),('DOCKER_BUILD.log','build_log_sha256')]:
 if sha(out/name)!=admission['frontend_test'][key]:errors.append('Frontend log altered '+name)
visual=json.loads((out/'VISUAL.json').read_text())
if sha(out/'VISUAL.json')!=admission['visual']['record_sha256']:errors.append('Visual receipt altered')
for row in visual['captures']:
 if sha(out/row['path'])!=row['sha256']:errors.append('Capture altered '+row['path'])
for p in out.rglob('*.md'):
 for target in re.findall(r'(?<!!)\[[^\]]*\]\(([^)]+)\)',p.read_text()):
  if not target.startswith(('https://','http://','#')) and not (p.parent/target.split('#')[0]).exists():errors.append('Broken link '+target)
for p in out.rglob('*'):
 if p.is_file() and p.suffix in {'.json','.md','.log'}:
  if re.search(r'(?:sk-proj-|ghp_)[A-Za-z0-9_-]{20,}|-----BEGIN .*PRIVATE KEY-----|Bearer\s+[A-Za-z0-9_-]{20,}',p.read_text(errors='replace')):errors.append('Credential candidate '+p.name)
record={'status':'FAIL' if errors else 'PASS','errors':errors,'checks':results,'python':{'passed':941,'skipped':1,'state':'INHERITED_P1_UNCHANGED_233_FILES','execution':'45204dcac9b246ee82ecbdd9d6684622','new_full':'NOT_RUN_AUTHORIZED_SUCCESSOR'},'frontend':{'passed':476,'state':'INHERITED_RC13_EXACT_211_FILES','build':'PASS','admission_sha256':sha(out/'RC13_ADMISSION.json')},'visual':{'checks':22,'captures':7,'state':'INHERITED_RC13_PREVIEW5193','record_sha256':sha(out/'VISUAL.json')},'ci_hosted':'NOT_RUN','commit_push':'NOT_RUN','whole_product':'NOT_VALIDATED','counting':'Do not add focused or inherited executions','prior_attempt':'0455282be4cf442f81ce7079cca644c6 failed before execution: acceptance runner file absent; corrected materialization, no product tests had run. Original failed receipt preserved.','parser_repair':'ANSI stripped only in importer memory to parse test summary; original logs retained unchanged.'}
(out/'ACCEPTANCE.json').write_text(json.dumps(record,indent=2)+'\n')
print(json.dumps(record));raise SystemExit(bool(errors))
