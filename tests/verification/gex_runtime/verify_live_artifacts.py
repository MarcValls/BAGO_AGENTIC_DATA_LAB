"""Independent offline checks of actual browser/runtime evidence; no model calls."""
import base64
import hashlib
import json
from pathlib import Path
import sqlite3
from cryptography.hazmat.primitives import serialization
from jsonschema import Draft202012Validator, FormatChecker

ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / 'output/playwright/gex-runtime-20261020'
STATE = ROOT / '.worktrees/gex-runtime-20261020/state'
value = json.loads((OUT/'receipt.json').read_text())
rid = value['request_id']
schema = json.loads((ROOT/'docs/governed-execution/GEX_V1_SCHEMA.json').read_text())
def canon(v):
    # This actual envelope is all ASCII and integers: sorted JSON equals JCS.
    raw = json.dumps(v, sort_keys=True, ensure_ascii=False, separators=(',', ':'), allow_nan=False)
    assert raw.isascii(), 'Non-ASCII artifact requires UTF16-key JCS reference'
    return raw.encode()
def digest(domain,v): return hashlib.sha256(('ADL:GEX:'+domain+':v1\n').encode()+canon(v)).hexdigest()
def validate(kind,v): Draft202012Validator({'$defs':schema['$defs'],'$ref':'#/$defs/'+kind},format_checker=FormatChecker()).validate(v)
for kind, artifact in [('GEXRequestV1',value['request']),('ApprovalV1',value['approval']),('ReceiptV1',value['receipt']['gex_receipt']),('VerificationResultV1',value['receipt']['gex_verification']),('ToolProposalEnvelopeV1',value['proposal_envelope'])]: validate(kind,artifact)
assert digest('REQUEST',value['request']) == value['request_digest']
key = serialization.load_pem_private_key((STATE/'signing-key.pem').read_bytes(),None).public_key()
for kind,artifact in [('APPROVAL',value['approval']),('PERMIT',value['permit'])]:
    key.verify(base64.urlsafe_b64decode(artifact['signature']+'=='), ('ADL:GEX:'+kind+':v1\n').encode()+canon({k:v for k,v in artifact.items() if k!='signature'}))
expected=b'{"customer_id":"fixture-customer-001","status":"synthetic","open_invoice_count":2}\n'
output_hash=hashlib.sha256(expected).hexdigest()
assert value['receipt']['output'].encode()==expected
assert output_hash==value['receipt']['observed_sha256']==value['receipt']['executor_output_sha256']
assert value['receipt']['gex_receipt']['request_digest']==value['request_digest']
assert value['receipt']['gex_verification']['receipt_digest']==digest('RECEIPT',value['receipt']['gex_receipt'])
with sqlite3.connect('file:'+str(STATE/'execution.sqlite3')+'?mode=ro',uri=True) as db:
    db.row_factory=sqlite3.Row
    record=json.loads(db.execute('SELECT record_json FROM control_records WHERE request_id=?',(rid,)).fetchone()[0])
    assert record['receipt']==value['receipt']
    assert db.execute('SELECT COUNT(*) FROM attempts WHERE request_id=?',(rid,)).fetchone()[0]==1
    permit=dict(db.execute('SELECT * FROM permits WHERE request_id=?',(rid,)).fetchone())
    assert permit['state']=='CONSUMED' and permit['uses']==1
    # SQL normalization stores the fixed contract version implicitly, exactly as
    # events_for_request projects it; hash/signature checks use the full envelope.
    events=[{'contract_version':'gex-ledger-event/v1',**dict(e)} for e in db.execute('SELECT * FROM ledger_events WHERE request_id=? ORDER BY seq',(rid,))]
    previous=None
    for seq,e in enumerate(events):
        assert e['seq']==seq and e['prev_hash']==previous
        validate('LedgerEventV1',e)
        previous=e['event_digest']
        assert hashlib.sha256(canon({k:v for k,v in e.items() if k!='event_digest'})).hexdigest()==previous
    kinds=[e['kind'] for e in events]
    assert kinds.count('DISPATCH_INTENT')==1 and kinds.count('STARTED')==1 and kinds[-1]=='REPLAY_DENIED'
    for k in ['PROPOSED','POLICY_DECIDED','APPROVAL_REQUESTED','APPROVED','PERMIT_ISSUED','PERMIT_CONSUMED','DISPATCH_INTENT','STARTED','EFFECT_OBSERVED','RECEIPT_PERSISTED','VERIFICATION_RESULT_PERSISTED']: assert k in kinds
    durable_ver=json.loads(db.execute('SELECT result_json FROM gex_runtime_verifications WHERE request_id=?',(rid,)).fetchone()[0])
    assert durable_ver==value['receipt']['gex_verification']
    ingress=[];prior=None
    for row in db.execute('SELECT * FROM gex_ingress_artifacts ORDER BY seq'):
        item=json.loads(row['receipt_json']);validate('IngressDenialReceiptV1',item)
        assert row['seq']==len(ingress) and item['prev_ingress_hash']==prior
        assert hashlib.sha256(row['receipt_json'].encode()).hexdigest()==row['receipt_sha256']
        assert digest('INGRESS',{k:v for k,v in item.items() if k!='ingress_event_digest'})==item['ingress_event_digest']
        assert item['raw_request_sha256']==hashlib.sha256(b'ADL:GEX:REJECTED_INGRESS_MARKER:v1\n').hexdigest()
        prior=item['ingress_event_digest'];ingress.append(item)
    assert len(ingress)>=2
    (OUT/'actual-ingress-denials.json').write_text(json.dumps(ingress,indent=2))
recovered=json.loads((OUT/'restart-readback.json').read_text())
assert recovered['receipt']==value['receipt'] and all(recovered['integrity'].values())
for filename in ['proposal.json','receipt.json','restart-readback.json','replay-denial.json','03-dom.txt','server.log']:
    text=(OUT/filename).read_text(encoding='utf8')
    assert 'bago_gex_key_v1_' not in text and 'bago_gex_session_v1_' not in text
result={'status':'PASS','request_id':rid,'schemas_validated':['GEXRequestV1','ApprovalV1','ReceiptV1','VerificationResultV1','ToolProposalEnvelopeV1','LedgerEventV1','IngressDenialReceiptV1'],'independent_ed25519_signatures':2,'actual_bytes_sha256':output_hash,'one_consumed_permit':True,'dispatch_count':1,'durable_events':len(events),'actual_ingress_denials':len(ingress),'restart_exact_receipt':True,'secret_scan':'PASS'}
(OUT/'independent-artifact-verification.json').write_text(json.dumps(result,indent=2))
print(json.dumps(result))
