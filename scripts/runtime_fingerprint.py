"""Hash bounded ADL source/build inputs for a launcher freshness receipt.

The receipt detects ordinary source changes, additions and removals. It does
not attest loaded Python bytecode, external dependencies or atomic snapshots.
"""
from __future__ import annotations

import argparse
import hashlib
import os
import stat
from pathlib import Path

VERSION = b'bago-runtime-inputs-v1\0'
EXCLUDED = {'.git', '.venv', '__pycache__', 'node_modules', '.pytest_cache', '.bago', '.build', 'dist'}
BACKEND_FILES = ('requirements.txt', 'requirements-test.txt', 'requirements-documents.txt', 'requirements-whatsapp.txt', 'pyproject.toml', 'setup.cfg', 'scripts/runtime_fingerprint.py')
FRONTEND_FILES = ('index.html', 'ui-kit-preview.html', 'package.json', 'package-lock.json', 'tsconfig.json', 'tsconfig.node.json', 'vite.config.ts', 'vitest.config.ts', '.env', '.env.local', '.env.production', '.env.production.local')


def _is_link(info: os.stat_result) -> bool:
    return stat.S_ISLNK(info.st_mode) or bool(getattr(info, 'st_file_attributes', 0) & getattr(stat, 'FILE_ATTRIBUTE_REPARSE_POINT', 0x400))


def _walk_error(error: OSError) -> None:
    raise error


def _entries(root: Path, directories: tuple[str, ...], files: tuple[str, ...], required: tuple[str, ...]):
    entries: dict[str, Path | None] = {}
    for name in (*directories, *files):
        path = root / name
        for parent in reversed(path.relative_to(root).parents):
            if parent == Path('.'):
                continue
            parent_path = root / parent
            try:
                parent_info = parent_path.lstat()
            except FileNotFoundError:
                continue
            if _is_link(parent_info) or not stat.S_ISDIR(parent_info.st_mode):
                raise ValueError(f'unsafe parent: {parent}')
        try:
            info = path.lstat()
        except FileNotFoundError:
            if name in required:
                raise ValueError(f'required input missing: {name}')
            entries[name] = None
            continue
        if _is_link(info):
            raise ValueError(f'linked input denied: {name}')
        if name in files:
            if not stat.S_ISREG(info.st_mode):
                raise ValueError(f'not a regular file: {name}')
            entries[name] = path
            continue
        if not stat.S_ISDIR(info.st_mode):
            raise ValueError(f'not a directory: {name}')
        entries[name + '/'] = None
        for base, dirs, names in os.walk(path, followlinks=False, onerror=_walk_error):
            base_path = Path(base)
            dirs[:] = sorted(d for d in dirs if d not in EXCLUDED)
            for child in dirs:
                if _is_link((base_path / child).lstat()):
                    raise ValueError(f'linked directory denied: {(base_path / child).relative_to(root)}')
                entries[(base_path / child).relative_to(root).as_posix() + '/'] = None
            for child in sorted(names):
                item = base_path / child
                info = item.lstat()
                if _is_link(info) or not stat.S_ISREG(info.st_mode):
                    raise ValueError(f'unsafe input: {item.relative_to(root)}')
                if item.suffix.lower() in {'.pyc', '.pyo'}:
                    continue
                entries[item.relative_to(root).as_posix()] = item
    return entries


def fingerprint(root: Path, kind: str) -> str:
    root = root.resolve(strict=True)
    if kind == 'backend':
        directories, files, required = ('src', 'tools', '.bago/team/kit'), BACKEND_FILES, ('src',)
    elif kind == 'frontend':
        directories = ('frontend/src', 'frontend/public')
        files = tuple('frontend/' + name for name in FRONTEND_FILES)
        required = ('frontend/src', 'frontend/index.html', 'frontend/package.json', 'frontend/package-lock.json')
    elif kind == 'dist':
        directories, files, required = ('frontend/dist',), (), ('frontend/dist',)
    else:
        raise ValueError('unknown fingerprint kind')
    entries = _entries(root, directories, files, required)
    digest = hashlib.sha256(VERSION + kind.encode('ascii') + b'\0')
    for name, path in sorted(entries.items()):
        encoded = name.encode('utf-8')
        digest.update(len(encoded).to_bytes(8, 'big') + encoded)
        if path is None:
            digest.update(b'\0')
            continue
        before = path.stat()
        content = hashlib.sha256(path.read_bytes()).digest()
        after = path.stat()
        if (before.st_size, before.st_mtime_ns, before.st_ino) != (after.st_size, after.st_mtime_ns, after.st_ino):
            raise RuntimeError(f'input changed while hashing: {name}')
        digest.update(b'\1' + content)
    if kind == 'frontend':
        for name, value in sorted(os.environ.items()):
            if not (name.startswith('VITE_') or name in {'NODE_ENV', 'BAGO_API_PROXY_TARGET'}):
                continue
            name_bytes = name.encode('utf-8')
            value_bytes = value.encode('utf-8')
            digest.update(b'\2' + len(name_bytes).to_bytes(8, 'big') + name_bytes + len(value_bytes).to_bytes(8, 'big') + value_bytes)
    return digest.hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--kind', choices=('backend', 'frontend', 'dist'), required=True)
    args = parser.parse_args()
    print(fingerprint(args.root, args.kind))


if __name__ == '__main__':
    main()
