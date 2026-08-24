"""Shop-wide settings, stored as key/value rows and cached in memory.

The 10% discount lives here rather than in the code, so the owner can run a
festival 15% day from the Settings screen without a new build.
"""

from __future__ import annotations

from typing import Any

from ..db import Database

DEFAULTS: dict[str, str] = {
    # Identity, printed on every receipt
    "pharmacy_name": "Ten Percent Discount Pharmacy",
    "pharmacy_tagline": "10% Discount on Every Purchase",
    "pharmacy_address": "Kahror Pakka, District Lodhran, Punjab",
    "pharmacy_phone": "",
    "pharmacy_email": "",
    "license_no": "",
    "ntn": "",
    # Selling rules
    "default_discount_percent": "10",
    "max_discount_percent": "25",
    "round_off_totals": "1",
    "allow_negative_stock": "0",
    "warn_expiry_days": "90",
    "default_reorder_level": "10",
    # Documents
    "invoice_prefix": "INV-",
    "purchase_prefix": "PUR-",
    "sale_return_prefix": "SR-",
    "receipt_format": "thermal80",
    "receipt_footer": "Thank you for shopping with us. Get well soon!",
    "print_after_sale": "1",
    "show_savings_on_receipt": "1",
    # Housekeeping
    "auto_backup_on_exit": "1",
    "backup_copies_to_keep": "20",
}

BOOL_KEYS = {
    "round_off_totals",
    "allow_negative_stock",
    "print_after_sale",
    "auto_backup_on_exit",
    "show_savings_on_receipt",
}


class SettingsService:
    def __init__(self, db: Database):
        self.db = db
        self._cache: dict[str, str] = {}
        self.reload()

    def reload(self) -> None:
        rows = self.db.query("SELECT key, value FROM app_settings")
        self._cache = dict(DEFAULTS)
        self._cache.update({row["key"]: row["value"] for row in rows})

    def ensure_defaults(self) -> None:
        """Write any missing default so the Settings screen shows real rows."""
        existing = {row["key"] for row in self.db.query("SELECT key FROM app_settings")}
        missing = [(k, v) for k, v in DEFAULTS.items() if k not in existing]
        if missing:
            self.db.executemany(
                "INSERT INTO app_settings (key, value) VALUES (?, ?)", missing
            )
            self.reload()

    # ------------------------------------------------------------------ reads
    def get(self, key: str, default: str = "") -> str:
        return self._cache.get(key, DEFAULTS.get(key, default))

    def get_int(self, key: str, default: int = 0) -> int:
        try:
            return int(float(self.get(key, str(default))))
        except (TypeError, ValueError):
            return default

    def get_float(self, key: str, default: float = 0.0) -> float:
        try:
            return float(self.get(key, str(default)))
        except (TypeError, ValueError):
            return default

    def get_bool(self, key: str, default: bool = False) -> bool:
        return self.get(key, "1" if default else "0").strip().lower() in {
            "1",
            "true",
            "yes",
            "on",
        }

    @property
    def discount_percent(self) -> float:
        return self.get_float("default_discount_percent", 10.0)

    def all(self) -> dict[str, str]:
        return dict(self._cache)

    # ----------------------------------------------------------------- writes
    def set(self, key: str, value: Any) -> None:
        self.set_many({key: value})

    def set_many(self, values: dict[str, Any]) -> None:
        rows = []
        for key, value in values.items():
            if isinstance(value, bool):
                value = "1" if value else "0"
            rows.append((key, str(value)))
        self.db.executemany(
            "INSERT INTO app_settings (key, value) VALUES (?, ?) "
            "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
            rows,
        )
        self.reload()
