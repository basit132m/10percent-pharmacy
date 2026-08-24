# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller recipe for the Windows build.

One folder rather than one file: the program starts in about a second instead
of unpacking itself into a temporary directory on every launch, and antivirus
software is far less suspicious of it.

Build with:  pyinstaller packaging/pharmacy.spec --noconfirm
"""

from pathlib import Path

ROOT = Path(SPECPATH).resolve().parent          # noqa: F821 - SPECPATH is injected
PACKAGING = ROOT / "packaging"
ICON = PACKAGING / "app.ico"

analysis = Analysis(                             # noqa: F821
    [str(ROOT / "run.py")],
    pathex=[str(ROOT)],
    binaries=[],
    datas=[(str(ROOT / "pharmacy_desktop" / "resources"), "resources")],
    hiddenimports=[],
    hookspath=[],
    runtime_hooks=[],
    excludes=[
        "tkinter",
        "unittest",
        "pytest",
        "pydoc_data",
        "PySide6.QtQml",
        "PySide6.QtQuick",
        "PySide6.QtTest",
        "PySide6.QtDBus",
    ],
    noarchive=False,
)

pyz = PYZ(analysis.pure)                         # noqa: F821

exe = EXE(                                       # noqa: F821
    pyz,
    analysis.scripts,
    [],
    exclude_binaries=True,
    name="TenPercentPharmacy",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,                               # a desktop app, not a terminal one
    disable_windowed_traceback=False,
    icon=str(ICON) if ICON.exists() else None,
    version=str(PACKAGING / "version_info.txt"),
)

collected = COLLECT(                             # noqa: F821
    exe,
    analysis.binaries,
    analysis.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="TenPercentPharmacy",
)
