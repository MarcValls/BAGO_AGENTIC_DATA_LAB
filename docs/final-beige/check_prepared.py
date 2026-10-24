"""Read-only preliminary identities; does not admit pending RC14 execution."""
from pathlib import Path
import hashlib,json
ROOT=Path(__file__).resolve().parents[2];OUT=Path(__file__).resolve().parent;L=ROOT.parent/'agent-chat-write-20261023'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
baseline=json.loads((ROOT/'docs/verification/publication-20261024/final/P1_SOURCE_BASELINE.json').read_text())
errors=[]
for row in baseline['files']:
 if not (ROOT/row['path']).is_file() or sha(ROOT/row['path'])!=row['sha256']:errors.append('Protected file changed: '+row['path'])
protected={r['path'] for r in baseline['files']}
current={p.relative_to(ROOT).as_posix() for folder in ['src','tests','scripts'] for p in (ROOT/folder).rglob('*.py') if '__pycache__' not in p.parts}|{p.relative_to(ROOT).as_posix() for p in ROOT.glob('requirements*.txt')}
if current-protected:errors.append('New Python/requirement files')
snapshot=json.loads((ROOT/'docs/verification/publication-20261024/final/RC13_PUBLIC_SNAPSHOT.json').read_text())
front=[r['path'] for r in snapshot['files'] if r['path'].startswith('frontend/')]
rows=[]
for name in front:
 match=(ROOT/name).is_file() and (L/name).is_file() and sha(ROOT/name)==sha(L/name)
 if not match:errors.append('Current frontend differs: '+name)
 rows.append({'path':name,'sha256':sha(ROOT/name) if (ROOT/name).is_file() else None,'matches_current_L':match})
extras=[p.relative_to(ROOT).as_posix() for folder in ['frontend/src','frontend/tests'] for p in (ROOT/folder).rglob('*') if p.is_file() and p.relative_to(ROOT).as_posix() not in set(front)]
if extras:errors.append('Unexpected extra frontend source')
imported=json.loads((OUT/'SOURCE_IMPORT.json').read_text())
for name,digest in imported['preserved_controls'].items():
 if sha(ROOT/name)!=digest:errors.append('Preserved control changed: '+name)
record={'status':'FAIL' if errors else 'PASS_PREPARATION_ONLY','errors':errors,'protected_files':len(baseline['files']),'python_suite':{'passed':941,'skipped':1,'state':'INHERITED_P1_BYTES_UNCHANGED','new_full':'NOT_RUN'},'frontend_files':len(rows),'frontend':rows,'extra_sources':extras,'frontend_execution_binding':'PENDING_RC14_SNAPSHOT_AND_TESTS; current L comparison is not a test result','source_state':'PREPARED_NOT_VALIDATED','pending':['BS03','RC14 package/frontend/visual acceptance','PFB01 managed acceptance','PFB02 independent review'],'google_simplified_flow':'PROPOSED_NO_OAUTH_LIVE','publication':'NOT_RUN'}
(OUT/'PREPARATION_CHECK.json').write_text(json.dumps(record,indent=2)+'\n');print(json.dumps({k:v for k,v in record.items() if k!='frontend'}));raise SystemExit(bool(errors))
