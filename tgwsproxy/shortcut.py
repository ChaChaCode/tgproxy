"""Create a desktop shortcut to the running executable (Windows only).

Uses the Windows Script Host COM object via PowerShell, so there's no extra
Python dependency. Silently no-ops on non-Windows or when not running as a
frozen exe (there's nothing meaningful to point a shortcut at from source).
"""
from __future__ import annotations

import logging
import os
import subprocess
import sys
from pathlib import Path

log = logging.getLogger("tg-ws-proxy")


def _target_exe() -> str:
    """Path to point the shortcut at: the frozen exe, or this script's python."""
    if getattr(sys, "frozen", False):
        return sys.executable
    return sys.executable  # dev fallback: python.exe (shortcut still valid)


def create_desktop_shortcut(name: str = "TG WS Proxy") -> bool:
    """Create <Desktop>/<name>.lnk pointing at the exe. Returns success."""
    if os.name != "nt":
        log.debug("desktop shortcut skipped: not Windows")
        return False

    desktop = Path.home() / "Desktop"
    lnk = desktop / f"{name}.lnk"
    target = _target_exe()
    workdir = str(Path(target).parent)

    ps = (
        "$ws = New-Object -ComObject WScript.Shell; "
        f"$s = $ws.CreateShortcut('{lnk}'); "
        f"$s.TargetPath = '{target}'; "
        f"$s.WorkingDirectory = '{workdir}'; "
        f"$s.IconLocation = '{target},0'; "
        "$s.Save()"
    )
    try:
        subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-Command", ps],
            check=True, capture_output=True, timeout=15,
        )
        log.info("desktop shortcut created: %s", lnk)
        return True
    except Exception as exc:
        log.warning("could not create desktop shortcut: %s", exc)
        return False
