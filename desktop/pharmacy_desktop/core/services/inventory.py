"""Stock: batches, expiry, adjustments and the FEFO rule.

Stock is held per **batch**, never as one number per medicine — a pharmacy has
to know which batch went out of the door when a recall notice arrives, and it
has to sell the batch that expires first (FEFO, first-expired-first-out).
"""

from __future__ import annotations

from typing import Any

from .. import dates
from ..db import Database
from ..errors import InsufficientStockError, NotFoundError, ValidationError
from .audit import AuditService

ADJUSTMENT_REASONS = (
    "Damaged / broken",
    "Expired — written off",
    "Lost / stolen",
    "Stock count correction",
    "Sample / free issue",
    "Returned to supplier",
    "Opening stock",
    "Other",
)


class InventoryService:
    def __init__(self, db: Database, audit: AuditService | None = None):
        self.db = db
        self.audit = audit or AuditService(db)

    # ----------------------------------------------------------------- reads
    _SELECT = """
        SELECT b.*, p.name AS product_name, p.unit_label, p.pack_size, p.reorder_level,
               p.is_active AS product_active, m.name AS manufacturer_name,
               CAST(julianday(b.expiry_date) - julianday(date('now')) AS INTEGER)
                   AS days_to_expiry
        FROM batches b
        JOIN products p ON p.id = b.product_id
        LEFT JOIN manufacturers m ON m.id = p.manufacturer_id
    """

    def get_batch(self, batch_id: int):
        row = self.db.query_one(self._SELECT + " WHERE b.id = ?", (batch_id,))
        if row is None:
            raise NotFoundError("That batch no longer exists.")
        return row

    def batches_for(self, product_id: int, *, only_available: bool = False) -> list:
        sql = self._SELECT + " WHERE b.product_id = ?"
        if only_available:
            sql += " AND b.quantity > 0"
        sql += " ORDER BY (b.expiry_date IS NULL), b.expiry_date, b.id"
        return self.db.query(sql, (product_id,))

    def list_batches(
        self,
        search: str = "",
        *,
        view: str = "all",
        expiry_days: int = 90,
        limit: int | None = None,
    ) -> list:
        """``view`` is all / in_stock / out_of_stock / expiring / expired."""
        clauses: list[str] = []
        params: list[Any] = []
        search = (search or "").strip()
        if search:
            like = f"%{search}%"
            clauses.append("(p.name LIKE ? OR b.batch_no LIKE ? OR p.generic_name LIKE ?)")
            params += [like, like, like]
        if view == "in_stock":
            clauses.append("b.quantity > 0")
        elif view == "out_of_stock":
            clauses.append("b.quantity <= 0")
        elif view == "expiring":
            clauses.append(
                "b.quantity > 0 AND b.expiry_date IS NOT NULL "
                "AND b.expiry_date >= date('now') "
                "AND b.expiry_date <= date('now', ? || ' days')"
            )
            params.append(f"+{int(expiry_days)}")
        elif view == "expired":
            clauses.append(
                "b.quantity > 0 AND b.expiry_date IS NOT NULL AND b.expiry_date < date('now')"
            )
        sql = self._SELECT
        if clauses:
            sql += " WHERE " + " AND ".join(clauses)
        sql += " ORDER BY (b.expiry_date IS NULL), b.expiry_date, p.name"
        if limit:
            sql += f" LIMIT {int(limit)}"
        return self.db.query(sql, params)

    def stock_on_hand(self, product_id: int) -> int:
        return int(
            self.db.scalar(
                "SELECT COALESCE(SUM(quantity), 0) FROM batches WHERE product_id = ?",
                (product_id,),
            )
        )

    def sellable_on_hand(self, product_id: int) -> int:
        return int(
            self.db.scalar(
                "SELECT COALESCE(SUM(quantity), 0) FROM batches "
                "WHERE product_id = ? AND quantity > 0 "
                "AND (expiry_date IS NULL OR expiry_date >= date('now'))",
                (product_id,),
            )
        )

    # --------------------------------------------------------------- receipts
    def add_stock(
        self,
        *,
        product_id: int,
        quantity: int,
        batch_no: str = "-",
        expiry_date: str | None = None,
        purchase_price: int = 0,
        sale_price: int = 0,
        source: str = "opening",
    ) -> int:
        """Put units on the shelf, merging into a batch that already exists."""
        quantity = int(quantity)
        if quantity <= 0:
            raise ValidationError("Quantity must be more than zero.")
        batch_no = (batch_no or "-").strip() or "-"
        expiry_iso = dates.to_iso(expiry_date)
        if expiry_date and not expiry_iso:
            raise ValidationError(
                f"'{expiry_date}' is not a date I understand. Use DD-MM-YYYY or MM/YYYY."
            )
        with self.db.transaction() as conn:
            existing = conn.execute(
                "SELECT id, quantity FROM batches "
                "WHERE product_id = ? AND batch_no = ? AND expiry_date IS ?",
                (product_id, batch_no, expiry_iso),
            ).fetchone()
            if existing:
                batch_id = int(existing["id"])
                conn.execute(
                    "UPDATE batches SET quantity = quantity + ?, purchase_price = ?, "
                    "sale_price = ? WHERE id = ?",
                    (quantity, purchase_price, sale_price or 0, batch_id),
                )
            else:
                cursor = conn.execute(
                    "INSERT INTO batches (product_id, batch_no, expiry_date, quantity, "
                    "purchase_price, sale_price, received_at, source) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                    (
                        product_id,
                        batch_no,
                        expiry_iso,
                        quantity,
                        purchase_price,
                        sale_price or 0,
                        dates.now_iso(),
                        source,
                    ),
                )
                batch_id = int(cursor.lastrowid)
        return batch_id

    def update_batch(
        self,
        batch_id: int,
        *,
        batch_no: str | None = None,
        expiry_date: str | None = None,
        sale_price: int | None = None,
        purchase_price: int | None = None,
    ) -> None:
        values: dict[str, Any] = {}
        if batch_no is not None:
            values["batch_no"] = batch_no.strip() or "-"
        if expiry_date is not None:
            values["expiry_date"] = dates.to_iso(expiry_date)
        if sale_price is not None:
            values["sale_price"] = sale_price
        if purchase_price is not None:
            values["purchase_price"] = purchase_price
        self.db.update("batches", batch_id, values)
        self.audit.log("batch.update", entity="batch", entity_id=batch_id)

    def delete_batch(self, batch_id: int) -> None:
        used = self.db.scalar(
            "SELECT COUNT(*) FROM sale_items WHERE batch_id = ?", (batch_id,)
        )
        if used:
            raise ValidationError(
                "This batch has been sold from, so it must stay for the record. "
                "Adjust its quantity to zero instead."
            )
        self.db.execute("DELETE FROM batches WHERE id = ?", (batch_id,))
        self.audit.log("batch.delete", entity="batch", entity_id=batch_id)

    # ------------------------------------------------------------- allocation
    def allocate(
        self, product_id: int, quantity: int, *, allow_negative: bool = False
    ) -> list[tuple[Any, int]]:
        """Choose which batches fill a sale of ``quantity`` units, FEFO order.

        Expired batches are never picked. Returns ``[(batch_row, units), ...]``.
        """
        if quantity <= 0:
            raise ValidationError("Quantity must be more than zero.")
        batches = self.db.query(
            self._SELECT
            + " WHERE b.product_id = ? AND b.quantity > 0 "
            "   AND (b.expiry_date IS NULL OR b.expiry_date >= date('now'))"
            " ORDER BY (b.expiry_date IS NULL), b.expiry_date, b.id",
            (product_id,),
        )
        picked: list[tuple[Any, int]] = []
        remaining = quantity
        for batch in batches:
            if remaining <= 0:
                break
            take = min(int(batch["quantity"]), remaining)
            picked.append((batch, take))
            remaining -= take
        if remaining > 0:
            if not allow_negative:
                available = quantity - remaining
                product = self.db.query_one(
                    "SELECT name FROM products WHERE id = ?", (product_id,)
                )
                name = product["name"] if product else "This medicine"
                raise InsufficientStockError(
                    f"{name}: only {available} in stock (not expired), {quantity} asked for."
                )
            if picked:
                batch, take = picked[-1]
                picked[-1] = (batch, take + remaining)
            else:
                fallback = self.db.query_one(
                    self._SELECT
                    + " WHERE b.product_id = ? ORDER BY (b.expiry_date IS NULL), "
                    "b.expiry_date DESC LIMIT 1",
                    (product_id,),
                )
                if fallback is None:
                    raise InsufficientStockError(
                        "This medicine has no batch on file yet. Receive stock first."
                    )
                picked.append((fallback, remaining))
        return picked

    def consume(self, batch_id: int, quantity: int) -> None:
        self.db.execute(
            "UPDATE batches SET quantity = quantity - ? WHERE id = ?", (quantity, batch_id)
        )

    def restore(self, batch_id: int, quantity: int) -> None:
        self.db.execute(
            "UPDATE batches SET quantity = quantity + ? WHERE id = ?", (quantity, batch_id)
        )

    # ------------------------------------------------------------ adjustments
    def adjust(
        self,
        *,
        batch_id: int,
        quantity: int,
        reason: str,
        note: str = "",
        user=None,
    ) -> None:
        """Change a batch's quantity by ``quantity`` (negative removes units)."""
        if quantity == 0:
            raise ValidationError("Enter how many units to add or remove.")
        if not reason:
            raise ValidationError("Choose a reason for the adjustment.")
        batch = self.get_batch(batch_id)
        if int(batch["quantity"]) + quantity < 0:
            raise ValidationError(
                f"Only {batch['quantity']} units are on hand in batch {batch['batch_no']}."
            )
        with self.db.transaction() as conn:
            conn.execute(
                "UPDATE batches SET quantity = quantity + ? WHERE id = ?",
                (quantity, batch_id),
            )
            conn.execute(
                "INSERT INTO stock_adjustments "
                "(created_at, product_id, batch_id, user_id, quantity, reason, note) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    dates.now_iso(),
                    batch["product_id"],
                    batch_id,
                    getattr(user, "id", None),
                    quantity,
                    reason,
                    note or None,
                ),
            )
        self.audit.log(
            "stock.adjust",
            user=user,
            entity="batch",
            entity_id=batch_id,
            details=f"{batch['product_name']} {quantity:+d} ({reason})",
        )

    def adjustments(self, limit: int = 300) -> list:
        return self.db.query(
            """
            SELECT a.*, p.name AS product_name, b.batch_no, u.username
            FROM stock_adjustments a
            JOIN products p ON p.id = a.product_id
            LEFT JOIN batches b ON b.id = a.batch_id
            LEFT JOIN users u ON u.id = a.user_id
            ORDER BY a.id DESC LIMIT ?
            """,
            (limit,),
        )

    def write_off_expired(self, user=None) -> dict:
        """Clear every expired batch off the shelf in one action."""
        expired = self.list_batches(view="expired")
        units = 0
        value = 0
        for batch in expired:
            quantity = int(batch["quantity"])
            self.adjust(
                batch_id=int(batch["id"]),
                quantity=-quantity,
                reason="Expired — written off",
                note=f"Expiry {batch['expiry_date']}",
                user=user,
            )
            units += quantity
            value += quantity * int(batch["purchase_price"])
        return {"batches": len(expired), "units": units, "cost_value": value}

    # ----------------------------------------------------------------- alerts
    def low_stock(self, limit: int | None = None) -> list:
        sql = """
            SELECT p.id, p.name, p.unit_label, p.reorder_level, p.sale_price,
                   m.name AS manufacturer_name,
                   COALESCE(s.quantity, 0) AS stock_quantity
            FROM products p
            LEFT JOIN product_stock s ON s.product_id = p.id
            LEFT JOIN manufacturers m ON m.id = p.manufacturer_id
            WHERE p.is_active = 1 AND p.reorder_level > 0
              AND COALESCE(s.quantity, 0) <= p.reorder_level
            ORDER BY (COALESCE(s.quantity, 0) * 1.0 / p.reorder_level), p.name
        """
        if limit:
            sql += f" LIMIT {int(limit)}"
        return self.db.query(sql)

    def out_of_stock(self, limit: int | None = None) -> list:
        sql = """
            SELECT p.id, p.name, p.unit_label, m.name AS manufacturer_name
            FROM products p
            LEFT JOIN product_stock s ON s.product_id = p.id
            LEFT JOIN manufacturers m ON m.id = p.manufacturer_id
            WHERE p.is_active = 1 AND COALESCE(s.quantity, 0) <= 0
            ORDER BY p.name
        """
        if limit:
            sql += f" LIMIT {int(limit)}"
        return self.db.query(sql)

    def expiring_soon(self, days: int = 90, limit: int | None = None) -> list:
        return self.list_batches(view="expiring", expiry_days=days, limit=limit)

    def expired(self, limit: int | None = None) -> list:
        return self.list_batches(view="expired", limit=limit)

    def stock_value(self) -> dict:
        row = self.db.query_one(
            """
            SELECT COALESCE(SUM(b.quantity), 0) AS units,
                   COALESCE(SUM(b.quantity * b.purchase_price), 0) AS cost_value,
                   COALESCE(SUM(b.quantity * CASE WHEN b.sale_price > 0
                        THEN b.sale_price ELSE p.sale_price END), 0) AS retail_value
            FROM batches b JOIN products p ON p.id = b.product_id
            WHERE b.quantity > 0
            """
        )
        return {
            "units": int(row["units"]),
            "cost_value": int(row["cost_value"]),
            "retail_value": int(row["retail_value"]),
        }
