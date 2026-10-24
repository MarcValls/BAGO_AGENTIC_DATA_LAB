"""Authorized successor initialization; archive RC13 PF runtime without deletion."""
from pathlib import Path
import hashlib,json,shutil
ROOT=Path(__file__).resolve().parents[2];OUT=Path(__file__).resolve().parent
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
def write(p,v):p.write_text(json.dumps(v,indent=2)+'\n')
runtime=ROOT/'.bago/team/runtime';state=json.loads((runtime/'state.json').read_text())
assert state['mission']['mission_id']=='BAGO_PUBLICATION_FINAL_20261024'
assert state['work_status']['PF01']['status']=='DONE' and state['work_status']['PF02']['status']=='READY'
archive=ROOT/'.bago/goals/publication-beige-20261024/pf-runtime'
assert runtime.resolve().is_relative_to(ROOT) and archive.resolve().is_relative_to(ROOT) and not archive.exists()
old_files=[{'path':p.relative_to(runtime).as_posix(),'sha256':sha(p)} for p in sorted(runtime.rglob('*')) if p.is_file()]
old=OUT/'predecessor';old.mkdir()
paths=['frontend/src/App.tsx','frontend/src/NavigationOrder.css','frontend/tests/ui/communications/navigation-control-order.test.tsx','.github/workflows/ci.yml','.gitattributes','frontend/src/App.css','docs/verification/publication-20261024/final/handoff.json','docs/verification/publication-20261024/final/PUBLIC_FILES.json']
objects=old/'objects';objects.mkdir();sources=[]
for name in paths:
 p=ROOT/name;digest=sha(p);blob=objects/digest
 if not blob.exists():blob.write_bytes(p.read_bytes())
 sources.append({'path':name,'sha256':digest,'snapshot':blob.relative_to(ROOT).as_posix()})
write(old/'IDENTITY.json',{'mission':state['mission']['mission_id'],'status':'SUPERSEDED_BY_EXPLICIT_USER_PREFERENCE_NOT_INVALIDATED_HISTORY','PF01':'DONE','PF02':'READY_ARCHIVED_NOT_EXECUTED','terminal':'OPEN_ARCHIVED','runtime_files':old_files,'sources':sources,'required_change':'RC13 stays historical; beige footer preference requires PFB new evidence. Do not re-sign prior handoffs.'})
archive.parent.mkdir(parents=True,exist_ok=True);shutil.move(str(runtime),str(archive))
mission=json.loads((OUT/'mission.proposed.json').read_text())
mission['constraints']=[c for c in mission['constraints'] if not c.startswith('PROPOSED only')]
mission['constraints'].append('Source import authorized PREPARED before BS03; acceptance and handoff wait for independently validated RC14')
write(OUT/'mission.json',mission)
print(json.dumps({'status':'PASS','archived_runtime_files':len(old_files),'predecessor_sources':len(sources),'mission':mission['mission_id']}))
