"""Tests for the settings dialog's DC:IP text parsing."""
import pytest

pytest.importorskip("customtkinter")

from tgproxy.settings import _format_dc_ip, _parse_dc_ip_text


def test_parse_valid_lines():
    text = "2:149.154.167.220\n4:149.154.167.220\n"
    assert _parse_dc_ip_text(text) == {
        "2": "149.154.167.220",
        "4": "149.154.167.220",
    }


def test_parse_ignores_blank_lines_and_spaces():
    text = "\n  2 : 149.154.167.220  \n\n"
    assert _parse_dc_ip_text(text) == {"2": "149.154.167.220"}


@pytest.mark.parametrize("bad", [
    "noseparator",
    "x:1.2.3.4",        # DC not a number
    "2:not-an-ip",
    "2:999.1.1.1",      # out of range octet
])
def test_parse_rejects_bad_input(bad):
    with pytest.raises(ValueError):
        _parse_dc_ip_text(bad)


def test_format_roundtrip_is_sorted_numerically():
    dc_ip = {"10": "1.2.3.4", "2": "5.6.7.8"}
    text = _format_dc_ip(dc_ip)
    assert text.splitlines() == ["2:5.6.7.8", "10:1.2.3.4"]
    assert _parse_dc_ip_text(text) == dc_ip
