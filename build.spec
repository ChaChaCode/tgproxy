# PyInstaller spec: bundle the tray app into a single windowed TgProxy.exe.
# Build with:  python -m PyInstaller build.spec
from PyInstaller.utils.hooks import collect_submodules, collect_data_files

hiddenimports = (
    collect_submodules("pystray")
    + collect_submodules("PIL")
    + collect_submodules("customtkinter")
    + ["tgwsproxy.server", "tgwsproxy.tray", "tgwsproxy.config",
       "tgwsproxy.welcome", "tgwsproxy.shortcut"]
)

a = Analysis(
    ["run_tray.py"],
    pathex=[],
    binaries=[],
    datas=collect_data_files("customtkinter"),  # bundle its theme assets
    hiddenimports=hiddenimports,
    hookspath=[],
    excludes=[],
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
