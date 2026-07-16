"""Bidirectional relays: TCP <-> WebSocket, and plain TCP <-> TCP.

Once the SOCKS layer has produced a client connection and we've decided how to
reach Telegram, all that's left is to shovel bytes both ways until one side
closes. Two shapes are needed:

  * bridge_ws  — client TCP  <->  Telegram WebSocket (the main path);
  * bridge_tcp — client TCP  <->  Telegram TCP        (the fallback path);
  * pipe       — a dumb TCP relay for non-Telegram passthrough.

Each returns once either direction ends, then tears the other down.
"""
from __future__ import annotations

import asyncio
from typing import Optional

from .websocket import RawWebSocket

_CHUNK = 65536


async def _cancel_all(tasks) -> None:
    for t in tasks:
        t.cancel()
    for t in tasks:
        try:
            await t
        except (asyncio.CancelledError, Exception):
            pass


async def bridge_ws(
    reader: asyncio.StreamReader,
    writer: asyncio.StreamWriter,
    sock: RawWebSocket,
) -> None:
    """Relay between a client TCP stream and a Telegram WebSocket."""

    async def tcp_to_ws() -> None:
        while True:
            data = await reader.read(_CHUNK)
            if not data:
                break
            await sock.send(data)

    async def ws_to_tcp() -> None:
        while True:
            data = await sock.recv()
            if data is None:
                break
            writer.write(data)
            await writer.drain()

    tasks = [asyncio.ensure_future(tcp_to_ws()), asyncio.ensure_future(ws_to_tcp())]
    try:
        await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
    finally:
        await _cancel_all(tasks)
        await sock.close()
        _close_writer(writer)


async def bridge_tcp(
    reader: asyncio.StreamReader,
    writer: asyncio.StreamWriter,
    remote_reader: asyncio.StreamReader,
    remote_writer: asyncio.StreamWriter,
) -> None:
    """Relay between two TCP stream pairs (client and Telegram)."""

    async def forward(src, dst) -> None:
        while True:
            data = await src.read(_CHUNK)
            if not data:
                break
            dst.write(data)
            await dst.drain()

    tasks = [
        asyncio.ensure_future(forward(reader, remote_writer)),
        asyncio.ensure_future(forward(remote_reader, writer)),
    ]
    try:
        await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
    finally:
        await _cancel_all(tasks)
        _close_writer(remote_writer)
        _close_writer(writer)


async def pipe(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
    """One-directional dumb relay, used for non-Telegram passthrough halves."""
    try:
        while True:
            data = await reader.read(_CHUNK)
            if not data:
                break
            writer.write(data)
            await writer.drain()
    except (asyncio.CancelledError, Exception):
        pass
    finally:
        _close_writer(writer)


def _close_writer(writer: Optional[asyncio.StreamWriter]) -> None:
    if writer is None:
        return
    try:
        writer.close()
    except Exception:
        pass
