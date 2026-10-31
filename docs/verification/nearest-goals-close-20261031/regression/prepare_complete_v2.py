"""Preserve test collection order and stage a real shallow Git candidate."""
from pathlib import Path
import hashlib

HERE = Path(__file__).resolve().parent
source = HERE / 'run_docker_complete.py'
text = source.read_text(encoding='utf-8')
text = text.replace("ATTEMPT = OUT / 'docker-attempt4'", "ATTEMPT = OUT / 'docker-attempt5'")
text = text.replace("archive_path = ROOT / 'output/ng-complete.tar'", "archive_path = ROOT / 'output/ng-complete-v2.tar'")
text = text.replace('selection = set()', 'selection = []')
text = text.replace("selection.add(file + '::' + case.attrib['name'])", "node = file + '::' + case.attrib['name']\n                if node not in selection: selection.append(node)")
text = text.replace('json.dumps(sorted(selection))', 'json.dumps(selection)')
marker = "    dependency_inventory = []"
assert marker in text
text = text.replace(marker, """    object_ids = subprocess.check_output(['git','rev-list','--objects','--no-object-names','--no-walk=unsorted',head],cwd=ROOT)
    pack_path = ROOT / 'output/ng-candidate-objects.pack'
    with pack_path.open('wb') as stream:
        subprocess.run(['git','pack-objects','--stdout'],cwd=ROOT,input=object_ids,stdout=stream,check=True)
""" + marker)
marker = "    with tarfile.open(archive_path, 'a') as archive:"
assert marker in text
text = text.replace(marker, marker + """
        info=tarfile.TarInfo('check-candidate.pack');info.size=pack_path.stat().st_size;info.mode=0o644
        with pack_path.open('rb') as stream:archive.addfile(info,stream)
""")
marker = "root=Path('/workspace');out=root/'check-results';out.mkdir()"
assert marker in text
text = text.replace(marker, """root=Path('/workspace')
subprocess.run(['git','init','--quiet',str(root)],check=True)
with (root/'check-candidate.pack').open('rb') as stream:subprocess.run(['git','index-pack','--stdin'],cwd=root,stdin=stream,check=True,capture_output=True)
sha='8065906f4560f4f0b0951cc445b673ecad7ce175'
subprocess.run(['git','update-ref','refs/heads/codex/nearest-goals-close-20261031',sha],cwd=root,check=True)
subprocess.run(['git','symbolic-ref','HEAD','refs/heads/codex/nearest-goals-close-20261031'],cwd=root,check=True)
(root/'.git/shallow').write_text(sha+'\\n')
subprocess.run(['git','read-tree','HEAD'],cwd=root,check=True)
subprocess.run(['git','remote','add','origin','https://github.com/MarcValls/BAGO_AGENTIC_DATA_LAB.git'],cwd=root,check=True)
assert subprocess.check_output(['git','rev-parse','HEAD'],cwd=root,text=True).strip()==sha
out=root/'check-results';out.mkdir()""")
target = HERE / 'run_docker_complete_v2.py'
assert not target.exists(), 'Never replace an executed checker'
target.write_text(text, encoding='utf-8')
print('Prepared', target.name, hashlib.sha256(target.read_bytes()).hexdigest())
