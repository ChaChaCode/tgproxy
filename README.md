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

## Install

```bash
git clone https://github.com/ChaChaCode/tg-ws-proxy.git
cd tg-ws-proxy
pip install -r requirements.txt
```

## Run

```bash
python -m tgwsproxy            # listens on 127.0.0.1:2080
python -m tgwsproxy --port 2085 -v
python -m tgwsproxy --dc-ip 2:149.154.167.220
```

Then in **Telegram Desktop**: Settings → Advanced → Connection type → Use custom
proxy → **SOCKS5**, host `127.0.0.1`, port `2080`, no username/password.

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
