"""Selling: the cart at the counter, the invoice it becomes, and returns.

The cart is a plain Python object with no database or Qt in it, so the whole of
the money arithmetic — the 10% discount included — is testable on its own. It
only touches the database at the moment the sale is completed, and then
everything (invoice, lines, stock movements, customer ledger) is written inside
a single transaction: a power cut half way through leaves no half-sold stock.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Iterable

from .. import dates
from ..db import Database
from ..errors import NotFoundError, ValidationError
from ..money import percent_of, round_to_rupee
from .audit import AuditService
from .inventory import InventoryService
from .parties import PartyService
from .settings import SettingsService

PAYMENT_METHODS = ("Cash", "Card", "Easypaisa / JazzCash", "Bank transfer", "Credit")


@dataclass
class CartLine:
    """One row of the bill — always tied to a single batch."""

    product_id: int
    product_name: str
    batch_id: int | None
    batch_no: str
    expiry_date: str | None
    unit_price: int
    quantity: int = 1
    discount_percent: float = 0.0
    tax_percent: float = 0.0
    unit_cost: int = 0
    unit_label: str = "Unit"
    available: int = 0
    prescription_required: bool = False

    @property
    def gross(self) -> int:
        return self.unit_price * self.quantity

    @property
    def discount_amount(self) -> int:
        return percent_of(self.gross, self.discount_percent)

    @property
    def taxable(self) -> int:
        return self.gross - self.discount_amount

    @property
    def tax_amount(self) -> int:
        return percent_of(self.taxable, self.tax_percent)

    @property
    def total(self) -> int:
        return self.taxable + self.tax_amount

    def as_dict(self) -> dict:
        return {
            "product_id": self.product_id,
            "product_name": self.product_name,
            "batch_id": self.batch_id,
            "batch_no": self.batch_no,
            "expiry_date": self.expiry_date,
            "unit_price": self.unit_price,
            "quantity": self.quantity,
            "discount_percent": self.discount_percent,
            "tax_percent": self.tax_percent,
            "unit_cost": self.unit_cost,
            "unit_label": self.unit_label,
            "available": self.available,
            "prescription_required": self.prescription_required,
        }


@dataclass
class Cart:
    """The bill being built at the counter."""

    lines: list[CartLine] = field(default_factory=list)
    customer_id: int | None = None
    customer_name: str = ""
    doctor_name: str = ""
    notes: str = ""
    extra_discount: int = 0
    round_off_enabled: bool = True

    # ----------------------------------------------------------- line access
    def __len__(self) -> int:
        return len(self.lines)

    @property
    def is_empty(self) -> bool:
        return not self.lines

    @property
    def total_units(self) -> int:
        return sum(line.quantity for line in self.lines)

    def line_for_batch(self, batch_id: int | None, unit_price: int) -> CartLine | None:
        for line in self.lines:
            if line.batch_id == batch_id and line.unit_price == unit_price:
                return line
        return None

    def quantity_from_batch(self, batch_id: int | None) -> int:
        return sum(line.quantity for line in self.lines if line.batch_id == batch_id)

    def remove(self, index: int) -> None:
        if 0 <= index < len(self.lines):
            self.lines.pop(index)

    def clear(self) -> None:
        self.lines.clear()
        self.customer_id = None
        self.customer_name = ""
        self.doctor_name = ""
        self.notes = ""
        self.extra_discount = 0

    def set_discount_percent(self, percent: float) -> None:
        for line in self.lines:
            line.discount_percent = percent

    # --------------------------------------------------------------- totals
    @property
    def gross_amount(self) -> int:
        return sum(line.gross for line in self.lines)

    @property
    def line_discount(self) -> int:
        return sum(line.discount_amount for line in self.lines)

    @property
    def discount_amount(self) -> int:
        return self.line_discount + self.extra_discount

    @property
    def tax_amount(self) -> int:
        return sum(line.tax_amount for line in self.lines)

    @property
    def cost_amount(self) -> int:
        return sum(line.unit_cost * line.quantity for line in self.lines)

    @property
    def subtotal(self) -> int:
        """Everything charged, before the cash round-off."""
        return sum(line.total for line in self.lines) - self.extra_discount

    @property
    def round_off(self) -> int:
        if not self.round_off_enabled:
            return 0
        return round_to_rupee(self.subtotal) - self.subtotal

    @property
    def net_amount(self) -> int:
        return self.subtotal + self.round_off

    @property
    def savings(self) -> int:
        """What the customer saved — the number the receipt shouts about."""
        return self.discount_amount

    def to_json(self) -> str:
        return json.dumps(
            {
                "lines": [line.as_dict() for line in self.lines],
                "customer_id": self.customer_id,
                "customer_name": self.customer_name,
                "doctor_name": self.doctor_name,
                "notes": self.notes,
                "extra_discount": self.extra_discount,
            }
        )

    @classmethod
    def from_json(cls, payload: str) -> "Cart":
        data = json.loads(payload)
        cart = cls(
            customer_id=data.get("customer_id"),
            customer_name=data.get("customer_name", ""),
            doctor_name=data.get("doctor_name", ""),
            notes=data.get("notes", ""),
            extra_discount=int(data.get("extra_discount") or 0),
        )
        cart.lines = [CartLine(**line) for line in data.get("lines", [])]
        return cart


class SalesService:
    def __init__(
        self,
        db: Database,
        settings: SettingsService,
        inventory: InventoryService | None = None,
        parties: PartyService | None = None,
        audit: AuditService | None = None,
    ):
        self.db = db
        self.settings = settings
        self.audit = audit or AuditService(db)
        self.inventory = inventory or InventoryService(db, self.audit)
        self.parties = parties or PartyService(db, self.audit)

    # ------------------------------------------------------------- cart help
    def new_cart(self) -> Cart:
        return Cart(round_off_enabled=self.settings.get_bool("round_off_totals", True))

    def add_to_cart(
        self,
        cart: Cart,
        product,
        quantity: int = 1,
        *,
        batch_id: int | None = None,
        unit_price: int | None = None,
        discount_percent: float | None = None,
    ) -> list[CartLine]:
        """Add a medicine to the bill, splitting across batches FEFO-first.

        Passing ``batch_id`` pins the sale to one batch (the counter staff picked
        it by hand); otherwise the batch expiring first is used up before the
        next one is opened.
        """
        quantity = int(quantity)
        if quantity <= 0:
            raise ValidationError("Quantity must be at least 1.")
        product_id = int(product["id"])
        default_discount = (
            discount_percent
            if discount_percent is not None
            else (self.settings.discount_percent if product["discount_eligible"] else 0.0)
        )
        allow_negative = self.settings.get_bool("allow_negative_stock", False)

        if batch_id is not None:
            batch = self.inventory.get_batch(batch_id)
            candidates: list[tuple[Any, int]] = [(batch, quantity)]
        else:
            available = self._free_stock(cart, product_id)
            if quantity > available and not allow_negative:
                raise ValidationError(
                    f"{product['name']}: only {available} {product['unit_label'].lower()}(s) "
                    "left that are not expired or already on this bill."
                )
            candidates = self._split_fefo(cart, product_id, quantity, allow_negative)

        touched: list[CartLine] = []
        for batch, take in candidates:
            price = (
                unit_price
                if unit_price is not None
                else int(batch["sale_price"] or 0) or int(product["sale_price"])
            )
            line = cart.line_for_batch(int(batch["id"]), price)
            if line is None:
                line = CartLine(
                    product_id=product_id,
                    product_name=product["name"],
                    batch_id=int(batch["id"]),
                    batch_no=batch["batch_no"],
                    expiry_date=batch["expiry_date"],
                    unit_price=price,
                    quantity=0,
                    discount_percent=default_discount,
                    tax_percent=float(product["tax_percent"] or 0),
                    unit_cost=int(batch["purchase_price"] or product["purchase_price"] or 0),
                    unit_label=product["unit_label"],
                    available=int(batch["quantity"]),
                    prescription_required=bool(product["prescription_required"]),
                )
                cart.lines.append(line)
            line.quantity += take
            touched.append(line)
        return touched

    def _free_stock(self, cart: Cart, product_id: int) -> int:
        on_hand = self.inventory.sellable_on_hand(product_id)
        in_cart = sum(line.quantity for line in cart.lines if line.product_id == product_id)
        return on_hand - in_cart

    def _split_fefo(
        self, cart: Cart, product_id: int, quantity: int, allow_negative: bool
    ) -> list[tuple[Any, int]]:
        batches = self.db.query(
            "SELECT * FROM batches WHERE product_id = ? AND quantity > 0 "
            "AND (expiry_date IS NULL OR expiry_date >= date('now')) "
            "ORDER BY (expiry_date IS NULL), expiry_date, id",
            (product_id,),
        )
        picked: list[tuple[Any, int]] = []
        remaining = quantity
        for batch in batches:
            free = int(batch["quantity"]) - cart.quantity_from_batch(int(batch["id"]))
            if free <= 0:
                continue
            take = min(free, remaining)
            picked.append((batch, take))
            remaining -= take
            if remaining == 0:
                break
        if remaining > 0:
            if not allow_negative:
                raise ValidationError("Not enough stock for that quantity.")
            if picked:
                batch, take = picked[-1]
                picked[-1] = (batch, take + remaining)
            else:
                any_batch = self.db.query_one(
                    "SELECT * FROM batches WHERE product_id = ? ORDER BY id DESC LIMIT 1",
                    (product_id,),
                )
                if any_batch is None:
                    raise ValidationError(
                        "This medicine has no batch on file. Receive stock for it first."
                    )
                picked.append((any_batch, remaining))
        return picked

    def set_line_quantity(self, cart: Cart, index: int, quantity: int) -> None:
        line = cart.lines[index]
        quantity = int(quantity)
        if quantity <= 0:
            cart.remove(index)
            return
        if not self.settings.get_bool("allow_negative_stock", False):
            other = cart.quantity_from_batch(line.batch_id) - line.quantity
            in_batch = int(
                self.db.scalar(
                    "SELECT quantity FROM batches WHERE id = ?", (line.batch_id,), 0
                )
            )
            if quantity + other > in_batch:
                raise ValidationError(
                    f"Batch {line.batch_no} of {line.product_name} has only "
                    f"{in_batch - other} left."
                )
        line.quantity = quantity

    # ---------------------------------------------------------- complete sale
    def complete_sale(
        self,
        cart: Cart,
        *,
        user,
        paid_amount: int,
        payment_method: str = "Cash",
        sale_date: str | None = None,
    ) -> int:
        """Write the bill and take the stock off the shelf. Returns the sale id."""
        if cart.is_empty:
            raise ValidationError("There is nothing on the bill yet.")
        for line in cart.lines:
            if line.quantity <= 0:
                raise ValidationError(f"{line.product_name} has a quantity of zero.")
        net = cart.net_amount
        paid = int(paid_amount)
        if paid < 0:
            raise ValidationError("Paid amount cannot be negative.")
        credit_amount = max(net - paid, 0)
        if credit_amount and not cart.customer_id:
            raise ValidationError(
                "An unpaid balance has to be charged to a named customer. "
                "Pick a customer, or take the full amount."
            )
        change = max(paid - net, 0) if payment_method != "Credit" else 0
        if payment_method == "Credit":
            paid = min(paid, net)

        stamp = sale_date or dates.now_iso()
        invoice_no = self.db.next_document_number(
            "sale", self.settings.get("invoice_prefix", "INV-")
        )
        with self.db.transaction() as conn:
            cursor = conn.execute(
                """INSERT INTO sales (invoice_no, sale_date, customer_id, customer_name,
                        doctor_name, user_id, gross_amount, discount_amount, tax_amount,
                        round_off, net_amount, cost_amount, paid_amount, change_amount,
                        payment_method, status, notes)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    invoice_no,
                    stamp,
                    cart.customer_id,
                    cart.customer_name or None,
                    cart.doctor_name or None,
                    getattr(user, "id", None),
                    cart.gross_amount,
                    cart.discount_amount,
                    cart.tax_amount,
                    cart.round_off,
                    net,
                    cart.cost_amount,
                    paid,
                    change,
                    payment_method,
                    "completed",
                    cart.notes or None,
                ),
            )
            sale_id = int(cursor.lastrowid)
            for line in cart.lines:
                conn.execute(
                    """INSERT INTO sale_items (sale_id, product_id, batch_id, product_name,
                            batch_no, expiry_date, quantity, unit_price, unit_cost,
                            discount_percent, discount_amount, tax_percent, tax_amount,
                            line_total)
                       VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                    (
                        sale_id,
                        line.product_id,
                        line.batch_id,
                        line.product_name,
                        line.batch_no,
                        line.expiry_date,
                        line.quantity,
                        line.unit_price,
                        line.unit_cost,
                        line.discount_percent,
                        line.discount_amount,
                        line.tax_percent,
                        line.tax_amount,
                        line.total,
                    ),
                )
                if line.batch_id:
                    conn.execute(
                        "UPDATE batches SET quantity = quantity - ? WHERE id = ?",
                        (line.quantity, line.batch_id),
                    )
            if cart.customer_id:
                self.parties.add_entry(
                    cart.customer_id,
                    doc_type="sale",
                    doc_id=sale_id,
                    description=f"Invoice {invoice_no}",
                    debit=net,
                    credit=paid,
                    reference=invoice_no,
                    entry_date=stamp,
                )
        self.audit.log(
            "sale.complete",
            user=user,
            entity="sale",
            entity_id=sale_id,
            details=f"{invoice_no} — {net / 100:.2f} ({len(cart.lines)} items)",
        )
        return sale_id

    # ------------------------------------------------------------- retrieval
    def get_sale(self, sale_id: int):
        row = self.db.query_one(
            """SELECT s.*, u.full_name AS cashier_name, u.username,
                      p.name AS party_name, p.phone AS party_phone, p.address AS party_address
               FROM sales s
               LEFT JOIN users u ON u.id = s.user_id
               LEFT JOIN parties p ON p.id = s.customer_id
               WHERE s.id = ?""",
            (sale_id,),
        )
        if row is None:
            raise NotFoundError("That invoice no longer exists.")
        return row

    def find_by_invoice(self, invoice_no: str):
        row = self.db.query_one(
            "SELECT id FROM sales WHERE invoice_no = ? COLLATE NOCASE",
            (invoice_no.strip(),),
        )
        return self.get_sale(int(row["id"])) if row else None

    def sale_items(self, sale_id: int) -> list:
        return self.db.query(
            "SELECT * FROM sale_items WHERE sale_id = ? ORDER BY id", (sale_id,)
        )

    def list_sales(
        self,
        *,
        date_from: str = "",
        date_to: str = "",
        search: str = "",
        user_id: int | None = None,
        customer_id: int | None = None,
        limit: int = 500,
    ) -> list:
        clauses: list[str] = []
        params: list[Any] = []
        if date_from:
            clauses.append("s.sale_date >= ?")
            params.append(date_from)
        if date_to:
            clauses.append("s.sale_date <= ?")
            params.append(date_to + " 23:59:59")
        if search:
            like = f"%{search}%"
            clauses.append("(s.invoice_no LIKE ? OR s.customer_name LIKE ? OR p.name LIKE ?)")
            params += [like, like, like]
        if user_id:
            clauses.append("s.user_id = ?")
            params.append(user_id)
        if customer_id:
            clauses.append("s.customer_id = ?")
            params.append(customer_id)
        sql = """
            SELECT s.*, u.username, p.name AS party_name
            FROM sales s
            LEFT JOIN users u ON u.id = s.user_id
            LEFT JOIN parties p ON p.id = s.customer_id
        """
        if clauses:
            sql += " WHERE " + " AND ".join(clauses)
        sql += " ORDER BY s.id DESC LIMIT ?"
        params.append(limit)
        return self.db.query(sql, params)

    def delete_sale(self, sale_id: int, *, user=None, restock: bool = True) -> None:
        """Cancel an invoice completely (owner only) and put the stock back."""
        sale = self.get_sale(sale_id)
        with self.db.transaction() as conn:
            if restock:
                for item in self.sale_items(sale_id):
                    if item["batch_id"]:
                        net_qty = int(item["quantity"]) - int(item["returned_quantity"])
                        if net_qty:
                            conn.execute(
                                "UPDATE batches SET quantity = quantity + ? WHERE id = ?",
                                (net_qty, item["batch_id"]),
                            )
            conn.execute(
                "DELETE FROM ledger_entries WHERE doc_type = 'sale' AND doc_id = ?",
                (sale_id,),
            )
            conn.execute("DELETE FROM sales WHERE id = ?", (sale_id,))
        self.audit.log(
            "sale.delete",
            user=user,
            entity="sale",
            entity_id=sale_id,
            details=f"{sale['invoice_no']} cancelled",
        )

    # --------------------------------------------------------------- returns
    def create_return(
        self,
        sale_id: int,
        items: Iterable[dict],
        *,
        user,
        reason: str = "",
        restock: bool = True,
    ) -> int:
        """Take goods back against an invoice.

        ``items`` is ``[{'sale_item_id': int, 'quantity': int}, ...]``. The
        refund keeps the discount the customer originally got, so a 10% bill
        refunds 10% less than list price.
        """
        sale = self.get_sale(sale_id)
        originals = {int(row["id"]): row for row in self.sale_items(sale_id)}
        prepared: list[tuple[Any, int, int]] = []
        for entry in items:
            item_id = int(entry["sale_item_id"])
            quantity = int(entry.get("quantity") or 0)
            if quantity <= 0:
                continue
            item = originals.get(item_id)
            if item is None:
                raise ValidationError("That line is not on this invoice.")
            returnable = int(item["quantity"]) - int(item["returned_quantity"])
            if quantity > returnable:
                raise ValidationError(
                    f"{item['product_name']}: only {returnable} can still be returned."
                )
            unit_refund = round(int(item["line_total"]) / int(item["quantity"]))
            prepared.append((item, quantity, unit_refund * quantity))
        if not prepared:
            raise ValidationError("Enter how many units are coming back.")

        total_refund = sum(refund for _, _, refund in prepared)
        return_no = self.db.next_document_number(
            "sale_return", self.settings.get("sale_return_prefix", "SR-")
        )
        stamp = dates.now_iso()
        with self.db.transaction() as conn:
            cursor = conn.execute(
                "INSERT INTO sale_returns (return_no, sale_id, return_date, user_id, "
                "total_amount, restocked, reason) VALUES (?,?,?,?,?,?,?)",
                (
                    return_no,
                    sale_id,
                    stamp,
                    getattr(user, "id", None),
                    total_refund,
                    1 if restock else 0,
                    reason or None,
                ),
            )
            return_id = int(cursor.lastrowid)
            for item, quantity, refund in prepared:
                conn.execute(
                    "INSERT INTO sale_return_items (return_id, sale_item_id, product_id, "
                    "batch_id, product_name, quantity, unit_price, refund_amount) "
                    "VALUES (?,?,?,?,?,?,?,?)",
                    (
                        return_id,
                        int(item["id"]),
                        item["product_id"],
                        item["batch_id"],
                        item["product_name"],
                        quantity,
                        item["unit_price"],
                        refund,
                    ),
                )
                conn.execute(
                    "UPDATE sale_items SET returned_quantity = returned_quantity + ? "
                    "WHERE id = ?",
                    (quantity, int(item["id"])),
                )
                if restock and item["batch_id"]:
                    conn.execute(
                        "UPDATE batches SET quantity = quantity + ? WHERE id = ?",
                        (quantity, item["batch_id"]),
                    )
            fully_returned = all(
                int(row["quantity"]) <= int(row["returned_quantity"])
                for row in conn.execute(
                    "SELECT quantity, returned_quantity FROM sale_items WHERE sale_id = ?",
                    (sale_id,),
                ).fetchall()
            )
            conn.execute(
                "UPDATE sales SET status = ? WHERE id = ?",
                ("returned" if fully_returned else "part-returned", sale_id),
            )
            if sale["customer_id"]:
                self.parties.add_entry(
                    int(sale["customer_id"]),
                    doc_type="sale_return",
                    doc_id=return_id,
                    description=f"Return {return_no} against {sale['invoice_no']}",
                    credit=total_refund,
                    reference=return_no,
                    entry_date=stamp,
                )
        self.audit.log(
            "sale.return",
            user=user,
            entity="sale",
            entity_id=sale_id,
            details=f"{return_no} — {total_refund / 100:.2f}",
        )
        return return_id

    def list_returns(self, date_from: str = "", date_to: str = "", limit: int = 300) -> list:
        clauses: list[str] = []
        params: list[Any] = []
        if date_from:
            clauses.append("r.return_date >= ?")
            params.append(date_from)
        if date_to:
            clauses.append("r.return_date <= ?")
            params.append(date_to + " 23:59:59")
        sql = """
            SELECT r.*, s.invoice_no, s.customer_name, u.username
            FROM sale_returns r
            JOIN sales s ON s.id = r.sale_id
            LEFT JOIN users u ON u.id = r.user_id
        """
        if clauses:
            sql += " WHERE " + " AND ".join(clauses)
        sql += " ORDER BY r.id DESC LIMIT ?"
        params.append(limit)
        return self.db.query(sql, params)

    def return_items(self, return_id: int) -> list:
        return self.db.query(
            "SELECT * FROM sale_return_items WHERE return_id = ? ORDER BY id", (return_id,)
        )

    # ------------------------------------------------------------ held bills
    def hold_cart(self, cart: Cart, label: str, user=None) -> int:
        if cart.is_empty:
            raise ValidationError("There is nothing to hold.")
        return self.db.insert(
            "held_sales",
            {
                "label": label or dates.fmt_datetime(dates.now_iso()),
                "created_at": dates.now_iso(),
                "user_id": getattr(user, "id", None),
                "payload": cart.to_json(),
            },
        )

    def held_carts(self) -> list:
        return self.db.query(
            "SELECT h.*, u.username FROM held_sales h "
            "LEFT JOIN users u ON u.id = h.user_id ORDER BY h.id DESC"
        )

    def resume_cart(self, held_id: int) -> Cart:
        row = self.db.query_one("SELECT * FROM held_sales WHERE id = ?", (held_id,))
        if row is None:
            raise NotFoundError("That held bill is gone.")
        cart = Cart.from_json(row["payload"])
        cart.round_off_enabled = self.settings.get_bool("round_off_totals", True)
        self.db.execute("DELETE FROM held_sales WHERE id = ?", (held_id,))
        return cart

    def discard_held(self, held_id: int) -> None:
        self.db.execute("DELETE FROM held_sales WHERE id = ?", (held_id,))
