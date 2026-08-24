"""One object that owns the database and every service, wired together once.

The UI receives an :class:`AppContext` and reaches services through it, so no
screen ever constructs its own database connection.
"""

from __future__ import annotations

from pathlib import Path

from .db import Database
from .services.audit import AuditService
from .services.auth import AuthService
from .services.backup import BackupService
from .services.catalog import CatalogService
from .services.inventory import InventoryService
from .services.parties import PartyService
from .services.purchases import PurchaseService
from .services.reports import ReportService
from .services.sales import SalesService
from .services.settings import SettingsService


class AppContext:
    def __init__(self, db_path: str | Path | None = None):
        self.db = Database(db_path)
        self.audit = AuditService(self.db)
        self.settings = SettingsService(self.db)
        self.auth = AuthService(self.db, self.audit)
        self.catalog = CatalogService(self.db, self.audit)
        self.inventory = InventoryService(self.db, self.audit)
        self.parties = PartyService(self.db, self.audit)
        self.sales = SalesService(
            self.db, self.settings, self.inventory, self.parties, self.audit
        )
        self.purchases = PurchaseService(
            self.db, self.settings, self.inventory, self.parties, self.catalog, self.audit
        )
        self.reports = ReportService(self.db, self.settings)
        self.backups = BackupService(self.db, self.audit)
        self.bootstrap()

    def bootstrap(self) -> None:
        """First-run setup: defaults that make the app usable out of the box."""
        self.settings.ensure_defaults()
        self.auth.ensure_default_admin()
        self.catalog.ensure_default_categories()

    @property
    def user(self):
        return self.auth.current_user

    def close(self, *, backup: bool = True) -> None:
        if backup and self.settings.get_bool("auto_backup_on_exit", True):
            try:
                self.backups.create("onexit")
                self.backups.prune(self.settings.get_int("backup_copies_to_keep", 20))
            except Exception:  # pragma: no cover - never block shutdown on a backup
                pass
        self.db.close()
