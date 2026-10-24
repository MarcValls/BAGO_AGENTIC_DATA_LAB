"""Bounded extractions/adaptations from MarcValls/BAGO (MIT).

Provenance and exact source bytes: REUSE_MAP.json. Full license:
THIRD_PARTY_LICENSE_BAGO.txt. No legacy runtime imports.
"""
from pathlib import Path
import os
import re
import tempfile

# github_repository_admin.py NAME_RE / validate_name / normalize_visibility.
NAME_RE = re.compile(r"^[A-Za-z0-9._-]{1,100}$")


def validate_repository_name(name):
    if not isinstance(name, str) or not NAME_RE.fullmatch(name):
        raise ValueError("name must be 1-100 characters using letters, digits, '.', '_' or '-'")
    return name


def normalize_visibility(value):
    visibility = (value or "private").lower()
    if visibility not in {"private", "public"}:
        raise ValueError("visibility must be 'private' or 'public'")
    return visibility


# commit_readiness.py MERGE_CONFLICT_RE, unchanged.
MERGE_CONFLICT_RE = re.compile(r'^(<{7}|={7}|>{7})( |$)', re.MULTILINE)


def atomic_write(path: Path, payload: bytes):
    """Adapt filesystem_effects.write_file_effect atomic block + readback.

    Removed manager/gateway/observability dependencies. Caller supplies an
    already validated target; fsync, replace and readback remain executable.
    """
    descriptor, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.workspace-", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(descriptor, "wb") as temporary:
            temporary.write(payload)
            temporary.flush()
            os.fsync(temporary.fileno())
        os.replace(temporary_name, path)
        if os.name != "nt":
            directory_fd = os.open(path.parent, os.O_RDONLY)
            try:
                os.fsync(directory_fd)
            finally:
                os.close(directory_fd)
        if path.read_bytes() != payload:
            raise OSError("Readback does not match authorized bytes")
    finally:
        try:
            os.unlink(temporary_name)
        except FileNotFoundError:
            pass
