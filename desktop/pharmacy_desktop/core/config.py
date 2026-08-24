"""Where the application keeps its files.

Everything lives under one folder per machine so a backup of that folder is a
backup of the whole pharmacy. On Windows that is
``%LOCALAPPDATA%\\TenPercentPharmacy``; the POSIX path is only used when
developing on Linux/macOS.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

from .. import APP_SHORT_NAME

ENV_DATA_DIR = "PHARMACY_DATA_DIR"


def data_dir() -> Path:
    """Root folder for the database, backups, logs and exports."""
    override = os.environ.get(ENV_DATA_DIR)
    if override:
        path = Path(override).expanduser()
    elif sys.platform.startswith("win"):
        base = os.environ.get("LOCALAPPDATA") or os.environ.get("APPDATA") or "~"
        path = Path(base).expanduser() / APP_SHORT_NAME
    else:
        base = os.environ.get("XDG_DATA_HOME", "~/.local/share")
        path = Path(base).expanduser() / APP_SHORT_NAME
    path.mkdir(parents=True, exist_ok=True)
    return path


def database_path() -> Path:
    return data_dir() / "pharmacy.db"


def backup_dir() -> Path:
    path = data_dir() / "backups"
    path.mkdir(parents=True, exist_ok=True)
    return path


def export_dir() -> Path:
    path = data_dir() / "exports"
    path.mkdir(parents=True, exist_ok=True)
    return path


def log_path() -> Path:
    return data_dir() / "pharmacy.log"


def resource_path(*parts: str) -> Path:
    """Locate a bundled resource, both in development and inside a PyInstaller exe."""
    if getattr(sys, "frozen", False):  # pragma: no cover - only true in the exe
        base = Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent))
        candidate = base / "resources"
        if candidate.exists():
            return candidate.joinpath(*parts)
    return Path(__file__).resolve().parent.parent / "resources" / Path(*parts)
