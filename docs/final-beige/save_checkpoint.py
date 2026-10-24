"""Prepare a public WIP checkpoint; never stages or publishes anything."""
from pathlib import Path
import json,hashlib,shutil,datetime
ROOT=Path(__file__).resolve().parents[2]
SOURCE=ROOT.parent/'agent-chat-write-20261023'
OUT=ROOT/'docs/final-beige/checkpoint-20261024'
assert not OUT.exists();OUT.mkdir()
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
freeze=SOURCE/'docs/communications-navigation-20261024/context-readability/implementation/FREEZE.json'
rows=json.loads(freeze.read_text(encoding='utf-8'))['files']
for row in rows:
 name=row['path'];assert name.startswith('frontend/') and '..' not in Path(name).parts
 assert sha(SOURCE/name)==row['sha256']
 target=ROOT/name;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes((SOURCE/name).read_bytes())
proof=OUT/'context-prepared';proof.mkdir()
for name in ['FREEZE.json','PRESERVATION_PROOF.json','ACCEPTANCE_RESULTS.json','focused.log','build.log']:
 source=freeze.parent/name
 if source.is_file():shutil.copyfile(source,proof/name)
(OUT/'STATUS.md').write_text('''# Punto de control público

Guardado de trabajo en curso. No es una promoción ni un cierre de la última interfaz.

- Servicios y Comunicaciones: commit anterior conservado.
- Configuración al pie y acentos beige: RC14 verificada y aplicada localmente en8093.
- Primer ajuste de contexto: fuentes CL01 preparadas,54 pruebas focales y build; la petición posterior de reducir texto todavía está pendiente.
- CI: preparación de Node adelantada a las pruebas Python.
-941 pruebas Python de la preparación P son evidencia heredada de sus bytes;945 de L/RC14 son una ejecución distinta. No se suman.
- Google simplificado, ampliación de capacidades y nuevo corpus Bocado24 no están implementados por este checkpoint.
- No se incluyen sesiones, proveedores, bases de datos, contactos privados ni el corpus sintético en preparación.

Esta rama se guarda para evitar pérdida de trabajo y continuar revisando. Hosted CI y últimos recorridos: consultar sus estados propios.
''',encoding='utf-8')
names={'.gitattributes','.github/workflows/ci.yml','frontend/src/App.tsx','frontend/src/NavigationOrder.css','frontend/tests/ui/communications/navigation-control-order.test.tsx'}
names.update(row['path'] for row in rows)
for root in ['docs/verification/publication-20261024/final','docs/final-beige']:
 names.update(p.relative_to(ROOT).as_posix() for p in (ROOT/root).rglob('*') if p.is_file() and '__pycache__' not in p.parts)
assert all((ROOT/name).is_file() for name in names)
manifest=OUT/'CHECKPOINT_FILES.json'
manifest.write_text(json.dumps({'status':'WIP_CHECKPOINT_NOT_FINAL','at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'files':[{'path':name,'sha256':sha(ROOT/name)} for name in sorted(names)]},indent=2),encoding='utf-8')
print(json.dumps({'status':'PREPARED','files':len(names),'manifest':manifest.relative_to(ROOT).as_posix()}))
