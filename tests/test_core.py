"""Unit tests for the pure (non-networking) parts of the core."""
import asyncio
import os
import struct

from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

from tgproxy import mtproto, socks5, telegram


def test_is_telegram_ip():
    assert telegram.is_telegram_ip("149.154.167.220")
    assert telegram.is_telegram_ip("91.108.4.5")
    assert not telegram.is_telegram_ip("8.8.8.8")
    assert not telegram.is_telegram_ip("not-an-ip")


def test_ws_host_for_dc():
    assert telegram.ws_host_for_dc(2) == "kws2.web.telegram.org"
    assert telegram.ws_host_for_dc(7) == "kws7.telegram.org"


def _make_init_packet(dc_id: int, is_media: bool) -> bytes:
    """Build a valid 64-byte init packet encoding *dc_id* for round-tripping."""
    prefix = os.urandom(8)
    key = os.urandom(32)
    iv = os.urandom(16)
    dc_raw = -dc_id if is_media else dc_id
    plain_tail = struct.pack("<h", dc_raw) + os.urandom(6)

    cipher = Cipher(algorithms.AES(key), modes.CTR(iv))
    enc = cipher.encryptor()
    encrypted_tail = enc.update(plain_tail) + enc.finalize()
    return prefix + key + iv + encrypted_tail


def test_dc_from_init_roundtrip():
    for dc in range(1, 6):
        for media in (False, True):
            packet = _make_init_packet(dc, media)
            result = mtproto.dc_from_init(packet)
            assert result == (dc, media), (dc, media, result)


def test_dc_from_init_rejects_short():
    assert mtproto.dc_from_init(b"too short") is None


def test_socks5_negotiate():
    async def run():
        # Simulate a client: greeting (no-auth) + CONNECT to 149.154.167.220:443
        payload = bytes([0x05, 0x01, 0x00])  # VER, NMETHODS, method=no-auth
        payload += bytes([0x05, 0x01, 0x00, socks5.ATYP_IPV4])
        payload += bytes([149, 154, 167, 220]) + struct.pack("!H", 443)

        reader = asyncio.StreamReader()
        reader.feed_data(payload)
        reader.feed_eof()

        drained = []

        class FakeWriter:
            def write(self, d): drained.append(d)
            async def drain(self): pass

        req = await socks5.negotiate(reader, FakeWriter())
        assert req.host == "149.154.167.220"
        assert req.port == 443
        # server must have offered the no-auth method
        assert drained[0] == bytes([0x05, 0x00])

    asyncio.run(run())
