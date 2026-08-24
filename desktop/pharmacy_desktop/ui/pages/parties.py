"""Customers & suppliers — accounts, ledgers and payments."""

from __future__ import annotations

from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QFormLayout,
    QHBoxLayout,
    QLineEdit,
    QPlainTextEdit,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from ...core import dates
from ...core.errors import PharmacyError
from ...core.money import fmt
from ...core.services.parties import PAYMENT_METHODS
from .. import theme
from ..widgets.common import (
    Card,
    DateEdit,
    MoneyEdit,
    MutedLabel,
    SearchBox,
    SectionTitle,
    button,
    confirm,
    error,
    warn,
)
from ..widgets.table import Col, DataTable, DATETIME, MONEY
from .base import Page


class PartiesPage(Page):
    title = "Customers & suppliers"
    subtitle = "Accounts, credit and payments"

    def build(self) -> None:
        self.tabs = QTabWidget()
        self.customer_tab = PartyTab(self.context, "customer", self)
        self.supplier_tab = PartyTab(self.context, "supplier", self)
        self.tabs.addTab(self.customer_tab, "Customers")
        self.tabs.addTab(self.supplier_tab, "Suppliers")
        self.tabs.currentChanged.connect(lambda _i: self.reload())
        self.body.addWidget(self.tabs, 1)

    def reload(self) -> None:
        self.tabs.currentWidget().reload()

    def focus_default(self) -> None:
        self.tabs.currentWidget().search.setFocus()


class PartyTab(QWidget):
    def __init__(self, context, party_type: str, page: PartiesPage):
        super().__init__()
        self.context = context
        self.party_type = party_type
        self.page = page
        self.is_customer = party_type == "customer"

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 12, 10, 10)
        layout.setSpacing(10)

        tools = QHBoxLayout()
        self.search = SearchBox("Search by name or phone…")
        self.search.textChanged.connect(lambda _t: self.reload())
        tools.addWidget(self.search, 3)
        tools.addWidget(button("Add", kind="Primary", on_click=self._add))
        tools.addWidget(button("Edit", on_click=self._edit))
        tools.addWidget(
            button(
                "Receive payment" if self.is_customer else "Pay supplier",
                kind="Accent",
                on_click=self._payment,
            )
        )
        tools.addWidget(button("Turn on/off", on_click=self._toggle))
        tools.addWidget(button("Delete", kind="Danger", on_click=self._delete))
        layout.addLayout(tools)

        split = QHBoxLayout()
        split.setSpacing(12)

        left = Card()
        left.body.addWidget(SectionTitle("Accounts"))
        self.table = DataTable(
            [
                Col("name", "Name", stretch=True),
                Col("phone", "Phone"),
                Col("balance", "Balance", MONEY),
            ]
        )
        self.table.row_style = self._tone
        self.table.rowSelected.connect(lambda _row: self._load_ledger())
        self.table.rowActivated.connect(lambda _row: self._edit())
        left.body.addWidget(self.table, 1)
        self.summary = MutedLabel("")
        left.body.addWidget(self.summary)
        split.addWidget(left, 4)

        right = Card()
        header = QHBoxLayout()
        header.addWidget(SectionTitle("Account ledger"))
        header.addStretch(1)
        header.addWidget(button("Print statement", on_click=self._print_statement))
        right.body.addLayout(header)
        self.ledger_heading = MutedLabel("Choose an account on the left.")
        right.body.addWidget(self.ledger_heading)
        self.ledger = DataTable(
            [
                Col("entry_date", "Date", DATETIME),
                Col("description", "Detail", stretch=True),
                Col("reference", "Reference"),
                Col("debit", "Debit", MONEY),
                Col("credit", "Credit", MONEY),
                Col("balance", "Balance", MONEY),
            ]
        )
        right.body.addWidget(self.ledger, 1)
        split.addWidget(right, 6)
        layout.addLayout(split, 1)

    @staticmethod
    def _tone(row) -> str:
        if not row["is_active"]:
            return "muted"
        return "warning" if int(row["balance"] or 0) != 0 else ""

    # ----------------------------------------------------------------- data
    def reload(self) -> None:
        rows = self.context.parties.list_parties(
            self.party_type, self.search.text(), only_active=False
        )
        if not self.is_customer:
            rows = [{**dict(row), "balance": -int(row["balance"])} for row in rows]
        self.table.set_rows(rows)
        total = sum(int(row["balance"]) for row in rows if int(row["balance"]) > 0)
        word = "Customers owe us" if self.is_customer else "We owe suppliers"
        self.summary.setText(f"{len(rows)} account(s) · {word} {fmt(total, symbol=True)}")
        self._load_ledger()

    def _load_ledger(self) -> None:
        row = self.table.current()
        if row is None:
            self.ledger.set_rows([])
            return
        entries = self.context.parties.ledger(int(row["id"]))
        if not self.is_customer:
            entries = [
                {**entry, "balance": -int(entry["balance"]),
                 "debit": entry["credit"], "credit": entry["debit"]}
                for entry in entries
            ]
        self.ledger.set_rows(entries)
        balance = int(entries[-1]["balance"]) if entries else 0
        label = "owes us" if self.is_customer else "we owe"
        colour = theme.DANGER if balance > 0 else theme.SUCCESS
        self.ledger_heading.setText(
            f"<b>{row['name']}</b> · {row['phone'] or 'no phone'} — "
            f"<span style='color:{colour}'>{label} "
            f"<b>{fmt(abs(balance), symbol=True)}</b></span>"
        )

    # -------------------------------------------------------------- actions
    def _selected(self):
        row = self.table.current()
        if row is None:
            warn(self, "Choose an account from the list first.")
        return row

    def _add(self) -> None:
        if PartyDialog(self.context, self.party_type, parent=self).exec() == QDialog.Accepted:
            self.page.notify_change()

    def _edit(self) -> None:
        row = self._selected()
        if row is None:
            return
        dialog = PartyDialog(self.context, self.party_type, row=row, parent=self)
        if dialog.exec() == QDialog.Accepted:
            self.page.notify_change()

    def _payment(self) -> None:
        row = self._selected()
        if row is None:
            return
        direction = "in" if self.is_customer else "out"
        if PaymentDialog(self.context, int(row["id"]), direction, parent=self).exec() == (
            QDialog.Accepted
        ):
            self.page.notify_change()

    def _toggle(self) -> None:
        row = self._selected()
        if row is None:
            return
        self.context.parties.set_active(int(row["id"]), not row["is_active"])
        self.reload()

    def _delete(self) -> None:
        row = self._selected()
        if row is None:
            return
        if not confirm(self, f"Delete the account “{row['name']}”?", danger=True):
            return
        try:
            self.context.parties.delete(int(row["id"]))
        except PharmacyError as exc:
            error(self, str(exc))
            return
        self.reload()

    def _print_statement(self) -> None:
        row = self._selected()
        if row is None:
            return
        from ...core.services.reports import Column, ReportResult
        from .. import printing

        entries = self.ledger.rows()
        report = ReportResult(
            title=f"Account statement — {row['name']}",
            subtitle=(
                f"{row['phone'] or ''} · as on {dates.fmt_date(dates.today_iso())}"
            ),
            columns=[
                Column("entry_date", "Date", "datetime"),
                Column("description", "Detail"),
                Column("reference", "Reference"),
                Column("debit", "Debit", "money"),
                Column("credit", "Credit", "money"),
                Column("balance", "Balance", "money"),
            ],
            rows=[dict(entry) for entry in entries],
        )
        printing.preview_html(
            self, printing.report_html(self.context.settings, report), page_format=printing.A4
        )


class PartyDialog(QDialog):
    def __init__(self, context, party_type: str, row=None, parent=None):
        super().__init__(parent)
        self.context = context
        self.party_type = party_type
        self.row = row
        is_customer = party_type == "customer"
        self.setWindowTitle(
            ("Customer" if is_customer else "Supplier") + (" — edit" if row is not None else " — new")
        )
        self.setMinimumWidth(470)
        box = QVBoxLayout(self)
        box.setSpacing(12)
        form = QFormLayout()
        form.setSpacing(9)
        self.name = QLineEdit()
        self.phone = QLineEdit()
        self.email = QLineEdit()
        self.address = QPlainTextEdit()
        self.address.setMaximumHeight(64)
        self.opening = MoneyEdit()
        self.credit_limit = MoneyEdit()
        self.notes = QPlainTextEdit()
        self.notes.setMaximumHeight(56)
        form.addRow("Name *", self.name)
        form.addRow("Phone", self.phone)
        form.addRow("Email", self.email)
        form.addRow("Address", self.address)
        form.addRow(
            "Opening balance" + (" (owed to us)" if is_customer else " (we owe)"), self.opening
        )
        if is_customer:
            form.addRow("Credit limit", self.credit_limit)
        form.addRow("Notes", self.notes)
        box.addLayout(form)
        box.addWidget(
            MutedLabel(
                "The opening balance is what was outstanding before this software started. "
                "Leave it at 0 for a new account."
            )
        )
        buttons = QHBoxLayout()
        buttons.addStretch(1)
        buttons.addWidget(button("Cancel", on_click=self.reject))
        buttons.addWidget(button("Save", kind="Primary", on_click=self._save))
        box.addLayout(buttons)
        if row is not None:
            self.name.setText(row["name"])
            self.phone.setText(row["phone"] or "")
            self.email.setText(row["email"] or "")
            self.address.setPlainText(row["address"] or "")
            self.opening.set_paisa(int(row["opening_balance"]))
            self.credit_limit.set_paisa(int(row["credit_limit"]))
            self.notes.setPlainText(row["notes"] or "")

    def _save(self) -> None:
        values = {
            "name": self.name.text(),
            "phone": self.phone.text(),
            "email": self.email.text(),
            "address": self.address.toPlainText(),
            "opening_balance": self.opening.paisa(),
            "credit_limit": self.credit_limit.paisa(),
            "notes": self.notes.toPlainText(),
        }
        try:
            if self.row is None:
                self.context.parties.create(self.party_type, values)
            else:
                self.context.parties.update(int(self.row["id"]), values)
        except PharmacyError as exc:
            error(self, str(exc))
            return
        self.accept()


class PaymentDialog(QDialog):
    """Record money received from a customer, or paid to a supplier."""

    def __init__(self, context, party_id: int, direction: str, parent=None):
        super().__init__(parent)
        self.context = context
        self.party_id = party_id
        self.direction = direction
        party = context.parties.get(party_id)
        balance = context.parties.balance(party_id)
        owed = balance if direction == "in" else -balance
        self.setWindowTitle(
            f"Receive payment — {party['name']}"
            if direction == "in"
            else f"Pay supplier — {party['name']}"
        )
        self.setMinimumWidth(430)
        box = QVBoxLayout(self)
        box.setSpacing(12)
        box.addWidget(
            MutedLabel(
                f"Outstanding: <b>{fmt(max(owed, 0), symbol=True)}</b>"
                + (
                    f" (advance of {fmt(-owed, symbol=True)} on the account)"
                    if owed < 0
                    else ""
                )
            )
        )
        form = QFormLayout()
        form.setSpacing(9)
        self.amount = MoneyEdit(max(owed, 0))
        self.method = QComboBox()
        self.method.addItems(PAYMENT_METHODS)
        self.date = DateEdit()
        self.reference = QLineEdit()
        self.reference.setPlaceholderText("Cheque or transaction number (optional)")
        self.note = QLineEdit()
        form.addRow("Amount", self.amount)
        form.addRow("Method", self.method)
        form.addRow("Date", self.date)
        form.addRow("Reference", self.reference)
        form.addRow("Note", self.note)
        box.addLayout(form)
        buttons = QHBoxLayout()
        buttons.addStretch(1)
        buttons.addWidget(button("Cancel", on_click=self.reject))
        buttons.addWidget(button("Save payment", kind="Primary", on_click=self._save))
        box.addLayout(buttons)
        self.amount.setFocus()

    def _save(self) -> None:
        try:
            self.context.parties.record_payment(
                self.party_id,
                amount=self.amount.paisa(),
                direction=self.direction,
                method=self.method.currentText(),
                reference=self.reference.text(),
                note=self.note.text(),
                user=self.context.auth.current_user,
                paid_at=self.date.iso() + " " + dates.now_iso()[11:],
            )
        except PharmacyError as exc:
            error(self, str(exc))
            return
        self.accept()
