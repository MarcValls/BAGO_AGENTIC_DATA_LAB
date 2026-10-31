"""Verify the finite evidence export without executing archived content."""
from pathlib import Path
import hashlib
import json
import re


def main():
    root=Path(__file__).resolve().parent
    manifest=json.loads((root/'EXPORT_MANIFEST.json').read_text(encoding='utf-8'))
    logical=set();objects=set()
    for row in manifest['files']:
        assert row['path'] not in logical
        logical.add(row['path'])
        assert re.fullmatch(r'objects/[0-9a-f]{24}',row['object']),row['object']
        data=(root/row['object']).read_bytes()
        assert len(data)==row['bytes']
        assert hashlib.sha256(data).hexdigest()==row['sha256'],row['path']
        objects.add(row['object'])
    result={'status':'PASS','logical_files':len(logical),'unique_objects':len(objects),
            'scope':'exact-byte export integrity of two accepted historical closures'}
    (root/'verification.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(result))


if __name__=='__main__':
    main()
