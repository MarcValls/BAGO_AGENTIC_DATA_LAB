"""Prototype for recognizable explicit credentials, not comprehensive DLP.

Pattern families come from the evaluation credential detector, excluding its
bare hexadecimal and opaque entropy heuristics to preserve content hashes.
This module only identifies recognizable patterns; it is not comprehensive DLP. Isolated opaque Bearer tokens without Authorization context are not recognized.
"""
from __future__ import annotations
import json
import re

_LABEL = re.compile(r"""(?:api[_ -]?key|access[_ -]?token|refresh[_ -]?token|id[_ -]?token|client[_ -]?secret|password|credential)["']?\s*[:=]\s*(?:"(?:\\.|[^"\\])+(?:"|\Z)|'(?:\\.|[^'\\])+(?:'|\Z)|(?!(?:none|null|false|true)(?=$|[\s,}\]]))(?![{\["'])\S+)""", re.IGNORECASE)
_AUTH_HEADER = re.compile(r"""\bauthorization["']?\s*[:=]\s*["']?(?:basic|bearer)\s+[^\s"',}]+""", re.IGNORECASE)
_PEM = re.compile(r'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----[\s\S]*?(?:-----END (?:RSA |EC |OPENSSH )?PRIVATE KEY-----|\Z)', re.IGNORECASE)
_TOKEN = re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----|\b(?:github_pat_|gh[pousr]_?|xox[baprs]-|AIza|ya29\.|AKIA|ASIA|sk-|rk-)[A-Za-z0-9_./+=-]{12,}\b|\beyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\b", re.IGNORECASE)

def contains_recognizable_credential(value: str) -> bool:
    return bool(_LABEL.search(value) or _AUTH_HEADER.search(value) or _PEM.search(value) or _TOKEN.search(value))

def redact_recognizable_credentials(value: str) -> str:
    return _TOKEN.sub('[REDACTED]', _LABEL.sub('[REDACTED]', _AUTH_HEADER.sub('[REDACTED]', _PEM.sub('[REDACTED]', value))))



_SENSITIVE_KEY = re.compile(r"^(?:(?:x-)?api[_ -]?key|access[_ -]?token|refresh[_ -]?token|id[_ -]?token|client[_ -]?secret|password|credential)$", re.IGNORECASE)

_AUTHORIZATION_SCHEME = re.compile(r"^\s*(?:basic|bearer)\s+\S+\s*$", re.IGNORECASE)


class _JsonObject(list):
    """JSON object as ordered pairs, retaining repeated names."""


def _decode_json_container(value):
    try:
        decoded = json.loads(value, object_pairs_hook=_JsonObject)
    except (ValueError, RecursionError):
        return None
    return decoded if isinstance(decoded, (dict, list)) else None


def _contains_json_node(node):
    if isinstance(node, _JsonObject):
        return any(_sensitive_key(key, value) or contains_credential_tree(key)
                   or _contains_json_node(value) for key, value in node)
    if isinstance(node, list):
        return any(_contains_json_node(value) for value in node)
    return contains_credential_tree(node)


def _redact_json_node(node, sensitive_key=None):
    if isinstance(node, _JsonObject):
        reserved = {key for key, _ in node if redact_credential_tree(key) == key}
        used = set(reserved)
        pairs = _JsonObject()
        for key, value in node:
            clean_key = redact_credential_tree(key)
            if clean_key != key:
                base = clean_key
                suffix = 2
                while clean_key in used:
                    clean_key = f"{base} [{suffix}]"
                    suffix += 1
                used.add(clean_key)
            pairs.append((clean_key, _redact_json_node(value, key)))
        return pairs
    if isinstance(node, list):
        return [_redact_json_node(value, sensitive_key) for value in node]
    if sensitive_key is not None and _sensitive_key(sensitive_key, node):
        return "[REDACTED]"
    return redact_credential_tree(node)


def _dump_json_node(node):
    if isinstance(node, _JsonObject):
        return "{" + ", ".join(json.dumps(key, ensure_ascii=False) + ": " + _dump_json_node(value)
                               for key, value in node) + "}"
    if isinstance(node, list):
        return "[" + ", ".join(_dump_json_node(value) for value in node) + "]"
    return json.dumps(node, ensure_ascii=False)


def _sensitive_key(key, value):
    if isinstance(value, _JsonObject):
        return False
    if isinstance(value, (list, tuple)):
        return any(_sensitive_key(key, item) for item in value)
    if not isinstance(key, str) or not isinstance(value, str) or not value.strip():
        return False
    if key.casefold() == "authorization":
        return bool(_AUTHORIZATION_SCHEME.fullmatch(value))
    return bool(_SENSITIVE_KEY.fullmatch(key))


def _redact_sensitive_value(key, value):
    if isinstance(value, list):
        return [_redact_sensitive_value(key, item) for item in value]
    if isinstance(value, tuple):
        return tuple(_redact_sensitive_value(key, item) for item in value)
    return "[REDACTED]" if _sensitive_key(key, value) else redact_credential_tree(value)

def contains_credential_tree(value):
    if isinstance(value,str):
        decoded = _decode_json_container(value)
        if decoded is not None:
            return _contains_json_node(decoded)
        return contains_recognizable_credential(value)
    if isinstance(value,dict):
        return any((_sensitive_key(k, v)) or contains_credential_tree(k) or contains_credential_tree(v) for k,v in value.items())
    if isinstance(value,(list,tuple)):
        return any(contains_credential_tree(v) for v in value)
    return False


def redact_credential_tree(value):
    if isinstance(value,str):
        decoded = _decode_json_container(value)
        if decoded is not None:
            if _contains_json_node(decoded):
                return _dump_json_node(_redact_json_node(decoded))
            return value
        return redact_recognizable_credentials(value)
    if isinstance(value,dict):
        result = {}
        # Reserve unchanged keys first: a generated redacted key must not overwrite
        # a genuine key which occurs later in the input mapping.
        reserved = {key for key in value if redact_credential_tree(key) == key}
        for key, item in value.items():
            clean_key = redact_credential_tree(key)
            if clean_key != key and (clean_key in result or clean_key in reserved):
                suffix = 2
                candidate = f"{clean_key} [{suffix}]"
                while candidate in result or candidate in reserved:
                    suffix += 1
                    candidate = f"{clean_key} [{suffix}]"
                clean_key = candidate
            result[clean_key] = _redact_sensitive_value(key, item)
        return result
    if isinstance(value,list):
        return [redact_credential_tree(item) for item in value]
    if isinstance(value,tuple):
        return tuple(redact_credential_tree(item) for item in value)
    return value
