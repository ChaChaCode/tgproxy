"""Command-line entry point: python -m tgproxy [--port N] [--dc-ip DC:IP]..."""
from __future__ import annotations

import argparse
import asyncio
import logging
import socket
import sys
from typing import Dict, List

from .server import DEFAULT_PORT, run


def parse_dc_ip_list(items: List[str]) -> Dict[int, str]:
    """Turn ['2:149.154.167.220', ...] into {2: '149.154.167.220', ...}."""
    result: Dict[int, str] = {}
    for item in items:
        if ":" not in item:
            raise ValueError(f"invalid --dc-ip {item!r}, expected DC:IP")
        dc_str, ip = item.split(":", 1)
        try:
            dc = int(dc_str)
            socket.inet_aton(ip)
        except (ValueError, OSError):
            raise ValueError(f"invalid --dc-ip {item!r}, expected DC:IP")
        result[dc] = ip
    return result


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="tgproxy",
        description="Local SOCKS5 proxy that bridges Telegram over WebSocket.",
    )
    p.add_argument("--port", type=int, default=DEFAULT_PORT,
                   help=f"listen port (default {DEFAULT_PORT})")
    p.add_argument("--dc-ip", action="append", default=[], metavar="DC:IP",
                   help="override a DC's IP, e.g. --dc-ip 2:149.154.167.220")
    p.add_argument("-v", "--verbose", action="store_true", help="debug logging")
    return p


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    try:
        dc_ip = parse_dc_ip_list(args.dc_ip)
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s  %(levelname)-5s  %(message)s",
        datefmt="%H:%M:%S",
    )

    try:
        asyncio.run(run(port=args.port, dc_ip=dc_ip))
    except KeyboardInterrupt:
        logging.getLogger("tgproxy").info("shutting down")
    return 0


if __name__ == "__main__":
    sys.exit(main())
