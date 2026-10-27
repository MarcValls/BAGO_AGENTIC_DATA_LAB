"""Resolve ADL-owned persistent paths beneath the application copy.

Resolution is side-effect-free: importing this module or asking for a path
never creates directories. A deployment may set ``BAGO_DATA_ROOT`` before
startup to place all ADL-owned state somewhere else explicitly.
"""
from __future__ import annotations

import os
import json
import re
import stat
from pathlib import Path


class StoragePathError(ValueError):
    """A requested application data path is invalid or crosses a link."""


_RESERVED = re.compile(r"(?i)^(CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9])(?:\..*)?$")
_ALIAS_FILE = "storage-aliases.json"
_MAX_ALIAS_BYTES = 64 * 1024
_MAX_ALIASES = 100


def _reject_reparse(path: Path) -> None:
    """Reject existing symlink/junction components before resolving them."""
    absolute = Path(os.path.abspath(os.fspath(path)))
    for component in reversed((absolute, *absolute.parents)):
        try:
            info = component.lstat()
        except FileNotFoundError:
            continue
        except OSError as error:
            raise StoragePathError("storage_path_inspection_failed") from error
        attributes = getattr(info, "st_file_attributes", 0)
        if stat.S_ISLNK(info.st_mode) or attributes & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400):
            raise StoragePathError("storage_reparse_point_denied")


def application_root() -> Path:
    """Return the loaded source/application root without creating anything."""
    override = os.environ.get("BAGO_APP_ROOT")
    raw = Path(override).expanduser() if override else Path(__file__).resolve().parents[2]
    if not raw.is_absolute():
        raise StoragePathError("application_root_must_be_absolute")
    _reject_reparse(raw)
    try:
        root = raw.resolve(strict=True)
    except (OSError, RuntimeError) as error:
        raise StoragePathError("application_root_unavailable") from error
    if not root.is_dir():
        raise StoragePathError("application_root_unavailable")
    return root


def data_root() -> Path:
    """Return the portable data root, defaulting to ``<app>/.bago/data``."""
    override = os.environ.get("BAGO_DATA_ROOT")
    if override:
        raw = Path(override).expanduser()
        if not raw.is_absolute():
            raise StoragePathError("data_root_must_be_absolute")
    else:
        raw = application_root() / ".bago" / "data"
    _reject_reparse(raw)
    try:
        resolved = raw.resolve(strict=False)
    except (OSError, RuntimeError) as error:
        raise StoragePathError("data_root_unavailable") from error
    return resolved


def _validate_component(value: str) -> str:
    if (not isinstance(value, str) or not value or value in {".", ".."}
            or "/" in value or "\\" in value or ":" in value or "\x00" in value
            or any(ord(char) < 32 or char in '<>"|?*' for char in value)
            or value != value.rstrip(" .") or _RESERVED.fullmatch(value)):
        raise StoragePathError("unsafe_data_path")
    return value


def data_path(*parts: str) -> Path:
    """Return a safe path below the effective data root without making it."""
    if not parts:
        raise StoragePathError("data_path_component_required")
    root = data_root()
    target = root.joinpath(*(_validate_component(part) for part in parts))
    _reject_reparse(target)
    try:
        resolved = target.resolve(strict=False)
    except (OSError, RuntimeError) as error:
        raise StoragePathError("data_path_unavailable") from error
    if resolved != root and root not in resolved.parents:
        raise StoragePathError("data_path_escape")
    return target


def configured_path(environment_name: str, *default_parts: str) -> Path:
    """Use an explicit legacy/test override, otherwise the portable path.

    Explicit per-store overrides remain supported for tests and deployments.
    ``/api/runtime/storage`` reports any override that resolves outside the
    common root, so an external override cannot be mistaken for a portable run.
    """
    override = os.environ.get(environment_name)
    if override:
        raw = Path(override).expanduser()
        if not raw.is_absolute():
            raw = Path.cwd() / raw
        _reject_reparse(raw)
        return raw.resolve(strict=False)
    return data_path(*default_parts)


def _alias_records() -> list[dict[str, str]]:
    path = data_path(_ALIAS_FILE)
    _reject_reparse(path)
    try:
        if path.stat().st_size > _MAX_ALIAS_BYTES:
            raise StoragePathError("storage_aliases_invalid")
        raw = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return []
    except StoragePathError:
        raise
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise StoragePathError("storage_aliases_invalid") from error
    if (not isinstance(raw, dict) or set(raw) != {"version", "aliases"} or raw.get("version") != 1
            or not isinstance(raw.get("aliases"), list) or len(raw["aliases"]) > _MAX_ALIASES):
        raise StoragePathError("storage_aliases_invalid")
    result: list[dict[str, str]] = []
    for record in raw["aliases"]:
        if not isinstance(record, dict) or set(record) != {"source_prefix", "target_prefix"}:
            raise StoragePathError("storage_aliases_invalid")
        source_value, target_value = record["source_prefix"], record["target_prefix"]
        if not isinstance(source_value, str) or not source_value or not isinstance(target_value, str) or not target_value:
            raise StoragePathError("storage_aliases_invalid")
        source = Path(source_value).expanduser()
        if not source.is_absolute():
            raise StoragePathError("storage_aliases_invalid")
        _reject_reparse(source)
        try:
            resolved_source = source.resolve(strict=False)
        except (OSError, RuntimeError) as error:
            raise StoragePathError("storage_aliases_invalid") from error
        target_parts = tuple(target_value.replace("\\", "/").split("/"))
        if (target_value.startswith(("/", "\\")) or not target_parts
                or any(not part for part in target_parts)):
            raise StoragePathError("storage_aliases_invalid")
        safe_target = data_path(*target_parts)
        root = data_root().resolve(strict=False)
        resolved_target = safe_target.resolve(strict=False)
        if resolved_target != root and root not in resolved_target.parents:
            raise StoragePathError("storage_aliases_invalid")
        result.append({"source_prefix": str(resolved_source), "target_prefix": "/".join(target_parts)})
    return result


def relocate_owned_path(path: str | Path) -> Path:
    """Apply only an explicit, validated alias into the application data root.

    This is used for ADL-owned development state whose historical profile may
    still name an older host path. It never rewrites the profile or redirects a
    project/workspace root.
    """
    source = Path(path).expanduser()
    if not source.is_absolute():
        source = Path.cwd() / source
    _reject_reparse(source)
    try:
        resolved_source = source.resolve(strict=False)
    except (OSError, RuntimeError) as error:
        raise StoragePathError("owned_path_unavailable") from error
    candidates = []
    for record in _alias_records():
        prefix = Path(record["source_prefix"])
        try:
            relative = resolved_source.relative_to(prefix)
        except ValueError:
            continue
        candidates.append((len(prefix.parts), record, relative))
    if not candidates:
        return resolved_source
    _, record, relative = max(candidates, key=lambda item: item[0])
    target_parts = tuple(record["target_prefix"].split("/")) + relative.parts
    return data_path(*target_parts)


def storage_status() -> dict[str, object]:
    """Describe ADL-owned storage roots and detect per-store escapes.

    The response contains paths and override variable names only; it never
    opens databases, reads stored values, or returns environment contents.
    """
    app = application_root()
    root = data_root()
    paths = {
        "conversations": configured_path("BAGO_CONVERSATION_DB_PATH", "conversations", "library.sqlite3"),
        "capabilities": configured_path("BAGO_CAPABILITY_DB_PATH", "capabilities"),
        "evaluations": configured_path("BAGO_AGENT_EVALUATION_DB_PATH", "evaluations"),
        "contacts": configured_path("BAGO_CONTACTS_STATE_DIR", "contacts"),
        "communications": configured_path("BAGO_COMMUNICATIONS_STATE_DIR", "communications"),
        "tasks": configured_path("BAGO_TASK_HISTORY_PATH", "tasks"),
        "providers": configured_path("BAGO_PROVIDER_REGISTRY_PATH", "providers", "provider-registry.json"),
        "ollama_config": configured_path("BAGO_OLLAMA_CONFIG_PATH", "providers", "ollama.json"),
        "model_policy": configured_path("BAGO_MODEL_POLICY_PATH", "providers", "model-policy.json"),
        "active_provider": data_path("providers", "active-provider.json"),
        "agents": data_path("agents", "created"),
        "workspace_config": data_path("config"),
        "gex_runtime": configured_path("BAGO_GEX_STATE_DIR", "gex", "runtime"),
        "gex_identity": configured_path("BAGO_GEX_IDENTITY_DB_PATH", "gex", "identity.sqlite3"),
        "knowledge": configured_path("ADL_KNOWLEDGE_DB", "knowledge", "local-knowledge.sqlite3"),
        "knowledge_traces": configured_path("ADL_KNOWLEDGE_TRACE_DIR", "traces", "grounded-rag"),
        "ontology": configured_path("ADL_ONTOLOGY_DB", "knowledge", "ontology.sqlite3"),
        "ontology_traces": configured_path("ADL_ONTOLOGY_TRACE_DIR", "traces", "ontology"),
        "whatsapp": configured_path("BAGO_WHATSAPP_STATE_DIR", "whatsapp"),
        "web_research": configured_path("BAGO_WEB_RESEARCH_STATE_DIR", "web-research"),
        "document_exports": configured_path("BAGO_DOCUMENT_OUTPUT_ROOT", "document-exports"),
        "connections": data_path("connections", "registry.json"),
        "etl_metadata": configured_path("ADL_ETL_METADATA_DB", "etl", "metadata.sqlite3"),
        "jobs": data_path("jobs", "history"),
        "traces": data_path("traces"),
        "storage_aliases": data_path(_ALIAS_FILE),
    }
    override_names = (
        "BAGO_CONVERSATION_DB_PATH", "BAGO_CAPABILITY_DB_PATH", "BAGO_AGENT_EVALUATION_DB_PATH",
        "BAGO_TASK_HISTORY_PATH", "BAGO_CONTACTS_STATE_DIR", "BAGO_COMMUNICATIONS_STATE_DIR",
        "BAGO_PROVIDER_REGISTRY_PATH", "BAGO_MODEL_POLICY_PATH", "BAGO_GEX_STATE_DIR",
        "BAGO_GEX_IDENTITY_DB_PATH", "ADL_KNOWLEDGE_DB", "ADL_ONTOLOGY_DB",
        "BAGO_WHATSAPP_STATE_DIR", "BAGO_WEB_RESEARCH_STATE_DIR", "BAGO_DOCUMENT_OUTPUT_ROOT",
        "ADL_KNOWLEDGE_TRACE_DIR", "ADL_ONTOLOGY_TRACE_DIR", "BAGO_OLLAMA_CONFIG_PATH",
        "ADL_ETL_METADATA_DB",
    )
    external = []
    for name in override_names:
        value = os.environ.get(name)
        if not value:
            continue
        try:
            path = Path(value).expanduser()
            if not path.is_absolute():
                path = Path.cwd() / path
            resolved = path.resolve(strict=False)
            if resolved != root and root not in resolved.parents:
                external.append(name)
        except (OSError, RuntimeError, ValueError):
            external.append(name)
    local_source_root = Path(__file__).resolve().parents[2]
    return {
        "application_root": str(app),
        "effective_source_root": str(local_source_root),
        "application_root_matches_source": app == local_source_root,
        "data_root": str(root),
        "mode": "external_data_root" if os.environ.get("BAGO_DATA_ROOT") else "portable",
        "data_root_exists": root.exists(),
        "resolver_creates_directories": False,
        "external_overrides": sorted(external),
        "effective_paths": {key: str(value) for key, value in paths.items()},
        "host_bound_profile_configured": bool(os.environ.get("BAGO_DEVELOPMENT_PROFILE")),
        "storage_alias_configuration_present": data_path(_ALIAS_FILE).is_file(),
    }
