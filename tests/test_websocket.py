"""Tests for the frame codec and handshake parsing (no real network)."""
import asyncio
import struct

import pytest

from tgproxy import websocket as ws


def test_mask_is_involutive():
    key = b"\x01\x02\x03\x04"
    data = b"hello telegram, this is a longer payload"
    assert ws._mask(ws._mask(data, key), key) == data


def test_build_frame_small():
    frame = ws.build_frame(ws.OP_BINARY, b"abc")
    assert frame[0] == 0x80 | ws.OP_BINARY  # FIN + binary
    assert frame[1] & 0x80  # masked
    assert (frame[1] & 0x7F) == 3  # length
    key = frame[2:6]
    assert ws._mask(frame[6:], key) == b"abc"


def test_build_frame_extended_16bit():
    payload = b"x" * 1000
    frame = ws.build_frame(ws.OP_BINARY, payload)
    assert (frame[1] & 0x7F) == 126
    assert struct.unpack(">H", frame[2:4])[0] == 1000


def _server_frame(opcode: int, payload: bytes) -> bytes:
    """Build an *unmasked* server frame, as a real server would send."""
    out = bytearray([0x80 | opcode])
    length = len(payload)
    if length < 126:
        out.append(length)
    elif length < 65536:
        out.append(126)
        out.extend(struct.pack(">H", length))
    else:
        out.append(127)
        out.extend(struct.pack(">Q", length))
    out.extend(payload)
    return bytes(out)


def test_recv_binary_and_ping():
    async def run():
        reader = asyncio.StreamReader()
        sent = []

        class FakeWriter:
            def write(self, d): sent.append(d)
            async def drain(self): pass
            def close(self): pass
            async def wait_closed(self): pass

        sock = ws.RawWebSocket(reader, FakeWriter())

        # A ping (should be answered with pong, transparently), then data.
        reader.feed_data(_server_frame(ws.OP_PING, b"pp"))
        reader.feed_data(_server_frame(ws.OP_BINARY, b"payload"))
        reader.feed_eof()

        data = await sock.recv()
        assert data == b"payload"
        # exactly one pong frame should have been written
        pongs = [f for f in sent if f and (f[0] & 0x0F) == ws.OP_PONG]
        assert len(pongs) == 1

    asyncio.run(run())


def test_recv_close_returns_none():
    async def run():
        reader = asyncio.StreamReader()

        class FakeWriter:
            def write(self, d): pass
            async def drain(self): pass
            def close(self): pass
            async def wait_closed(self): pass

        sock = ws.RawWebSocket(reader, FakeWriter())
        reader.feed_data(_server_frame(ws.OP_CLOSE, b""))
        reader.feed_eof()
        assert await sock.recv() is None

    asyncio.run(run())


def test_handshake_parsing_success():
    async def run():
        reader = asyncio.StreamReader()
        reader.feed_data(
            b"HTTP/1.1 101 Switching Protocols\r\n"
            b"Upgrade: websocket\r\n"
            b"Connection: Upgrade\r\n"
            b"\r\n"
        )
        reader.feed_eof()
        code, line, headers = await ws.RawWebSocket._read_handshake(reader, 5)
        assert code == 101
        assert headers["upgrade"] == "websocket"

    asyncio.run(run())


def test_handshake_parsing_redirect():
    async def run():
        reader = asyncio.StreamReader()
        reader.feed_data(
            b"HTTP/1.1 302 Found\r\n"
            b"Location: https://blocked.example/\r\n"
            b"\r\n"
        )
        reader.feed_eof()
        code, line, headers = await ws.RawWebSocket._read_handshake(reader, 5)
        assert code == 302
        assert headers["location"] == "https://blocked.example/"
        err = ws.WsHandshakeError(code, line, headers["location"])
        assert err.is_redirect

    asyncio.run(run())
