"""Retry the exact frozen verifier function, correcting only its broken CLI caller."""
import argparse,hashlib,importlib.util,json,pathlib,sys
p=argparse.ArgumentParser()
p.add_argument('--work',type=pathlib.Path,required=True)
p.add_argument('--expected-verifier-sha256',required=True)
a=p.parse_args(); work=a.work.resolve()
source=work/'candidate/src/verify_mission.py'
assert hashlib.sha256(source.read_bytes()).hexdigest()==a.expected_verifier_sha256
spec=importlib.util.spec_from_file_location('frozen_cognitive_verifier',source)
module=importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
final,result=module.check(work)
print(json.dumps(result,ensure_ascii=False,sort_keys=True))
sys.exit(0 if final['status']=='PASS' else 1)
