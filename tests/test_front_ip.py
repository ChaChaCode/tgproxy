"""The front-IP behaviour: dial a configured IP, present the WS host as SNI.

This is what makes the proxy work on networks where the address kws*.web.telegram.org
resolves to is blackholed — regressing it silently breaks those users, so pin it.
"""
import asyncio

import pytest

from tgproxy import telegram, websocket as ws


def test_media_host_uses_dash_one_variant():
    assert telegram.ws_host_for_dc(2) == "kws2.web.telegram.org"
    assert telegram.ws_host_for_dc(2, is_media=True) == "kws2-1.web.telegram.org"


def test_connect_dials_given_ip_not_dns(monkeypatch):
    """When ip= is passed, connect must use it and never resolve the host."""
    dialed = {}

    async def fake_open_connection(host, port, **kw):
        dialed["host"] = host
        dialed["port"] = port
        dialed["sni"] = kw.get("server_hostname")
        raise RuntimeError("stop here — we only care about the dial target")

    async def fail_resolve(host):
        raise AssertionError("must not resolve when an explicit IP is given")

    monkeypatch.setattr(ws.asyncio, "open_connection", fake_open_connection)
    monkeypatch.setattr(ws, "_resolve", fail_resolve)

    async def run():
        with pytest.raises(RuntimeError):
            await ws.RawWebSocket.connect(
                "kws2.web.telegram.org", "/apiws", 5, ip="149.154.167.220"
            )

    asyncio.run(run())
    assert dialed["host"] == "149.154.167.220"  # dialled the front IP
    assert dialed["port"] == 443
    assert dialed["sni"] == "kws2.web.telegram.org"  # ...but SNI is the WS host


def test_connect_falls_back_to_dns_without_ip(monkeypatch):
    dialed = {}

    async def fake_open_connection(host, port, **kw):
        dialed["host"] = host
        raise RuntimeError("stop")

    async def fake_resolve(host):
        return "1.2.3.4"

    monkeypatch.setattr(ws.asyncio, "open_connection", fake_open_connection)
    monkeypatch.setattr(ws, "_resolve", fake_resolve)

    async def run():
        with pytest.raises(RuntimeError):
            await ws.RawWebSocket.connect("kws2.web.telegram.org", "/apiws", 5)

    asyncio.run(run())
    assert dialed["host"] == "1.2.3.4"
