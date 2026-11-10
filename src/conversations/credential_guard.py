"""Prototype for recognizable explicit credentials, not comprehensive DLP.

Pattern families come from the evaluation credential detector, excluding its
bare hexadecimal and opaque entropy heuristics to preserve content hashes.
This module only identifies recognizable patterns; it is not comprehensive DLP. Isolated opaque Bearer tokens without Authorization context are not recognized.
"""
from __future__ import annotations
import ast
import io
import json
import tokenize
import re

_LABEL = re.compile(r"""(?:api[_ -]?key|access[_ -]?token|refresh[_ -]?token|id[_ -]?token|client[_ -]?secret|password|credential)["']?\s*[:=]\s*(?:"(?:\\.|[^"\\])+(?:"|\Z)|'(?:\\.|[^'\\])+(?:'|\Z)|(?!(?:none|null|false|true)(?=$|[\s,}\]]))(?![{\["'])\S+)""", re.IGNORECASE)
_AUTH_HEADER = re.compile(r"""\bauthorization["']?\s*[:=]\s*["']?(?:basic|bearer)\s+[^\s"',}]+""", re.IGNORECASE)
_PEM = re.compile(r'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----[\s\S]*?(?:-----END (?:RSA |EC |OPENSSH )?PRIVATE KEY-----|\Z)', re.IGNORECASE)
_TOKEN = re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----|\b(?:github_pat_|gh[pousr]_?|xox[baprs]-|AIza|ya29\.|AKIA|ASIA|sk-|rk-)[A-Za-z0-9_./+=-]{12,}\b|\beyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\b", re.IGNORECASE)

def _safe_code_assignment(value: str) -> bool:
    """Allow narrow reference assignments only when comments contain no known secret."""
    try:
        tree = ast.parse(value.strip())
        comments = (token.string for token in tokenize.generate_tokens(io.StringIO(value).readline) if token.type == tokenize.COMMENT)
        if any(any(pattern.search(comment) for pattern in (_TOKEN, _PEM, _LABEL, _AUTH_HEADER)) for comment in comments):
            return False
    except (SyntaxError, ValueError, RecursionError, tokenize.TokenError, IndentationError):
        return False
    nodes = tree.body
    if len(nodes) == 2 and isinstance(nodes[0], ast.Import) and len(nodes[0].names) == 1 and nodes[0].names[0].name == 'os' and nodes[0].names[0].asname is None:
        nodes = nodes[1:]
    if len(nodes) != 1 or not isinstance(nodes[0], ast.Assign):
        return False
    node = nodes[0]
    if len(node.targets) != 1 or not isinstance(node.targets[0], ast.Name) or not _SENSITIVE_KEY.fullmatch(node.targets[0].id):
        return False
    expr = node.value
    if isinstance(expr, ast.Subscript) and isinstance(expr.value, ast.Attribute) and expr.value.attr == 'environ' and isinstance(expr.value.value, ast.Name) and expr.value.value.id == 'os':
        argument = expr.slice
    elif isinstance(expr, ast.Call) and not expr.keywords:
        func = expr.func
        if isinstance(func, ast.Name) and func.id == 'input':
            if not expr.args:
                return True
            if len(expr.args) != 1:
                return False
            argument = expr.args[0]
        elif len(expr.args) == 1 and ((isinstance(func, ast.Attribute) and func.attr == 'getenv' and isinstance(func.value, ast.Name) and func.value.id == 'os') or (isinstance(func, ast.Attribute) and func.attr == 'get' and isinstance(func.value, ast.Attribute) and func.value.attr == 'environ' and isinstance(func.value.value, ast.Name) and func.value.value.id == 'os')):
            argument = expr.args[0]
        else:
            return False
    else:
        return False
    return (isinstance(argument, ast.Constant) and isinstance(argument.value, str)
            and not any(pattern.search(argument.value) for pattern in (_TOKEN, _PEM, _LABEL, _AUTH_HEADER)))


def _unsafe_code_credential_call(value: str) -> bool:
    try:
        tree = ast.parse(value.strip())
    except (SyntaxError, ValueError, RecursionError):
        return False
    return any(isinstance(node, ast.Assign)
               and any(isinstance(target, ast.Name) and _SENSITIVE_KEY.fullmatch(target.id) for target in node.targets)
               and (isinstance(node.value, (ast.Call, ast.BinOp)) or (isinstance(node.value, ast.Constant) and isinstance(node.value.value, str) and bool(node.value.value)))
               for node in tree.body)
def _code_has_credential_literal(value: str) -> bool:
    """Scan literal runs once; never evaluate expressions or execute code."""
    parts = []
    awaiting_string = False
    def sensitive():
        text = ''.join(parts)
        return any(pattern.search(text) for pattern in (_TOKEN, _PEM, _LABEL, _AUTH_HEADER))
    try:
        for token in tokenize.generate_tokens(io.StringIO(value).readline):
            if token.type == tokenize.STRING:
                try:
                    decoded = ast.literal_eval(token.string)
                except (SyntaxError, ValueError, RecursionError):
                    decoded = None
                if isinstance(decoded, str):
                    if parts and any(pattern.search(parts[-1] + decoded) for pattern in (_TOKEN, _PEM, _LABEL, _AUTH_HEADER)):
                        return True
                    parts.append(decoded)
                    awaiting_string = False
                    continue
            elif token.type == tokenize.OP and token.string == '+' and parts and not awaiting_string:
                awaiting_string = True
                continue
            elif token.type in (tokenize.COMMENT, tokenize.NL) and parts:
                if token.type == tokenize.COMMENT and any(pattern.search(token.string) for pattern in (_TOKEN, _PEM, _LABEL, _AUTH_HEADER)):
                    return True
                continue
            elif (token.type == tokenize.NAME and parts and token.string.lower() in ('u', 'r')
                  and token.line[token.end[1]:token.end[1] + 1] in ('"', "'")):
                # Python 3.11 tokenizes an unfinished prefixed string as NAME
                # followed by ERRORTOKEN; retain the preceding literal run.
                continue
            elif token.type == tokenize.ERRORTOKEN and token.string.isspace() and awaiting_string:
                continue
            elif token.type == tokenize.ERRORTOKEN and token.string in ('"', "'") and parts:
                # tokenize emits an opening quote separately for an unfinished
                # literal. Inspect the remaining line as data, never execute it.
                line = token.line[token.start[1] + 1:]
                if any(pattern.search(''.join(parts) + line) for pattern in (_TOKEN, _PEM, _LABEL, _AUTH_HEADER)):
                    return True
            if parts:
                if sensitive():
                    return True
                parts.clear()
                awaiting_string = False
        return bool(parts and sensitive())
    except tokenize.TokenError as error:
        if parts and error.args and ('unterminated string literal' in str(error.args[0]) or 'EOF in multi-line string' in str(error.args[0])):
            try:
                row, offset = error.args[1]
                lines = value.splitlines(keepends=True)
                line = lines[row - 1]
                # tokenize reports the quote at a zero-based offset for triple
                # strings, and a one-based offset for unterminated single strings.
                positions = (offset, offset - 1, offset + 1)
                start = next((i for i in positions if 0 <= i < len(line) and line[i] in ('"', "'")), -1)
                if start < 0:
                    return bool(parts and sensitive())
                quote = line[start]
                while start > 0 and line[start - 1] == quote:
                    start -= 1
                delimiter_length = 3 if line[start:start + 3] == quote * 3 else 1
                suffix = line[start + delimiter_length:]
                if delimiter_length == 3:
                    suffix += ''.join(lines[row:])
                    # Decode only a synthetically closed literal, never code. Raw
                    # prefixes retain backslashes and real whitespace verbatim.
                    prefix_match = re.search(r'(?i)(?<![\w])([rub]{0,2})$', line[:start])
                    prefix = prefix_match.group(1) if prefix_match else ''
                    try:
                        decoded = ast.literal_eval(prefix + quote * 3 + suffix + quote * 3)
                        if isinstance(decoded, str):
                            suffix = decoded
                    except (SyntaxError, ValueError, RecursionError):
                        # A lone final backslash leaves the source incomplete.
                        # Decode the preceding prefix only, for detection, and
                        # never normalize raw literal content.
                        trailing = len(suffix) - len(suffix.rstrip('\\'))
                        if trailing % 2 and 'r' not in prefix.lower():
                            try:
                                decoded = ast.literal_eval(prefix + quote * 3 + suffix[:-1] + quote * 3)
                                if isinstance(decoded, str):
                                    suffix = decoded + '\\'
                            except (SyntaxError, ValueError, RecursionError):
                                pass
                if any(pattern.search(''.join(parts) + suffix) for pattern in (_TOKEN, _PEM, _LABEL, _AUTH_HEADER)):
                    return True
            except (IndexError, TypeError, ValueError):
                pass
        return bool(parts and sensitive())
    except (IndentationError, RecursionError):
        # Preserve ordinary malformed prose; only fail closed when a literal run
        # already contains a recognized marker.
        return bool(parts and sensitive())

def contains_recognizable_credential(value: str) -> bool:
    return _code_has_credential_literal(value) or (not _safe_code_assignment(value) and bool(_unsafe_code_credential_call(value) or _LABEL.search(value) or _AUTH_HEADER.search(value) or _PEM.search(value) or _TOKEN.search(value)))

def redact_recognizable_credentials(value: str) -> str:
    if _code_has_credential_literal(value):
        return '[REDACTED]'
    if _safe_code_assignment(value):
        return value
    if _unsafe_code_credential_call(value):
        return '[REDACTED]'
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
