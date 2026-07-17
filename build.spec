# PyInstaller spec: bundle the tray app into a single windowed TgProxy.exe.
# Build with:  python -m PyInstaller build.spec
from PyInstaller.utils.hooks import collect_submodules

hiddenimports = (
    collect_submodules("pystray")
    + collect_submodules("PIL")
    + ["tgwsproxy.server", "tgwsproxy.tray", "tgwsproxy.config"]
)

a = Analysis(
    ["run_tray.py"],
    pathex=[],
    binaries=[],
    datas=[],
    hiddenimports=hiddenimports,
    hookspath=[],
    excludes=["tkinter", "customtkinter"],  # not used; keeps the exe smaller
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="TgProxy",
    debug=False,
    strip=False,
    upx=True,
    console=False,          # no console window; runs from the tray
    disable_windowed_traceback=False,
)
