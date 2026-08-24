"""Customers and suppliers, with a running account for each.

Both live in one table because they behave the same way: a name, a phone
number and a balance that moves when a credit bill is raised or a payment is
made. Internally every balance is kept as *"what this party owes us"*, so a
supplier normally sits at a negative number; the UI flips the sign and calls it
**Payable**.
"""

from __future__ import annotations

from typing import Any

from .. import dates
from ..db import Database
from ..errors import NotFoundError, ValidationError
from .audit import AuditService

PAYMENT_METHODS = ("Cash", "Bank transfer", "Easypaisa / JazzCash", "Cheque", "Card")
WALK_IN_CUSTOMER = "Walk-in customer"


class PartyService:
    def __init__(self, db: Database, audit: AuditService | None = None):
        self.db = db
        self.audit = audit or AuditService(db)

    # ----------------------------------------------------------------- reads
    def list_parties(
        self,
        party_type: str,
        search: str = "",
        *,
        only_active: bool = True,
        with_balance: bool = True,
    ) -> list:
        clauses = ["p.type = ?"]
        params: list[Any] = [party_type]
        if only_active:
            clauses.append("p.is_active = 1")
        search = (search or "").strip()
        if search:
            like = f"%{search}%"
            clauses.append("(p.name LIKE ? OR p.phone LIKE ?)")
            params += [like, like]
        balance_sql = (
            """,
               (CASE WHEN p.type = 'customer' THEN p.opening_balance
                     ELSE -p.opening_balance END)
               + COALESCE((SELECT SUM(l.debit) - SUM(l.credit) FROM ledger_entries l
                           WHERE l.party_id = p.id), 0) AS balance"""
            if with_balance
            else ""
        )
        return self.db.query(
            f"SELECT p.*{balance_sql} FROM parties p WHERE "
            + " AND ".join(clauses)
            + " ORDER BY p.name",
            params,
        )

    def get(self, party_id: int):
        row = self.db.query_one("SELECT * FROM parties WHERE id = ?", (party_id,))
        if row is None:
            raise NotFoundError("That account no longer exists.")
        return row

    def find_by_phone(self, phone: str):
        phone = (phone or "").strip()
        if not phone:
            return None
        return self.db.query_one(
            "SELECT * FROM parties WHERE phone = ? AND type = 'customer'", (phone,)
        )

    def balance(self, party_id: int) -> int:
        """Signed balance in paisa: positive means the party owes us."""
        party = self.get(party_id)
        opening = int(party["opening_balance"])
        if party["type"] == "supplier":
            opening = -opening
        movement = self.db.scalar(
            "SELECT COALESCE(SUM(debit) - SUM(credit), 0) FROM ledger_entries "
            "WHERE party_id = ?",
            (party_id,),
        )
        return opening + int(movement)

    def ledger(self, party_id: int, date_from: str = "", date_to: str = "") -> list[dict]:
        """Ledger rows with a running balance, opening row first."""
        party = self.get(party_id)
        opening = int(party["opening_balance"])
        if party["type"] == "supplier":
            opening = -opening
        clauses = ["party_id = ?"]
        params: list[Any] = [party_id]
        if date_from:
            clauses.append("entry_date >= ?")
            params.append(date_from)
        if date_to:
            clauses.append("entry_date <= ?")
            params.append(date_to + " 23:59:59")
        rows = self.db.query(
            "SELECT * FROM ledger_entries WHERE "
            + " AND ".join(clauses)
            + " ORDER BY entry_date, id",
            params,
        )
        running = opening
        out: list[dict] = [
            {
                "entry_date": party["created_at"],
                "doc_type": "opening",
                "reference": "",
                "description": "Opening balance",
                "debit": max(opening, 0),
                "credit": max(-opening, 0),
                "balance": running,
            }
        ]
        for row in rows:
            running += int(row["debit"]) - int(row["credit"])
            out.append({**dict(row), "balance": running})
        return out

    def outstanding(self, party_type: str) -> list:
        """Accounts that still carry a balance, biggest first."""
        rows = self.list_parties(party_type, only_active=False)
        sign = 1 if party_type == "customer" else -1
        return sorted(
            [row for row in rows if sign * int(row["balance"]) > 0],
            key=lambda row: -sign * int(row["balance"]),
        )

    def total_outstanding(self, party_type: str) -> int:
        sign = 1 if party_type == "customer" else -1
        return sum(sign * int(row["balance"]) for row in self.outstanding(party_type))

    # ---------------------------------------------------------------- writes
    def create(self, party_type: str, values: dict[str, Any]) -> int:
        if party_type not in {"customer", "supplier"}:
            raise ValidationError(f"Unknown account type: {party_type}")
        name = (values.get("name") or "").strip()
        if not name:
            raise ValidationError("Name is required.")
        payload = {
            "type": party_type,
            "name": name,
            "phone": (values.get("phone") or "").strip() or None,
            "email": (values.get("email") or "").strip() or None,
            "address": (values.get("address") or "").strip() or None,
            "opening_balance": int(values.get("opening_balance") or 0),
            "credit_limit": int(values.get("credit_limit") or 0),
            "notes": (values.get("notes") or "").strip() or None,
            "is_active": 1,
            "created_at": dates.now_iso(),
        }
        party_id = self.db.insert("parties", payload)
        self.audit.log(
            f"{party_type}.create", entity="party", entity_id=party_id, details=name
        )
        return party_id

    def update(self, party_id: int, values: dict[str, Any]) -> None:
        name = (values.get("name") or "").strip()
        if not name:
            raise ValidationError("Name is required.")
        self.db.update(
            "parties",
            party_id,
            {
                "name": name,
                "phone": (values.get("phone") or "").strip() or None,
                "email": (values.get("email") or "").strip() or None,
                "address": (values.get("address") or "").strip() or None,
                "opening_balance": int(values.get("opening_balance") or 0),
                "credit_limit": int(values.get("credit_limit") or 0),
                "notes": (values.get("notes") or "").strip() or None,
            },
        )
        self.audit.log("party.update", entity="party", entity_id=party_id, details=name)

    def set_active(self, party_id: int, active: bool) -> None:
        self.db.update("parties", party_id, {"is_active": 1 if active else 0})

    def delete(self, party_id: int) -> None:
        used = self.db.scalar(
            "SELECT (SELECT COUNT(*) FROM sales WHERE customer_id = ?) "
            "     + (SELECT COUNT(*) FROM purchases WHERE supplier_id = ?) "
            "     + (SELECT COUNT(*) FROM ledger_entries WHERE party_id = ?)",
            (party_id, party_id, party_id),
        )
        if used:
            raise ValidationError(
                "This account has bills or payments against it. Mark it inactive "
                "instead of deleting it."
            )
        self.db.execute("DELETE FROM parties WHERE id = ?", (party_id,))
        self.audit.log("party.delete", entity="party", entity_id=party_id)

    # --------------------------------------------------------------- ledger
    def add_entry(
        self,
        party_id: int,
        *,
        doc_type: str,
        doc_id: int | None,
        description: str,
        debit: int = 0,
        credit: int = 0,
        reference: str = "",
        entry_date: str | None = None,
    ) -> int:
        return self.db.insert(
            "ledger_entries",
            {
                "party_id": party_id,
                "entry_date": entry_date or dates.now_iso(),
                "doc_type": doc_type,
                "doc_id": doc_id,
                "reference": reference or None,
                "description": description,
                "debit": int(debit),
                "credit": int(credit),
            },
        )

    def record_payment(
        self,
        party_id: int,
        *,
        amount: int,
        direction: str,
        method: str = "Cash",
        reference: str = "",
        note: str = "",
        user=None,
        paid_at: str | None = None,
    ) -> int:
        """``direction='in'`` is money received, ``'out'`` is money paid out."""
        if amount <= 0:
            raise ValidationError("Enter an amount greater than zero.")
        if direction not in {"in", "out"}:
            raise ValidationError("Payment direction must be 'in' or 'out'.")
        party = self.get(party_id)
        stamp = paid_at or dates.now_iso()
        with self.db.transaction():
            payment_id = self.db.insert(
                "payments",
                {
                    "party_id": party_id,
                    "direction": direction,
                    "amount": amount,
                    "method": method,
                    "paid_at": stamp,
                    "reference": reference or None,
                    "note": note or None,
                    "user_id": getattr(user, "id", None),
                },
            )
            self.add_entry(
                party_id,
                doc_type="payment",
                doc_id=payment_id,
                description=(
                    f"Payment received ({method})"
                    if direction == "in"
                    else f"Payment made ({method})"
                ),
                debit=amount if direction == "out" else 0,
                credit=amount if direction == "in" else 0,
                reference=reference,
                entry_date=stamp,
            )
        self.audit.log(
            "payment.in" if direction == "in" else "payment.out",
            user=user,
            entity="party",
            entity_id=party_id,
            details=f"{party['name']} {amount / 100:.2f}",
        )
        return payment_id

    def payments(self, party_id: int | None = None, limit: int = 300) -> list:
        sql = """
            SELECT pay.*, p.name AS party_name, p.type AS party_type, u.username
            FROM payments pay
            JOIN parties p ON p.id = pay.party_id
            LEFT JOIN users u ON u.id = pay.user_id
        """
        params: list[Any] = []
        if party_id:
            sql += " WHERE pay.party_id = ?"
            params.append(party_id)
        sql += " ORDER BY pay.id DESC LIMIT ?"
        params.append(limit)
        return self.db.query(sql, params)

    def delete_payment(self, payment_id: int) -> None:
        with self.db.transaction():
            self.db.execute(
                "DELETE FROM ledger_entries WHERE doc_type = 'payment' AND doc_id = ?",
                (payment_id,),
            )
            self.db.execute("DELETE FROM payments WHERE id = ?", (payment_id,))
        self.audit.log("payment.delete", entity="payment", entity_id=payment_id)
