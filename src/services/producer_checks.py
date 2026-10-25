"""Fixed host check: source/output byte integrity, never business acceptance."""
from pathlib import Path
import argparse
import hashlib
import json


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--manifest',required=True)
    parser.add_argument('--check',choices=['artifact-integrity','synthetic-fixture-v1'],default='artifact-integrity')
    args=parser.parse_args();value=json.loads(Path(args.manifest).read_text(encoding='utf8'))
    checked=[]
    for row in value['files']:
        path=Path(row['path'])
        for part in (path,*path.parents):
            info=part.lstat()
            if part.is_symlink() or getattr(info,'st_file_attributes',0)&1024:raise ValueError('link rejected')
        raw=path.read_bytes()
        if len(raw)>16*1024*1024 or hashlib.sha256(raw).hexdigest()!=row['sha256']:raise ValueError('source/output hash changed')
        checked.append({'path':str(path),'sha256':row['sha256']})
    if not checked:raise ValueError('no files to check')
    if args.check=='synthetic-fixture-v1':
        artifacts=value.get('artifact_paths',[])
        if len(artifacts)!=1 or Path(artifacts[0]).read_bytes()!=b'SYNTHETIC DELIVERY ACCEPTANCE V1\n':raise ValueError('synthetic content acceptance failed')
        print(json.dumps({'check':'business_acceptance','scope':'synthetic fixed fixture content only; not accounting','result':'PASS'}))
        return 0
    print(json.dumps({'check':'artifact_integrity','checked':checked,'business_acceptance':'NOT_RUN'},ensure_ascii=False))
    return 0


if __name__=='__main__':raise SystemExit(main())
