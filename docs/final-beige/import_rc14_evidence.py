"""Copy privacy-reviewed final evidence; independent BS03 admission remains separate."""
from pathlib import Path
import hashlib,json,re
ROOT=Path(__file__).resolve().parents[2];OUT=Path(__file__).resolve().parent
L=ROOT.parent/'agent-chat-write-20261023';BS=L/'docs/communications-navigation-20261024/beige-settings';PACK=BS/'packaging';INTEGRATION=BS/'integration'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
read=lambda p:json.loads(p.read_text())
evidence=OUT/'evidence';evidence.mkdir(exist_ok=True)
package=read(PACK/'PACKAGE.json');assert package['candidate']=='beige-settings-20261024-rc14'
assert sha(PACK/package['archive'])==package['sha256']=='5c8e091df12201ed833f5aabeffa6f5f614a2ce36cf2056b51da99d1e7f7c2ff'
snapshot=read(PACK/'PUBLIC_SNAPSHOT.json');assert sha(PACK/'PUBLIC_SNAPSHOT.json')==package['public_snapshot_sha256']
front=[r for r in snapshot['files'] if r['path'].startswith('frontend/')]
assert all((ROOT/r['path']).is_file() and sha(ROOT/r['path'])==r['sha256'] for r in front)
listed={r['path'] for r in front}
extras=[p.relative_to(ROOT).as_posix() for f in ['frontend/src','frontend/tests'] for p in (ROOT/f).rglob('*') if p.is_file() and p.relative_to(ROOT).as_posix() not in listed]
assert not extras
docker=read(PACK/'DOCKER_RESULT.json');assert docker['status']=='PASS' and docker['package_sha256']==package['sha256']
for step in docker['steps']:
 assert step['returncode']==0 and sha(PACK/step['log'])==step['log_sha256']
visual=read(INTEGRATION/'VISUAL.json');assert visual['status']=='PASS' and visual['candidate']==package['candidate'] and all(c['result']=='PASS' for c in visual['checks']) and visual['mutations']==[]
for row in visual['captures']:
 src=INTEGRATION/row['path'];assert sha(src)==row['sha256']
 dst=evidence/row['path'];dst.parent.mkdir(exist_ok=True,parents=True);dst.write_bytes(src.read_bytes())
copies=[(PACK/'PUBLIC_SNAPSHOT.json','RC14_PUBLIC_SNAPSHOT.json'),(PACK/'DOCKER_TEST.log','DOCKER_TEST.log'),(PACK/'DOCKER_BUILD.log','DOCKER_BUILD.log'),(INTEGRATION/'VISUAL.json','VISUAL.json'),(INTEGRATION/'README_FULL.log','README_FULL_L.log'),(INTEGRATION/'README_CHECK.log','README_CHECK_L.log'),(INTEGRATION/'ACCEPTANCE.json','BS02_ACCEPTANCE.json'),(INTEGRATION/'handoff.json','BS02_HANDOFF.json'),(INTEGRATION/'PREVIEW_DIAGNOSIS.json','PREVIEW_DIAGNOSIS.json')]
for src,name in copies:(evidence/name).write_bytes(src.read_bytes())
plain=re.sub(r'\x1b\[[0-?]*[ -/]*[@-~]','',(evidence/'DOCKER_TEST.log').read_text(errors='replace'))
count=re.search(r'Tests\s+(\d+) passed\s+\((\d+)\)',plain);assert count and count[1]==count[2] and int(count[1])==docker['frontend_passed']
full=re.search(r'README generado tras\s+(\d+)\s+tests pasados',(evidence/'README_FULL_L.log').read_text());assert full
check=(evidence/'README_CHECK_L.log').read_text();assert 'README verificado' in check
record={'state':'EVIDENCE_COPIED_PENDING_BS03','candidate':package['candidate'],'archive':package['archive'],'archive_sha256':package['sha256'],'public_sources':package['public_sources'],'zip_files':package['files'],'snapshot_sha256':package['public_snapshot_sha256'],'frontend_files_compared':len(front),'extra_frontend_sources':extras,'frontend':{'passed':docker['frontend_passed'],'build':docker['build'],'image':docker['image'],'image_id':docker['image_id'],'canonical_result_sha256':sha(PACK/'DOCKER_RESULT.json'),'closed_steps':[{'id':s['id'],'returncode':s['returncode'],'log_sha256':s['log_sha256']} for s in docker['steps']]},'readme_L':{'full_passed':int(full[1]),'new_execution_in_L_not_P':True,'check':'PASS_REPRODUCIBILITY_ONLY','executions_sha256':sha(INTEGRATION/'README_EXECUTIONS.json')},'visual':{'checks':len(visual['checks']),'captures':len(visual['captures']),'privacy':'Root and publication preparer personally inspected seven originals: no visible names, numbers, emails or QR; unchanged PNG bytes.','runtime':'Preview5193 only; no applied8093 claim'},'initial_preview_attempt':{'state':'FAIL_PRESERVED_IN_L_ATTEMPT01','cause':'INCONCLUSIVE','observation':'Root initially blank, normal reload changed root child count0to1; no captured errors/resources. Final observation PASS with unchanged source.','diagnosis_sha256':sha(evidence/'PREVIEW_DIAGNOSIS.json')},'copied_files':[{'path':(evidence/name).relative_to(ROOT).as_posix(),'sha256':sha(evidence/name)} for _,name in copies],'pending':['BS03','PFB01 managed acceptance','PFB02 review'],'limits':['Google simplified flow PROPOSED/no live OAuth','Context readability patch PROPOSED, not applied','No new capability assignments, real providers/WhatsApp or hostedCI claims','Python P941+1 stays separate from L full result; no added counts']}
(OUT/'RC14_EVIDENCE.json').write_text(json.dumps(record,indent=2)+'\n')
print(json.dumps({'state':record['state'],'frontend_files':len(front),'frontend_passed':docker['frontend_passed'],'visual_checks':len(visual['checks']),'captures':len(visual['captures']),'L_full_passed':int(full[1])}))
