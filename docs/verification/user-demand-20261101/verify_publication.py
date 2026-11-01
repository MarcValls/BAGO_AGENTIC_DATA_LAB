"""Verify finite published evidence with stdlib only, from a clone or extraction."""
from pathlib import Path, PurePosixPath
import argparse
import hashlib
import json


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--root', type=Path, default=Path(__file__).resolve().parent)
    args = parser.parse_args()
    root = args.root.resolve()
    index = json.loads((root / 'PUBLICATION_INDEX.json').read_bytes())
    errors = []
    for row in index['files']:
        rel = PurePosixPath(row['published'])
        if rel.is_absolute() or '..' in rel.parts or '\\' in str(rel):
            errors.append({'source': row['source'], 'reason': 'unsafe published path'})
            continue
        path = root.joinpath(*rel.parts)
        try:
            data = path.read_bytes()
            assert path.resolve().is_relative_to(root) and not path.is_symlink()
            assert len(data) == row['bytes']
            assert hashlib.sha256(data).hexdigest() == row['sha256']
        except (OSError, AssertionError):
            errors.append({'source': row['source'], 'reason': 'missing or changed published bytes'})
    for row in index['source_normalization']:
        try:
            data = (root / row['raw_object']).read_bytes()
            assert hashlib.sha256(data).hexdigest() == row['raw_sha256']
            normalized = data if row['equivalence'] == 'IDENTICAL' else data.replace(b'\r\n', b'\n')
            assert hashlib.sha256(normalized).hexdigest() == row['git_blob_sha256']
        except (OSError, AssertionError):
            errors.append({'source': row['source'], 'reason': 'raw to Git LF mapping failed'})
    for row in index['tooling']:
        try:
            assert hashlib.sha256((root / row['path']).read_bytes()).hexdigest() == row['sha256']
        except (OSError, AssertionError):
            errors.append({'source': row['path'], 'reason': 'portable tooling changed'})
    result = {'status': 'FAIL' if errors else 'PASS', 'scope': 'finite raw bytes and raw-to-Git-LF equivalence only',
              'logical_files': len(index['files']), 'physical_payloads': len({r['published'] for r in index['files']}),
              'source_normalizations': len(index['source_normalization']), 'errors': errors,
              'product_validation': 'NOT_IMPLIED', 'Windows_paths_required': False}
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 1 if errors else 0


if __name__ == '__main__':
    raise SystemExit(main())
