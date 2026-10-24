"""Materialize the next public checkpoint without changing Git or local user data."""
from pathlib import Path
import json,hashlib,shutil
ROOT=Path(__file__).resolve().parents[2];SOURCE=ROOT.parent/'agent-chat-write-20261023';OUT=ROOT/'docs/ui-context-light'
assert not OUT.exists();OUT.mkdir()
base=SOURCE/'docs/communications-navigation-20261024/context-readability-lite'
rows=json.loads((base/'implementation/FREEZE.json').read_text(encoding='utf-8'))['files']
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
for row in rows:
 name=row['path'];assert name.startswith('frontend/') and sha(SOURCE/name)==row['sha256'];target=ROOT/name;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes((SOURCE/name).read_bytes())
for area in ['implementation','integration/prototype','integration/baseline']:
 target=OUT/area;target.mkdir(parents=True)
 for p in (base/area).iterdir():
  if p.is_file() and p.suffix in {'.json','.log','.png'} and p.name not in {'handoff.json','MANAGED_CHECK.json','BEFORE.json','SOURCE_DELTA.json'}:shutil.copyfile(p,target/p.name)
(OUT/'README.md').write_text('''# Contexto con menos texto visible

Implementación preparada y comprobada en preview5193. Aplicación final pendiente.

Por defecto se muestran carpeta activa y cinco fuentes con sus estados. Los parámetros y explicaciones quedan en «Detalles», cerrado. Las rutas conservan su valor completo y desplazamiento local accesible; Workspace mantiene su funcionamiento.

Con los mismos metadatos, el bloque pasó de496a281px a1920, de712a340px a960 y de1288a512px a320. Texto visible:1346→412 caracteres. Son medidas de un mismo recorrido, no pruebas independientes que deban sumarse.64pruebas focales y buildPASS pertenecen al estado local congelado; la batería final y despliegue se registrarán aparte.

Capturas actuales con rutas ocultas antes de guardar: [ancha](integration/prototype/1920.png), [media](integration/prototype/960.png), [estrecha](integration/prototype/320.png). Los datos siguen disponibles en Detalles.

Los objetos históricos de docs/final-beige/predecessor/objects usanSHA256como nombre. Su nueva reglaGit evita normalizar CRLF y recupera sus bytes originales; los manifiestos históricos no se recalculan. Las comprobaciones de índice verifican los blobs reales.
''',encoding='utf-8')
names={r['path'] for r in rows}|{'.gitattributes','docs/final-beige/publication_guard.py','docs/final-beige/save_lite_checkpoint.py','tests/test_public_evidence_bytes.py'}
names.update(p.relative_to(ROOT).as_posix() for p in OUT.rglob('*') if p.is_file())
names.update(p.relative_to(ROOT).as_posix() for p in (ROOT/'docs/final-beige/predecessor/objects').iterdir())
manifest=OUT/'CHECKPOINT_FILES.json';manifest.write_text(json.dumps({'state':'PREPARED_PREVIEW_VERIFIED_FINAL_PENDING','files':[{'path':name,'sha256':sha(ROOT/name)} for name in sorted(names)]},indent=2),encoding='utf-8');print(json.dumps({'files':len(names),'manifest':manifest.relative_to(ROOT).as_posix()}))
