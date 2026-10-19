"""ADL legacy-operation adaptations applied before a BER request is prepared."""

from __future__ import annotations

import os
from collections.abc import Mapping
from typing import Any


def legacy_compatible_operation(operation: Mapping[str, Any]) -> dict[str, Any]:
    """Preserve ADL legacy text-write newline translation at the BER boundary.

    The legacy sandbox writes text with ``Path.write_text`` and therefore
    translates LF to the host newline on Windows. BAGO writes the exact UTF-8
    content it receives. Adapt only this representation detail; BAGO still
    prepares, authorizes, executes and receipts the actual request.
    """

    adapted = dict(operation)
    target_value = operation.get("target")
    arguments_value = operation.get("arguments")
    target = dict(target_value) if isinstance(target_value, Mapping) else {}
    arguments = dict(arguments_value) if isinstance(arguments_value, Mapping) else {}
    adapted["target"] = target
    adapted["arguments"] = arguments
    if operation.get("effect_id") == "filesystem.write" and os.name == "nt":
        content = arguments.get("content")
        if isinstance(content, str):
            arguments["content"] = content.replace("\n", os.linesep)
    return adapted


__all__ = ["legacy_compatible_operation"]
