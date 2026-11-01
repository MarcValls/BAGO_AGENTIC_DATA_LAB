from pathlib import Path
import subprocess,json,sys
W=Path(__file__).resolve().parents[1];REPO=next(p for p in W.parents if (p/'.git').exists());kind=sys.argv[1]
if kind=='portable-evidence':argv=[sys.executable,'-B',str(W/'verify_publication.py')]
else:argv=[sys.executable,'-B',str(REPO/'.bago/goals/continuity-publication-20261101/readme-gate/verify_gate.py')]
p=subprocess.run(argv,cwd=REPO,capture_output=True,text=True,encoding='utf-8');assert p.returncode==0,p.stdout+p.stderr
result={'status':'PASS','check_id':kind,'scope':'Read-only verification of already executed actual generator/consistency receipts.' if kind!='portable-evidence' else 'Finite raw public bytes only; no runtime repeated.','observed':json.loads(p.stdout)}
(W/'checks'/(kind+'.json')).write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8');print(json.dumps(result))
