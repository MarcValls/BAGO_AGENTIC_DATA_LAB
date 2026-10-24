"""Read-only publication checks. Never stages, commits, fetches, pushes or sends."""
from pathlib import Path
import argparse,hashlib,json,re,subprocess,sys
ROOT=Path(__file__).resolve().parents[2]
def digest(raw):return hashlib.sha256(raw).hexdigest()
def git(*args):return subprocess.check_output(['git',*args],cwd=ROOT)
def load_manifest(name):
 p=(ROOT/name).resolve();assert p.is_relative_to(ROOT) and p.is_file()
 data=json.loads(p.read_text());rows=data['files'];assert isinstance(rows,list) and rows
 files={};issues=[]
 for row in rows:
  name=row['path'];path=Path(name)
  assert not path.is_absolute() and ':' not in name and '\\' not in name and '..' not in path.parts and path.as_posix()==name
  assert name not in files,'Duplicate allowlist path'
  target=ROOT/path
  assert target.resolve().is_relative_to(ROOT) and target.is_file() and not target.is_symlink()
  assert not any(part in {'node_modules','.venv','dist','__pycache__'} for part in path.parts)
  assert not name.startswith('.bago/') and 'integrated-tabs-preview-20261023' not in name
  assert target.suffix.lower() not in {'.zip','.sqlite','.sqlite3','.db'}
  assert target.stat().st_size<=50*1024*1024,'File exceeds50MiB'
  raw=target.read_bytes();expected=row.get('working_tree_sha256',row.get('working_sha256',row.get('sha256')))
  assert expected and digest(raw)==expected,'Allowlist file changed: '+name
  files[name]=raw
 own=p.relative_to(ROOT).as_posix()
 files.setdefault(own,p.read_bytes())
 return files
def inventory(files):
 return {'status':'PASS','files':len(files),'bytes':sum(map(len,files.values())),'scope':'Explicit existing paths and working-byte identity only; no stage or publication'}
def scan(files):
 rules=[('PRIVATE_KEY',r'-----BEGIN (?:RSA |EC |OPENSSH |DSA )?PRIVATE KEY-----'),('GITHUB_TOKEN',r'\b(?:gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{40,})\b'),('OPENAI_TOKEN',r'\bsk-(?:proj-|svcacct-)?[A-Za-z0-9_-]{30,}\b'),('AWS_ACCESS_ID',r'\b(?:AKIA|ASIA)[A-Z0-9]{16}\b')]
 findings=[]
 for name,raw in files.items():
  if b'\x00' in raw or Path(name).suffix.lower() in {'.png','.jpg','.jpeg','.gif','.webp','.pdf','.ico','.woff','.woff2'}:continue
  for number,line in enumerate(raw.decode('utf-8',errors='replace').splitlines(),1):
   for kind,pattern in rules:
    if re.search(pattern,line):findings.append({'path':name,'line':number,'kind':kind})
 return {'status':'FAIL' if findings else 'PASS','findings':findings,'scope':'Finite token/private-key patterns; no matched values printed. Image privacy and synthetic-fixture classification require the separately recorded human review.'}
def index(files):
 changed=git('diff','--cached','--no-renames','--name-status','-z','HEAD').split(b'\0')
 staged=[];issues=[]
 for i in range(0,len(changed)-1,2):
  status=changed[i].decode();name=changed[i+1].decode('utf-8')
  staged.append(name)
  if name not in files:issues.append({'path':name,'reason':'Staged path outside explicit allowlist'})
  if status.startswith('D'):issues.append({'path':name,'reason':'Deletion is outside this publication delta'})
 if not staged:return {'status':'NOT_RUN','reason':'No staged changes; root must stage explicit final allowlist after independent review','scope':'Read-only; no index writes'}
 entries={}
 for row in git('ls-files','--stage','-z').split(b'\0'):
  if not row:continue
  metadata,name=row.split(b'\t',1);mode,blob,stage=metadata.split()
  entries[name.decode('utf-8')]=(mode.decode(),blob.decode(),stage.decode())
 pins=[]
 for line in (ROOT/'.gitattributes').read_text().splitlines():
  if line and not line.startswith('#'):
   name,attribute=line.split();assert attribute=='-text';pins.append(name.lstrip('/'))
 assert len(pins)>=11
 rows=[]
 for name in staged:
  if name not in files or name not in entries:continue
  mode,blob,stage=entries[name]
  if stage!='0' or mode not in {'100644','100755'}:issues.append({'path':name,'reason':'Conflict or unsupported index mode'});continue
  raw=files[name];binary=b'\x00' in raw or Path(name).suffix.lower() in {'.png','.jpg','.jpeg','.gif','.webp','.pdf','.ico','.woff','.woff2'}
  raw_pin=git('check-attr','--cached','text','--',name).strip().endswith(b': text: unset')
  expected=raw if raw_pin or binary else raw.replace(b'\r\n',b'\n')
  actual=git('cat-file','blob',blob)
  if actual!=expected:issues.append({'path':name,'reason':'Index differs from admitted raw-pin/binary or normalized text bytes'})
  rows.append({'path':name,'git_blob_sha1':blob,'index_sha256':digest(actual),'working_sha256':digest(raw),'raw_pin':raw_pin,'normalization_changes_bytes':raw!=expected})
 return {'status':'FAIL' if issues else 'PASS','issues':issues,'staged':len(staged),'files':rows,'scope':'Actual index blobs, not prospective hash-object examples; historical source hashes are retained without rewriting'}
def main():
 parser=argparse.ArgumentParser(description=__doc__)
 parser.add_argument('action',choices=['inventory','scan','index'])
 parser.add_argument('--manifest',required=True,help='Final admitted path/hash manifest, not an old candidate manifest')
 parser.add_argument('--output',required=True,help='JSON output below docs/final-beige')
 args=parser.parse_args();target=(ROOT/args.output).resolve()
 assert target.is_relative_to(ROOT/'docs/final-beige') and target.suffix=='.json'
 assert not target.exists(),'Preserve gate receipts; use a new output path'
 try:result={'action':args.action,**globals()[args.action](load_manifest(args.manifest))}
 except Exception as error:result={'action':args.action,'status':'FAIL','reason':type(error).__name__+': '+str(error)}
 result['mutations']='Only this requested JSON receipt; no Git writes or network actions'
 target.parent.mkdir(parents=True,exist_ok=True);target.write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))
 return 0 if result['status']=='PASS' else 2 if result['status']=='NOT_RUN' else 1
if __name__=='__main__':raise SystemExit(main())
