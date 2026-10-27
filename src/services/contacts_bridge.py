"""ADL composition adapter: one address book, unchanged standalone SDK."""
import hashlib
import json
import os
import sqlite3
import uuid
from pathlib import Path
from src.contacts_service.core import Contacts, ServiceError, validate_contact, now
from src.communications.service import CommunicationError
from src.storage.portable import configured_path


def contacts_root():
    return configured_path('BAGO_CONTACTS_STATE_DIR', 'contacts')


class ContactsBridge:
    def __init__(self, root=None):
        self.root = root

    def _store(self):
        return Contacts(self.root if self.root is not None else contacts_root())

    @staticmethod
    def _project(record):
        return {key: record[key] for key in ('id', 'name', 'phone')}

    def import_legacy(self, records):
        """Idempotent transaction; preserve IDs and source DB, reject collisions."""
        if not records:
            return
        try:
            store = self._store()
            with store.connect() as db:
                db.execute('CREATE TABLE IF NOT EXISTS communications_legacy_imports (id TEXT PRIMARY KEY, fingerprint TEXT NOT NULL)')
                db.execute('BEGIN IMMEDIATE')
                for old in records:
                    identity = old.get('id')
                    if not isinstance(identity, str) or not identity.startswith('contact_'):
                        raise CommunicationError('Identidad de contacto heredado no válida.', 409)
                    record = validate_contact(old)
                    fingerprint = hashlib.sha256(json.dumps(record,sort_keys=True).encode()).hexdigest()
                    imported = db.execute('SELECT fingerprint FROM communications_legacy_imports WHERE id=?',(identity,)).fetchone()
                    if imported is not None:
                        if imported['fingerprint'] != fingerprint:
                            raise CommunicationError('El origen heredado cambió tras conciliarse; revisión necesaria.',409)
                        continue
                    existing = db.execute('SELECT * FROM contacts WHERE id=?', (identity,)).fetchone()
                    if existing is not None:
                        if any(existing[key] != record[key] for key in ('name','phone')):
                            raise CommunicationError('Conflicto de identidad en agenda heredada; revisión necesaria.',409)
                        db.execute('INSERT INTO communications_legacy_imports VALUES (?,?)',(identity,fingerprint))
                        continue
                    if store.duplicates(db, record):
                        raise CommunicationError('Contacto heredado duplicado con otro ID; conciliación explícita necesaria.',409)
                    record.update(id=identity,source='communications_legacy',source_id=identity,
                                  revision=uuid.uuid4().hex,created_at=now(),updated_at=now())
                    db.execute('INSERT INTO contacts VALUES (:id,:name,:phone,:email,:source,:source_id,:revision,:created_at,:updated_at)',record)
                    db.execute('INSERT INTO communications_legacy_imports VALUES (?,?)',(identity,fingerprint))
        except ServiceError as exc:
            raise CommunicationError('Contacto heredado inválido; agenda original conservada.',409) from exc
        except (OSError, sqlite3.Error) as exc:
            raise CommunicationError('No se pudo conciliar la agenda; datos originales conservados.',503) from exc

    def list(self):
        try:
            return [self._project(record) for record in self._store().list()['contacts']]
        except (ServiceError, OSError, sqlite3.Error) as exc:
            raise CommunicationError('No se pudo leer la agenda compartida.', 503) from exc

    def add(self, name, phone):
        try:
            return self._project(self._store().add({'name':name, 'phone':phone}))
        except ServiceError as exc:
            raise CommunicationError(str(exc), exc.status) from exc
        except (OSError, sqlite3.Error) as exc:
            raise CommunicationError('No se pudo conservar el contacto.', 503) from exc


# No files, credentials or state are accessed during module import.
shared_contacts = ContactsBridge()
