"""Purchases — entering supplier bills and receiving goods into batches."""

from __future__ import annotations

from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDoubleSpinBox,
    QHBoxLayout,
    QLineEdit,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from ...core import dates
from ...core.errors import PharmacyError
from ...core.money import fmt
from ...core.services.purchases import PurchaseDraft, PurchaseLine
from .. import printing, theme
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
from ..widgets.table import Col, DataTable, DATE, INT, MONEY
from .base import Page


class PurchasesPage(Page):
    title = "Purchases"
    subtitle = "Supplier bills and goods received"

    def build(self) -> None:
        if self.can("purchases.manage"):
            self.header.add_action(
                button("Enter supplier bill", kind="Primary", shortcut="Ctrl+N",
                       on_click=self._new_purchase)
            )
        self.header.add_action(button("Print selected", on_click=self._print))

        filters = QHBoxLayout()
        self.search = SearchBox("Search reference, supplier bill number or supplier…")
        self.search.textChanged.connect(lambda _t: self.reload())
        filters.addWidget(self.search, 3)
        self.date_from = DateEdit(dates.month_start())
        self.date_to = DateEdit()
        for widget in (self.date_from, self.date_to):
            widget.dateChanged.connect(lambda _d: self.reload())
        filters.addWidget(MutedLabel("From"))
        filters.addWidget(self.date_from)
        filters.addWidget(MutedLabel("to"))
        filters.addWidget(self.date_to)
        self.body.addLayout(filters)

        self.table = DataTable(
            [
                Col("purchase_date", "Date", DATE),
                Col("reference_no", "Reference"),
                Col("supplier_bill_no", "Supplier bill"),
                Col("supplier_name", "Supplier", stretch=True),
                Col("gross_amount", "Gross", MONEY),
                Col("discount_amount", "Discount", MONEY),
                Col("net_amount", "Net", MONEY),
                Col("paid_amount", "Paid", MONEY),
                Col("username", "Entered by"),
            ]
        )
        self.table.rowActivated.connect(lambda _row: self._view())
        self.body.addWidget(self.table, 1)

        tools = QHBoxLayout()
        self.summary = MutedLabel("")
        tools.addWidget(self.summary)
        tools.addStretch(1)
        tools.addWidget(button("View items", on_click=self._view))
        if self.can("purchases.manage"):
            tools.addWidget(button("Pay supplier…", on_click=self._pay))
            tools.addWidget(button("Delete bill", kind="Danger", on_click=self._delete))
        self.body.addLayout(tools)

    def reload(self) -> None:
        rows = self.context.purchases.list_purchases(
            date_from=self.date_from.iso(),
            date_to=self.date_to.iso(),
            search=self.search.text(),
        )
        self.table.set_rows(rows)
        net = sum(int(row["net_amount"]) for row in rows)
        paid = sum(int(row["paid_amount"]) for row in rows)
        self.summary.setText(
            f"{len(rows)} bill(s) · purchased {fmt(net, symbol=True)} · "
            f"paid {fmt(paid, symbol=True)} · outstanding {fmt(net - paid, symbol=True)}"
        )

    # --------------------------------------------------------------- actions
    def _new_purchase(self) -> None:
        dialog = PurchaseEntryDialog(self.context, self)
        if dialog.exec() == QDialog.Accepted:
            self.notify_change()
            if dialog.saved_id and confirm(self, "Print a goods received note?"):
                self._print_purchase(dialog.saved_id)

    def _selected(self):
        row = self.table.current()
        if row is None:
            warn(self, "Choose a purchase from the list first.")
        return row

    def _view(self) -> None:
        row = self._selected()
        if row is None:
            return
        PurchaseViewDialog(self.context, int(row["id"]), self).exec()

    def _print(self) -> None:
        row = self._selected()
        if row is None:
            return
        self._print_purchase(int(row["id"]))

    def _print_purchase(self, purchase_id: int) -> None:
        purchase = self.context.purchases.get_purchase(purchase_id)
        items = self.context.purchases.purchase_items(purchase_id)
        content = printing.purchase_html(self.context.settings, purchase, items)
        printing.preview_html(self, content, page_format=printing.A4)

    def _pay(self) -> None:
        row = self._selected()
        if row is None:
            return
        if not row["supplier_id"]:
            warn(self, "This bill is not linked to a supplier account.")
            return
        from .parties import PaymentDialog

        dialog = PaymentDialog(self.context, int(row["supplier_id"]), "out", parent=self)
        if dialog.exec() == QDialog.Accepted:
            self.notify_change()

    def _delete(self) -> None:
        row = self._selected()
        if row is None:
            return
        if not confirm(
            self,
            f"Delete purchase {row['reference_no']}? The units it brought in will be "
            "taken back off the shelf.",
            danger=True,
        ):
            return
        try:
            self.context.purchases.delete_purchase(int(row["id"]), user=self.user)
        except PharmacyError as exc:
            error(self, str(exc))
            return
        self.notify_change()


class PurchaseEntryDialog(QDialog):
    """Type a supplier bill line by line, then receive the whole lot."""

    def __init__(self, context, parent=None):
        super().__init__(parent)
        self.context = context
        self.draft = PurchaseDraft()
        self.saved_id: int | None = None
        self.setWindowTitle("Enter supplier bill")
        self.setMinimumSize(1080, 700)
        box = QVBoxLayout(self)
        box.setSpacing(10)
        box.addWidget(self._header_card())
        box.addWidget(self._line_entry_card())
        self.table = DataTable(
            [
                Col("product", "Medicine", stretch=True),
                Col("batch", "Batch"),
                Col("expiry", "Expiry", DATE),
                Col("quantity", "Qty", INT),
                Col("bonus", "Bonus", INT),
                Col("cost", "Cost", MONEY),
                Col("discount", "Disc %", "percent"),
                Col("retail", "Retail", MONEY),
                Col("total", "Amount", MONEY),
            ]
        )
        box.addWidget(self.table, 1)

        bottom = QHBoxLayout()
        bottom.addWidget(button("Remove line", kind="Danger", on_click=self._remove_line))
        bottom.addStretch(1)
        self.totals = MutedLabel("")
        self.totals.setStyleSheet("font-size: 15px; font-weight: 700;")
        bottom.addWidget(self.totals)
        box.addLayout(bottom)

        pay_row = QHBoxLayout()
        pay_row.addWidget(MutedLabel("Paid to supplier now"))
        self.paid = MoneyEdit()
        self.paid.setMaximumWidth(160)
        pay_row.addWidget(self.paid)
        pay_row.addStretch(1)
        pay_row.addWidget(button("Cancel", on_click=self.reject))
        pay_row.addWidget(button("Save & receive stock", kind="Primary", on_click=self._save))
        box.addLayout(pay_row)
        self._refresh()

    def _header_card(self) -> QWidget:
        card = Card(margins=12, spacing=8)
        form = QHBoxLayout()
        self.supplier = QComboBox()
        self.supplier.addItem("— no supplier account —", None)
        for row in self.context.parties.list_parties("supplier"):
            self.supplier.addItem(row["name"], int(row["id"]))
        self.bill_no = QLineEdit()
        self.bill_no.setPlaceholderText("Supplier's bill number")
        self.date = DateEdit()
        form.addWidget(MutedLabel("Supplier"))
        form.addWidget(self.supplier, 2)
        form.addWidget(button("New supplier…", on_click=self._new_supplier))
        form.addWidget(MutedLabel("Bill no."))
        form.addWidget(self.bill_no, 1)
        form.addWidget(MutedLabel("Date"))
        form.addWidget(self.date)
        card.body.addLayout(form)
        return card

    def _line_entry_card(self) -> QWidget:
        card = Card(margins=12, spacing=8)
        card.body.addWidget(SectionTitle("Add a line"))
        grid = QHBoxLayout()
        self.product = QComboBox()
        self.product.setEditable(True)
        self.product.setMinimumWidth(240)
        self.product.setInsertPolicy(QComboBox.NoInsert)
        self._load_products()
        self.product.currentIndexChanged.connect(self._prefill)

        self.quantity = QSpinBox()
        self.quantity.setRange(1, 1000000)
        self.bonus = QSpinBox()
        self.bonus.setRange(0, 1000000)
        self.batch_no = QLineEdit()
        self.batch_no.setPlaceholderText("Batch")
        self.batch_no.setMaximumWidth(110)
        self.expiry = DateEdit()
        self.cost = MoneyEdit()
        self.cost.setMaximumWidth(100)
        self.retail = MoneyEdit()
        self.retail.setMaximumWidth(100)
        self.discount = QDoubleSpinBox()
        self.discount.setRange(0, 100)
        self.discount.setSuffix(" %")

        for label, widget in [
            ("Medicine", self.product),
            ("Qty", self.quantity),
            ("Bonus", self.bonus),
            ("Batch", self.batch_no),
            ("Expiry", self.expiry),
            ("Cost", self.cost),
            ("Disc", self.discount),
            ("Retail", self.retail),
        ]:
            column = QVBoxLayout()
            column.setSpacing(2)
            column.addWidget(MutedLabel(label))
            column.addWidget(widget)
            grid.addLayout(column)
        add = button("Add line", kind="Primary", on_click=self._add_line)
        add.setShortcut("Ctrl+Return")
        grid.addWidget(add)
        card.body.addLayout(grid)
        card.body.addWidget(
            MutedLabel(
                "Quantities are in single units. A carton of 20 strips of 10 tablets is "
                "200. Bonus units are received free and pull the average cost down."
            )
        )
        return card

    def _load_products(self) -> None:
        self.product.clear()
        for row in self.context.catalog.list_products(limit=5000):
            label = row["name"] + (f" — {row['strength']}" if row["strength"] else "")
            self.product.addItem(label, int(row["id"]))

    def _new_supplier(self) -> None:
        from .parties import PartyDialog

        dialog = PartyDialog(self.context, "supplier", parent=self)
        if dialog.exec() != QDialog.Accepted:
            return
        self.supplier.clear()
        self.supplier.addItem("— no supplier account —", None)
        for row in self.context.parties.list_parties("supplier"):
            self.supplier.addItem(row["name"], int(row["id"]))
        self.supplier.setCurrentIndex(self.supplier.count() - 1)

    def _prefill(self) -> None:
        product_id = self.product.currentData()
        if not product_id:
            return
        product = self.context.catalog.get(int(product_id))
        self.cost.set_paisa(int(product["purchase_price"]))
        self.retail.set_paisa(int(product["sale_price"]))

    def _add_line(self) -> None:
        product_id = self.product.currentData()
        if not product_id:
            warn(self, "Choose a medicine.")
            return
        product = self.context.catalog.get(int(product_id))
        self.draft.lines.append(
            PurchaseLine(
                product_id=int(product_id),
                product_name=product["name"],
                quantity=self.quantity.value(),
                unit_cost=self.cost.paisa(),
                batch_no=self.batch_no.text() or "-",
                expiry_date=self.expiry.iso(),
                bonus_quantity=self.bonus.value(),
                unit_sale_price=self.retail.paisa(),
                discount_percent=float(self.discount.value()),
                tax_percent=float(product["tax_percent"] or 0),
            )
        )
        self.quantity.setValue(1)
        self.bonus.setValue(0)
        self.batch_no.clear()
        self.product.setFocus()
        self._refresh()

    def _remove_line(self) -> None:
        index = self.table.currentRow()
        if 0 <= index < len(self.draft.lines):
            self.draft.lines.pop(index)
            self._refresh()

    def _refresh(self) -> None:
        self.table.set_rows(
            [
                {
                    "product": line.product_name,
                    "batch": line.batch_no,
                    "expiry": line.expiry_date,
                    "quantity": line.quantity,
                    "bonus": line.bonus_quantity,
                    "cost": line.unit_cost,
                    "discount": line.discount_percent,
                    "retail": line.unit_sale_price,
                    "total": line.total,
                }
                for line in self.draft.lines
            ]
        )
        self.totals.setText(
            f"Gross {fmt(self.draft.gross_amount)}   ·   "
            f"Discount {fmt(self.draft.discount_amount)}   ·   "
            f"Net payable {fmt(self.draft.net_amount, symbol=True)}   ·   "
            f"{self.draft.total_units:,} units"
        )
        if not self.paid.text():
            self.paid.set_paisa(self.draft.net_amount)

    def _save(self) -> None:
        self.draft.supplier_id = self.supplier.currentData()
        self.draft.supplier_bill_no = self.bill_no.text().strip()
        self.draft.purchase_date = self.date.iso()
        try:
            self.saved_id = self.context.purchases.create_purchase(
                self.draft,
                user=self.context.auth.current_user,
                paid_amount=self.paid.paisa(),
            )
        except PharmacyError as exc:
            error(self, str(exc))
            return
        self.accept()


class PurchaseViewDialog(QDialog):
    def __init__(self, context, purchase_id: int, parent=None):
        super().__init__(parent)
        self.context = context
        purchase = context.purchases.get_purchase(purchase_id)
        items = context.purchases.purchase_items(purchase_id)
        self.setWindowTitle(f"Purchase {purchase['reference_no']}")
        self.setMinimumSize(860, 520)
        box = QVBoxLayout(self)
        box.addWidget(
            MutedLabel(
                f"<b>{purchase['supplier_name'] or 'No supplier account'}</b> · bill "
                f"{purchase['supplier_bill_no'] or '—'} · "
                f"{dates.fmt_date(purchase['purchase_date'])} · entered by "
                f"{purchase['username'] or '—'}"
            )
        )
        table = DataTable(
            [
                Col("product_name", "Medicine", stretch=True),
                Col("batch_no", "Batch"),
                Col("expiry_date", "Expiry", DATE),
                Col("quantity", "Qty", INT),
                Col("bonus_quantity", "Bonus", INT),
                Col("unit_cost", "Cost", MONEY),
                Col("unit_sale_price", "Retail", MONEY),
                Col("line_total", "Amount", MONEY),
            ]
        )
        table.set_rows(items)
        box.addWidget(table, 1)
        due = int(purchase["net_amount"]) - int(purchase["paid_amount"])
        summary = MutedLabel(
            f"Gross {fmt(purchase['gross_amount'])} · discount "
            f"{fmt(purchase['discount_amount'])} · <b>net "
            f"{fmt(purchase['net_amount'], symbol=True)}</b> · paid "
            f"{fmt(purchase['paid_amount'])} · balance "
            f"<b style='color:{theme.DANGER if due else theme.SUCCESS}'>{fmt(due)}</b>"
        )
        summary.setStyleSheet("font-size: 14px;")
        box.addWidget(summary)
        buttons = QHBoxLayout()
        buttons.addStretch(1)
        buttons.addWidget(
            button(
                "Print",
                on_click=lambda: printing.preview_html(
                    self,
                    printing.purchase_html(context.settings, purchase, items),
                    page_format=printing.A4,
                ),
            )
        )
        buttons.addWidget(button("Close", kind="Primary", on_click=self.accept))
        box.addLayout(buttons)
