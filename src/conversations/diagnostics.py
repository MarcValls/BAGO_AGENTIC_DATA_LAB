"""Opt-in, bounded SQLite path observations. Never logs SQL or message payloads.

A path stat is not a SQLite descriptor identity or proof of the replacing actor.
Keep journals outside any directory suspected of being restored/synchronized.
"""
from __future__ import annotations

from collections import OrderedDict
import hashlib
import hmac
import json
import logging
import os
from pathlib import Path
import threading
import time
import uuid

_LOG = logging.getLogger(__name__)


class ConversationDiagnostics:
    def __init__(self, directory: Path | str, *, max_events: int = 20000):
        if max_events < 2:
            raise ValueError("max_events must be at least 2")
        self.session = uuid.uuid4().hex
        self._key = os.urandom(32)
        self._lock = threading.Lock()
        self._last = OrderedDict()
        self._confirmed = OrderedDict()
        self._events = 0
        self._max_events = max_events
        directory = Path(directory)
        directory.mkdir(parents=True, exist_ok=True)
        self.path = directory / f"sqlite-{os.getpid()}-{self.session}.jsonl"
        self._fd = os.open(self.path, os.O_CREAT | os.O_EXCL | os.O_WRONLY | os.O_APPEND, 0o600)

    def close(self):
        with self._lock:
            if self._fd is not None:
                os.close(self._fd)
                self._fd = None

    def _token(self, value):
        return hmac.new(self._key, str(value).encode(), hashlib.sha256).hexdigest()[:24]

    @staticmethod
    def _stat(path):
        try:
            st = path.stat()
            return {key: getattr(st, key) for key in
                    ('st_dev', 'st_ino', 'st_size', 'st_mtime_ns', 'st_ctime_ns', 'st_nlink')}
        except FileNotFoundError:
            return {'missing': True}
        except OSError:
            return {'unavailable': True}

    def record(self, database_path, phase, *, conversation_id=None, revision=None,
               message_count=None, sequence=None):
        """Metadata allowlist only; errors never change persistence behavior."""
        with self._lock:
            if self._fd is None or self._events >= self._max_events:
                return
            try:
                db = Path(database_path)
                files = {suffix or 'main': self._stat(Path(str(db) + suffix))
                         for suffix in ('', '-journal', '-wal', '-shm')}
                main = files['main']
                database_token = self._token(db.absolute())
                previous = self._last.get(database_token)
                flags = []
                if previous and all('st_ino' in s for s in (previous, main)):
                    if (previous['st_dev'], previous['st_ino']) != (main['st_dev'], main['st_ino']):
                        flags.append('path_identity_changed')
                    if main['st_mtime_ns'] < previous['st_mtime_ns']:
                        flags.append('mtime_regressed')
                elif previous and main.get('missing') and not previous.get('missing'):
                    flags.append('path_disappeared')
                token = self._token(database_token + ":" + conversation_id) if conversation_id is not None else None
                high = self._confirmed.get(token)
                if high is not None and revision is not None and revision < high:
                    flags.append('below_confirmed_revision')
                if high is not None and phase == 'get_missing':
                    flags.append('confirmed_conversation_missing')
                if phase == 'append_committed' and revision is not None:
                    self._confirmed[token] = max(high or 0, revision)
                    self._confirmed.move_to_end(token)
                    if len(self._confirmed) > 1024:
                        self._confirmed.popitem(last=False)
                event = dict(schema='adl.sqlite.diagnostic.v1', session=self.session,
                             pid=os.getpid(), thread=threading.get_native_id(),
                             time_ns=time.time_ns(), monotonic_ns=time.monotonic_ns(),
                             event_number=self._events, database=database_token,
                             phase=phase, conversation=token, revision=revision,
                             message_count=message_count, sequence=sequence,
                             confirmed_revision=high, files=files, flags=flags)
                if self._events == self._max_events - 1:
                    event['diagnostic_limit_reached'] = True
                data = (json.dumps(event, separators=(',', ':')) + '\n').encode()
                # Handle short writes; serialization is under the same lock.
                while data:
                    written = os.write(self._fd, data)
                    if written <= 0:
                        raise OSError('diagnostic write failed')
                    data = data[written:]
                self._events += 1
                self._last[database_token] = main
                self._last.move_to_end(database_token)
                if len(self._last) > 64:
                    self._last.popitem(last=False)
            except Exception:
                _LOG.warning('SQLite diagnostics unavailable; persistence operation unchanged')
                if self._fd is not None:
                    os.close(self._fd)
                    self._fd = None
