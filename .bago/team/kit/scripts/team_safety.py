"""Portable validation adapted for the ADL team controller (stdlib, Python >= 3.11).

Integrity checking is NOT authentication and filesystem checks are not an OS sandbox.
"""
from __future__ import annotations
import json
import os
from pathlib import Path, PurePosixPath
import re
import stat
import unicodedata

SHA256 = re.compile(r"[0-9a-f]{64}\Z")
RESERVED = {"CON", "PRN", "AUX", "NUL"} | {f"COM{i}" for i in range(1, 10)} | {f"LPT{i}" for i in range(1, 10)}


def safe_rel(value: str, *, glob: bool = False) -> PurePosixPath:
    if not isinstance(value, str) or not value or value.startswith('/') or '\\' in value:
        raise ValueError(f"unsafe relative path: {value!r}")
    if unicodedata.normalize('NFC', value) != value:
        raise ValueError('path must use canonical Unicode NFC')
    for part in value.split('/'):
        if part in ('', '.', '..') or part.endswith(('.', ' ')):
            raise ValueError(f"unsafe path segment: {value!r}")
        forbidden = '<>:"|' if glob else '<>:"|?*'
        if any(ord(c) < 32 or ord(c) == 127 or c in forbidden for c in part):
            raise ValueError(f"unsafe path characters: {value!r}")
        if not glob and unicodedata.normalize('NFKC', part.split('.')[0]).upper() in RESERVED:
            raise ValueError(f"reserved device name: {value!r}")
    return PurePosixPath(value)


def collision_key(path: str) -> str:
    return unicodedata.normalize('NFC', path).casefold()


def reject_links(path: Path) -> None:
    """Reject existing symlinks/reparse points in a path and its ancestors."""
    path = Path(os.path.abspath(path.expanduser()))
    for item in [path, *path.parents]:
        try:
            st = item.lstat()
        except FileNotFoundError:
            continue
        if stat.S_ISLNK(st.st_mode) or getattr(st, 'st_file_attributes', 0) & 0x400:
            raise ValueError(f"symbolic link or reparse point forbidden: {item}")


def _pairs(items):
    obj = {}
    for key, value in items:
        if key in obj:
            raise ValueError(f'duplicate JSON key: {key}')
        obj[key] = value
    return obj


def strict_json(data: str | bytes):
    def invalid(value):
        raise ValueError(f'non-finite JSON number: {value}')
    return json.loads(data, object_pairs_hook=_pairs, parse_constant=invalid)


def read_json(path: Path, max_bytes: int = 25_000_000):
    reject_links(path)
    with path.open('rb') as stream:
        data = stream.read(max_bytes + 1)
    if len(data) > max_bytes:
        raise ValueError('JSON exceeds byte budget')
    return strict_json(data)

