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

log = logging.getLogger("tgproxy")


def _target_exe() -> str:
    """Path to point the shortcut at: the frozen exe, or this script's python."""
    if getattr(sys, "frozen", False):
        return sys.executable
    return sys.executable  # dev fallback: python.exe (shortcut still valid)


def _icon_location(target: str) -> str:
    """Icon source for the shortcut.

    The frozen exe embeds the icon, so pointing at the exe is stable and always
    valid. From source we fall back to the repo's assets/icon.ico.
    """
    if getattr(sys, "frozen", False):
        return f"{target},0"
    ico = Path(__file__).resolve().parent.parent / "assets" / "icon.ico"
    return f"{ico},0" if ico.exists() else f"{target},0"


def create_desktop_shortcut(name: str = "TG Proxy") -> bool:
    """Create <Desktop>/<name>.lnk pointing at the exe. Returns success."""
    if os.name != "nt":
        log.debug("desktop shortcut skipped: not Windows")
        return False

    desktop = Path.home() / "Desktop"
    lnk = desktop / f"{name}.lnk"
    target = _target_exe()
    workdir = str(Path(target).parent)
    icon = _icon_location(target)

    ps = (
        "$ws = New-Object -ComObject WScript.Shell; "
        f"$s = $ws.CreateShortcut('{lnk}'); "
        f"$s.TargetPath = '{target}'; "
        f"$s.WorkingDirectory = '{workdir}'; "
        f"$s.IconLocation = '{icon}'; "
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
