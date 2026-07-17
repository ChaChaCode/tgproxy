# tg-ws-proxy

A small local **SOCKS5 proxy that keeps Telegram working through DPI-based
blocking** by tunnelling its MTProto traffic over WebSocket — the same transport
`web.telegram.org` uses — and falling back to direct TCP when WebSocket is
interfered with.

Point Telegram Desktop at it as an ordinary SOCKS5 proxy and it does the rest.

## How it works

For each connection the proxy:

1. speaks SOCKS5 with the client (Telegram Desktop);
2. checks whether the destination is a Telegram IP — everything else is relayed
   straight through, so the rest of your traffic is untouched;
3. reads the 64-byte MTProto init packet and detects the target data-center;
4. connects to that DC's WebSocket endpoint (`wss://kws{N}.web.telegram.org/apiws`)
   and bridges the MTProto stream inside binary WebSocket frames;
5. if the WebSocket handshake is redirected or blocked, falls back to a direct
   TCP connection to the DC and remembers the failure for a while.

## Download (for users)

1. Grab **`TgProxy.exe`** from the [Releases](https://github.com/ChaChaCode/tgproxy/releases) page.
2. Run it — an icon appears in the system tray.
3. Right-click the tray icon → **Open in Telegram**. Telegram asks to enable the
   proxy; confirm, and you're connected.

No Python, no installation needed.

### "Windows protected your PC" (SmartScreen)

On first launch Windows may show a blue **SmartScreen** warning saying the
publisher is unknown. This appears for *every* app that isn't code-signed with a
paid certificate — it is not a sign that anything is wrong with the file. To run
it: click **More info** → **Run anyway**.

If you'd rather verify the download first, the SHA-256 checksum of `TgProxy.exe`
is shown on the [Releases](https://github.com/ChaChaCode/tgproxy/releases) page,
and the full source is in this repo so you can build the exe yourself.

**По-русски:** при первом запуске Windows может показать синее окно
«Система Windows защитила ваш компьютер» (SmartScreen). Это появляется у **любой**
программы без платной цифровой подписи и **не означает вирус**. Нажмите
**«Подробнее» → «Выполнить в любом случае»**. Файл можно проверить по SHA-256 на
странице релизов или собрать exe самому из исходников.

## Run from source (for developers)

```bash
git clone https://github.com/ChaChaCode/tgproxy.git
cd tgproxy
pip install -r requirements.txt

python -m tgwsproxy            # CLI, listens on 127.0.0.1:2080
python -m tgwsproxy --port 2085 -v
pip install pystray pillow
python -m tgwsproxy.tray       # tray app
```

To configure Telegram manually: Settings → Advanced → Connection type → Use
custom proxy → **SOCKS5**, host `127.0.0.1`, port `2080`, no username/password.

## Build the exe

```bash
pip install pyinstaller pystray pillow
python -m PyInstaller build.spec
# result: dist/TgProxy.exe
```

## Options

| Flag | Meaning |
|------|---------|
| `--port N` | Listen port (default 2080) |
| `--dc-ip DC:IP` | Override a data-center's IP (repeatable) |
| `-v`, `--verbose` | Debug logging |

## Development

```bash
pip install pytest cryptography
python -m pytest -q
```

## Credits

Inspired by the original **TgWsProxy by Flowseal**. That project is no longer
available; this is an independent reimplementation written from scratch, in
tribute to the original idea.

## License

MIT — see [LICENSE](LICENSE).
