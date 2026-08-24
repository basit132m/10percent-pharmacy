"""Audit trail — who did what, kept forever.

Every write that matters (a sale, a price change, a user being disabled) leaves
a row here, so a disputed till at the end of the day can be traced to a person.
"""

from __future__ import annotations

from datetime import datetime

from ..db import Database


class AuditService:
    def __init__(self, db: Database):
        self.db = db

    def log(
        self,
        action: str,
        *,
        user=None,
        entity: str | None = None,
        entity_id: int | None = None,
        details: str | None = None,
    ) -> None:
        self.db.insert(
            "audit_log",
            {
                "created_at": datetime.now().isoformat(timespec="seconds"),
                "user_id": getattr(user, "id", None),
                "username": getattr(user, "username", None),
                "action": action,
                "entity": entity,
                "entity_id": entity_id,
                "details": details,
            },
        )

    def recent(self, limit: int = 300, search: str = "") -> list:
        if search:
            like = f"%{search}%"
            return self.db.query(
                "SELECT * FROM audit_log "
                "WHERE action LIKE ? OR username LIKE ? OR details LIKE ? OR entity LIKE ? "
                "ORDER BY id DESC LIMIT ?",
                (like, like, like, like, limit),
            )
        return self.db.query("SELECT * FROM audit_log ORDER BY id DESC LIMIT ?", (limit,))

    def purge_before(self, iso_date: str) -> int:
        cursor = self.db.execute("DELETE FROM audit_log WHERE created_at < ?", (iso_date,))
        return cursor.rowcount
