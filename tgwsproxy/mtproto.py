"""Reading the data-center id out of an MTProto obfuscated-init packet.

Telegram's "obfuscated2" transport opens every connection with a 64-byte init
packet. The first 8 bytes are discarded by the server, bytes 8..56 seed an
AES-256-CTR keystream, and once you decrypt bytes 56..64 the last two bytes
(interpreted little-endian, signed) carry the DC id. Media DCs use the same id
with a distinguishing high bit set by the client.

This is documented behaviour of the MTProto transport; we only *read* the id so
the proxy can pick the right WebSocket endpoint — we never decrypt payload.
"""
from __future__ import annotations

import struct
from typing import Optional, Tuple

from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

INIT_PACKET_LEN = 64


def dc_from_init(data: bytes) -> Optional[Tuple[int, bool]]:
    """Return (dc_id, is_media) from a 64-byte init packet, or None.

    None means the buffer is not a well-formed init packet (too short, or the
    decoded id is out of the plausible 1..5 range), in which case the caller
    should treat the stream as opaque and fall back to a plain relay.
    """
    if len(data) < INIT_PACKET_LEN:
        return None

    # Per the transport spec the AES key/iv are taken from bytes 8..56, and the
    # DC marker lives in the block at 56..64 once the keystream is applied.
    key = data[8:40]
    iv = data[40:56]
    encrypted_tail = data[56:64]

    cipher = Cipher(algorithms.AES(key), modes.CTR(iv))
    decryptor = cipher.encryptor()  # CTR: encrypt and decrypt are the same op
    tail = decryptor.update(encrypted_tail) + decryptor.finalize()

    dc_raw = struct.unpack("<h", tail[:2])[0]
    dc_id = abs(dc_raw)
    is_media = dc_raw < 0

    if not 1 <= dc_id <= 5:
        return None
    return dc_id, is_media
