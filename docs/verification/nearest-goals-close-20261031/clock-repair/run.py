"""Bounded deterministic clock regression checks; no provider network calls."""
from pathlib import Path
import datetime, hashlib, json, os, subprocess, sys
import xml.etree.ElementTree as ET

ROOT=Path(__file__).resolve().parents[4]
OUT=Path(__file__).resolve().parent

def main():
    phase=sys.argv[1]
    destination=OUT/phase
    destination.mkdir(exist_ok=False)
    temp=destination/'t';temp.mkdir()
    env=os.environ.copy()
    for name in ('BAGO_APP_ROOT','BAGO_DATA_ROOT','PYTEST_ADDOPTS'):
        env.pop(name,None)
    env.update(PYTHONUTF8='1',PYTHONDONTWRITEBYTECODE='1',BAGO_DATA_ROOT=str(temp/'data'),
               TEMP=str(temp),TMP=str(temp),TMPDIR=str(temp))
    nodes=['tests/test_agent_delegation.py'] if phase.startswith('green') else [
        'tests/test_agent_delegation.py::test_parent_trace_clock_regression_preserves_child_outcome_and_replay_scope',
        'tests/test_agent_delegation.py::test_parent_trace_normal_clock_keeps_ordered_interval_and_duration']
    # Keep fixtures inside this evidence scope while avoiding the legacy Win32
    # path limit; no junction, drive mapping or host configuration is changed.
    fixture_temp=('\\\\?\\'+str(temp/'p')) if os.name=='nt' else str(temp/'p')
    argv=[sys.executable,'-B','-m','pytest','-q','-p','no:cacheprovider',*nodes,
          '--basetemp='+fixture_temp,'--junitxml='+str(destination/'tests.xml')]
    started=datetime.datetime.now(datetime.timezone.utc).isoformat()
    with (destination/'stdout.log').open('wb') as stdout,(destination/'stderr.log').open('wb') as stderr:
        process=subprocess.run(argv,cwd=ROOT,env=env,stdout=stdout,stderr=stderr,timeout=240)
    counts={}
    if (destination/'tests.xml').exists():
        tree=ET.parse(destination/'tests.xml').getroot();suites=[tree] if tree.tag=='testsuite' else list(tree)
        counts={key:sum(int(s.attrib.get(key,0)) for s in suites) for key in ('tests','failures','errors','skipped')}
    files=['src/api/server.py','tests/test_agent_delegation.py']
    result={'phase':phase,'test_result':'PASS' if process.returncode==0 else 'FAIL','returncode':process.returncode,
            'argv':argv,'started_at':started,'finished_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),
            'counts':counts,'sources':{p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in files},
            'logs':{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in destination.glob('*') if p.is_file()},
            'network':'Provider functions are synthetic fixture callbacks; no live inference',
            'temp_scope':str(temp)}
    (destination/'result.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf8')
    print(json.dumps(result,indent=2))
    return process.returncode

if __name__=='__main__':
    raise SystemExit(main())
