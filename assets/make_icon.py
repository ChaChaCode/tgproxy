# -*- coding: utf-8 -*-
"""Build assets/icon.ico (multi-size) from the source PNG assets/icon_src.png.

Run: python assets/make_icon.py
"""
from pathlib import Path

from PIL import Image

HERE = Path(__file__).parent
SRC = HERE / "icon_src.png"
SIZES = [16, 24, 32, 48, 64, 128, 256]


def main() -> None:
    img = Image.open(SRC).convert("RGBA")
    # Square-pad so the icon isn't distorted when resized to square .ico slots.
    w, h = img.size
    side = max(w, h)
    canvas = Image.new("RGBA", (side, side), (0, 0, 0, 0))
    canvas.paste(img, ((side - w) // 2, (side - h) // 2), img)

    frames = [canvas.resize((s, s), Image.LANCZOS) for s in SIZES]
    frames[-1].save(HERE / "icon.ico", format="ICO", sizes=[(s, s) for s in SIZES])
    frames[-1].save(HERE / "icon.png")
    print("wrote icon.ico and icon.png from", SRC.name)


if __name__ == "__main__":
    main()
