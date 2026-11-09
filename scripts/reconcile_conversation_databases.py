"""Build a separate candidate library from two quiescent ADL conversation databases.

Neither input is modified. This does not activate the candidate or recover agent
profiles. Stop all writers first; review the output before any replacement.
"""
from __future__ import annotations

import argparse
from contextlib import ExitStack, closing
import json
import os
from pathlib import Path
import sqlite3
import stat
import tempfile

CONVERSATION_COLUMNS = ('id', 'project_id', 'owner_kind', 'owner_id', 'title', 'status',
                        'created_at', 'updated_at', 'revision')
MESSAGE_COLUMNS = ('id', 'conversation_id', 'sequence', 'role', 'content', 'created_at',
                   'status', 'references_json')


class ReconciliationError(ValueError):
    pass


def _reject_reparse(path: Path) -> None:
    absolute = Path(os.path.abspath(path))
    for part in (absolute, *absolute.parents):
        if part.exists():
            info = part.lstat()
            if stat.S_ISLNK(info.st_mode) or getattr(info, 'st_file_attributes', 0) & 0x400:
                raise ReconciliationError('reparse_path_denied')


def _connect_readonly(path: Path) -> sqlite3.Connection:
    _reject_reparse(path)
    if not path.is_file():
        raise ReconciliationError('input_must_be_a_regular_file')
    _no_sidecars(path)
    db = sqlite3.connect(path.resolve().as_uri() + '?mode=ro', uri=True)
    db.row_factory = sqlite3.Row
    return db


def _no_sidecars(path: Path) -> None:
    if any(Path(str(path) + suffix).exists() for suffix in ('-wal', '-shm', '-journal')):
        raise ReconciliationError('database_not_quiescent')


def _reserve_writer_lock(path: Path) -> sqlite3.Connection:
    """Prevent SQLite writers; execute no DML or DDL on the source connection."""
    _reject_reparse(path)
    _no_sidecars(path)
    connection = None
    try:
        connection = sqlite3.connect(path.resolve().as_uri() + '?mode=rw', uri=True, timeout=0)
        connection.execute('BEGIN IMMEDIATE')
        _no_sidecars(path)
        return connection
    except (sqlite3.Error, ReconciliationError) as error:
        if connection is not None:
            connection.close()
        raise ReconciliationError('source_lock_unavailable') from error


def _schema(db: sqlite3.Connection) -> bool:
    if db.execute("SELECT 1 FROM sqlite_master WHERE type IN ('trigger', 'view') LIMIT 1").fetchone():
        raise ReconciliationError('unsupported_schema_objects')
    tables = {r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")}
    if tables != {'conversations', 'messages'}:
        raise ReconciliationError('unsupported_tables')
    conv_info = db.execute('PRAGMA table_info(conversations)').fetchall()
    msg_info = db.execute('PRAGMA table_info(messages)').fetchall()
    conv = tuple(r[1] for r in conv_info)
    msgs = tuple(r[1] for r in msg_info)
    if conv not in (CONVERSATION_COLUMNS, CONVERSATION_COLUMNS + ('labels_json',)) or msgs != MESSAGE_COLUMNS:
        raise ReconciliationError('unsupported_schema')
    if [(r[1], r[5]) for r in conv_info if r[5]] != [('id', 1)] or [(r[1], r[5]) for r in msg_info if r[5]] != [('id', 1)]:
        raise ReconciliationError('missing_primary_key')
    unique_indexes = []
    for index in db.execute('PRAGMA index_list(messages)').fetchall():
        if index[2] and not index[4]:  # Unique and not partial.
            quoted = '"' + index[1].replace('"', '""') + '"'
            unique_indexes.append(tuple(row[2] for row in db.execute(f'PRAGMA index_info({quoted})')))
    if ('conversation_id', 'sequence') not in unique_indexes:
        raise ReconciliationError('missing_message_sequence_constraint')
    foreign_keys = db.execute('PRAGMA foreign_key_list(messages)').fetchall()
    if not any(row[2] == 'conversations' and row[3] == 'conversation_id' and row[4] == 'id' for row in foreign_keys):
        raise ReconciliationError('missing_message_foreign_key')
    if db.execute('SELECT 1 FROM messages m LEFT JOIN conversations c ON m.conversation_id=c.id WHERE c.id IS NULL LIMIT 1').fetchone():
        raise ReconciliationError('orphaned_message')
    if db.execute('PRAGMA integrity_check').fetchone()[0] != 'ok' or db.execute('PRAGMA foreign_key_check').fetchone():
        raise ReconciliationError('invalid_database')
    if db.execute("SELECT 1 FROM conversations WHERE owner_kind IS NULL OR owner_kind NOT IN ('assistant','agent') OR status IS NULL OR status NOT IN ('active','archived','deleted') OR project_id IS NULL OR project_id='' LIMIT 1").fetchone():
        raise ReconciliationError('invalid_conversation_values')
    if db.execute("SELECT 1 FROM messages WHERE role IS NULL OR role NOT IN ('user','assistant') LIMIT 1").fetchone():
        raise ReconciliationError('invalid_message_values')
    def invalid_constant(value):
        raise ValueError(f'invalid JSON constant: {value}')
    try:
        if len(conv) > len(CONVERSATION_COLUMNS):
            for row in db.execute('SELECT labels_json FROM conversations'):
                labels = json.loads(row[0] or '[]', parse_constant=invalid_constant)
                if not isinstance(labels, list) or any(not isinstance(label, str) for label in labels):
                    raise ValueError('labels must be a list of strings')
        for row in db.execute('SELECT references_json FROM messages'):
            if not isinstance(json.loads(row[0], parse_constant=invalid_constant), dict):
                raise ValueError('references must be an object')
    except (TypeError, ValueError) as error:
        raise ReconciliationError('invalid_json_payload') from error
    return len(conv) > len(CONVERSATION_COLUMNS)


def _promote_without_overwrite(staged: Path, output: Path) -> bool:
    try:
        os.link(staged, output)
    except OSError as error:
        if os.name != 'nt' or getattr(error, 'winerror', None) not in (1, 50):
            raise
        # Windows rename refuses to replace an existing destination, including
        # on exFAT where hard links are unavailable.
        os.rename(staged, output)
        return True
    else:
        try:
            staged.unlink()
            return True
        except OSError:
            # The output already exists at this point. Report cleanup failure
            # without misreporting a completed promotion as a failed operation.
            return False


def reconcile(base: Path, incoming: Path, output: Path, *, allow_shared_projects: frozenset[str] = frozenset()) -> dict:
    base, incoming, output = Path(base), Path(incoming), Path(output)
    _reject_reparse(output)
    if base.resolve() == incoming.resolve() or output.resolve() in (base.resolve(), incoming.resolve()):
        raise ReconciliationError('paths_must_be_distinct')
    source_sidecars = {Path(str(path.resolve()) + suffix) for path in (base, incoming)
                       for suffix in ('-wal', '-shm', '-journal')}
    if output.resolve() in source_sidecars:
        raise ReconciliationError('output_conflicts_with_source_sidecar')
    if base.exists() and incoming.exists() and os.path.samefile(base, incoming):
        raise ReconciliationError('paths_must_be_distinct')
    if output.exists() or output.is_symlink():
        raise ReconciliationError('output_already_exists')
    if not output.parent.is_dir():
        raise ReconciliationError('output_parent_missing')
    with ExitStack() as stack:
        # Deterministic acquisition order and zero timeout avoid lock deadlocks.
        for path in sorted((base, incoming), key=lambda item: os.path.normcase(str(item.resolve()))):
            stack.enter_context(closing(_reserve_writer_lock(path)))
        first = stack.enter_context(closing(_connect_readonly(base)))
        second = stack.enter_context(closing(_connect_readonly(incoming)))
        first.execute('BEGIN')
        second.execute('BEGIN')
        first_labels, second_labels = _schema(first), _schema(second)
        if any(not isinstance(value, str) or not value for value in allow_shared_projects):
            raise ReconciliationError('invalid_shared_project_authorization')
        first_projects = {row[0] for row in first.execute('SELECT DISTINCT project_id FROM conversations')}
        second_projects = {row[0] for row in second.execute('SELECT DISTINCT project_id FROM conversations')}
        shared_projects = first_projects & second_projects
        if shared_projects - allow_shared_projects:
            raise ReconciliationError('shared_project_identity_requires_confirmation')
        if allow_shared_projects - shared_projects:
            raise ReconciliationError('unknown_shared_project_authorization')
        # A failed candidate stays under a unique staging directory and is never
        # exposed at the requested final name.
        stage = Path(tempfile.mkdtemp(prefix='.bago-reconcile-', dir=output.parent))
        staged = stage / 'candidate.sqlite3'
        try:
            with closing(sqlite3.connect(staged)) as target:
                first.backup(target)
                target.execute('PRAGMA foreign_keys=ON')
                target.execute('BEGIN IMMEDIATE')
                if not first_labels:
                    target.execute("ALTER TABLE conversations ADD COLUMN labels_json TEXT NOT NULL DEFAULT '[]'")
                columns = ','.join(CONVERSATION_COLUMNS)
                incoming_query = f'SELECT {columns}' + (',labels_json' if second_labels else ",'[]' AS labels_json") + ' FROM conversations'
                conv_count = 0
                for row in second.execute(incoming_query):
                    target.execute(f'INSERT INTO conversations ({columns},labels_json) VALUES (?,?,?,?,?,?,?,?,?,?)', tuple(row))
                    conv_count += 1
                msg_count = 0
                for row in second.execute('SELECT ' + ','.join(MESSAGE_COLUMNS) + ' FROM messages'):
                    target.execute('INSERT INTO messages (' + ','.join(MESSAGE_COLUMNS) + ') VALUES (?,?,?,?,?,?,?,?)', tuple(row))
                    msg_count += 1
                if target.execute('PRAGMA foreign_key_check').fetchone() or target.execute('PRAGMA integrity_check').fetchone()[0] != 'ok':
                    raise ReconciliationError('candidate_integrity_failed')
                _no_sidecars(base)
                _no_sidecars(incoming)
                target.commit()
            _reject_reparse(output)
            staging_clean = _promote_without_overwrite(staged, output)
            if staging_clean:
                try:
                    stage.rmdir()
                except OSError:
                    staging_clean = False
        except (OSError, sqlite3.Error, ReconciliationError) as error:
            # Preserve staging for diagnosis, but never claim it is usable.
            raise ReconciliationError(f'candidate_failed_or_id_conflict:stage={stage.name}') from error
    return {'status': 'prepared', 'incoming_conversations': conv_count, 'incoming_messages': msg_count,
            'output': os.fspath(output), 'activated': False,
            'shared_projects_explicitly_approved': len(shared_projects),
            'shared_project_ids': sorted(shared_projects),
            'staging_retained': None if staging_clean else os.fspath(stage)}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('base', type=Path)
    parser.add_argument('incoming', type=Path)
    parser.add_argument('output', type=Path)
    parser.add_argument('--allow-shared-project', action='append', default=[], metavar='PROJECT_ID',
                        help='Confirm that this exact project ID refers to the same project in both inputs; repeat for each shared project.')
    args = parser.parse_args()
    try:
        print(json.dumps(reconcile(args.base, args.incoming, args.output,
                                   allow_shared_projects=frozenset(args.allow_shared_project))))
    except ReconciliationError as error:
        parser.exit(1, f'reconciliation failed: {error}\n')


if __name__ == '__main__':
    main()
