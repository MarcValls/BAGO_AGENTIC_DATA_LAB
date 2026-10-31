"""Revalidate finite F02 evidence; do not rerun frontend suites."""
from pathlib import Path
import hashlib,json,subprocess,sys
ROOT=Path(__file__).resolve().parents[4]
OUT=Path(__file__).resolve().parent/'frontend-integrity'
def digest(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def main():
    OUT.mkdir(exist_ok=False)
    command=[sys.executable,'-B','.bago/team/kit/scripts/teamctl.py','--root','frontend','verify']
    process=subprocess.run(command,cwd=ROOT,capture_output=True,text=True)
    report={'status':'FAIL','operation':'Integrity/source-binding only; no frontend tests rerun',
        'candidate_head':subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
        'verify':{'argv':command,'returncode':process.returncode,'stdout':process.stdout,'stderr':process.stderr}}
    try:
        assert process.returncode==0,process.stdout+process.stderr
        hp=ROOT/'frontend/.bago/team/runtime/handoffs/F02.json';handoff=json.loads(hp.read_text())
        assert handoff['work_id']=='F02' and handoff['status']=='DONE'
        verified=[]
        for item in handoff['outputs']:
            actual=digest(ROOT/'frontend'/item['path']);assert actual==item['sha256'],item['path']
            verified.append({'path':'frontend/'+item['path'],'sha256':actual,'kind':item.get('kind')})
        tests=json.loads((ROOT/'frontend/nearest-goals-check/footer-repair/layout-r2/TEST_RESULTS_R2.json').read_text())
        browser=json.loads((ROOT/'frontend/nearest-goals-check/footer-repair/layout-r2/browser-attempt2/BROWSER_RESULTS.json').read_text())
        assert tests['status']=='PASS' and tests['focused_now']=={'passed':6,'failed':0}
        assert browser['status']=='PASS' and len(browser['checks'])==21 and all(x['passed'] for x in browser['checks'])
        old=tests['historical_full_vitest'];assert old['passed']==827 and old['new_execution'] is False
        assert digest(ROOT/old['archived_receipt'])==old['receipt_sha256']
        assert digest(ROOT/'frontend/nearest-goals-check/footer-repair/TEST_RESULTS.json')==old['result_sha256']
        for relative,expected in browser['source_sha256'].items():assert digest(ROOT/'frontend'/relative)==expected,relative
        (OUT/'F02-handoff.json').write_bytes(hp.read_bytes())
        report.update(status='PASS',frontend_mission=handoff['mission_id'],handoff_sha256=digest(hp),
            outputs_verified=verified,source_bindings=[x for x in verified if x['kind']=='SOURCE'],
            fresh_focused_tests=tests['focused_now'],fresh_build='PASS',actual_app_browser_checks=21,
            browser_scope=browser['scope'],provider_calls=browser['provider_calls'],historical_full_vitest=old,
            limits=['827 Vitest is historical before F02 CSS; no new execution.',
                    'F02 ran six affected tests, fresh build and21 actual-App browser checks with synthetic APIs.',
                    'Integrity does not replace independent product acceptance.'])
    except Exception as error:report['error']=repr(error)
    (OUT/'report.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf8')
    print(json.dumps({'status':report['status'],'outputs_verified':len(report.get('outputs_verified',[])),'error':report.get('error')}))
    return 0 if report['status']=='PASS' else 1
if __name__=='__main__':raise SystemExit(main())
