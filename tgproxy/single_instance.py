"""Single-instance guard.

Uses a named Windows mutex: the first process creates it, any later process
sees ERROR_ALREADY_EXISTS and can bow out. A mutex is more reliable than
scanning the process list — it is owned by the OS, released automatically when
the process dies (even on a crash), and is not fooled by a renamed exe.

The handle is deliberately kept alive for the process lifetime; do not let it
be garbage-collected or the lock disappears.
"""
from __future__ import annotations

import logging
import os

log = logging.getLogger("tgproxy")

_MUTEX_NAME = "Global\\TgProxy_SingleInstance_Mutex"
_ERROR_ALREADY_EXISTS = 183

_handle = None  # module-level: keeps the mutex alive


def already_running() -> bool:
    """Return True if another instance already holds the lock."""
    global _handle
    if os.name != "nt":
        return False
    try:
        import ctypes
        from ctypes import wintypes

        kernel32 = ctypes.windll.kernel32
        kernel32.CreateMutexW.argtypes = [wintypes.LPCVOID, wintypes.BOOL, wintypes.LPCWSTR]
        kernel32.CreateMutexW.restype = wintypes.HANDLE

        _handle = kernel32.CreateMutexW(None, True, _MUTEX_NAME)
        return kernel32.GetLastError() == _ERROR_ALREADY_EXISTS
    except Exception as exc:  # never block startup because of the guard itself
        log.debug("single-instance check failed: %s", exc)
        return False


def show_already_running_message() -> None:
    """Tell the user the app is already running, the way Windows apps do."""
    try:
        import ctypes
        ctypes.windll.user32.MessageBoxW(
            0, "Приложение уже запущено.", "TG Proxy", 0x40  # MB_ICONINFORMATION
        )
    except Exception:
        print("TG Proxy is already running.")
