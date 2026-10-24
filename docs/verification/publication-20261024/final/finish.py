"""Freeze the successor only after its managed acceptance succeeds."""
from pathlib import Path
import hashlib,json,sys
root=Path(__file__).resolve().parents[4]
out=Path(__file__).resolve().parent
receipt_path=Path(sys.argv[1]);receipt=json.loads((root/receipt_path).read_text())
assert receipt['work_id']=='PF01' and receipt['result']=='PASS'
assert json.loads((out/'ACCEPTANCE.json').read_text())['status']=='PASS'
product=['.github/workflows/ci.yml','.gitattributes','frontend/src/App.tsx','frontend/src/App.css','frontend/src/NavigationOrder.css','frontend/tests/ui/communications/navigation-control-order.test.tsx']
files=sorted({root/p for p in product}|{p for p in out.rglob('*') if p.is_file() and 'review' not in p.relative_to(out).parts and p.name not in ['handoff.json','PUBLIC_FILES.json','PUBLIC_FILES.txt']})
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
manifest=[{'path':p.relative_to(root).as_posix(),'size':p.stat().st_size,'working_tree_sha256':sha(p)} for p in files]
(out/'PUBLIC_FILES.json').write_text(json.dumps({'scope':'PF01 successor only; add to P1 committed snapshot. Working-tree bytes do not assert final Git-index identity. No runtime, dependencies or archive payload included.','files':manifest},indent=2)+'\n')
files.append(out/'PUBLIC_FILES.json')
paths=sorted(p.relative_to(root).as_posix() for p in files)
(out/'PUBLIC_FILES.txt').write_text('\n'.join(paths)+'\n')
handoff={'work_id':'PF01','role':'team-orchestrator','status':'DONE','mission_id':receipt['mission_id'],'candidate_id':receipt['candidate_id'],'scope_sha256':receipt['scope_sha256'],'changed_files':paths,'outputs':[{'id':'pf01-'+str(i),'path':p.relative_to(root).as_posix(),'sha256':sha(p),'frozen':True} for i,p in enumerate(files)],'verification':[{'id':receipt['check_id'],'command':receipt['command_text'],'result':'PASS','evidence':receipt_path.as_posix(),'execution_id':receipt['execution_id']}],'residual_risks':['Independent PF02 and root final index/base freshness required before draft PR publication.','Python941PASS/1SKIP belongs to unchanged P1 working tree; source proof permits inheritance only.','Hosted CI, real WhatsApp/provider effects and whole-product validation NOT_RUN.','Capabilities dynamic registry/effective tool assignment remains PROPOSED.','Previous Inspector goal remains paused; historical PP handoffs retained for P1, never re-signed for final sources.'],'next_consumers':['PF02']}
handoff['payload_sha256']=hashlib.sha256(json.dumps(handoff,sort_keys=True,separators=(',',':'),ensure_ascii=False,allow_nan=False).encode()).hexdigest()
(out/'handoff.json').write_text(json.dumps(handoff,indent=2,ensure_ascii=False)+'\n')
print(json.dumps({'status':'PASS','public_files':len(files),'public_manifest_sha256':sha(out/'PUBLIC_FILES.json'),'handoff_sha256':sha(out/'handoff.json')}))
