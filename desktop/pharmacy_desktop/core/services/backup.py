"""Backups.

A pharmacy that loses its database loses its stock position, its credit book
and its purchase history. The rule here is simple: a copy is taken every time
the program closes, copies are kept until there are too many, and any copy can
be restored from the Settings screen.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from .. import config
from ..db import Database
from ..errors import ValidationError
from .audit import AuditService


class BackupService:
    def __init__(self, db: Database, audit: AuditService | None = None):
        self.db = db
        self.audit = audit or AuditService(db)

    def backup_folder(self) -> Path:
        return config.backup_dir()

    def create(self, note: str = "manual", *, folder: Path | None = None) -> Path:
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        safe_note = "".join(ch for ch in note if ch.isalnum() or ch in "-_") or "backup"
        destination = (folder or self.backup_folder()) / f"pharmacy-{stamp}-{safe_note}.db"
        self.db.backup_to(destination)
        self.audit.log("backup.create", details=destination.name)
        return destination

    def copy_to(self, destination: str | Path) -> Path:
        """Backup to a place the owner chose — a USB stick, usually."""
        destination = Path(destination)
        if destination.is_dir():
            stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
            destination = destination / f"pharmacy-{stamp}.db"
        return self.db.backup_to(destination)

    def list_backups(self) -> list[dict]:
        entries = []
        for path in sorted(
            self.backup_folder().glob("pharmacy-*.db"),
            key=lambda item: item.stat().st_mtime,
            reverse=True,
        ):
            stat = path.stat()
            entries.append(
                {
                    "path": path,
                    "name": path.name,
                    "size_kb": round(stat.st_size / 1024),
                    "created_at": datetime.fromtimestamp(stat.st_mtime).isoformat(
                        timespec="seconds"
                    ),
                }
            )
        return entries

    def prune(self, keep: int = 20) -> int:
        backups = self.list_backups()
        removed = 0
        for entry in backups[max(keep, 1) :]:
            try:
                entry["path"].unlink()
                removed += 1
            except OSError:  # pragma: no cover - a locked file is not fatal
                pass
        return removed

    def restore(self, source: str | Path) -> None:
        source = Path(source)
        if not source.exists():
            raise ValidationError("That backup file is missing.")
        self.db.restore_from(source)
        self.audit.log("backup.restore", details=source.name)
