"""The start window shown on launch: instructions + a "Start" button.

Built with customtkinter. Returns to the caller how the user chose to proceed:
whether to open the proxy in Telegram immediately, and whether to keep showing
this window on future launches. Kept entirely separate from the tray so the app
still runs headless if the GUI toolkit is missing.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import customtkinter as ctk


@dataclass
class WelcomeResult:
    started: bool = False           # user pressed Start (vs. closed the window)
    open_in_telegram: bool = True   # checkbox: hand the proxy to Telegram now
    keep_showing: bool = True       # checkbox: show this window next time too
    add_desktop_shortcut: bool = False  # checkbox: create a desktop shortcut


def _shortcut_exists(name: str = "TG WS Proxy") -> bool:
    return (Path.home() / "Desktop" / f"{name}.lnk").exists()


def _icon_ico_path() -> Path | None:
    """Find icon.ico whether running frozen (PyInstaller) or from source."""
    import sys
    candidates = []
    if getattr(sys, "frozen", False):
        candidates.append(Path(sys._MEIPASS) / "assets" / "icon.ico")  # type: ignore[attr-defined]
    candidates.append(Path(__file__).resolve().parent.parent / "assets" / "icon.ico")
    for c in candidates:
        if c.exists():
            return c
    return None


def _set_window_icon(root) -> None:
    """Set the title-bar / taskbar icon for the window."""
    ico = _icon_ico_path()
    if not ico:
        return
    try:
        root.iconbitmap(str(ico))
    except Exception:
        pass


def show_welcome(port: int) -> WelcomeResult:
    """Display the start window and block until the user acts. Returns choices."""
    ctk.set_appearance_mode("system")
    ctk.set_default_color_theme("blue")

    result = WelcomeResult()
    root = ctk.CTk()
    root.title("TG WS Proxy")
    root.geometry("560x508")
    root.resizable(False, False)
    _set_window_icon(root)

    accent = "#2f81f7"

    def bar_heading(parent, text):
        row = ctk.CTkFrame(parent, fg_color="transparent")
        ctk.CTkFrame(row, width=4, height=24, fg_color=accent).pack(side="left", padx=(0, 10))
        ctk.CTkLabel(row, text=text, font=ctk.CTkFont(size=17, weight="bold")).pack(side="left")
        return row

    pad = {"padx": 28, "anchor": "w"}
    bar_heading(root, "Прокси запущен и работает в системном трее").pack(pady=(26, 18), **pad)

    ctk.CTkLabel(root, text="Как подключить Telegram Desktop:",
                 font=ctk.CTkFont(size=14, weight="bold")).pack(pady=(0, 10), **pad)

    ctk.CTkLabel(root, text="Автоматически:", text_color=accent,
                 font=ctk.CTkFont(size=13, weight="bold")).pack(pady=(0, 4), **pad)
    ctk.CTkLabel(root, text="ПКМ по иконке в трее → «Открыть в Telegram»").pack(pady=(0, 2), **pad)
    ctk.CTkLabel(root, text=f"Или ссылка: tg://socks?server=127.0.0.1&port={port}").pack(pady=(0, 16), **pad)

    ctk.CTkLabel(root, text="Вручную:", text_color=accent,
                 font=ctk.CTkFont(size=13, weight="bold")).pack(pady=(0, 4), **pad)
    ctk.CTkLabel(root, text="Настройки → Продвинутые → Тип подключения → Прокси").pack(pady=(0, 2), **pad)
    ctk.CTkLabel(root, text=f"SOCKS5 → 127.0.0.1 : {port}  (без логина/пароля)").pack(pady=(0, 20), **pad)

    open_var = ctk.BooleanVar(value=True)
    ctk.CTkCheckBox(root, text="Открыть прокси в Telegram сейчас",
                    variable=open_var).pack(pady=(0, 6), **pad)
    shortcut_var = ctk.BooleanVar(value=not _shortcut_exists())
    ctk.CTkCheckBox(root, text="Добавить ярлык на рабочий стол",
                    variable=shortcut_var).pack(pady=(0, 6), **pad)
    keep_var = ctk.BooleanVar(value=True)
    ctk.CTkCheckBox(root, text="Показывать это окно при запуске",
                    variable=keep_var).pack(pady=(0, 26), **pad)

    def on_start():
        result.started = True
        result.open_in_telegram = open_var.get()
        result.add_desktop_shortcut = shortcut_var.get()
        result.keep_showing = keep_var.get()
        root.destroy()

    def on_close():
        result.keep_showing = keep_var.get()
        root.destroy()

    ctk.CTkButton(root, text="Начать", height=44, corner_radius=10,
                  font=ctk.CTkFont(size=15, weight="bold"),
                  command=on_start).pack(padx=28, pady=(0, 24), fill="x")

    root.protocol("WM_DELETE_WINDOW", on_close)
    root.after(50, root.lift)
    root.mainloop()
    return result
