"""Bind public RC13 frontend execution and current privacy-reviewed captures."""
from pathlib import Path
import hashlib,json,re
root=Path(__file__).resolve().parents[4];out=Path(__file__).resolve().parent
source=root.parent/'agent-chat-write-20261023/docs/communications-navigation-20261024/authority-order/final/integration'
rc=source/'rc13';sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
package=json.loads((rc/'PACKAGE.json').read_text());snapshot=json.loads((rc/'PUBLIC_SNAPSHOT.json').read_text())
assert sha(rc/package['archive'])==package['sha256']=='32f9b1b860a308c2341afbdb9ba83898ba37fab85c8fba90f88738f3cf3c58fe'
assert sha(rc/'PUBLIC_SNAPSHOT.json')==package['public_snapshot_sha256']
front=[r for r in snapshot['files'] if r['path'].startswith('frontend/')]
assert front and all((root/r['path']).is_file() and sha(root/r['path'])==r['sha256'] for r in front)
scope={'frontend/src','frontend/tests'}
listed={r['path'] for r in front}
extras=[p.relative_to(root).as_posix() for folder in scope for p in (root/folder).rglob('*') if p.is_file() and p.relative_to(root).as_posix() not in listed]
assert not extras,extras
visual=json.loads((source/'VISUAL.json').read_text())
assert visual['status']=='PASS' and len(visual['checks'])==22 and all(c['result']=='PASS' for c in visual['checks'])
assert len(visual['captures'])==7 and visual['mutations']==[]
for row in visual['captures']:
 src=source/row['path'];assert sha(src)==row['sha256']
 dst=out/row['path'];dst.parent.mkdir(parents=True,exist_ok=True);dst.write_bytes(src.read_bytes())
(out/'VISUAL.json').write_bytes((source/'VISUAL.json').read_bytes())
for name in ['DOCKER_TEST.log','DOCKER_BUILD.log']:
 text=(rc/name).read_text(errors='replace')
 assert not re.search(r'(?:sk-proj-|ghp_)[A-Za-z0-9_-]{20,}|-----BEGIN .*PRIVATE KEY-----|Bearer\s+[A-Za-z0-9_-]{20,}',text)
 (out/name).write_bytes((rc/name).read_bytes())
test=(rc/'DOCKER_TEST.log').read_text(errors='replace')
test=re.sub(r'\x1b\[[0-?]*[ -/]*[@-~]','',test)
assert re.search(r'Tests\s+476 passed \(476\)',test) and 'built in' in test
(out/'RC13_PUBLIC_SNAPSHOT.json').write_bytes((rc/'PUBLIC_SNAPSHOT.json').read_bytes())
record={'status':'PASS','candidate':package['candidate'],'archive':package['archive'],'archive_sha256':package['sha256'],'public_sources':package['public_sources'],'package_files':package['files'],'snapshot_sha256':sha(out/'RC13_PUBLIC_SNAPSHOT.json'),'frontend_source_files_compared':len(front),'extra_frontend_sources':extras,'frontend_test':{'status':'INHERITED_EXACT_SOURCE_MATCH','passed':476,'files_passed':53,'build':'PASS','root_reported_process_exit':0,'root_process_session':61459,'log_sha256':sha(out/'DOCKER_TEST.log'),'build_log_sha256':sha(out/'DOCKER_BUILD.log')},'visual':{'status':'INHERITED_EXACT_CANDIDATE','checks_passed':22,'captures':7,'record_sha256':sha(out/'VISUAL.json'),'privacy_review':'Seven PNGs personally inspected by publication preparer; no visible names, numbers, emails or QR. Preserved original bytes and masks.','runtime':'Preview5193; no claim RC13 applied to8093'},'whole_product':'NOT_VALIDATED','hosted_ci':'NOT_RUN','external_effects':'NOT_RUN'}
(out/'RC13_ADMISSION.json').write_text(json.dumps(record,indent=2)+'\n')
print(json.dumps({'status':'PASS','frontend_files':len(front),'tests':476,'visual':22,'captures':7}))
