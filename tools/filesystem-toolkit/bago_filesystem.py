"""Bounded filesystem operations for trusted local callers; Python standard library only.

Approval records are explicit capabilities supplied by the trusted host, not authentication.
The root and its metadata must not be writable by an adversarial concurrent process.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import re
import shutil
import stat
import time
import uuid
from contextlib import contextmanager


OPERATIONS = frozenset({'mkdir', 'write', 'copy', 'move', 'rename', 'trash', 'restore'})
MAX_BYTES = 16 * 1024 * 1024
RESERVED = re.compile(r'^(CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9])(?:\.|$)', re.I)


class FilesystemError(ValueError):
    pass


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=True,
                                     separators=(',', ':')).encode()).hexdigest()


def file_hash(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


class FilesystemToolkit:
    def __init__(self, root):
        raw = Path(root).absolute()
        for part in (raw, *raw.parents):
            self._plain(part)
        self.root = raw.resolve(strict=True)
        if not self.root.is_dir():
            raise FilesystemError('root must be a directory')
        self.state = self.root / '.bago-filesystem'
        if os.path.lexists(self.state):
            self._plain(self.state)
            if not self.state.is_dir():
                raise FilesystemError('toolkit state must be a directory')

    def _ensure_state(self):
        """Initialize metadata only for plan/execution, never for inventory."""
        self._plain(self.root)
        self.state.mkdir(exist_ok=True)
        self._plain(self.state)
        for name in ('plans', 'receipts', 'trash-index'):
            folder = self.state / name
            folder.mkdir(exist_ok=True)
            self._plain(folder)

    @staticmethod
    def _plain(path):
        info = path.lstat()
        if stat.S_ISLNK(info.st_mode) or getattr(info, 'st_file_attributes', 0) & 0x400:
            raise FilesystemError('symlink/reparse points are forbidden')

    def _path(self, relative, *, internal=False, allow_dot=False):
        if relative == '.' and allow_dot:
            self._plain(self.root)
            return self.root
        if not isinstance(relative, str) or not relative or '\\' in relative:
            raise FilesystemError('canonical relative POSIX path required')
        parts = relative.split('/')
        if any(p in ('', '.', '..') or ':' in p or p[-1:] in (' ', '.')
               or any(ord(c) < 32 or c in '<>"|?*' for c in p) or RESERVED.match(p)
               for p in parts):
            raise FilesystemError('unsafe path')
        if not internal and parts[0].casefold() in ('.bago-filesystem', 'trash'):
            raise FilesystemError('reserved toolkit path')
        current = self.root
        self._plain(current)
        for part in parts:
            if current.exists():
                if not current.is_dir():
                    raise FilesystemError('parent is not a directory')
                for entry in current.iterdir():
                    if entry.name.casefold() == part.casefold() and entry.name != part:
                        raise FilesystemError('case collision')
            current = current / part
            if os.path.lexists(current):
                self._plain(current)
        return current

    def _snapshot(self, path):
        if not path.exists():
            return None
        self._plain(path)
        info = path.stat()
        if not path.is_file() or info.st_nlink != 1 or info.st_size > MAX_BYTES:
            raise FilesystemError('only regular single-link files up to 16 MiB supported')
        return {'sha256': file_hash(path), 'size': info.st_size,
                'mtime_ns': info.st_mtime_ns, 'inode': info.st_ino}

    def _save_new(self, path, value):
        self._plain(path.parent)
        with path.open('x', encoding='utf-8') as stream:
            json.dump(value, stream, sort_keys=True, ensure_ascii=True, indent=2)
            stream.flush()
            os.fsync(stream.fileno())

    def _load(self, folder, identifier):
        if not isinstance(identifier, str) or not re.fullmatch('[a-f0-9]{32}', identifier):
            raise FilesystemError('invalid record id')
        path = self.state / folder / (identifier + '.json')
        self._plain(path.parent)
        self._plain(path)
        return json.loads(path.read_text(encoding='utf-8'))

    @contextmanager
    def _lock(self):
        self._ensure_state()
        lock = self.state / 'lock'
        self._plain(self.state)
        try:
            lock.mkdir()
        except FileExistsError:
            raise FilesystemError('workspace busy or interrupted: inspect pending receipts before recovery')
        try:
            yield
        finally:
            lock.rmdir()

    def inventory(self, path='.', *, max_entries=1000):
        if not isinstance(max_entries, int) or not 1 <= max_entries <= 1000:
            raise FilesystemError('max_entries must be 1..1000')
        folder = self._path(path, allow_dot=True)
        if not folder.is_dir():
            raise FilesystemError('inventory requires a directory')
        result = []
        for entry in sorted(folder.iterdir(), key=lambda p: p.name.casefold()):
            if folder == self.root and entry.name.casefold() in ('.bago-filesystem', 'trash'):
                continue
            if len(result) >= max_entries:
                raise FilesystemError('inventory limit exceeded; choose a narrower folder')
            self._plain(entry)
            result.append({'path': entry.relative_to(self.root).as_posix(),
                           'kind': 'directory' if entry.is_dir() else 'file',
                           'snapshot': None if entry.is_dir() else self._snapshot(entry)})
        return {'root': str(self.root), 'entries': result, 'recursive': False}

    def plan(self, operation, *, source=None, target=None, content=None, trash_id=None):
        if operation not in OPERATIONS:
            raise FilesystemError('unsupported operation')
        with self._lock():
            identifier = uuid.uuid4().hex
            trash_record = None
            if operation == 'restore':
                trash_record = self._load('trash-index', trash_id)
                source, target = trash_record['stored_path'], trash_record['original_path']
            elif operation == 'trash':
                target = 'trash/' + identifier + '.payload'
            src = self._path(source, internal=operation == 'restore') if source else None
            dst = self._path(target, internal=operation == 'trash') if target else None
            if operation in ('copy', 'move', 'rename', 'trash', 'restore'):
                if src is None or not src.exists():
                    raise FilesystemError('source is required')
                snapshot = self._snapshot(src)
                if trash_record and snapshot['sha256'] != trash_record['sha256']:
                    raise FilesystemError('trash payload changed')
            else:
                if source is not None or trash_id is not None:
                    raise FilesystemError('unexpected source')
                snapshot = None
            if dst is None or dst.exists():
                raise FilesystemError('target must be new')
            if not dst.parent.is_dir() and not (operation == 'trash' and dst.parent == self.root / 'trash'):
                raise FilesystemError('target parent must exist')
            if operation == 'rename' and src.parent != dst.parent:
                raise FilesystemError('rename must stay in the same directory')
            if operation == 'write':
                if not isinstance(content, str) or len(content.encode('utf-8')) > MAX_BYTES:
                    raise FilesystemError('write requires UTF-8 text up to 16 MiB')
            elif content is not None:
                raise FilesystemError('content only valid for write')
            plan = {'version': 1, 'id': identifier, 'root': str(self.root), 'operation': operation,
                    'source': source, 'target': target, 'source_snapshot': snapshot,
                    'target_snapshot': None, 'content': content, 'trash_id': trash_id,
                    'created_at': time.time(), 'expires_at': time.time() + 900,
                    'effects': ['create_target'] + (['remove_source_after_verified_copy']
                        if operation in ('move', 'rename', 'trash', 'restore') else []),
                    'content_sha256': hashlib.sha256(content.encode()).hexdigest() if content is not None else None}
            plan['sha256'] = digest(plan)
            self._save_new(self.state / 'plans' / (identifier + '.json'), plan)
            return plan

    def execute(self, plan_id, *, approval):
        """Trusted host must verify human authority before constructing approval.

        An approval must bind root, exact plan hash, operation, actor, and expiry.
        It is intentionally never exposed as a model-callable mutation tool.
        """
        with self._lock():
            plan = self._load('plans', plan_id)
            expected = plan['sha256']
            if digest({k: v for k, v in plan.items() if k != 'sha256'}) != expected:
                raise FilesystemError('plan checksum mismatch')
            op = plan['operation']
            if (not isinstance(approval, dict) or approval.get('root') != str(self.root)
                    or approval.get('plan_sha256') != expected
                    or not isinstance(approval.get('operations'), (list, tuple, set, frozenset))
                    or op not in approval['operations']
                    or not isinstance(approval.get('actor'), str) or not approval['actor'].strip()
                    or not isinstance(approval.get('expires_at'), (int, float))
                    or not math.isfinite(approval['expires_at'])
                    or approval['expires_at'] <= time.time() or plan['expires_at'] <= time.time()
                    or plan['root'] != str(self.root)):
                raise FilesystemError('missing, expired or mismatched trusted-host approval')
            pending = self.state / 'receipts' / (plan_id + '.pending.json')
            final = self.state / 'receipts' / (plan_id + '.json')
            if pending.exists() or final.exists():
                raise FilesystemError('plan already attempted; inspect receipt')
            receipt = {'plan_id': plan_id, 'plan_sha256': expected, 'root': str(self.root),
                       'operation': op, 'actor': approval['actor'], 'status': 'STARTED',
                       'effects': [], 'started_at': time.time(), 'source': plan['source'], 'target': plan['target']}
            self._save_new(pending, receipt)
            try:
                src = self._path(plan['source'], internal=op == 'restore') if plan['source'] else None
                dst = self._path(plan['target'], internal=op == 'trash')
                if dst.exists():
                    raise FilesystemError('target collision')
                if src and self._snapshot(src) != plan['source_snapshot']:
                    raise FilesystemError('source changed after plan')
                if op == 'mkdir':
                    dst.mkdir()
                    receipt['effects'].append('target_created')
                    if not dst.is_dir():
                        raise FilesystemError('directory readback failed')
                    readback = {'kind': 'directory'}
                else:
                    if op == 'trash':
                        trash = self._path('trash', internal=True)
                        trash.mkdir(exist_ok=True)
                        self._plain(trash)
                        # Persist restoration metadata before any payload effect.
                        self._save_new(self.state / 'trash-index' / (plan_id + '.json'),
                                       {'id': plan_id, 'original_path': plan['source'],
                                        'stored_path': plan['target'], 'sha256': plan['source_snapshot']['sha256']})
                    with dst.open('xb') as output:
                        receipt['effects'].append('target_created')
                        if op == 'write':
                            output.write(plan['content'].encode('utf-8'))
                        else:
                            with src.open('rb') as input_stream:
                                shutil.copyfileobj(input_stream, output, 65536)
                        output.flush()
                        os.fsync(output.fileno())
                    readback = self._snapshot(dst)
                    wanted = plan['content_sha256'] if op == 'write' else plan['source_snapshot']['sha256']
                    if readback['sha256'] != wanted:
                        raise FilesystemError('target readback mismatch')
                    if src and self._snapshot(src) != plan['source_snapshot']:
                        raise FilesystemError('source changed during copy')
                    if op in ('move', 'rename', 'trash', 'restore'):
                        src.unlink()
                        receipt['effects'].append('source_removed')
                        if src.exists():
                            raise FilesystemError('source removal readback failed')
                receipt.update(status='VERIFIED', readback=readback)
            except Exception as exc:
                receipt.update(status='PARTIAL' if receipt['effects'] else 'FAILED',
                               error=type(exc).__name__ + ': ' + str(exc))
            receipt['finished_at'] = time.time()
            receipt['sha256'] = digest(receipt)
            self._save_new(final, receipt)
            return receipt


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', required=True)
    commands = parser.add_subparsers(dest='command', required=True)
    listing = commands.add_parser('inventory')
    listing.add_argument('--path', default='.')
    planning = commands.add_parser('plan')
    planning.add_argument('operation', choices=sorted(OPERATIONS))
    for field in ('source', 'target', 'content', 'trash-id'):
        planning.add_argument('--' + field)
    execution = commands.add_parser('execute')
    execution.add_argument('plan_id')
    execution.add_argument('--approval-file', required=True)
    args = parser.parse_args()
    try:
        toolkit = FilesystemToolkit(args.root)
        if args.command == 'inventory':
            result = toolkit.inventory(args.path)
        elif args.command == 'plan':
            result = toolkit.plan(args.operation, source=args.source, target=args.target,
                                  content=args.content, trash_id=args.trash_id)
        else:
            result = toolkit.execute(args.plan_id, approval=json.loads(Path(args.approval_file).read_text(encoding='utf-8')))
        print(json.dumps(result, ensure_ascii=True, indent=2))
        return 0 if result.get('status', 'VERIFIED') == 'VERIFIED' else 1
    except (ValueError, OSError) as exc:
        print(json.dumps({'status': 'BLOCKED', 'error': str(exc)}))
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
