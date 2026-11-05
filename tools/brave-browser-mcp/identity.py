"""Inspect the exact local listener before attaching to Chromium DevTools."""

from __future__ import annotations

import ipaddress
import ntpath
import os


def _is_windows() -> bool:
    return os.name == "nt"


def listener_state(address: str, port: int, expected_executable: str) -> str:
    """Return MATCH, ABSENT, MISMATCH or UNKNOWN; unknown never authorizes attach.

    Only an exact loopback binding owned by the configured Brave executable is
    accepted. Wildcard bindings are treated as conflicts, not as absent ports.
    """
    if not _is_windows():
        return "UNKNOWN"
    if ntpath.basename(expected_executable).casefold() != "brave.exe":
        return "MISMATCH"
    try:
        expected_address = ipaddress.ip_address(address)
        if not expected_address.is_loopback:
            return "UNKNOWN"
        import psutil
        connections = psutil.net_connections(kind="tcp")
    except (ImportError, ValueError, OSError):
        return "UNKNOWN"
    except psutil.AccessDenied:
        return "UNKNOWN"

    matches = []
    for connection in connections:
        if connection.status != psutil.CONN_LISTEN or not connection.laddr:
            continue
        if connection.laddr.port != port:
            continue
        try:
            bound = ipaddress.ip_address(connection.laddr.ip)
        except ValueError:
            return "UNKNOWN"
        # A wildcard listener may own the requested endpoint, including on a
        # dual-stack socket. Do not launch another browser or attach to it.
        if bound.is_unspecified:
            return "MISMATCH"
        if bound == expected_address:
            matches.append(connection)
    if not matches:
        return "ABSENT"
    if len(matches) != 1 or matches[0].pid is None:
        return "UNKNOWN"
    try:
        executable = psutil.Process(matches[0].pid).exe()
    except (psutil.AccessDenied, psutil.NoSuchProcess, OSError):
        return "UNKNOWN"
    normalize = lambda value: ntpath.normcase(ntpath.normpath(value))
    return "MATCH" if normalize(executable) == normalize(expected_executable) else "MISMATCH"
