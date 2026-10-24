"""Import the explicit HR01 freeze, never the failed RC12 candidate."""
from pathlib import Path
import hashlib,json
root=Path(__file__).resolve().parents[4]
out=Path(__file__).resolve().parent
source=root.parent/'agent-chat-write-20261023'
freeze_path=source/'docs/communications-navigation-20261024/authority-order/final/implementation/FREEZE.json'
freeze=json.loads(freeze_path.read_text())
assert freeze['status']=='FROZEN' and len(freeze['files'])==4
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
copies=[]
for row in freeze['files']:
 src=source/row['path'];dst=root/row['path']
 assert sha(src)==row['sha256']
 dst.parent.mkdir(parents=True,exist_ok=True);dst.write_bytes(src.read_bytes())
 assert sha(dst)==row['sha256']
 copies.append({'source':row['path'],'path':row['path'],'sha256':row['sha256']})
docs=[('authority-order/MANUAL_ES.md','AUTHORITY_ORDER/MANUAL_ES.md')]
for name in ['CAPABILITIES_PLAN.md','CAPABILITIES_LIVE.json','PACKAGE_SOURCE_COMPARISON.json','TOOL_CATALOG_MAP.json','CAPABILITY_COMPONENT_HASHES.json']:
 docs.append(('authority-design/'+name,'AUTHORITY_ORDER/authority-design/'+name))
for src_rel,dst_rel in docs:
 src=source/'docs/communications-navigation-20261024'/src_rel;dst=out/dst_rel
 text=src.read_text()
 assert not any(marker in text for marker in ['C:\\Users\\','E:\\','Bearer '])
 dst.parent.mkdir(parents=True,exist_ok=True);dst.write_bytes(src.read_bytes())
 copies.append({'source':'docs/communications-navigation-20261024/'+src_rel,'path':dst.relative_to(root).as_posix(),'sha256':sha(dst)})
(out/'HR01_FREEZE.json').write_bytes(freeze_path.read_bytes())
(out/'HR01_IMPORT.json').write_text(json.dumps({'status':'PASS','source_mission':'HR01','freeze_sha256':sha(freeze_path),'managed_execution':freeze['managed_execution'],'frontend_full':'WAITING_ROOT_RC13','copies':copies},indent=2)+'\n')
cr=json.loads((out/'CHANGE_REQUEST.json').read_text())
for row in cr['changes']:
 if row.get('state')=='WAITING_FROZEN_HR01_RC':
  row['new_sha256']=sha(root/row['path']);row['state']='IMPORTED_HR01_FROZEN'
(out/'CHANGE_REQUEST.json').write_text(json.dumps(cr,indent=2)+'\n')
print(json.dumps({'status':'PASS','ui_files':4,'documentation':len(docs),'rc13_frontend':'WAITING'}))
