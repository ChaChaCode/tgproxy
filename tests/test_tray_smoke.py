"""Import-and-call smoke tests for tray helpers that don't need a display.

These guard against NameError/typo regressions in code paths the other tests
don't touch (icon lookup, tg:// link building).
"""
import pytest

pytest.importorskip("pystray")
pytest.importorskip("PIL")

from tgproxy.tray import TrayApp


def test_icon_path_does_not_raise():
    # Should return a str path or None, never raise (regression: missing Path import).
    result = TrayApp._icon_path()
    assert result is None or isinstance(result, str)


def test_make_icon_returns_image():
    img = TrayApp._make_icon()
    assert img.size[0] > 0 and img.size[1] > 0


def test_telegram_link_uses_config_port(monkeypatch):
    app = TrayApp.__new__(TrayApp)
    app._cfg = {"port": 2080}
    opened = {}
    monkeypatch.setattr("webbrowser.open", lambda url: opened.setdefault("url", url) or True)
    app.open_in_telegram()
    assert opened["url"] == "tg://socks?server=127.0.0.1&port=2080"
