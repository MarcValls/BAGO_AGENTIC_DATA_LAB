"""Preserve preparation evidence before a separately scoped successor mission."""
from pathlib import Path
import hashlib,json,subprocess,shutil

root=Path(__file__).resolve().parents[4]
out=Path(__file__).resolve().parent
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def write(p,v): p.write_text(json.dumps(v,indent=2)+'\n',encoding='utf-8')
commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=root,text=True).strip()
assert commit=='165d01588bf86944d99dd5c8d9c632fa2736dc29'
runtime=root/'.bago/team/runtime'
archive=root/'.bago/goals/publication-final-20261024/preparation-runtime'
assert runtime.resolve().is_relative_to(root) and archive.resolve().is_relative_to(root)
assert not archive.exists()
state=json.loads((runtime/'state.json').read_text())
assert state['lifecycle']=='CLOSED'
runtime_manifest=[{'path':p.relative_to(runtime).as_posix(),'sha256':sha(p)} for p in sorted(runtime.rglob('*')) if p.is_file()]
archive.parent.mkdir(parents=True,exist_ok=True)
shutil.move(str(runtime),str(archive))
protected=[]
for folder in ['src','tests','scripts']:
 protected += [p for p in (root/folder).rglob('*.py') if '__pycache__' not in p.parts]
protected += [p for p in root.glob('requirements*.txt')]
protected += [root/p for p in ['README.md','scripts/generate_dynamic_readme.py','docs/readme_manifest.json','docs/readme_frontend.md','tests/test_readme_presentation.py']]
protected=sorted(set(protected))
write(out/'P1_SOURCE_BASELINE.json',{'commit':commit,'files':[{'path':p.relative_to(root).as_posix(),'sha256':sha(p)} for p in protected],'runtime_archive':'.bago/goals/publication-final-20261024/preparation-runtime','runtime_files':runtime_manifest,'semantics':'PP01/PP02 evidence remains historical for P1; changed sources require successor evidence, never re-signing prior receipts.'})
scopes=['.github/workflows/ci.yml','.gitattributes','frontend/src/App.tsx','frontend/src/App.css','frontend/src/NavigationOrder.css','frontend/tests/ui/communications/navigation-control-order.test.tsx','docs/verification/publication-20261024/final/**']
mission={'mission_id':'BAGO_PUBLICATION_FINAL_20261024','operation':'PROMOTION','title':'Bounded final publication successor','objective':'Prepare CI prerequisite order, exact byte attributes and verified navigation successor; independent review before root publication','destination':'GitHub draft PR preparation only; root controls staging, commit and push','constraints':['No Python full rerun; inherit P941 only after exact source proof','No browser/provider setup or external messages','Preserve P1 historical evidence; no edits to frozen preparation/review outputs','Import UI only from frozen verified HR01 and final RC source identities','Hosted CI and whole-product validation not implied'],'max_concurrency':1,'terminal_work_items':['PF02'],'work_items':[{'id':'PF01','title':'Prepare bounded final successor and verify identities','role':'team-orchestrator','depends_on':[],'read_scopes':['**'],'write_scopes':scopes,'output_scopes':['docs/verification/publication-20261024/final/**'],'required_checks':['acceptance']},{'id':'PF02','title':'Independent final successor review','role':'verification-engineer','depends_on':['PF01'],'read_scopes':['**'],'write_scopes':['docs/verification/publication-20261024/final/review/**'],'output_scopes':['docs/verification/publication-20261024/final/review/**'],'required_checks':['acceptance']}]}
write(out/'mission.json',mission)
print(json.dumps({'status':'PASS','protected_files':len(protected),'archived_runtime_files':len(runtime_manifest),'mission':mission['mission_id']}))
