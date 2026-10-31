"""Local read-only adaptation of the installed cognitive mission; never edits Suite."""
import hashlib,json,pathlib,shutil,subprocess
h=pathlib.Path(__file__).resolve().parent
repo=next(p for p in h.parents if (p/'.git').exists())
suite=pathlib.Path.home()/'.codex/skills/bago-operating-suite'
module=suite/'modules/cognitive-mission'
project=h/'project'; project.mkdir(exist_ok=False)
src=h/'candidate/src'; src.mkdir(parents=True)
shutil.copyfile(module/'src/runtime_paths.py',src/'runtime_paths.py')
code=(module/'src/mission_runtime.py').read_text(encoding='utf-8')
code=code.replace("FILES=('REQUIREMENTS.md','config_manager.py','PROVENANCE.json','pyproject.toml')","FILES=('REQUIREMENTS.md','mission_snapshot.json','goal_status.json','PROVENANCE.json','pyproject.toml')")
code=code.replace("WRITE_FILES=('config_manager.py',)","WRITE_FILES=()")
code=code.replace("Repara el fallo de persistencia en config_manager.py dentro de la copia autorizada. ","Audita la continuidad operativa y sus evidencias de BAGO5 dentro del alcance de solo lectura. ")
code=code.replace("len(obs.get('tests',[]))!=12","len(obs.get('tests',[]))!=cfg['observer_test_count']")
code=code.replace("{n:after[n] for n in FILES if n.endswith('.py')}","{n:after[n] for n in FILES}")
code=code.replace('Choose useful actions; no oracle solutions are provided. Do not edit before an observed failing acceptance run. In recovery verify, do not reapply a successful patch.','Choose useful read-only audit actions. Run the acceptance evaluator. No source writes are authorized; do not turn integration success into original mission acceptance.')
code=code.replace("goal='repair_explicit_config_persistence'","goal='audit_bago5_governed_continuity'")
code=code.replace('real-module-copy product=','original-mission-review product=')
(src/'mission_runtime.py').write_text(code,encoding='utf-8')
sha=lambda b:hashlib.sha256(b).hexdigest()
sources={}
path='.bago/goals/operational-continuity-governance-20261031/status.json'
data=(repo/path).read_bytes(); (project/'goal_status.json').write_bytes(data)
sources['goal_status.json']={'path':path,'sha256':sha(data)}
ref='ef52fe44cf1fdd7538da93cb00403d6c51694732'
path='docs/verification/operational-continuity-governance-20261031/runtime-summary.json'
data=subprocess.check_output(['git','show',ref+':'+path],cwd=repo)
(project/'mission_snapshot.json').write_bytes(data)
sources['mission_snapshot.json']={'git_ref':ref,'path':path,'sha256':sha(data)}
provenance={'schema':'bago.continuity.cognitive-audit-input.v1','repository':str(repo),'original_mission':'CODEX_GOVERNED_CONTINUITY_20261031','sources':sources,'installed_adapter_source_sha256':sha((module/'src/mission_runtime.py').read_bytes()),'scope':'Read-only audit of actual mission state, not a ConfigManager fixture; no original repair or receipt rewrite.'}
(project/'PROVENANCE.json').write_text(json.dumps(provenance,indent=2),encoding='utf-8')
(project/'REQUIREMENTS.md').write_text('''# Cognitive audit of the current BAGO5 mission
Observe actual mission records, provenance, the frozen LOCAL_POLICY output and current teamctl verify.
Determine whether the original mission meets its acceptance criteria. Preserve FAIL/NO_GO when obligations are pending.
Three native Spiral cycles must use fresh host decisions, actual gateway reads and the fixed evaluator; preserve memory across processes.
No writes to original sources, handoffs, Git, registry, UI, external services or global configuration. Project audit input files are immutable.
The accepted relay R2 only validates snapshot continuity, not the original mission. T1 is PARTIAL; open criteria cannot be promoted.
The deliverable is a traced, evidence-bound audit and explicit governed next actions, not a claim that LOCAL_POLICY is repaired.
''',encoding='utf-8')
(project/'pyproject.toml').write_text('[project]\nname = "bago5-continuity-cognitive-audit"\nversion = "0.1.0"\n',encoding='utf-8')
print(json.dumps({'status':'PREPARED','project':str(project),'adapter':str(src/'mission_runtime.py'),'suite_modified':False}))
