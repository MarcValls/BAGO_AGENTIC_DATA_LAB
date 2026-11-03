"""Acceptance of diagnostic evidence, never a product repair verdict."""
from pathlib import Path
import gzip
import hashlib
import json
root=Path(__file__).resolve().parents[4]
evidence=Path(__file__).resolve().parent
historical=root/'docs/verification/csv-chat-20261101/review/audit_store_lifetime.jsonl'
assert hashlib.sha256(historical.read_bytes()).hexdigest()=='fdbfb77ea1a60e16f7065990a1ba36ea73056b88b3cdbe3ba1bf29748d2746db'
rows=[json.loads(x) for x in historical.read_text().splitlines()]
assert [r['case'] for r in rows if r['status']=='FAIL']==[3,7]
contrast=json.loads((evidence/'connection-contrast.json').read_text())
assert contrast[0]['connections_after_context']==['OPEN']*3
assert contrast[1]['connections_after_context']==['CLOSED']*3
for mode in ('replace','in-place'):
 report=json.loads((evidence/f'control-{mode}.jsonl').read_text())
 assert report['status']=='FAIL' and report['final']==[0,0]
 assert bool(report['replacements'])==(mode=='replace')
 with gzip.open(evidence/(report['diagnostics']+'.gz'),'rt') as stream:
  events=[json.loads(x) for x in stream]
 assert any('below_confirmed_revision' in x['flags'] for x in events)
 assert any('path_identity_changed' in x['flags'] for x in events)==(mode=='replace')
assert json.loads((evidence/'attempt-01-failure.json').read_text())['status']=='FAIL'
print(json.dumps({'status':'PASS','claim':'diagnostic controls and preserved evidence only; persistence NOT_REPAIRED'}))
