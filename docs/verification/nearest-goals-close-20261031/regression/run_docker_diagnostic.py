"""Retry with observable delegation exceptions; full README gate stays unpatched."""
from pathlib import Path
import importlib.util

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('archive_runner', HERE / 'run_docker_archive.py')
runner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runner)
runner.ATTEMPT = HERE / 'docker-attempt3'

PLUGIN = r'''
import functools,json,traceback
from pathlib import Path
def pytest_configure(config):
    from src.services.agent_delegation import AgentDelegations
    for name in ('_observe_child','_finish'):
        original=getattr(AgentDelegations,name)
        def decorate(fn,label):
            @functools.wraps(fn)
            def observed(*args,**kwargs):
                try:return fn(*args,**kwargs)
                except Exception as error:
                    record={'method':label,'type':type(error).__name__,'exception':str(error),
                            'traceback':traceback.format_exc()}
                    path=Path('/workspace/output/delegation-diagnostics.jsonl')
                    with path.open('a',encoding='utf-8') as stream:stream.write(json.dumps(record)+'\n')
                    raise
            return observed
        setattr(AgentDelegations,name,decorate(original,name))
'''

INSTRUMENT = """
import subprocess
(root/'delegation_diag_plugin.py').write_text(PLUGIN_CODE,encoding='utf-8')
original_run=subprocess.run
def diagnosed(argv,*args,**kwargs):
    if isinstance(argv,list) and '-m' in argv and 'pytest' in argv:
        argv=[*argv,'--showlocals','--tb=long','-p','delegation_diag_plugin']
        kwargs['env']=dict(kwargs.get('env',os.environ),PYTHONPATH=str(root))
    return original_run(argv,*args,**kwargs)
subprocess.run=diagnosed
""".replace('PLUGIN_CODE', repr(PLUGIN))

EXPORT = """
diagnostic=root/'output/delegation-diagnostics.jsonl'
if diagnostic.exists():shutil.copyfile(diagnostic,'/results/delegation-diagnostics.jsonl')
for folder in (root/'output/ngd1/triage').glob('test_no_parent_grant*'):
    if folder.is_dir():shutil.copytree(folder,Path('/results')/'failed-fixture'/folder.name,dirs_exist_ok=True)
"""

runner.BOOTSTRAP = runner.BOOTSTRAP.replace('docker-attempt2', 'docker-attempt3')
runner.BOOTSTRAP = runner.BOOTSTRAP.replace('code=inner()', INSTRUMENT + '\ncode=inner()')
runner.BOOTSTRAP = runner.BOOTSTRAP.replace("shutil.copytree(out,'/results',dirs_exist_ok=True)",
    "shutil.copytree(out,'/results',dirs_exist_ok=True)\n" + EXPORT)

if __name__ == '__main__':
    raise SystemExit(runner.main())
