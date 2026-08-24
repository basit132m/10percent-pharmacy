"""Buying: supplier bills, goods received into batches, and returns to supplier.

Receiving is where batch numbers and expiry dates enter the system, so this is
the one place that creates stock out of nothing. Everything else only moves it.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable

from .. import dates
from ..db import Database
from ..errors import NotFoundError, ValidationError
from ..money import percent_of
from .audit import AuditService
from .catalog import CatalogService
from .inventory import InventoryService
from .parties import PartyService
from .settings import SettingsService


@dataclass
class PurchaseLine:
    """One line of a supplier bill, in base units (tablets, bottles, …)."""

    product_id: int
    product_name: str
    quantity: int
    unit_cost: int
    batch_no: str = "-"
    expiry_date: str | None = None
    bonus_quantity: int = 0
    unit_sale_price: int = 0
    discount_percent: float = 0.0
    tax_percent: float = 0.0

    @property
    def gross(self) -> int:
        return self.unit_cost * self.quantity

    @property
    def discount_amount(self) -> int:
        return percent_of(self.gross, self.discount_percent)

    @property
    def tax_amount(self) -> int:
        return percent_of(self.gross - self.discount_amount, self.tax_percent)

    @property
    def total(self) -> int:
        return self.gross - self.discount_amount + self.tax_amount

    @property
    def received_quantity(self) -> int:
        return self.quantity + self.bonus_quantity

    @property
    def effective_unit_cost(self) -> int:
        """Bill total spread over every unit received, bonus units included."""
        units = self.received_quantity
        return round(self.total / units) if units else 0


@dataclass
class PurchaseDraft:
    supplier_id: int | None = None
    supplier_bill_no: str = ""
    purchase_date: str = field(default_factory=dates.today_iso)
    notes: str = ""
    lines: list[PurchaseLine] = field(default_factory=list)

    @property
    def gross_amount(self) -> int:
        return sum(line.gross for line in self.lines)

    @property
    def discount_amount(self) -> int:
        return sum(line.discount_amount for line in self.lines)

    @property
    def tax_amount(self) -> int:
        return sum(line.tax_amount for line in self.lines)

    @property
    def net_amount(self) -> int:
        return sum(line.total for line in self.lines)

    @property
    def total_units(self) -> int:
        return sum(line.received_quantity for line in self.lines)


class PurchaseService:
    def __init__(
        self,
        db: Database,
        settings: SettingsService,
        inventory: InventoryService | None = None,
        parties: PartyService | None = None,
        catalog: CatalogService | None = None,
        audit: AuditService | None = None,
    ):
        self.db = db
        self.settings = settings
        self.audit = audit or AuditService(db)
        self.inventory = inventory or InventoryService(db, self.audit)
        self.parties = parties or PartyService(db, self.audit)
        self.catalog = catalog or CatalogService(db, self.audit)

    # --------------------------------------------------------------- receive
    def create_purchase(
        self,
        draft: PurchaseDraft,
        *,
        user,
        paid_amount: int = 0,
        update_product_prices: bool = True,
    ) -> int:
        if not draft.lines:
            raise ValidationError("Add at least one medicine to the bill.")
        for line in draft.lines:
            if line.quantity <= 0:
                raise ValidationError(f"{line.product_name}: quantity must be more than 0.")
            if line.unit_cost < 0:
                raise ValidationError(f"{line.product_name}: cost cannot be negative.")
        net = draft.net_amount
        paid = max(0, int(paid_amount))
        if paid > net:
            raise ValidationError("Paid amount is more than the bill total.")

        reference_no = self.db.next_document_number(
            "purchase", self.settings.get("purchase_prefix", "PUR-")
        )
        purchase_date = dates.to_iso(draft.purchase_date) or dates.today_iso()
        with self.db.transaction() as conn:
            cursor = conn.execute(
                """INSERT INTO purchases (reference_no, supplier_bill_no, purchase_date,
                        supplier_id, user_id, gross_amount, discount_amount, tax_amount,
                        net_amount, paid_amount, status, notes)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    reference_no,
                    draft.supplier_bill_no or None,
                    purchase_date,
                    draft.supplier_id,
                    getattr(user, "id", None),
                    draft.gross_amount,
                    draft.discount_amount,
                    draft.tax_amount,
                    net,
                    paid,
                    "received",
                    draft.notes or None,
                ),
            )
            purchase_id = int(cursor.lastrowid)
            for line in draft.lines:
                batch_id = self.inventory.add_stock(
                    product_id=line.product_id,
                    quantity=line.received_quantity,
                    batch_no=line.batch_no,
                    expiry_date=line.expiry_date,
                    purchase_price=line.effective_unit_cost,
                    sale_price=line.unit_sale_price,
                    source="purchase",
                )
                conn.execute(
                    """INSERT INTO purchase_items (purchase_id, product_id, batch_id,
                            product_name, batch_no, expiry_date, quantity, bonus_quantity,
                            unit_cost, unit_sale_price, discount_percent, tax_percent,
                            line_total)
                       VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                    (
                        purchase_id,
                        line.product_id,
                        batch_id,
                        line.product_name,
                        line.batch_no,
                        dates.to_iso(line.expiry_date),
                        line.quantity,
                        line.bonus_quantity,
                        line.unit_cost,
                        line.unit_sale_price,
                        line.discount_percent,
                        line.tax_percent,
                        line.total,
                    ),
                )
                if update_product_prices and line.unit_sale_price:
                    self.catalog.update_prices(
                        line.product_id, line.effective_unit_cost, line.unit_sale_price
                    )
            if draft.supplier_id:
                self.parties.add_entry(
                    draft.supplier_id,
                    doc_type="purchase",
                    doc_id=purchase_id,
                    description=f"Purchase {reference_no}"
                    + (f" (bill {draft.supplier_bill_no})" if draft.supplier_bill_no else ""),
                    credit=net,
                    debit=paid,
                    reference=reference_no,
                    entry_date=purchase_date,
                )
        self.audit.log(
            "purchase.create",
            user=user,
            entity="purchase",
            entity_id=purchase_id,
            details=f"{reference_no} — {net / 100:.2f} ({len(draft.lines)} items)",
        )
        return purchase_id

    # ------------------------------------------------------------- retrieval
    def get_purchase(self, purchase_id: int):
        row = self.db.query_one(
            """SELECT pu.*, p.name AS supplier_name, p.phone AS supplier_phone,
                      u.username
               FROM purchases pu
               LEFT JOIN parties p ON p.id = pu.supplier_id
               LEFT JOIN users u ON u.id = pu.user_id
               WHERE pu.id = ?""",
            (purchase_id,),
        )
        if row is None:
            raise NotFoundError("That purchase no longer exists.")
        return row

    def purchase_items(self, purchase_id: int) -> list:
        return self.db.query(
            "SELECT * FROM purchase_items WHERE purchase_id = ? ORDER BY id", (purchase_id,)
        )

    def list_purchases(
        self,
        *,
        date_from: str = "",
        date_to: str = "",
        supplier_id: int | None = None,
        search: str = "",
        limit: int = 500,
    ) -> list:
        clauses: list[str] = []
        params: list[Any] = []
        if date_from:
            clauses.append("pu.purchase_date >= ?")
            params.append(date_from)
        if date_to:
            clauses.append("pu.purchase_date <= ?")
            params.append(date_to)
        if supplier_id:
            clauses.append("pu.supplier_id = ?")
            params.append(supplier_id)
        if search:
            like = f"%{search}%"
            clauses.append(
                "(pu.reference_no LIKE ? OR pu.supplier_bill_no LIKE ? OR p.name LIKE ?)"
            )
            params += [like, like, like]
        sql = """
            SELECT pu.*, p.name AS supplier_name, u.username
            FROM purchases pu
            LEFT JOIN parties p ON p.id = pu.supplier_id
            LEFT JOIN users u ON u.id = pu.user_id
        """
        if clauses:
            sql += " WHERE " + " AND ".join(clauses)
        sql += " ORDER BY pu.id DESC LIMIT ?"
        params.append(limit)
        return self.db.query(sql, params)

    def delete_purchase(self, purchase_id: int, *, user=None) -> None:
        """Undo a wrongly entered bill, taking the received units back off."""
        purchase = self.get_purchase(purchase_id)
        items = self.purchase_items(purchase_id)
        for item in items:
            if not item["batch_id"]:
                continue
            on_hand = int(
                self.db.scalar("SELECT quantity FROM batches WHERE id = ?", (item["batch_id"],))
            )
            received = int(item["quantity"]) + int(item["bonus_quantity"])
            if on_hand < received:
                raise ValidationError(
                    f"{item['product_name']}: part of this batch has already been sold, "
                    "so the purchase cannot be deleted. Use a purchase return instead."
                )
        with self.db.transaction() as conn:
            for item in items:
                if item["batch_id"]:
                    conn.execute(
                        "UPDATE batches SET quantity = quantity - ? WHERE id = ?",
                        (int(item["quantity"]) + int(item["bonus_quantity"]), item["batch_id"]),
                    )
            conn.execute(
                "DELETE FROM ledger_entries WHERE doc_type = 'purchase' AND doc_id = ?",
                (purchase_id,),
            )
            conn.execute("DELETE FROM purchases WHERE id = ?", (purchase_id,))
        self.audit.log(
            "purchase.delete",
            user=user,
            entity="purchase",
            entity_id=purchase_id,
            details=purchase["reference_no"],
        )

    # -------------------------------------------------------------- returns
    def return_to_supplier(
        self,
        supplier_id: int | None,
        items: Iterable[dict],
        *,
        user,
        reason: str = "Returned to supplier",
    ) -> int:
        """Send stock back: units leave the shelf and the payable comes down.

        ``items`` is ``[{'batch_id': int, 'quantity': int}, ...]``.
        """
        prepared: list[tuple[Any, int, int]] = []
        for entry in items:
            batch = self.inventory.get_batch(int(entry["batch_id"]))
            quantity = int(entry.get("quantity") or 0)
            if quantity <= 0:
                continue
            if quantity > int(batch["quantity"]):
                raise ValidationError(
                    f"{batch['product_name']}: only {batch['quantity']} units in "
                    f"batch {batch['batch_no']}."
                )
            prepared.append((batch, quantity, quantity * int(batch["purchase_price"])))
        if not prepared:
            raise ValidationError("Choose at least one batch and quantity to return.")
        total = sum(value for _, _, value in prepared)
        with self.db.transaction():
            for batch, quantity, _ in prepared:
                self.inventory.adjust(
                    batch_id=int(batch["id"]),
                    quantity=-quantity,
                    reason="Returned to supplier",
                    note=reason,
                    user=user,
                )
            if supplier_id:
                self.parties.add_entry(
                    supplier_id,
                    doc_type="purchase_return",
                    doc_id=None,
                    description=reason,
                    debit=total,
                )
        self.audit.log(
            "purchase.return",
            user=user,
            entity="party",
            entity_id=supplier_id,
            details=f"{len(prepared)} batches — {total / 100:.2f}",
        )
        return total
