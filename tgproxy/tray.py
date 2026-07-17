"""System-tray front-end for tgproxy.

Runs the asyncio proxy on a background thread and exposes a small tray menu:
start / stop / restart, "Open in Telegram" (which hands Telegram a tg://socks
link so it offers to enable the proxy), a config editor, and log access.

GUI dependencies (pystray, Pillow) are optional — importing this module without
them raises a clear message rather than failing cryptically.
"""
from __future__ import annotations

import asyncio
import logging
import threading
import webbrowser
from pathlib import Path
from typing import Optional

from . import config
from .server import run as run_proxy

try:
    import pystray
    from PIL import Image, ImageDraw
except ImportError as exc:  # pragma: no cover - GUI extra not installed
    raise ImportError(
        "Tray mode needs the GUI extras. Install with: pip install pystray pillow"
    ) from exc

log = logging.getLogger("tgproxy")


class TrayApp:
    def __init__(self) -> None:
        self._cfg = config.load()
        self._thread: Optional[threading.Thread] = None
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._stop_event: Optional[asyncio.Event] = None
        self._icon: Optional["pystray.Icon"] = None

    # -- proxy lifecycle -----------------------------------------------------

    def start_proxy(self) -> None:
        if self._thread and self._thread.is_alive():
            log.info("proxy already running")
            return
        self._thread = threading.Thread(target=self._proxy_main, daemon=True)
        self._thread.start()
        log.info("proxy starting on port %d", self._cfg["port"])

    def _proxy_main(self) -> None:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        self._loop = loop
        self._stop_event = asyncio.Event()
        try:
            loop.run_until_complete(
                run_proxy(
                    port=self._cfg["port"],
                    dc_ip=config.dc_ip_int_keys(self._cfg),
                    stop_event=self._stop_event,
                )
            )
        except Exception as exc:
            log.error("proxy crashed: %s", exc)
        finally:
            loop.close()

    def stop_proxy(self) -> None:
        if self._loop and self._stop_event and not self._loop.is_closed():
            self._loop.call_soon_threadsafe(self._stop_event.set)
        if self._thread:
            self._thread.join(timeout=5)
        log.info("proxy stopped")

    def restart_proxy(self) -> None:
        self.stop_proxy()
        self.start_proxy()

    # -- tray actions --------------------------------------------------------

    def open_in_telegram(self, *_args) -> None:
        """Ask Telegram to enable this proxy via a tg://socks deep link."""
        link = f"tg://socks?server=127.0.0.1&port={self._cfg['port']}"
        log.info("opening %s", link)
        try:
            webbrowser.open(link)
        except Exception as exc:
            log.error("could not open Telegram link: %s", exc)

    def _on_restart(self, *_args) -> None:
        threading.Thread(target=self.restart_proxy, daemon=True).start()

    def _on_quit(self, *_args) -> None:
        self.stop_proxy()
        if self._icon:
            self._icon.stop()

    # -- icon ----------------------------------------------------------------

    @staticmethod
    def _icon_path() -> Optional[str]:
        """Locate the bundled icon, whether running frozen or from source."""
        import sys
        candidates = []
        if getattr(sys, "frozen", False):
            candidates.append(Path(sys._MEIPASS) / "assets" / "icon.ico")  # type: ignore[attr-defined]
        candidates.append(Path(__file__).resolve().parent.parent / "assets" / "icon.ico")
        for c in candidates:
            if c.exists():
                return str(c)
        return None

    @classmethod
    def _make_icon(cls, size: int = 64) -> "Image.Image":
        path = cls._icon_path()
        if path:
            try:
                return Image.open(path)
            except Exception:
                pass
        # Fallback: simple blue disc with a T.
        img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)
        draw.ellipse((4, 4, size - 4, size - 4), fill=(41, 128, 185, 255))
        draw.text((size // 2 - 6, size // 2 - 12), "T", fill="white")
        return img

    def _build_menu(self) -> "pystray.Menu":
        return pystray.Menu(
            pystray.MenuItem("Open in Telegram", self.open_in_telegram, default=True),
            pystray.MenuItem("Restart proxy", self._on_restart),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Quit", self._on_quit),
        )

    def _maybe_show_welcome(self) -> None:
        """Show the start window if enabled, then honour the user's choices."""
        if not self._cfg.get("show_welcome", True):
            return
        try:
            from .welcome import show_welcome
        except Exception as exc:  # GUI toolkit missing: skip silently
            log.debug("welcome window unavailable: %s", exc)
            return

        result = show_welcome(self._cfg["port"])
        if result.keep_showing != self._cfg.get("show_welcome", True):
            self._cfg["show_welcome"] = result.keep_showing
            config.save(self._cfg)
        if result.started and result.add_desktop_shortcut:
            try:
                from .shortcut import create_desktop_shortcut
                create_desktop_shortcut()
            except Exception as exc:
                log.debug("shortcut creation failed: %s", exc)
        if result.started and result.open_in_telegram:
            self.open_in_telegram()

    def run(self) -> None:
        self.start_proxy()
        self._maybe_show_welcome()
        self._icon = pystray.Icon(
            "tgproxy",
            icon=self._make_icon(),
            title="TG Proxy",
            menu=self._build_menu(),
        )
        self._icon.run()


def main() -> None:
    cfg = config.load()
    logging.basicConfig(
        level=logging.DEBUG if cfg.get("verbose") else logging.INFO,
        format="%(asctime)s  %(levelname)-5s  %(message)s",
        datefmt="%H:%M:%S",
    )
    TrayApp().run()


if __name__ == "__main__":
    main()
