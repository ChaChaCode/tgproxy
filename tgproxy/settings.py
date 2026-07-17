"""Settings dialog: listen port, DC->IP front mappings, verbose logging.

The DC->IP mappings are the setting that actually matters: they decide which
Telegram front address the WebSocket bridge dials (the hostname only travels as
SNI). Networks differ in which IPs stay reachable, so users need to edit these.

Returns the updated config dict on save, or None if the user cancelled.
"""
from __future__ import annotations

import socket
from pathlib import Path
from typing import Dict, Optional

import customtkinter as ctk


def _icon_ico_path() -> Optional[Path]:
    import sys
    candidates = []
    if getattr(sys, "frozen", False):
        candidates.append(Path(sys._MEIPASS) / "assets" / "icon.ico")  # type: ignore[attr-defined]
    candidates.append(Path(__file__).resolve().parent.parent / "assets" / "icon.ico")
    for c in candidates:
        if c.exists():
            return c
    return None


def _parse_dc_ip_text(text: str) -> Dict[str, str]:
    """Parse 'DC:IP' lines into {"2": "1.2.3.4"}. Raises ValueError on bad input."""
    result: Dict[str, str] = {}
    for lineno, raw in enumerate(text.splitlines(), 1):
        line = raw.strip()
        if not line:
            continue
        if ":" not in line:
            raise ValueError(f"строка {lineno}: ожидается формат DC:IP")
        dc_str, ip = (part.strip() for part in line.split(":", 1))
        try:
            dc = int(dc_str)
        except ValueError:
            raise ValueError(f"строка {lineno}: номер DC должен быть числом")
        try:
            socket.inet_aton(ip)
        except OSError:
            raise ValueError(f"строка {lineno}: некорректный IP {ip!r}")
        result[str(dc)] = ip
    return result


def _format_dc_ip(dc_ip: Dict[str, str]) -> str:
    return "\n".join(f"{dc}:{ip}" for dc, ip in sorted(dc_ip.items(), key=lambda x: int(x[0])))


def show_settings(cfg: Dict) -> Optional[Dict]:
    """Show the settings window. Returns an updated config, or None on cancel."""
    ctk.set_appearance_mode("system")
    ctk.set_default_color_theme("blue")

    result: Dict = {}
    saved = {"ok": False}

    root = ctk.CTk()
    root.title("TG Proxy — Настройки")
    root.geometry("480x470")
    root.resizable(False, False)
    ico = _icon_ico_path()
    if ico:
        try:
            root.iconbitmap(str(ico))
        except Exception:
            pass

    accent = "#2f81f7"
    pad = {"padx": 26, "anchor": "w"}

    ctk.CTkLabel(root, text="Порт прокси", text_color=accent,
                 font=ctk.CTkFont(size=13, weight="bold")).pack(pady=(24, 6), **pad)
    port_entry = ctk.CTkEntry(root, width=150, height=34)
    port_entry.insert(0, str(cfg.get("port", 2080)))
    port_entry.pack(pady=(0, 18), **pad)

    ctk.CTkLabel(root, text="DC → IP маппинги (по одному на строку, формат DC:IP)",
                 text_color=accent,
                 font=ctk.CTkFont(size=13, weight="bold")).pack(pady=(0, 6), **pad)
    dc_box = ctk.CTkTextbox(root, width=428, height=130)
    dc_box.insert("1.0", _format_dc_ip(cfg.get("dc_ip", {})))
    dc_box.pack(pady=(0, 14), padx=26)

    verbose_var = ctk.BooleanVar(value=bool(cfg.get("verbose", False)))
    ctk.CTkCheckBox(root, text="Подробное логирование (verbose)",
                    variable=verbose_var).pack(pady=(0, 8), **pad)

    error_label = ctk.CTkLabel(root, text="", text_color="#e5534b",
                               font=ctk.CTkFont(size=12), wraplength=420, justify="left")
    error_label.pack(pady=(0, 2), **pad)

    ctk.CTkLabel(root, text="Изменения вступят в силу после перезапуска прокси.",
                 text_color="gray", font=ctk.CTkFont(size=12)).pack(pady=(0, 14), **pad)

    def on_save():
        try:
            port = int(port_entry.get().strip())
        except ValueError:
            error_label.configure(text="Порт должен быть числом.")
            return
        if not 1 <= port <= 65535:
            error_label.configure(text="Порт должен быть от 1 до 65535.")
            return
        try:
            dc_ip = _parse_dc_ip_text(dc_box.get("1.0", "end"))
        except ValueError as exc:
            error_label.configure(text=str(exc))
            return

        result.update(cfg)
        result["port"] = port
        result["dc_ip"] = dc_ip
        result["verbose"] = verbose_var.get()
        saved["ok"] = True
        root.destroy()

    buttons = ctk.CTkFrame(root, fg_color="transparent")
    buttons.pack(padx=26, fill="x")
    ctk.CTkButton(buttons, text="Сохранить", height=40, corner_radius=10,
                  font=ctk.CTkFont(size=14, weight="bold"),
                  command=on_save).pack(side="left", padx=(0, 10))
    ctk.CTkButton(buttons, text="Отмена", height=40, corner_radius=10,
                  fg_color="gray30", hover_color="gray40",
                  command=root.destroy).pack(side="left")

    root.after(50, root.lift)
    root.mainloop()
    return result if saved["ok"] else None
