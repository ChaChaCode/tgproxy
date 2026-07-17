"""The proxy server: ties SOCKS5, DC detection, WebSocket and fallback together.

Per client connection the flow is:

  1. SOCKS5 handshake -> destination host:port.
  2. If the destination is not a Telegram IP, relay it straight through
     (passthrough) so the client's other traffic keeps working.
  3. Read the first bytes (the MTProto init packet) and detect the DC.
  4. Try the DC's WebSocket endpoint. On success, bridge over WebSocket.
  5. On WebSocket failure (redirect / TLS / timeout), fall back to a direct
     TCP connection to the DC IP, and remember the failure so we don't keep
     retrying WebSocket for a while.
"""
from __future__ import annotations

import asyncio
import logging
import time
from typing import Dict, Optional, Set, Tuple

from . import bridge, socks5, telegram
from .mtproto import dc_from_init
from .websocket import RawWebSocket, WsHandshakeError

log = logging.getLogger("tgproxy")

DEFAULT_PORT = 2080
WS_PATH = "/apiws"


def port_is_free(port: int, host: str = "127.0.0.1") -> bool:
    """Return True if *port* can be bound right now.

    Other proxy/VPN clients (Throne, sing-box, v2ray...) commonly squat on 2080;
    without this check a failed bind would leave the tray icon sitting there
    doing nothing while Telegram silently talks to the other program.
    """
    import socket as _s
    with _s.socket(_s.AF_INET, _s.SOCK_STREAM) as sock:
        try:
            sock.bind((host, port))
            return True
        except OSError:
            return False


def find_free_port(preferred: int, host: str = "127.0.0.1", tries: int = 20) -> Optional[int]:
    """Return *preferred* if it is free, else the next free port after it."""
    for candidate in range(preferred, preferred + tries):
        if port_is_free(candidate, host):
            return candidate
    return None


_INIT_READ = 64
_WS_TIMEOUT = 10.0
_TCP_TIMEOUT = 10.0
_FAIL_COOLDOWN = 300.0  # seconds to avoid WebSocket after it fails for a DC


class Proxy:
    def __init__(self, dc_ip: Optional[Dict[int, str]] = None):
        # Operator-supplied DC -> IP overrides (from --dc-ip).
        self._dc_ip: Dict[int, str] = dc_ip or {}
        # DCs whose WebSocket keeps redirecting: skip WS until cooldown expires.
        self._ws_fail_until: Dict[Tuple[int, bool], float] = {}

    async def handle_client(
        self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter
    ) -> None:
        peer = writer.get_extra_info("peername")
        label = f"{peer[0]}:{peer[1]}" if peer else "?"
        try:
            req = await socks5.negotiate(reader, writer)
        except (socks5.Socks5Error, asyncio.IncompleteReadError) as exc:
            log.debug("[%s] SOCKS5 rejected: %s", label, exc)
            bridge._close_writer(writer)
            return

        if not telegram.is_telegram_ip(req.host):
            await self._passthrough(reader, writer, req, label)
            return

        writer.write(socks5.build_reply(socks5.REP_SUCCESS))
        await writer.drain()
        await self._handle_telegram(reader, writer, req, label)

    async def _passthrough(self, reader, writer, req, label) -> None:
        """Relay non-Telegram traffic directly, so the client stays usable."""
        try:
            remote_r, remote_w = await asyncio.wait_for(
                asyncio.open_connection(req.host, req.port), _TCP_TIMEOUT
            )
        except Exception as exc:
            log.debug("[%s] passthrough to %s:%d failed: %s",
                      label, req.host, req.port, exc)
            bridge._close_writer(writer)
            return
        writer.write(socks5.build_reply(socks5.REP_SUCCESS))
        await writer.drain()
        await bridge.bridge_tcp(reader, writer, remote_r, remote_w)

    async def _handle_telegram(self, reader, writer, req, label) -> None:
        try:
            init = await asyncio.wait_for(reader.readexactly(_INIT_READ), _TCP_TIMEOUT)
        except (asyncio.IncompleteReadError, asyncio.TimeoutError):
            log.debug("[%s] no init packet", label)
            bridge._close_writer(writer)
            return

        # DC detection is best-effort. If the init packet doesn't decode (real
        # clients don't always start with a clean 64-byte obfuscated init), we
        # still route over WebSocket using the DC implied by the target IP —
        # direct TCP is usually what's being blocked, so it must not be the
        # default path for Telegram traffic.
        detected = dc_from_init(init)
        if detected is None:
            dc_id, is_media = telegram.dc_for_ip(req.host), False
            log.debug("[%s] DC undetected, assuming DC%d from IP %s",
                      label, dc_id, req.host)
        else:
            dc_id, is_media = detected

        dst_ip = self._dc_ip.get(dc_id, req.host)

        if self._ws_on_cooldown(dc_id, is_media):
            log.info("[%s] DC%d%s WS on cooldown -> TCP", label, dc_id,
                     " media" if is_media else "")
            await self._tcp_to(dst_ip, req.port, reader, writer, init, label)
            return

        host = telegram.ws_host_for_dc(dc_id)
        try:
            sock = await RawWebSocket.connect(host, WS_PATH, _WS_TIMEOUT)
        except WsHandshakeError as exc:
            if exc.is_redirect:
                self._ws_fail_until[(dc_id, is_media)] = time.monotonic() + _FAIL_COOLDOWN
                log.info("[%s] DC%d WS redirect %d -> TCP fallback",
                         label, dc_id, exc.status_code)
            else:
                log.info("[%s] DC%d WS handshake %d -> TCP fallback",
                         label, dc_id, exc.status_code)
            await self._tcp_to(dst_ip, req.port, reader, writer, init, label)
            return
        except Exception as exc:
            log.info("[%s] DC%d WS connect failed (%s) -> TCP fallback",
                     label, dc_id, exc)
            await self._tcp_to(dst_ip, req.port, reader, writer, init, label)
            return

        log.info("[%s] DC%d%s -> WebSocket %s", label, dc_id,
                 " media" if is_media else "", host)
        await sock.send(init)  # replay the init bytes we peeked
        await bridge.bridge_ws(reader, writer, sock)

    async def _tcp_to(self, ip, port, reader, writer, init, label) -> None:
        """Direct TCP fallback to a Telegram DC IP, replaying the init bytes."""
        try:
            remote_r, remote_w = await asyncio.wait_for(
                asyncio.open_connection(ip, port), _TCP_TIMEOUT
            )
        except Exception as exc:
            log.warning("[%s] TCP fallback to %s:%d failed: %s", label, ip, port, exc)
            bridge._close_writer(writer)
            return
        remote_w.write(init)
        await remote_w.drain()
        await bridge.bridge_tcp(reader, writer, remote_r, remote_w)

    def _ws_on_cooldown(self, dc_id: int, is_media: bool) -> bool:
        until = self._ws_fail_until.get((dc_id, is_media))
        if until is None:
            return False
        if time.monotonic() >= until:
            del self._ws_fail_until[(dc_id, is_media)]
            return False
        return True


async def run(port: int = DEFAULT_PORT, dc_ip: Optional[Dict[int, str]] = None,
              stop_event: Optional[asyncio.Event] = None) -> None:
    """Start the proxy on 127.0.0.1:*port* and serve until *stop_event* is set."""
    proxy = Proxy(dc_ip=dc_ip)
    server = await asyncio.start_server(proxy.handle_client, "127.0.0.1", port)

    log.info("=" * 52)
    log.info("  tgproxy listening on 127.0.0.1:%d", port)
    log.info("  Configure Telegram Desktop:")
    log.info("    SOCKS5 proxy -> 127.0.0.1:%d  (no user/pass)", port)
    log.info("=" * 52)

    async with server:
        if stop_event is None:
            await server.serve_forever()
        else:
            serve = asyncio.ensure_future(server.serve_forever())
            await stop_event.wait()
            serve.cancel()
            try:
                await serve
            except asyncio.CancelledError:
                pass
