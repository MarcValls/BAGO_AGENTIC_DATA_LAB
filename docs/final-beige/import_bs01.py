"""Authorized preparation only; does not claim BS03 validation or RC14 acceptance."""
from pathlib import Path
import hashlib,json
ROOT=Path(__file__).resolve().parents[2];OUT=Path(__file__).resolve().parent
SOURCE=ROOT.parent/'agent-chat-write-20261023'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
def write(p,v):p.write_text(json.dumps(v,indent=2)+'\n')
state=json.loads((ROOT/'.bago/team/runtime/state.json').read_text())
assert state['mission']['mission_id']=='BAGO_PUBLICATION_BEIGE_FINAL_20261024' and state['work_status']['PFB01']['status']=='CLAIMED'
assert not (OUT/'SOURCE_IMPORT.json').exists()
freeze_path=SOURCE/'docs/communications-navigation-20261024/beige-settings/implementation/FREEZE.json'
freeze=json.loads(freeze_path.read_text());assert freeze['status']=='FROZEN'
allowed={'frontend/src/App.tsx','frontend/src/NavigationOrder.css','frontend/tests/ui/communications/navigation-control-order.test.tsx'}
assert {r['path'] for r in freeze['files']}==allowed
predecessor=json.loads((OUT/'predecessor/IDENTITY.json').read_text());old={r['path']:r['sha256'] for r in predecessor['sources']}
changes=[]
for row in freeze['files']:
 p=SOURCE/row['path'];target=ROOT/row['path'];assert sha(p)==row['sha256']
 assert sha(target)==old[row['path']],'Unexpected target divergence'
 target.write_bytes(p.read_bytes());assert sha(target)==row['sha256']
 changes.append({'path':row['path'],'old_sha256':old[row['path']],'new_sha256':row['sha256']})
for name in ['frontend/src/App.css','.github/workflows/ci.yml','.gitattributes']:assert sha(ROOT/name)==old[name]
(OUT/'BS01_FREEZE.json').write_bytes(freeze_path.read_bytes())
manual=SOURCE/'docs/communications-navigation-20261024/beige-settings/MANUAL_ES.md'
(OUT/'MANUAL_ES.md').write_bytes(manual.read_bytes())
write(OUT/'SOURCE_IMPORT.json',{'state':'PREPARED_NOT_VALIDATED','authorization':'Root explicit preparation before BS03; acceptance and handoff wait for RC14 independent validation','source_mission':'BAGO_BEIGE_SETTINGS_20261024','freeze_sha256':sha(freeze_path),'changes':changes,'manual_sha256':sha(manual),'preserved_controls':{p:old[p] for p in ['frontend/src/App.css','.github/workflows/ci.yml','.gitattributes']},'pending':['BS03','RC14 archive/source/frontend/visual binding','managed PFB01 acceptance','PFB02 independent review'],'historical_evidence':'PF01 RC13 and PF02 READY archived as predecessor; never re-signed for new sources'})
print(json.dumps({'status':'PREPARED','sources':len(changes),'validation':'NOT_RUN'}))
