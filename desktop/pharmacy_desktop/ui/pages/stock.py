"""Stock & expiry — batch-level view of everything on the shelf."""

from __future__ import annotations

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QFormLayout,
    QHBoxLayout,
    QLineEdit,
    QPlainTextEdit,
    QSpinBox,
    QVBoxLayout,
)

from ...core import config
from ...core.errors import PharmacyError
from ...core.money import fmt
from ...core.services.inventory import ADJUSTMENT_REASONS
from .. import theme
from ..widgets.common import (
    DateEdit,
    MoneyEdit,
    MutedLabel,
    SearchBox,
    button,
    confirm,
    error,
    info,
    warn,
)
from ..widgets.table import Col, DataTable, DATE, DATETIME, INT, MONEY
from .base import Page

VIEWS = [
    ("Everything in stock", "in_stock"),
    ("Expiring soon", "expiring"),
    ("Already expired", "expired"),
    ("Finished batches", "out_of_stock"),
    ("All batches", "all"),
]


class StockPage(Page):
    title = "Stock & expiry"
    subtitle = "Batch by batch, with expiry dates"

    def build(self) -> None:
        may_manage = self.can("stock.manage")
        if may_manage:
            self.header.add_action(
                button("Receive stock", kind="Primary", on_click=self._receive)
            )
            self.header.add_action(button("Adjust…", on_click=self._adjust))
            self.header.add_action(
                button("Write off expired", kind="Danger", on_click=self._write_off)
            )
        self.header.add_action(button("Export", on_click=self._export))

        filters = QHBoxLayout()
        self.search = SearchBox("Search medicine or batch number…")
        self.search.textChanged.connect(lambda _t: self._debounce.start())
        filters.addWidget(self.search, 3)
        self.view = QComboBox()
        for label, value in VIEWS:
            self.view.addItem(label, value)
        self.view.currentIndexChanged.connect(lambda _i: self.reload())
        filters.addWidget(self.view, 1)
        self.window_days = QComboBox()
        for days in (30, 60, 90, 180, 365):
            self.window_days.addItem(f"within {days} days", days)
        self.window_days.setCurrentIndex(2)
        self.window_days.currentIndexChanged.connect(lambda _i: self.reload())
        filters.addWidget(self.window_days)
        self.body.addLayout(filters)

        self.summary = MutedLabel("")
        self.summary.setStyleSheet(
            f"background: {theme.SURFACE}; border: 1px solid {theme.LINE}; "
            "border-radius: 8px; padding: 9px 12px;"
        )
        self.body.addWidget(self.summary)

        self.table = DataTable(
            [
                Col("product_name", "Medicine", stretch=True),
                Col("manufacturer_name", "Company"),
                Col("batch_no", "Batch"),
                Col("expiry_date", "Expiry", DATE),
                Col("days_to_expiry", "Days left", INT),
                Col("quantity", "Units", INT),
                Col("purchase_price", "Cost each", MONEY),
                Col("sale_price", "Retail each", MONEY),
                Col("received_at", "Received", DATE),
                Col("source", "From"),
            ]
        )
        self.table.row_style = self._tone
        self.table.rowActivated.connect(lambda _row: self._adjust())
        self.body.addWidget(self.table, 1)

        tools = QHBoxLayout()
        self.count_label = MutedLabel("")
        tools.addWidget(self.count_label)
        tools.addStretch(1)
        if may_manage:
            tools.addWidget(button("Edit batch…", on_click=self._edit_batch))
            tools.addWidget(button("Delete batch", kind="Danger", on_click=self._delete_batch))
        tools.addWidget(button("Recent adjustments…", on_click=self._show_adjustments))
        self.body.addLayout(tools)

        self._debounce = QTimer(self)
        self._debounce.setSingleShot(True)
        self._debounce.setInterval(180)
        self._debounce.timeout.connect(self.reload)

    def focus_default(self) -> None:
        self.search.setFocus()

    @staticmethod
    def _tone(row) -> str:
        days = row["days_to_expiry"]
        if days is not None and days < 0:
            return "danger"
        if days is not None and days <= 90:
            return "warning"
        if int(row["quantity"] or 0) <= 0:
            return "muted"
        return ""

    def reload(self) -> None:
        rows = self.context.inventory.list_batches(
            self.search.text(),
            view=self.view.currentData() or "in_stock",
            expiry_days=self.window_days.currentData() or 90,
        )
        self.table.set_rows(rows)
        units = sum(int(row["quantity"] or 0) for row in rows)
        value = sum(int(row["quantity"] or 0) * int(row["purchase_price"]) for row in rows)
        self.count_label.setText(
            f"{len(rows)} batch(es) · {units:,} units · cost value {fmt(value, symbol=True)}"
        )
        overall = self.context.inventory.stock_value()
        expiring = len(
            self.context.inventory.expiring_soon(
                days=self.context.settings.get_int("warn_expiry_days", 90)
            )
        )
        expired = len(self.context.inventory.expired())
        low = len(self.context.inventory.low_stock())
        self.summary.setText(
            f"<b>{overall['units']:,}</b> units on the shelf worth "
            f"<b>{fmt(overall['cost_value'], symbol=True)}</b> at cost "
            f"({fmt(overall['retail_value'], symbol=True)} at retail) · "
            f"<b>{expiring}</b> batch(es) expiring soon · "
            f"<b style='color:{theme.DANGER}'>{expired}</b> expired · "
            f"<b>{low}</b> medicine(s) to reorder"
        )

    # --------------------------------------------------------------- actions
    def _receive(self) -> None:
        if ReceiveStockDialog(self.context, parent=self).exec() == QDialog.Accepted:
            self.notify_change()

    def _selected(self):
        row = self.table.current()
        if row is None:
            warn(self, "Choose a batch from the list first.")
        return row

    def _adjust(self) -> None:
        row = self._selected()
        if row is None or not self.can("stock.manage"):
            return
        if AdjustDialog(self.context, row, parent=self).exec() == QDialog.Accepted:
            self.notify_change()

    def _edit_batch(self) -> None:
        row = self._selected()
        if row is None:
            return
        if BatchDialog(self.context, row, parent=self).exec() == QDialog.Accepted:
            self.notify_change()

    def _delete_batch(self) -> None:
        row = self._selected()
        if row is None:
            return
        if not confirm(
            self, f"Delete batch {row['batch_no']} of {row['product_name']}?", danger=True
        ):
            return
        try:
            self.context.inventory.delete_batch(int(row["id"]))
        except PharmacyError as exc:
            error(self, str(exc))
            return
        self.notify_change()

    def _write_off(self) -> None:
        expired = self.context.inventory.expired()
        if not expired:
            info(self, "Nothing on the shelf has expired. Well managed.")
            return
        units = sum(int(row["quantity"]) for row in expired)
        value = sum(int(row["quantity"]) * int(row["purchase_price"]) for row in expired)
        if not confirm(
            self,
            f"Remove {units:,} unit(s) in {len(expired)} expired batch(es) from stock?\n\n"
            f"Cost value written off: {fmt(value, symbol=True)}\n"
            "Each removal is recorded so it shows in the stock adjustment report.",
            danger=True,
        ):
            return
        result = self.context.inventory.write_off_expired(user=self.user)
        info(
            self,
            f"{result['units']:,} units in {result['batches']} batch(es) written off "
            f"({fmt(result['cost_value'], symbol=True)} at cost).",
        )
        self.notify_change()

    def _show_adjustments(self) -> None:
        AdjustmentLogDialog(self.context, self).exec()

    def _export(self) -> None:
        from PySide6.QtWidgets import QFileDialog

        path, _filter = QFileDialog.getSaveFileName(
            self, "Save stock list", str(config.export_dir() / "stock.csv"), "Spreadsheet (*.csv)"
        )
        if not path:
            return
        import csv

        with open(path, "w", newline="", encoding="utf-8-sig") as handle:
            writer = csv.writer(handle)
            writer.writerow([column.label for column in self.table.columns])
            for row in self.table.rows():
                writer.writerow(
                    [
                        fmt(row[column.key]) if column.kind == MONEY else row[column.key]
                        for column in self.table.columns
                    ]
                )
        info(self, f"Saved to:\n{path}")


class ReceiveStockDialog(QDialog):
    """Put stock on the shelf without a supplier bill (opening stock, samples)."""

    def __init__(self, context, product_id: int | None = None, parent=None):
        super().__init__(parent)
        self.context = context
        self.setWindowTitle("Receive stock")
        self.setMinimumWidth(520)
        box = QVBoxLayout(self)
        box.setSpacing(12)
        box.addWidget(
            MutedLabel(
                "Use this for opening stock or a quick addition. For a supplier bill with "
                "several items, use the <b>Purchases</b> screen instead — it keeps the "
                "supplier's account as well."
            )
        )
        form = QFormLayout()
        form.setSpacing(9)
        self.product = QComboBox()
        self.product.setEditable(True)
        self.product.setInsertPolicy(QComboBox.NoInsert)
        for row in context.catalog.list_products(limit=5000):
            label = f"{row['name']}" + (f" — {row['strength']}" if row["strength"] else "")
            self.product.addItem(label, int(row["id"]))
        if product_id is not None:
            index = self.product.findData(product_id)
            if index >= 0:
                self.product.setCurrentIndex(index)
        self.product.currentIndexChanged.connect(self._prefill)

        self.quantity = QSpinBox()
        self.quantity.setRange(1, 1000000)
        self.quantity.setValue(1)
        self.batch_no = QLineEdit()
        self.batch_no.setPlaceholderText("Batch number printed on the pack")
        self.expiry = DateEdit()
        self.cost = MoneyEdit()
        self.retail = MoneyEdit()

        form.addRow("Medicine", self.product)
        form.addRow("Quantity (units)", self.quantity)
        form.addRow("Batch number", self.batch_no)
        form.addRow("Expiry date", self.expiry)
        form.addRow("Cost per unit", self.cost)
        form.addRow("Retail per unit", self.retail)
        box.addLayout(form)

        buttons = QHBoxLayout()
        buttons.addStretch(1)
        buttons.addWidget(button("Cancel", on_click=self.reject))
        buttons.addWidget(button("Add to stock", kind="Primary", on_click=self._save))
        box.addLayout(buttons)
        self._prefill()

    def _prefill(self) -> None:
        product_id = self.product.currentData()
        if not product_id:
            return
        product = self.context.catalog.get(int(product_id))
        self.cost.set_paisa(int(product["purchase_price"]))
        self.retail.set_paisa(int(product["sale_price"]))

    def _save(self) -> None:
        product_id = self.product.currentData()
        if not product_id:
            warn(self, "Choose a medicine.")
            return
        try:
            self.context.inventory.add_stock(
                product_id=int(product_id),
                quantity=self.quantity.value(),
                batch_no=self.batch_no.text() or "-",
                expiry_date=self.expiry.iso(),
                purchase_price=self.cost.paisa(),
                sale_price=self.retail.paisa(),
                source="manual",
            )
        except PharmacyError as exc:
            error(self, str(exc))
            return
        self.context.audit.log(
            "stock.receive",
            user=self.context.auth.current_user,
            entity="product",
            entity_id=int(product_id),
            details=f"{self.quantity.value()} units, batch {self.batch_no.text() or '-'}",
        )
        self.accept()


class AdjustDialog(QDialog):
    """Add or remove units from one batch, with a reason that is kept."""

    def __init__(self, context, batch, parent=None):
        super().__init__(parent)
        self.context = context
        self.batch = batch
        self.setWindowTitle(f"Adjust stock — {batch['product_name']}")
        self.setMinimumWidth(460)
        box = QVBoxLayout(self)
        box.setSpacing(12)
        box.addWidget(
            MutedLabel(
                f"Batch <b>{batch['batch_no']}</b> · expiry "
                f"{batch['expiry_date'] or 'not set'} · <b>{batch['quantity']}</b> units on hand"
            )
        )
        form = QFormLayout()
        form.setSpacing(9)
        self.direction = QComboBox()
        self.direction.addItem("Remove units", -1)
        self.direction.addItem("Add units", 1)
        self.quantity = QSpinBox()
        self.quantity.setRange(1, 1000000)
        self.reason = QComboBox()
        self.reason.addItems(ADJUSTMENT_REASONS)
        self.note = QPlainTextEdit()
        self.note.setMaximumHeight(70)
        form.addRow("Action", self.direction)
        form.addRow("How many units", self.quantity)
        form.addRow("Reason", self.reason)
        form.addRow("Note", self.note)
        box.addLayout(form)

        buttons = QHBoxLayout()
        buttons.addStretch(1)
        buttons.addWidget(button("Cancel", on_click=self.reject))
        buttons.addWidget(button("Save adjustment", kind="Primary", on_click=self._save))
        box.addLayout(buttons)

    def _save(self) -> None:
        quantity = self.quantity.value() * int(self.direction.currentData())
        try:
            self.context.inventory.adjust(
                batch_id=int(self.batch["id"]),
                quantity=quantity,
                reason=self.reason.currentText(),
                note=self.note.toPlainText(),
                user=self.context.auth.current_user,
            )
        except PharmacyError as exc:
            error(self, str(exc))
            return
        self.accept()


class BatchDialog(QDialog):
    """Correct a batch number, expiry date or price."""

    def __init__(self, context, batch, parent=None):
        super().__init__(parent)
        self.context = context
        self.batch = batch
        self.setWindowTitle(f"Batch — {batch['product_name']}")
        self.setMinimumWidth(430)
        box = QVBoxLayout(self)
        form = QFormLayout()
        form.setSpacing(9)
        self.batch_no = QLineEdit(batch["batch_no"])
        self.expiry = DateEdit(batch["expiry_date"])
        self.cost = MoneyEdit(int(batch["purchase_price"]))
        self.retail = MoneyEdit(int(batch["sale_price"]))
        form.addRow("Batch number", self.batch_no)
        form.addRow("Expiry date", self.expiry)
        form.addRow("Cost per unit", self.cost)
        form.addRow("Retail per unit", self.retail)
        box.addLayout(form)
        box.addWidget(
            MutedLabel(
                "Changing the quantity is done through “Adjust…”, so that every movement "
                "leaves a record."
            )
        )
        buttons = QHBoxLayout()
        buttons.addStretch(1)
        buttons.addWidget(button("Cancel", on_click=self.reject))
        buttons.addWidget(button("Save", kind="Primary", on_click=self._save))
        box.addLayout(buttons)

    def _save(self) -> None:
        try:
            self.context.inventory.update_batch(
                int(self.batch["id"]),
                batch_no=self.batch_no.text(),
                expiry_date=self.expiry.iso(),
                purchase_price=self.cost.paisa(),
                sale_price=self.retail.paisa(),
            )
        except PharmacyError as exc:
            error(self, str(exc))
            return
        self.accept()


class AdjustmentLogDialog(QDialog):
    def __init__(self, context, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Recent stock adjustments")
        self.setMinimumSize(760, 480)
        box = QVBoxLayout(self)
        table = DataTable(
            [
                Col("created_at", "When", DATETIME),
                Col("product_name", "Medicine", stretch=True),
                Col("batch_no", "Batch"),
                Col("quantity", "Change", INT),
                Col("reason", "Reason"),
                Col("note", "Note"),
                Col("username", "By"),
            ]
        )
        table.row_style = lambda row: "danger" if int(row["quantity"]) < 0 else ""
        table.set_rows(context.inventory.adjustments())
        box.addWidget(table, 1)
        box.addWidget(button("Close", on_click=self.accept))
