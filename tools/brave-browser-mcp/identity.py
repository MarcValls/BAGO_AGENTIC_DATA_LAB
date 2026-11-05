"""Fail-closed identity check for local Chromium DevTools listeners."""

from __future__ import annotations

import os
from pathlib import PureWindowsPath


def loopback_listener_is_brave(port: int) -> bool:
    """Verify the Windows executable owning a local CDP listening port.

    Brave reports a generic Chrome product string through CDP. The listening
    executable is the identity signal; missing dependencies, inaccessible
    process tables, and non-Brave executables all fail closed.
    """
    if os.name != "nt":
        return False
    try:
        import psutil
    except ImportError:
        return False
    try:
        connections = psutil.net_connections(kind="tcp")
    except (psutil.AccessDenied, OSError):
        return False
    for connection in connections:
        if (
            connection.status != psutil.CONN_LISTEN
            or not connection.laddr
            or connection.laddr.port != port
            or connection.pid is None
        ):
            continue
        try:
            executable = psutil.Process(connection.pid).exe()
        except (psutil.AccessDenied, psutil.NoSuchProcess, OSError):
            continue
        if PureWindowsPath(executable).name.casefold() == "brave.exe":
            return True
    return False
