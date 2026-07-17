"""Telegram-specific facts: DC IP ranges, DC endpoints, and MTProto parsing.

The proxy needs three things about Telegram traffic:
  * recognise whether an outbound connection is going to Telegram at all;
  * work out which data-center (DC) the client is dialling;
  * know which WebSocket host to reach that DC through.

None of this is secret — the IP ranges are published by Telegram and the DC
layout is visible in every official client — but keeping it in one module keeps
the networking code readable.
"""
from __future__ import annotations

import socket
import struct
from typing import Optional, Tuple

# Public Telegram IP ranges (inclusive start/end), used to decide whether a
# SOCKS5 CONNECT target belongs to Telegram before we bother inspecting it.
_TG_RANGES_TEXT = [
    ("149.154.160.0", "149.154.175.255"),
    ("91.108.0.0", "91.108.255.255"),
    ("91.105.192.0", "91.105.193.255"),
    ("185.76.151.0", "185.76.151.255"),
]


def _ip_to_int(ip: str) -> int:
    return struct.unpack("!I", socket.inet_aton(ip))[0]


# Pre-computed integer ranges for fast membership checks.
_TG_RANGES: Tuple[Tuple[int, int], ...] = tuple(
    (_ip_to_int(lo), _ip_to_int(hi)) for lo, hi in _TG_RANGES_TEXT
)


def is_telegram_ip(ip: str) -> bool:
    """Return True if *ip* (dotted-quad string) is inside a Telegram range."""
    try:
        value = _ip_to_int(ip)
    except OSError:
        return False
    return any(lo <= value <= hi for lo, hi in _TG_RANGES)


# Best-effort mapping from a DC's canonical IP to its id, used when the DC
# cannot be read from the init packet. These are Telegram's published DC IPs.
_DC_BY_IP = {
    "149.154.175.53": 1,
    "149.154.167.51": 2,
    "149.154.167.41": 2,
    "149.154.175.100": 3,
    "149.154.167.91": 4,
    "149.154.167.92": 4,
    "91.108.56.130": 5,
}


def dc_for_ip(ip: str, default: int = 2) -> int:
    """Guess the DC id for a Telegram *ip*, defaulting to DC 2 (most common)."""
    return _DC_BY_IP.get(ip, default)


def ws_host_for_dc(dc_id: int, is_media: bool = False) -> str:
    """WebSocket host to reach a DC.

    DCs 1-5 are served under web.telegram.org; higher ids fall back to the bare
    telegram.org zone. Media connections use the "-1" variant of the host, the
    same naming the official web client uses (e.g. kws2-1.web.telegram.org).
    """
    zone = "web.telegram.org" if 1 <= dc_id <= 5 else "telegram.org"
    suffix = "-1" if is_media else ""
    return f"kws{dc_id}{suffix}.{zone}"
