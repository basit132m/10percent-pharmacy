"""Sales & returns — look up any past bill, reprint it, or take goods back."""

from __future__ import annotations

from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLineEdit,
    QSpinBox,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from ...core import dates
from ...core.errors import PharmacyError
from ...core.money import fmt
from .. import printing, theme
from ..widgets.common import (
    Card,
    DateEdit,
    MutedLabel,
    SearchBox,
    SectionTitle,
    button,
    confirm,
    error,
    warn,
)
from ..widgets.table import Col, DataTable, DATE, DATETIME, INT, MONEY
from .base import Page


class SalesHistoryPage(Page):
    title = "Sales & returns"
    subtitle = "Every bill, with reprint and refund"

    def build(self) -> None:
        self.tabs = QTabWidget()
        self.tabs.addTab(self._sales_tab(), "Invoices")
        self.tabs.addTab(self._returns_tab(), "Returns")
        self.tabs.currentChanged.connect(lambda _i: self.reload())
        self.body.addWidget(self.tabs, 1)

    # ----------------------------------------------------------------- tabs
    def _sales_tab(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(10, 12, 10, 10)
        layout.setSpacing(10)

        filters = QHBoxLayout()
        self.search = SearchBox("Search invoice number or customer…")
        self.search.textChanged.connect(lambda _t: self._reload_sales())
        filters.addWidget(self.search, 3)
        self.date_from = DateEdit(dates.today_iso())
        self.date_to = DateEdit()
        for widget in (self.date_from, self.date_to):
            widget.dateChanged.connect(lambda _d: self._reload_sales())
        filters.addWidget(MutedLabel("From"))
        filters.addWidget(self.date_from)
        filters.addWidget(MutedLabel("to"))
        filters.addWidget(self.date_to)
        filters.addWidget(button("Today", on_click=lambda: self._quick_range("today")))
        filters.addWidget(button("This month", on_click=lambda: self._quick_range("month")))
        layout.addLayout(filters)

        split = QHBoxLayout()
        split.setSpacing(12)
        left = Card()
        left.body.addWidget(SectionTitle("Bills"))
        self.sales_table = DataTable(
            [
                Col("invoice_no", "Invoice"),
                Col("sale_date", "When", DATETIME),
                Col("customer", "Customer", stretch=True),
                Col("payment_method", "Payment"),
                Col("discount_amount", "Discount", MONEY),
                Col("net_amount", "Total", MONEY),
                Col("due", "Due", MONEY),
                Col("status", "Status"),
            ]
        )
        self.sales_table.row_style = lambda row: (
            "danger" if row["status"] == "returned" else ("warning" if row["due"] else "")
        )
        self.sales_table.rowSelected.connect(lambda _row: self._show_items())
        self.sales_table.rowActivated.connect(lambda _row: self._reprint())
        left.body.addWidget(self.sales_table, 1)
        self.sales_summary = MutedLabel("")
        left.body.addWidget(self.sales_summary)
        split.addWidget(left, 6)

        right = Card()
        right.body.addWidget(SectionTitle("Items on the selected bill"))
        self.items_table = DataTable(
            [
                Col("product_name", "Medicine", stretch=True),
                Col("batch_no", "Batch"),
                Col("expiry_date", "Expiry", DATE),
                Col("quantity", "Qty", INT),
                Col("returned_quantity", "Returned", INT),
                Col("unit_price", "Rate", MONEY),
                Col("discount_amount", "Discount", MONEY),
                Col("line_total", "Amount", MONEY),
            ]
        )
        right.body.addWidget(self.items_table, 1)
        tools = QHBoxLayout()
        tools.addWidget(button("Reprint receipt", on_click=self._reprint))
        tools.addWidget(button("Save as PDF", on_click=self._save_pdf))
        if self.can("returns.manage"):
            tools.addWidget(button("Return goods…", kind="Accent", on_click=self._return))
        if self.can("sales.delete"):
            tools.addWidget(button("Cancel bill", kind="Danger", on_click=self._cancel_sale))
        tools.addStretch(1)
        right.body.addLayout(tools)
        split.addWidget(right, 5)
        layout.addLayout(split, 1)
        return page

    def _returns_tab(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(10, 12, 10, 10)
        self.returns_table = DataTable(
            [
                Col("return_date", "When", DATETIME),
                Col("return_no", "Return no"),
                Col("invoice_no", "Against invoice"),
                Col("customer_name", "Customer", stretch=True),
                Col("reason", "Reason"),
                Col("username", "By"),
                Col("total_amount", "Refunded", MONEY),
            ]
        )
        layout.addWidget(self.returns_table, 1)
        self.returns_summary = MutedLabel("")
        layout.addWidget(self.returns_summary)
        return page

    # ---------------------------------------------------------------- reload
    def reload(self) -> None:
        if self.tabs.currentIndex() == 0:
            self._reload_sales()
        else:
            self._reload_returns()

    def focus_default(self) -> None:
        self.search.setFocus()

    def _quick_range(self, period: str) -> None:
        start, end = dates.date_range(period)
        self.date_from.set_iso(start)
        self.date_to.set_iso(end)

    def _reload_sales(self) -> None:
        rows = []
        for row in self.context.sales.list_sales(
            date_from=self.date_from.iso(),
            date_to=self.date_to.iso(),
            search=self.search.text(),
        ):
            entry = dict(row)
            entry["customer"] = row["party_name"] or row["customer_name"] or "Walk-in customer"
            entry["due"] = int(row["net_amount"]) - int(row["paid_amount"])
            rows.append(entry)
        self.sales_table.set_rows(rows)
        net = sum(row["net_amount"] for row in rows)
        discount = sum(row["discount_amount"] for row in rows)
        due = sum(row["due"] for row in rows)
        self.sales_summary.setText(
            f"{len(rows)} bill(s) · total {fmt(net, symbol=True)} · "
            f"discount given {fmt(discount, symbol=True)} · unpaid {fmt(due, symbol=True)}"
        )
        self._show_items()

    def _reload_returns(self) -> None:
        rows = self.context.sales.list_returns(
            date_from=self.date_from.iso(), date_to=self.date_to.iso()
        )
        self.returns_table.set_rows(rows)
        total = sum(int(row["total_amount"]) for row in rows)
        self.returns_summary.setText(
            f"{len(rows)} return(s) · refunded {fmt(total, symbol=True)}"
        )

    def _show_items(self) -> None:
        row = self.sales_table.current()
        if row is None:
            self.items_table.set_rows([])
            return
        self.items_table.set_rows(self.context.sales.sale_items(int(row["id"])))

    # --------------------------------------------------------------- actions
    def _selected(self):
        row = self.sales_table.current()
        if row is None:
            warn(self, "Choose a bill from the list first.")
        return row

    def _receipt_html(self, sale_id: int, page_format: str) -> str:
        sale = self.context.sales.get_sale(sale_id)
        items = self.context.sales.sale_items(sale_id)
        return printing.receipt_html(
            self.context.settings,
            sale,
            items,
            page_format=page_format,
            copy_label="DUPLICATE COPY",
        )

    def _reprint(self) -> None:
        row = self._selected()
        if row is None:
            return
        page_format = self.context.settings.get("receipt_format", printing.THERMAL)
        printing.preview_html(
            self, self._receipt_html(int(row["id"]), page_format), page_format=page_format
        )

    def _save_pdf(self) -> None:
        row = self._selected()
        if row is None:
            return
        from PySide6.QtWidgets import QFileDialog

        from ...core import config

        path, _filter = QFileDialog.getSaveFileName(
            self,
            "Save the bill as PDF",
            str(config.export_dir() / f"{row['invoice_no']}.pdf"),
            "PDF file (*.pdf)",
        )
        if not path:
            return
        printing.save_pdf(
            self._receipt_html(int(row["id"]), printing.A5), path, page_format=printing.A5
        )
        from ..widgets.common import info

        info(self, f"Saved to:\n{path}")

    def _return(self) -> None:
        row = self._selected()
        if row is None:
            return
        dialog = ReturnDialog(self.context, int(row["id"]), self)
        if dialog.exec() == QDialog.Accepted:
            self.notify_change()

    def _cancel_sale(self) -> None:
        row = self._selected()
        if row is None:
            return
        if not confirm(
            self,
            f"Cancel invoice {row['invoice_no']} completely?\n\n"
            "The medicines go back into stock and the bill is removed. "
            "For a partial refund use “Return goods…” instead.",
            danger=True,
        ):
            return
        try:
            self.context.sales.delete_sale(int(row["id"]), user=self.user)
        except PharmacyError as exc:
            error(self, str(exc))
            return
        self.notify_change()


class ReturnDialog(QDialog):
    """Choose which lines are coming back, and how many of each."""

    def __init__(self, context, sale_id: int, parent=None):
        super().__init__(parent)
        self.context = context
        self.sale_id = sale_id
        sale = context.sales.get_sale(sale_id)
        self.items = context.sales.sale_items(sale_id)
        self.setWindowTitle(f"Return goods against {sale['invoice_no']}")
        self.setMinimumSize(760, 480)
        box = QVBoxLayout(self)
        box.setSpacing(10)
        box.addWidget(
            MutedLabel(
                f"Sold {dates.fmt_datetime(sale['sale_date'])} to "
                f"<b>{sale['party_name'] or sale['customer_name'] or 'Walk-in customer'}</b> "
                f"for {fmt(sale['net_amount'], symbol=True)}. "
                "Enter how many units of each line are coming back — the refund keeps the "
                "discount the customer was given."
            )
        )

        from PySide6.QtWidgets import QTableWidget, QTableWidgetItem

        self.grid = QTableWidget(len(self.items), 6)
        self.grid.setHorizontalHeaderLabels(
            ["Medicine", "Batch", "Sold", "Already returned", "Return now", "Refund"]
        )
        self.grid.verticalHeader().setVisible(False)
        self.spins: list[QSpinBox] = []
        for row_index, item in enumerate(self.items):
            returnable = int(item["quantity"]) - int(item["returned_quantity"])
            for column, value in enumerate(
                [
                    item["product_name"],
                    item["batch_no"] or "",
                    str(item["quantity"]),
                    str(item["returned_quantity"]),
                ]
            ):
                cell = QTableWidgetItem(value)
                cell.setFlags(cell.flags() & ~2)  # not editable
                self.grid.setItem(row_index, column, cell)
            spin = QSpinBox()
            spin.setRange(0, max(returnable, 0))
            spin.valueChanged.connect(self._recalculate)
            self.spins.append(spin)
            self.grid.setCellWidget(row_index, 4, spin)
            self.grid.setItem(row_index, 5, QTableWidgetItem("0.00"))
        self.grid.resizeColumnsToContents()
        self.grid.horizontalHeader().setStretchLastSection(True)
        box.addWidget(self.grid, 1)

        self.reason = QLineEdit()
        self.reason.setPlaceholderText("Reason for the return (wrong medicine, damaged, …)")
        box.addWidget(self.reason)

        from PySide6.QtWidgets import QCheckBox

        self.restock = QCheckBox("Put the returned units back into stock")
        self.restock.setChecked(True)
        self.restock.setToolTip(
            "Leave this unticked if the medicine cannot be sold again — it will then be "
            "refunded but not added back to the shelf."
        )
        box.addWidget(self.restock)

        bottom = QHBoxLayout()
        self.total_label = MutedLabel("Refund: 0.00")
        self.total_label.setStyleSheet(
            f"font-size: 16px; font-weight: 700; color: {theme.GREEN_DARK};"
        )
        bottom.addWidget(self.total_label)
        bottom.addStretch(1)
        bottom.addWidget(button("Cancel", on_click=self.reject))
        bottom.addWidget(button("Save return", kind="Primary", on_click=self._save))
        box.addLayout(bottom)

    def _unit_refund(self, item) -> int:
        return round(int(item["line_total"]) / int(item["quantity"]))

    def _recalculate(self) -> None:
        from PySide6.QtWidgets import QTableWidgetItem

        total = 0
        for index, item in enumerate(self.items):
            refund = self.spins[index].value() * self._unit_refund(item)
            total += refund
            self.grid.setItem(index, 5, QTableWidgetItem(fmt(refund)))
        self.total_label.setText(f"Refund: {fmt(total, symbol=True)}")

    def _save(self) -> None:
        payload = [
            {"sale_item_id": int(item["id"]), "quantity": self.spins[index].value()}
            for index, item in enumerate(self.items)
            if self.spins[index].value() > 0
        ]
        if not payload:
            warn(self, "Enter how many units are coming back.")
            return
        try:
            self.context.sales.create_return(
                self.sale_id,
                payload,
                user=self.context.auth.current_user,
                reason=self.reason.text(),
                restock=self.restock.isChecked(),
            )
        except PharmacyError as exc:
            error(self, str(exc))
            return
        self.accept()
