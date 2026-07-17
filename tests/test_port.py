"""Tests for busy-port detection and free-port selection."""
import socket

from tgproxy.server import find_free_port, port_is_free


def test_port_is_free_on_unused_port():
    # Bind an ephemeral port, release it, then it should read as free.
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    assert port_is_free(port)


def test_port_is_busy_when_taken():
    s = socket.socket()
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 0)
    s.bind(("127.0.0.1", 0))
    s.listen(1)
    port = s.getsockname()[1]
    try:
        assert not port_is_free(port)
    finally:
        s.close()


def test_find_free_port_skips_busy():
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    s.listen(1)
    busy = s.getsockname()[1]
    try:
        found = find_free_port(busy)
        assert found is not None
        assert found != busy  # must have moved past the occupied port
    finally:
        s.close()
