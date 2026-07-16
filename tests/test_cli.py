"""Tests for the --dc-ip parser and server startup/shutdown."""
import asyncio

import pytest

from tgwsproxy import server
from tgwsproxy.__main__ import parse_dc_ip_list


def test_parse_dc_ip_ok():
    assert parse_dc_ip_list(["2:149.154.167.220", "4:149.154.167.91"]) == {
        2: "149.154.167.220",
        4: "149.154.167.91",
    }


def test_parse_dc_ip_bad():
    for bad in ["noip", "x:1.2.3.4", "2:not-an-ip", "2:999.1.1.1"]:
        with pytest.raises(ValueError):
            parse_dc_ip_list([bad])


def test_server_starts_and_stops():
    async def run():
        stop = asyncio.Event()
        task = asyncio.ensure_future(server.run(port=0, stop_event=stop))
        await asyncio.sleep(0.1)  # let it bind
        assert not task.done()
        stop.set()
        await asyncio.wait_for(task, timeout=2)

    asyncio.run(run())
