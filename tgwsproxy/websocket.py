"""A minimal client-side WebSocket (RFC 6455) over asyncio + TLS.

This is deliberately tiny: only what the proxy needs to tunnel MTProto through
Telegram's WebSocket endpoint. We speak binary frames, mask them as a client
must, and handle control frames (ping/pong/close) inline. No extensions, no
fragmentation on send, no text frames.

The handshake raises WsHandshakeError on any non-101 response so the caller can
distinguish a redirect (DPI interference) from a clean upgrade and react — e.g.
blacklist the endpoint and fall back to plain TCP.
"""
from __future__ import annotations

import asyncio
import base64
import os
import ssl
import struct
from typing import Dict, Optional

# Frame opcodes (RFC 6455 §5.2).
OP_CONTINUATION = 0x0
OP_TEXT = 0x1
OP_BINARY = 0x2
OP_CLOSE = 0x8
OP_PING = 0x9
OP_PONG = 0xA

_HANDSHAKE_TIMEOUT = 10.0

# TLS context that does not verify the certificate. Telegram's WS endpoints are
# reached by IP with an SNI host that will not always match the presented cert,
# and the payload is already end-to-end encrypted by MTProto, so cert pinning
# here would only break the transport without adding security.
_ssl_ctx = ssl.create_default_context()
_ssl_ctx.check_hostname = False
_ssl_ctx.verify_mode = ssl.CERT_NONE


class WsHandshakeError(Exception):
    """Raised when the server does not return HTTP 101 Switching Protocols."""

    def __init__(self, status_code: int, status_line: str, location: str = ""):
        self.status_code = status_code
        self.status_line = status_line
        self.location = location
        super().__init__(f"HTTP {status_code}: {status_line}")

    @property
    def is_redirect(self) -> bool:
        return 300 <= self.status_code < 400


def _mask(data: bytes, key: bytes) -> bytes:
    """XOR *data* with the repeating 4-byte masking *key*."""
    return bytes(b ^ key[i & 3] for i, b in enumerate(data))


def build_frame(opcode: int, payload: bytes = b"") -> bytes:
    """Build a single masked client frame (FIN=1)."""
    frame = bytearray()
    frame.append(0x80 | opcode)  # FIN + opcode

    length = len(payload)
    mask_bit = 0x80  # clients MUST mask
    if length < 126:
        frame.append(mask_bit | length)
    elif length < 65536:
        frame.append(mask_bit | 126)
        frame.extend(struct.pack(">H", length))
    else:
        frame.append(mask_bit | 127)
        frame.extend(struct.pack(">Q", length))

    key = os.urandom(4)
    frame.extend(key)
    frame.extend(_mask(payload, key))
    return bytes(frame)


class RawWebSocket:
    """A connected client WebSocket carrying binary frames."""

    def __init__(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        self.reader = reader
        self.writer = writer
        self._closed = False

    @classmethod
    async def connect(
        cls,
        host: str,
        path: str,
        timeout: float = _HANDSHAKE_TIMEOUT,
    ) -> "RawWebSocket":
        """TLS-connect to *host* (resolved via DNS) and upgrade to WebSocket.

        The connection target is the WebSocket front (e.g. kws2.web.telegram.org),
        which resolves to a different IP than the DC's MTProto endpoint and is the
        only address that terminates TLS for the /apiws upgrade.
        """
        reader, writer = await asyncio.wait_for(
            asyncio.open_connection(host, 443, ssl=_ssl_ctx, server_hostname=host),
            timeout,
        )

        key = base64.b64encode(os.urandom(16)).decode("ascii")
        request = (
            f"GET {path} HTTP/1.1\r\n"
            f"Host: {host}\r\n"
            f"Upgrade: websocket\r\n"
            f"Connection: Upgrade\r\n"
            f"Sec-WebSocket-Key: {key}\r\n"
            f"Sec-WebSocket-Version: 13\r\n"
            f"Sec-WebSocket-Protocol: binary\r\n"
            f"Origin: https://web.telegram.org\r\n"
            f"User-Agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            f"AppleWebKit/537.36 (KHTML, like Gecko) "
            f"Chrome/131.0.0.0 Safari/537.36\r\n"
            f"\r\n"
        )
        writer.write(request.encode("ascii"))
        await writer.drain()

        status_code, status_line, headers = await cls._read_handshake(reader, timeout)
        if status_code != 101:
            writer.close()
            raise WsHandshakeError(
                status_code, status_line, headers.get("location", "")
            )
        return cls(reader, writer)

    @staticmethod
    async def _read_handshake(reader, timeout):
        first = await asyncio.wait_for(reader.readline(), timeout)
        if not first:
            raise WsHandshakeError(0, "empty response")
        # "HTTP/1.1 101 Switching Protocols"
        parts = first.decode("latin-1", "replace").strip().split(" ", 2)
        status_code = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else 0
        status_line = parts[2] if len(parts) > 2 else ""

        headers: Dict[str, str] = {}
        while True:
            line = await asyncio.wait_for(reader.readline(), timeout)
            if line in (b"\r\n", b"\n", b""):
                break
            text = line.decode("latin-1", "replace").strip()
            if ":" in text:
                name, _, value = text.partition(":")
                headers[name.strip().lower()] = value.strip()
        return status_code, status_line, headers

    async def send(self, data: bytes) -> None:
        """Send a binary data frame."""
        if self._closed:
            raise ConnectionError("WebSocket closed")
        self.writer.write(build_frame(OP_BINARY, data))
        await self.writer.drain()

    async def recv(self) -> Optional[bytes]:
        """Return the next binary payload, or None on clean close.

        Ping is answered with pong and pong is ignored, both transparently, so
        the caller only ever sees application data.
        """
        while not self._closed:
            frame = await self._read_frame()
            if frame is None:
                return None
            opcode, payload = frame
            if opcode in (OP_BINARY, OP_TEXT, OP_CONTINUATION):
                return payload
            if opcode == OP_PING:
                self.writer.write(build_frame(OP_PONG, payload))
                await self.writer.drain()
            elif opcode == OP_CLOSE:
                await self.close()
                return None
            # OP_PONG and anything else: ignore, loop again
        return None

    async def _read_frame(self):
        header = await self.reader.readexactly(2)
        opcode = header[0] & 0x0F
        masked = bool(header[1] & 0x80)
        length = header[1] & 0x7F
        if length == 126:
            length = struct.unpack(">H", await self.reader.readexactly(2))[0]
        elif length == 127:
            length = struct.unpack(">Q", await self.reader.readexactly(8))[0]

        key = await self.reader.readexactly(4) if masked else b""
        payload = await self.reader.readexactly(length)
        if masked:
            payload = _mask(payload, key)
        return opcode, payload

    async def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        try:
            self.writer.write(build_frame(OP_CLOSE))
            await self.writer.drain()
        except Exception:
            pass
        try:
            self.writer.close()
            await self.writer.wait_closed()
        except Exception:
            pass
