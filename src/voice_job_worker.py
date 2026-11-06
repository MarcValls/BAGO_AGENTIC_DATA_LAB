"""Enter the parent's Windows job before launching the receiver interpreter."""
import ctypes
import os
import subprocess
import sys
from ctypes import wintypes


def main() -> int:
    handle = int(sys.argv[1])
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    kernel.GetCurrentProcess.restype = wintypes.HANDLE
    kernel.AssignProcessToJobObject.argtypes = [wintypes.HANDLE, wintypes.HANDLE]
    kernel.AssignProcessToJobObject.restype = wintypes.BOOL
    kernel.CloseHandle.argtypes = [wintypes.HANDLE]
    kernel.CloseHandle.restype = wintypes.BOOL
    if not kernel.AssignProcessToJobObject(handle, kernel.GetCurrentProcess()):
        return 3
    if not kernel.CloseHandle(handle):
        return 3
    return subprocess.call(sys.argv[2:], stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


if __name__ == '__main__':
    sys.exit(main())
