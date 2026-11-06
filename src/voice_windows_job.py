"""Windows-only ownership of a voice receiver process tree."""
from __future__ import annotations

import ctypes
import os
import socket
import struct
import subprocess
import sys
from ctypes import wintypes
from pathlib import Path


class _Basic(ctypes.Structure):
    _fields_ = [('p', ctypes.c_int64), ('j', ctypes.c_int64), ('flags', wintypes.DWORD),
                ('min', ctypes.c_size_t), ('max', ctypes.c_size_t), ('active', wintypes.DWORD),
                ('affinity', ctypes.c_size_t), ('priority', wintypes.DWORD), ('schedule', wintypes.DWORD)]


class _Io(ctypes.Structure):
    _fields_ = [(str(i), ctypes.c_uint64) for i in range(6)]


class _Extended(ctypes.Structure):
    _fields_ = [('basic', _Basic), ('io', _Io), ('a', ctypes.c_size_t), ('b', ctypes.c_size_t),
                ('c', ctypes.c_size_t), ('d', ctypes.c_size_t)]


class OwnedVoiceJob:
    def __init__(self):
        if os.name != 'nt':
            raise OSError('voice job requires Windows')
        self.kernel = ctypes.WinDLL('kernel32', use_last_error=True)
        self.api = ctypes.WinDLL('iphlpapi', use_last_error=True)
        k = self.kernel
        k.CreateJobObjectW.argtypes = [ctypes.c_void_p, wintypes.LPCWSTR]; k.CreateJobObjectW.restype = wintypes.HANDLE
        k.CloseHandle.argtypes = [wintypes.HANDLE]; k.CloseHandle.restype = wintypes.BOOL
        k.TerminateJobObject.argtypes = [wintypes.HANDLE, wintypes.UINT]; k.TerminateJobObject.restype = wintypes.BOOL
        k.SetInformationJobObject.argtypes = [wintypes.HANDLE, wintypes.INT, ctypes.c_void_p, wintypes.DWORD]; k.SetInformationJobObject.restype = wintypes.BOOL
        k.QueryInformationJobObject.argtypes = [wintypes.HANDLE, wintypes.INT, ctypes.c_void_p, wintypes.DWORD, ctypes.c_void_p]; k.QueryInformationJobObject.restype = wintypes.BOOL
        k.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]; k.OpenProcess.restype = wintypes.HANDLE
        k.IsProcessInJob.argtypes = [wintypes.HANDLE, wintypes.HANDLE, ctypes.POINTER(wintypes.BOOL)]; k.IsProcessInJob.restype = wintypes.BOOL
        self.api.GetExtendedTcpTable.argtypes = [ctypes.c_void_p, ctypes.POINTER(wintypes.ULONG), wintypes.BOOL, wintypes.ULONG, wintypes.ULONG, wintypes.ULONG]
        self.api.GetExtendedTcpTable.restype = wintypes.DWORD
        self.handle = k.CreateJobObjectW(None, None)
        if not self.handle:
            raise OSError(ctypes.get_last_error(), 'CreateJobObject')
        data = _Extended(); data.basic.flags = 0x2000
        if not k.SetInformationJobObject(self.handle, 9, ctypes.byref(data), ctypes.sizeof(data)):
            error = ctypes.get_last_error(); k.CloseHandle(self.handle); self.handle = None
            raise OSError(error, 'SetInformationJobObject')

    def launch(self, args: list[str], *, cwd: str, env: dict) -> subprocess.Popen:
        if not self.handle:
            raise OSError('closed voice job')
        os.set_handle_inheritable(self.handle, True)
        try:
            info = subprocess.STARTUPINFO(); info.lpAttributeList = {'handle_list': [self.handle]}
            worker = Path(__file__).with_name('voice_job_worker.py')
            base_python = getattr(sys, '_base_executable', sys.executable)
            return subprocess.Popen([base_python, '-B', str(worker), str(self.handle), *args], cwd=cwd,
                                    env=env, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                                    stderr=subprocess.DEVNULL, startupinfo=info, close_fds=True,
                                    creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        finally:
            os.set_handle_inheritable(self.handle, False)

    def _server_owners(self, sock: socket.socket) -> list[int]:
        local = sock.getsockname(); peer = sock.getpeername(); size = wintypes.ULONG(0)
        result = self.api.GetExtendedTcpTable(None, ctypes.byref(size), False, 2, 5, 0)
        if result not in (0, 122) or size.value < 4:
            return []
        table = ctypes.create_string_buffer(size.value)
        if self.api.GetExtendedTcpTable(table, ctypes.byref(size), False, 2, 5, 0):
            return []
        count = struct.unpack_from('<I', table.raw, 0)[0]; owners = []
        for index in range(count):
            state, local_addr, local_port, remote_addr, remote_port, pid = struct.unpack_from('<IIIIII', table.raw, 4 + index * 24)
            address = lambda value: socket.inet_ntoa(struct.pack('<I', value))
            row = (address(local_addr), socket.ntohs(local_port & 0xffff), address(remote_addr), socket.ntohs(remote_port & 0xffff))
            if state == 5 and row == (peer[0], peer[1], local[0], local[1]):
                owners.append(pid)
        return owners

    def owns_connection(self, sock: socket.socket) -> bool:
        if not self.handle:
            return False
        try:
            first = self._server_owners(sock)
            if len(first) != 1:
                return False
            process = self.kernel.OpenProcess(0x1000, False, first[0])
            if not process:
                return False
            try:
                member = wintypes.BOOL()
                if not self.kernel.IsProcessInJob(process, self.handle, ctypes.byref(member)) or not member.value:
                    return False
                return self._server_owners(sock) == first
            finally:
                self.kernel.CloseHandle(process)
        except (OSError, ValueError, struct.error):
            return False

    def is_empty(self) -> bool:
        class Accounting(ctypes.Structure):
            _fields_ = [('a', ctypes.c_int64), ('b', ctypes.c_int64), ('c', ctypes.c_int64), ('d', ctypes.c_int64),
                        ('faults', wintypes.DWORD), ('total', wintypes.DWORD), ('active', wintypes.DWORD), ('terminated', wintypes.DWORD)]
        info = Accounting()
        return bool(self.handle and self.kernel.QueryInformationJobObject(self.handle, 1, ctypes.byref(info), ctypes.sizeof(info), None) and info.active == 0)

    def terminate(self) -> bool:
        return bool(self.handle and self.kernel.TerminateJobObject(self.handle, 1))

    def close(self) -> bool:
        if not self.handle:
            return True
        if not self.kernel.CloseHandle(self.handle):
            return False
        self.handle = None
        return True
