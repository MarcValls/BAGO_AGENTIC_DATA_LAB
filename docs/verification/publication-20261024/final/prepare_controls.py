"""Apply only the authorized CI move and eleven byte-preservation rules."""
from pathlib import Path
import hashlib,json,subprocess
root=Path(__file__).resolve().parents[4]
out=Path(__file__).resolve().parent
source=root.parent/'agent-chat-write-20261023/docs/communications-navigation-20261024/publication-audit/COMMIT_P1.json'
pins=json.loads(source.read_text())['raw_paths']
assert len(pins)==11
workflow=root/'.github/workflows/ci.yml'
old=workflow.read_bytes()
start=old.index(b'      - name: Setup Node.js')
end=old.index(b'      - name: Verify normative governed execution contract',start)
block=old[start:end]
assert block.count(b'      - name: ')==2
without=old[:start]+old[end:]
target=without.index(b'      - name: Run complete test suite')
new=without[:target]+block+without[target:]
workflow.write_bytes(new)
attrs=root/'.gitattributes'
assert not attrs.exists()
attrs.write_text('# Preserve exact bytes required by source/provenance SHA contracts.\n'+'\n'.join('/'+p+' -text' for p in pins)+'\n',encoding='utf-8')
sha=lambda b:hashlib.sha256(b).hexdigest()
records=[{'path':'.github/workflows/ci.yml','old_sha256':sha(old),'new_sha256':sha(new),'change':'Move existing Setup Node.js and Install frontend dependencies blocks before pytest; no step/permission edits'},{'path':'.gitattributes','old_sha256':None,'new_sha256':sha(attrs.read_bytes()),'change':'Only eleven explicit -text paths; no global filter changes'}]
for rel in ['frontend/src/App.tsx','frontend/src/App.css','frontend/src/NavigationOrder.css','frontend/tests/ui/communications/navigation-control-order.test.tsx']:
 p=root/rel
 records.append({'path':rel,'old_sha256':sha(p.read_bytes()) if p.exists() else None,'new_sha256':None,'state':'WAITING_FROZEN_HR01_RC'})
result={'id':'CR-PF01-FINAL-SUCCESSOR','base_commit':'165d01588bf86944d99dd5c8d9c632fa2736dc29','reason':'Explicit root successor: CI prerequisites, byte identity and separately verified visual navigation','impacted_consumers':['PF02','root publication index/PR'],'historical_consumers':['PP01','PP02'],'required_invalidations':'PP handoffs remain immutable historical evidence for P1. Never revalidate changed final sources through old PP handoffs; PF01/PF02 establish new evidence. Python execution inherited only on unchanged complete source list.','changes':records,'raw_pins':[{'path':p,'sha256':sha((root/p).read_bytes())} for p in pins]}
(out/'CHANGE_REQUEST.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps({'status':'PASS','ci_blocks_moved':2,'raw_pins':len(pins),'ui':'WAITING_FROZEN_HR01_RC'}))
