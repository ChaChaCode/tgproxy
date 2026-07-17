"""A tiny asyncio SOCKS5 server front-end.

Only the subset Telegram Desktop actually uses is implemented: no
authentication, CONNECT command, IPv4 / IPv6 / domain address types. The job of
this module is purely to parse the handshake and hand the caller a clean
(destination host, port, client streams) tuple; what happens next — WebSocket
bridge or plain TCP — is decided elsewhere.
"""
from __future__ import annotations

import asyncio
import socket
import struct
from dataclasses import dataclass

SOCKS_VERSION = 0x05

# Address types (RFC 1928).
ATYP_IPV4 = 0x01
ATYP_DOMAIN = 0x03
ATYP_IPV6 = 0x04

# Reply codes we actually emit.
REP_SUCCESS = 0x00
REP_GENERAL_FAILURE = 0x01
REP_CMD_NOT_SUPPORTED = 0x07


class Socks5Error(Exception):
    """Raised when the client speaks something that is not SOCKS5 CONNECT."""


@dataclass
class Socks5Request:
    host: str
    port: int


def build_reply(code: int) -> bytes:
    """A minimal SOCKS5 reply with a zeroed BND.ADDR/BND.PORT (0.0.0.0:0)."""
    return bytes([SOCKS_VERSION, code, 0x00, ATYP_IPV4, 0, 0, 0, 0, 0, 0])


async def negotiate(
    reader: asyncio.StreamReader, writer: asyncio.StreamWriter
) -> Socks5Request:
    """Perform the SOCKS5 greeting + CONNECT and return the request target.

    Raises Socks5Error on any protocol deviation. On an unsupported command the
    client is sent a proper reply before the error is raised, so Telegram shows
    a clean failure rather than a dangling socket.
    """
    # --- greeting: VER, NMETHODS, METHODS[] ---
    header = await reader.readexactly(2)
    if header[0] != SOCKS_VERSION:
        raise Socks5Error(f"not SOCKS5 (ver={header[0]})")
    n_methods = header[1]
    await reader.readexactly(n_methods)  # methods list; we ignore auth entirely

    # Select "no authentication".
    writer.write(bytes([SOCKS_VERSION, 0x00]))
    await writer.drain()

    # --- request: VER, CMD, RSV, ATYP, DST.ADDR, DST.PORT ---
    ver, cmd, _rsv, atyp = await reader.readexactly(4)
    if ver != SOCKS_VERSION:
        raise Socks5Error(f"bad request version {ver}")
    if cmd != 0x01:  # 0x01 = CONNECT
        writer.write(build_reply(REP_CMD_NOT_SUPPORTED))
        await writer.drain()
        raise Socks5Error(f"unsupported command {cmd}")

    host = await _read_address(reader, atyp)
    port = struct.unpack("!H", await reader.readexactly(2))[0]
    return Socks5Request(host=host, port=port)


async def _read_address(reader: asyncio.StreamReader, atyp: int) -> str:
    if atyp == ATYP_IPV4:
        return socket.inet_ntoa(await reader.readexactly(4))
    if atyp == ATYP_IPV6:
        return socket.inet_ntop(socket.AF_INET6, await reader.readexactly(16))
    if atyp == ATYP_DOMAIN:
        length = (await reader.readexactly(1))[0]
        return (await reader.readexactly(length)).decode("ascii", "replace")
    raise Socks5Error(f"unknown address type {atyp}")
