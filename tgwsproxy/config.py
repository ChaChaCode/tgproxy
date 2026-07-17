"""Persisted user settings, stored as JSON under the user's home directory.

Kept deliberately small: the tray app needs a listen port and a verbosity flag,
and any DC IP overrides the user wants to pin. Everything has a default so a
missing or partial file still yields a usable config.
"""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Dict

log = logging.getLogger("tg-ws-proxy")

APP_DIR = Path.home() / ".tg-ws-proxy"
CONFIG_FILE = APP_DIR / "config.json"
LOG_FILE = APP_DIR / "proxy.log"

DEFAULT_CONFIG: Dict = {
    "port": 2080,
    "verbose": False,
    "show_welcome": True,  # show the start window on launch
    "dc_ip": {},  # {"2": "149.154.167.220", ...}
}


def ensure_dir() -> None:
    APP_DIR.mkdir(parents=True, exist_ok=True)


def load() -> Dict:
    ensure_dir()
    cfg = dict(DEFAULT_CONFIG)
    if CONFIG_FILE.exists():
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                stored = json.load(f)
            for key, value in stored.items():
                cfg[key] = value
        except Exception as exc:
            log.warning("failed to load config: %s", exc)
    return cfg


def save(cfg: Dict) -> None:
    ensure_dir()
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=2)


def dc_ip_int_keys(cfg: Dict) -> Dict[int, str]:
    """Config stores DC ids as JSON string keys; the proxy wants ints."""
    result: Dict[int, str] = {}
    for key, value in cfg.get("dc_ip", {}).items():
        try:
            result[int(key)] = value
        except (ValueError, TypeError):
            continue
    return result
