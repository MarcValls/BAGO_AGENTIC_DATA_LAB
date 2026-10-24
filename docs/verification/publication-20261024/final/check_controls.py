"""Read-only finite successor checks; does not rerun inherited Python suite."""
from pathlib import Path
import hashlib,json,re,subprocess
root=Path(__file__).resolve().parents[4]
out=Path(__file__).resolve().parent
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
baseline=json.loads((out/'P1_SOURCE_BASELINE.json').read_text())
errors=[]
for row in baseline['files']:
 p=root/row['path']
 if not p.is_file() or sha(p)!=row['sha256']:errors.append('Protected source changed: '+row['path'])
oldpaths={r['path'] for r in baseline['files']}
current={p.relative_to(root).as_posix() for folder in ['src','tests','scripts'] for p in (root/folder).rglob('*.py') if '__pycache__' not in p.parts}
current|={p.relative_to(root).as_posix() for p in root.glob('requirements*.txt')}
if current-oldpaths:errors.append('New Python/requirement files: '+str(sorted(current-oldpaths)))
old=subprocess.check_output(['git','show',baseline['commit']+':.github/workflows/ci.yml'],cwd=root).replace(b'\r\n',b'\n')
new=(root/'.github/workflows/ci.yml').read_bytes().replace(b'\r\n',b'\n')
def blocks(data):
 parts=re.split(rb'(?=^      - name: )',data,flags=re.M)
 return parts[0],parts[1:]
oldhead,oldsteps=blocks(old);newhead,newsteps=blocks(new)
if oldhead!=newhead or sorted(oldsteps)!=sorted(newsteps):errors.append('Workflow edits exceed ordering')
def name(step):return step.split(b'\n',1)[0].decode().split(': ',1)[1]
oldnames=list(map(name,oldsteps));newnames=list(map(name,newsteps))
expected=[n for n in oldnames if n not in ['Setup Node.js','Install frontend dependencies']]
i=expected.index('Run complete test suite');expected[i:i]=['Setup Node.js','Install frontend dependencies']
if newnames!=expected:errors.append('Unexpected workflow order')
try:
 import yaml
 yaml.safe_load(new)
 syntax='PASS: PyYAML parses workflow'
except ImportError:
 syntax='NOT_RUN: YAML parser absent; exact existing step blocks and header validated'
except Exception as exc:
 errors.append('Workflow syntax: '+str(exc));syntax='FAIL'
cr=json.loads((out/'CHANGE_REQUEST.json').read_text())
pins=cr['raw_pins']
attrs=[line for line in (root/'.gitattributes').read_text().splitlines() if line and not line.startswith('#')]
if attrs!=['/'+r['path']+' -text' for r in pins]:errors.append('Attributes exceed exact eleven pins')
for row in pins:
 if sha(root/row['path'])!=row['sha256']:errors.append('Raw contract changed: '+row['path'])
check=subprocess.run(['git','check-attr','text','--']+[r['path'] for r in pins],cwd=root,text=True,capture_output=True)
if check.returncode or len(check.stdout.splitlines())!=11 or any(not line.endswith(': text: unset') for line in check.stdout.splitlines()):errors.append('Git attributes ineffective')
freeze=json.loads((out/'HR01_FREEZE.json').read_text())
for row in freeze['files']:
 if sha(root/row['path'])!=row['sha256']:errors.append('HR01 source changed: '+row['path'])
result={'status':'FAIL' if errors else 'PASS','errors':errors,'protected_sources':len(baseline['files']),'python_suite':{'status':'INHERITED_UNCHANGED_WORKING_TREE','passed':941,'skipped':1,'execution':'45204dcac9b246ee82ecbdd9d6684622','fresh_full':'NOT_RUN: explicit bounded successor authorization, all Python/requirements/scripts and README inputs unchanged'},'workflow':{'existing_steps':len(oldsteps),'only_reordered':newnames==expected,'syntax':syntax,'hosted_ci':'NOT_RUN'},'attributes':{'pins':len(pins),'effective_git_output':check.stdout.splitlines()},'ui':{'source':'HR01 freeze','files':len(freeze['files'])},'destination':'PREPARED draft PR candidate, no remote mutation'}
(out/'CONTROLS_CHECK.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps(result))
raise SystemExit(bool(errors))
