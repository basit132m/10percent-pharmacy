"""Counter sale — the screen the shop lives on.

Everything here is built for speed with a keyboard and a barcode scanner: type
or scan on the left, the bill builds on the right, the 10% discount is already
applied, and Ctrl+Enter takes the money.
"""

from __future__ import annotations

from PySide6.QtCore import QTimer, Qt
from PySide6.QtGui import QFont, QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDoubleSpinBox,
    QFormLayout,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from ...core import dates
from ...core.errors import PharmacyError
from ...core.money import fmt, to_paisa
from ...core.services.sales import PAYMENT_METHODS
from .. import printing, theme
from ..widgets.common import (
    Card,
    MutedLabel,
    SearchBox,
    SectionTitle,
    button,
    confirm,
    error,
    info,
    warn,
)
from ..widgets.table import Col, DataTable, DATE, INT, MONEY
from .base import Page


class PosPage(Page):
    title = "Counter sale"
    subtitle = "Scan a barcode or type the medicine name"

    def build(self) -> None:
        self.cart = self.context.sales.new_cart()
        self.header.add_action(button("Hold bill", tooltip="Park this bill", shortcut="Ctrl+H",
                                      on_click=self._hold))
        self.header.add_action(button("Held bills…", on_click=self._show_held))
        self.header.add_action(button("Clear", kind="Danger", on_click=self._clear_clicked))
        self.header.add_action(
            button("Take payment", kind="Accent", shortcut="Ctrl+Return", on_click=self._checkout)
        )

        split = QHBoxLayout()
        split.setSpacing(12)
        split.addWidget(self._search_panel(), 5)
        split.addWidget(self._bill_panel(), 5)
        self.body.addLayout(split, 1)

        QShortcut(QKeySequence("Ctrl+F"), self, activated=self._focus_search)
        QShortcut(QKeySequence(Qt.Key_Delete), self.cart_table, activated=self._remove_line)
        QShortcut(QKeySequence(Qt.Key_Plus), self.cart_table, activated=lambda: self._bump(1))
        QShortcut(QKeySequence(Qt.Key_Minus), self.cart_table, activated=lambda: self._bump(-1))
        QShortcut(QKeySequence("F12"), self, activated=self._checkout)

        self._search_timer = QTimer(self)
        self._search_timer.setSingleShot(True)
        self._search_timer.setInterval(160)
        self._search_timer.timeout.connect(self._run_search)

    # --------------------------------------------------------------- panels
    def _search_panel(self) -> QWidget:
        card = Card()
        self.search = SearchBox("Scan barcode, or type medicine / generic name…")
        self.search.textChanged.connect(lambda _text: self._search_timer.start())
        self.search.returnPressed.connect(self._add_highlighted)
        card.body.addWidget(self.search)

        quantity_row = QHBoxLayout()
        quantity_row.addWidget(QLabel("Quantity"))
        self.quantity = QSpinBox()
        self.quantity.setRange(1, 100000)
        self.quantity.setValue(1)
        self.quantity.setMinimumWidth(90)
        self.quantity.lineEdit().returnPressed.connect(self._add_highlighted)
        quantity_row.addWidget(self.quantity)
        quantity_row.addStretch(1)
        quantity_row.addWidget(
            button("Add to bill (Enter)", kind="Primary", on_click=self._add_highlighted)
        )
        card.body.addLayout(quantity_row)

        self.results = DataTable(
            [
                Col("name", "Medicine", stretch=True, width=180),
                Col("strength", "Strength"),
                Col("sellable_quantity", "Stock", INT),
                Col("sale_price", "Price", MONEY),
                Col("nearest_expiry", "Expiry", DATE),
            ],
            row_height=32,
        )
        self.results.row_style = self._result_tone
        self.results.rowActivated.connect(lambda _row: self._add_highlighted())
        self.results.rowSelected.connect(self._show_batches)
        card.body.addWidget(self.results, 1)

        self.batch_hint = MutedLabel(
            "Batches are picked automatically — the one expiring first is sold first."
        )
        card.body.addWidget(self.batch_hint)
        self.batch_list = QListWidget()
        self.batch_list.setMaximumHeight(96)
        self.batch_list.setToolTip(
            "Double-click a batch to sell from that batch instead of the automatic choice."
        )
        self.batch_list.itemDoubleClicked.connect(self._add_from_batch)
        card.body.addWidget(self.batch_list)
        return card

    def _bill_panel(self) -> QWidget:
        card = Card()
        top = QHBoxLayout()
        top.addWidget(SectionTitle("Current bill"))
        top.addStretch(1)
        self.customer_label = QLabel("Walk-in customer")
        self.customer_label.setStyleSheet(f"color: {theme.MUTED};")
        top.addWidget(self.customer_label)
        top.addWidget(button("Customer…", on_click=self._pick_customer))
        card.body.addLayout(top)

        self.cart_table = DataTable(
            [
                Col("name", "Medicine", stretch=True, width=150),
                Col("batch", "Batch"),
                Col("expiry", "Expiry", DATE),
                Col("qty", "Qty", INT),
                Col("price", "Rate", MONEY),
                Col("discount", "Discount", MONEY),
                Col("total", "Amount", MONEY),
            ],
            row_height=32,
        )
        self.cart_table.rowActivated.connect(lambda _row: self._edit_line())
        card.body.addWidget(self.cart_table, 1)

        line_tools = QHBoxLayout()
        line_tools.addWidget(button("− 1", on_click=lambda: self._bump(-1)))
        line_tools.addWidget(button("+ 1", on_click=lambda: self._bump(1)))
        line_tools.addWidget(button("Edit line…", on_click=self._edit_line))
        line_tools.addWidget(button("Remove (Del)", kind="Danger", on_click=self._remove_line))
        line_tools.addStretch(1)
        card.body.addLayout(line_tools)

        card.body.addWidget(self._totals_panel())
        return card

    def _totals_panel(self) -> QWidget:
        panel = QWidget()
        panel.setStyleSheet(
            f"background: {theme.GREEN_LIGHT}; border-radius: 10px;"
        )
        grid = QGridLayout(panel)
        grid.setContentsMargins(16, 12, 16, 12)
        grid.setVerticalSpacing(4)
        self.total_labels: dict[str, QLabel] = {}
        rows = [
            ("gross", "Sub total"),
            ("discount", "Discount"),
            ("tax", "Tax"),
            ("round", "Round off"),
            ("net", "TOTAL PAYABLE"),
        ]
        for index, (key, label) in enumerate(rows):
            name = QLabel(label)
            value = QLabel("0.00")
            value.setAlignment(Qt.AlignRight)
            if key == "net":
                for widget in (name, value):
                    font = widget.font()
                    font.setPointSizeF(font.pointSizeF() + 7)
                    font.setWeight(QFont.Bold)
                    widget.setFont(font)
                value.setStyleSheet(f"color: {theme.GREEN_DARK};")
            elif key == "discount":
                value.setStyleSheet(f"color: {theme.GOLD}; font-weight: 700;")
            self.total_labels[key] = value
            grid.addWidget(name, index, 0)
            grid.addWidget(value, index, 1)
        self.savings_label = QLabel("")
        self.savings_label.setAlignment(Qt.AlignRight)
        self.savings_label.setStyleSheet(f"color: {theme.GREEN_DARK}; font-weight: 600;")
        grid.addWidget(self.savings_label, len(rows), 0, 1, 2)
        grid.setColumnStretch(0, 1)
        return panel

    # -------------------------------------------------------------- searching
    def _result_tone(self, row) -> str:
        if int(row["sellable_quantity"] or 0) <= 0:
            return "danger"
        if row["reorder_level"] and int(row["sellable_quantity"]) <= int(row["reorder_level"]):
            return "warning"
        return ""

    def _focus_search(self) -> None:
        self.search.setFocus()
        self.search.selectAll()

    focus_default = _focus_search

    def _run_search(self) -> None:
        term = self.search.text().strip()
        if len(term) >= 3:
            scanned = self.context.catalog.find_by_barcode(term)
            if scanned is not None:
                self.search.clear()
                self._add_product(scanned, self.quantity.value())
                return
        self.results.set_rows(self.context.catalog.search_for_sale(term))
        self._show_batches(self.results.current())

    def _show_batches(self, row) -> None:
        self.batch_list.clear()
        if row is None:
            return
        for batch in self.context.inventory.batches_for(int(row["id"]), only_available=True):
            days = batch["days_to_expiry"]
            label = (
                f"Batch {batch['batch_no']} · {batch['quantity']} left · "
                f"expiry {dates.fmt_date(batch['expiry_date'], 'not set')}"
            )
            if days is not None and days < 0:
                label += "  ⛔ EXPIRED"
            elif days is not None and days <= 90:
                label += f"  ⚠ {days} days"
            item = QListWidgetItem(label)
            item.setData(Qt.UserRole, (int(row["id"]), int(batch["id"])))
            if days is not None and days < 0:
                item.setForeground(Qt.red)
            self.batch_list.addItem(item)

    # ------------------------------------------------------------ cart edits
    def _add_highlighted(self) -> None:
        row = self.results.current()
        if row is None:
            if self.search.text().strip():
                warn(self, "No medicine matched that. Check the spelling, or add it first.")
            return
        self._add_product(row, self.quantity.value())

    def _add_from_batch(self, item: QListWidgetItem) -> None:
        product_id, batch_id = item.data(Qt.UserRole)
        product = self.context.catalog.get(product_id)
        self._add_product(product, self.quantity.value(), batch_id=batch_id)

    def _add_product(self, product, quantity: int, *, batch_id: int | None = None) -> None:
        if product["prescription_required"]:
            self.header.set_subtitle(
                f"⚠ {product['name']} is a prescription medicine — check the doctor's slip."
            )
        try:
            self.context.sales.add_to_cart(
                self.cart, product, quantity, batch_id=batch_id
            )
        except PharmacyError as exc:
            warn(self, str(exc))
            return
        self.quantity.setValue(1)
        self.search.clear()
        self.search.setFocus()
        self._refresh_cart()

    def _selected_index(self) -> int | None:
        index = self.cart_table.currentRow()
        return index if 0 <= index < len(self.cart.lines) else None

    def _bump(self, delta: int) -> None:
        index = self._selected_index()
        if index is None:
            return
        try:
            self.context.sales.set_line_quantity(
                self.cart, index, self.cart.lines[index].quantity + delta
            )
        except PharmacyError as exc:
            warn(self, str(exc))
            return
        self._refresh_cart(keep_row=index)

    def _remove_line(self) -> None:
        index = self._selected_index()
        if index is None:
            return
        self.cart.remove(index)
        self._refresh_cart()

    def _edit_line(self) -> None:
        index = self._selected_index()
        if index is None:
            return
        line = self.cart.lines[index]
        dialog = LineEditor(self.context, line, self)
        if dialog.exec() != QDialog.Accepted:
            return
        try:
            self.context.sales.set_line_quantity(self.cart, index, dialog.quantity())
        except PharmacyError as exc:
            warn(self, str(exc))
        if index < len(self.cart.lines):
            self.cart.lines[index].discount_percent = dialog.discount()
            if dialog.unit_price() is not None:
                self.cart.lines[index].unit_price = dialog.unit_price()
        self._refresh_cart(keep_row=index)

    def _clear_clicked(self) -> None:
        if self.cart.is_empty:
            return
        if confirm(self, "Clear this bill and start again?", danger=True):
            self.cart = self.context.sales.new_cart()
            self._refresh_cart()

    def _pick_customer(self) -> None:
        dialog = CustomerPicker(self.context, self)
        if dialog.exec() != QDialog.Accepted:
            return
        self.cart.customer_id = dialog.customer_id
        self.cart.customer_name = dialog.customer_name
        self.cart.doctor_name = dialog.doctor_name()
        self._refresh_cart()

    # ---------------------------------------------------------------- totals
    def _refresh_cart(self, *, keep_row: int | None = None) -> None:
        rows = [
            {
                "name": line.product_name,
                "batch": line.batch_no,
                "expiry": line.expiry_date,
                "qty": line.quantity,
                "price": line.unit_price,
                "discount": line.discount_amount,
                "total": line.total,
            }
            for line in self.cart.lines
        ]
        self.cart_table.set_rows(rows)
        if keep_row is not None and 0 <= keep_row < len(rows):
            self.cart_table.selectRow(keep_row)
        self.total_labels["gross"].setText(fmt(self.cart.gross_amount))
        self.total_labels["discount"].setText("− " + fmt(self.cart.discount_amount))
        self.total_labels["tax"].setText(fmt(self.cart.tax_amount))
        self.total_labels["round"].setText(fmt(self.cart.round_off))
        self.total_labels["net"].setText(fmt(self.cart.net_amount, symbol=True))
        self.savings_label.setText(
            f"Customer saves {fmt(self.cart.savings, symbol=True)} on this bill"
            if self.cart.savings
            else ""
        )
        self.customer_label.setText(self.cart.customer_name or "Walk-in customer")

    def has_unsaved_bill(self) -> bool:
        return not self.cart.is_empty

    # -------------------------------------------------------------- checkout
    def _checkout(self) -> None:
        if self.cart.is_empty:
            warn(self, "Add at least one medicine to the bill first.")
            return
        dialog = PaymentDialog(self.context, self.cart, self)
        if dialog.exec() != QDialog.Accepted:
            return
        try:
            sale_id = self.context.sales.complete_sale(
                self.cart,
                user=self.user,
                paid_amount=dialog.paid_amount(),
                payment_method=dialog.payment_method(),
            )
        except PharmacyError as exc:
            error(self, str(exc))
            return
        self.cart = self.context.sales.new_cart()
        self._refresh_cart()
        self._run_search()
        self.notify_change()
        self._after_sale(sale_id, print_now=dialog.should_print())
        self.search.setFocus()

    def _after_sale(self, sale_id: int, *, print_now: bool) -> None:
        sale = self.context.sales.get_sale(sale_id)
        items = self.context.sales.sale_items(sale_id)
        page_format = self.context.settings.get("receipt_format", printing.THERMAL)
        content = printing.receipt_html(
            self.context.settings, sale, items, page_format=page_format
        )
        if print_now:
            try:
                printing.print_html(self, content, page_format=page_format, ask=False)
            except Exception as exc:  # pragma: no cover - depends on the printer
                warn(self, f"The bill was saved, but printing failed:\n{exc}")
        self.header.set_subtitle(
            f"Saved {sale['invoice_no']} — {fmt(sale['net_amount'], symbol=True)}"
            f" · customer saved {fmt(sale['discount_amount'], symbol=True)}"
        )

    # ----------------------------------------------------------- held bills
    def _hold(self) -> None:
        if self.cart.is_empty:
            return
        label = self.cart.customer_name or dates.fmt_datetime(dates.now_iso())
        self.context.sales.hold_cart(self.cart, label, user=self.user)
        self.cart = self.context.sales.new_cart()
        self._refresh_cart()
        info(self, f"Bill held as “{label}”. Pick it up from “Held bills…”.")

    def _show_held(self) -> None:
        held = self.context.sales.held_carts()
        if not held:
            info(self, "There are no held bills.")
            return
        dialog = HeldBillsDialog(self.context, held, self)
        if dialog.exec() != QDialog.Accepted or dialog.chosen_id is None:
            return
        if not self.cart.is_empty:
            self._hold()
        self.cart = self.context.sales.resume_cart(dialog.chosen_id)
        self._refresh_cart()

    def reload(self) -> None:
        self._run_search()
        self._refresh_cart()


# --------------------------------------------------------------------- dialogs
class LineEditor(QDialog):
    """Change quantity, price or discount on one line of the bill."""

    def __init__(self, context, line, parent=None):
        super().__init__(parent)
        self.context = context
        self.line = line
        self.setWindowTitle(line.product_name)
        self.setMinimumWidth(400)
        box = QVBoxLayout(self)
        box.setSpacing(12)
        form = QFormLayout()
        form.setSpacing(9)

        self._quantity = QSpinBox()
        self._quantity.setRange(1, 100000)
        self._quantity.setValue(line.quantity)
        form.addRow("Quantity", self._quantity)

        self._discount = QDoubleSpinBox()
        self._discount.setRange(0, 100)
        self._discount.setDecimals(2)
        self._discount.setSuffix(" %")
        self._discount.setValue(line.discount_percent)
        can_override = context.auth.current_user and context.auth.current_user.can(
            "pos.discount_override"
        )
        self._discount.setEnabled(bool(can_override))
        form.addRow("Discount", self._discount)

        self._price = QLineEdit(fmt(line.unit_price, grouping=False))
        self._price.setEnabled(
            bool(context.auth.current_user and context.auth.current_user.can("pos.price_override"))
        )
        form.addRow("Rate", self._price)
        box.addLayout(form)
        box.addWidget(
            MutedLabel(
                f"Batch {line.batch_no} · expiry {dates.fmt_date(line.expiry_date, 'not set')} · "
                f"{line.available} in this batch"
            )
        )
        if not can_override:
            box.addWidget(
                MutedLabel("Only a manager or the owner can change the discount or the rate.")
            )
        buttons = QHBoxLayout()
        buttons.addStretch(1)
        buttons.addWidget(button("Cancel", on_click=self.reject))
        buttons.addWidget(button("Apply", kind="Primary", on_click=self._apply))
        box.addLayout(buttons)

    def _apply(self) -> None:
        limit = self.context.settings.get_float("max_discount_percent", 25)
        if self._discount.value() > limit:
            warn(self, f"The most that may be given is {limit:g}%.")
            return
        self.accept()

    def quantity(self) -> int:
        return self._quantity.value()

    def discount(self) -> float:
        return float(self._discount.value())

    def unit_price(self) -> int | None:
        if not self._price.isEnabled():
            return None
        try:
            return to_paisa(self._price.text())
        except ValueError:
            return None


class CustomerPicker(QDialog):
    """Attach a named customer (and optionally a doctor) to the bill."""

    def __init__(self, context, parent=None):
        super().__init__(parent)
        self.context = context
        self.customer_id: int | None = None
        self.customer_name = ""
        self.setWindowTitle("Choose customer")
        self.setMinimumSize(620, 480)
        box = QVBoxLayout(self)
        box.setSpacing(10)

        self.search = SearchBox("Search by name or phone…")
        self.search.textChanged.connect(self._reload)
        box.addWidget(self.search)

        self.table = DataTable(
            [
                Col("name", "Customer", stretch=True),
                Col("phone", "Phone"),
                Col("balance", "Balance", MONEY),
            ]
        )
        self.table.rowActivated.connect(lambda _row: self._choose())
        box.addWidget(self.table, 1)

        self._doctor = QLineEdit()
        self._doctor.setPlaceholderText("Doctor's name (optional, printed on the bill)")
        box.addWidget(self._doctor)

        buttons = QHBoxLayout()
        buttons.addWidget(button("New customer…", on_click=self._new_customer))
        buttons.addStretch(1)
        buttons.addWidget(button("Walk-in (no account)", on_click=self._walk_in))
        buttons.addWidget(button("Choose", kind="Primary", on_click=self._choose))
        box.addLayout(buttons)
        self._reload()

    def _reload(self) -> None:
        self.table.set_rows(
            self.context.parties.list_parties("customer", self.search.text())
        )

    def _new_customer(self) -> None:
        from .parties import PartyDialog

        dialog = PartyDialog(self.context, "customer", parent=self)
        if dialog.exec() == QDialog.Accepted:
            self._reload()

    def _walk_in(self) -> None:
        self.customer_id = None
        self.customer_name = ""
        self.accept()

    def _choose(self) -> None:
        row = self.table.current()
        if row is None:
            warn(self, "Pick a customer from the list, or choose Walk-in.")
            return
        self.customer_id = int(row["id"])
        self.customer_name = row["name"]
        self.accept()

    def doctor_name(self) -> str:
        return self._doctor.text().strip()


class PaymentDialog(QDialog):
    """Take the money: amount tendered, method, change to hand back."""

    def __init__(self, context, cart, parent=None):
        super().__init__(parent)
        self.context = context
        self.cart = cart
        self.setWindowTitle("Take payment")
        self.setMinimumWidth(460)
        box = QVBoxLayout(self)
        box.setContentsMargins(20, 18, 20, 16)
        box.setSpacing(12)

        total = QLabel(f"Payable  {fmt(cart.net_amount, symbol=True)}")
        font = total.font()
        font.setPointSizeF(font.pointSizeF() + 9)
        font.setWeight(QFont.Bold)
        total.setFont(font)
        total.setAlignment(Qt.AlignCenter)
        total.setStyleSheet(f"color: {theme.GREEN_DARK};")
        box.addWidget(total)
        if cart.savings:
            saved = QLabel(f"Customer saved {fmt(cart.savings, symbol=True)}")
            saved.setAlignment(Qt.AlignCenter)
            saved.setStyleSheet(f"color: {theme.GOLD}; font-weight: 700;")
            box.addWidget(saved)

        form = QFormLayout()
        form.setSpacing(9)
        self._method = QComboBox()
        self._method.addItems(PAYMENT_METHODS)
        self._method.currentTextChanged.connect(self._method_changed)
        form.addRow("Payment method", self._method)

        self._paid = QLineEdit(fmt(cart.net_amount, grouping=False))
        self._paid.setAlignment(Qt.AlignRight)
        self._paid.textChanged.connect(self._recalculate)
        form.addRow("Amount received", self._paid)
        box.addLayout(form)

        quick = QHBoxLayout()
        for amount in self._quick_amounts(cart.net_amount):
            quick.addWidget(
                button(fmt(amount, grouping=True), on_click=lambda _=False, a=amount: self._set(a))
            )
        quick.addStretch(1)
        box.addLayout(quick)

        self._change = QLabel()
        self._change.setAlignment(Qt.AlignCenter)
        self._change.setStyleSheet("font-size: 18px; font-weight: 700;")
        box.addWidget(self._change)

        from PySide6.QtWidgets import QCheckBox

        self._print = QCheckBox("Print the receipt now")
        self._print.setChecked(context.settings.get_bool("print_after_sale", True))
        box.addWidget(self._print)

        buttons = QHBoxLayout()
        buttons.addStretch(1)
        buttons.addWidget(button("Cancel", on_click=self.reject))
        self._save = button("Save & print", kind="Accent", big=True, on_click=self._confirm)
        self._save.setDefault(True)
        buttons.addWidget(self._save)
        box.addLayout(buttons)
        self._paid.setFocus()
        self._paid.selectAll()
        self._recalculate()

    @staticmethod
    def _quick_amounts(net: int) -> list[int]:
        options = [net]
        for note in (5000, 10000, 50000, 100000):  # Rs 50 / 100 / 500 / 1000
            rounded = ((net + note - 1) // note) * note
            if rounded > net and rounded not in options:
                options.append(rounded)
        return options[:5]

    def _set(self, amount: int) -> None:
        self._paid.setText(fmt(amount, grouping=False))

    def _method_changed(self, method: str) -> None:
        if method == "Credit":
            self._paid.setText("0")
        self._recalculate()

    def _recalculate(self) -> None:
        paid = self.paid_amount()
        difference = paid - self.cart.net_amount
        if difference >= 0:
            self._change.setText(f"Change to return: {fmt(difference, symbol=True)}")
            self._change.setStyleSheet(f"color: {theme.GREEN_DARK}; font-size: 18px;")
        else:
            self._change.setText(f"Balance left on account: {fmt(-difference, symbol=True)}")
            self._change.setStyleSheet(f"color: {theme.DANGER}; font-size: 18px;")

    def _confirm(self) -> None:
        if self.paid_amount() < self.cart.net_amount and not self.cart.customer_id:
            warn(
                self,
                "The amount received is less than the total. Choose a customer for the "
                "credit, or take the full amount.",
            )
            return
        self.accept()

    def paid_amount(self) -> int:
        try:
            return to_paisa(self._paid.text())
        except ValueError:
            return 0

    def payment_method(self) -> str:
        return self._method.currentText()

    def should_print(self) -> bool:
        return self._print.isChecked()


class HeldBillsDialog(QDialog):
    def __init__(self, context, held, parent=None):
        super().__init__(parent)
        self.context = context
        self.chosen_id: int | None = None
        self.setWindowTitle("Held bills")
        self.setMinimumSize(560, 380)
        box = QVBoxLayout(self)
        self.table = DataTable(
            [
                Col("label", "Held as", stretch=True),
                Col("created_at", "When", "datetime"),
                Col("username", "By"),
            ]
        )
        self.table.set_rows(held)
        self.table.rowActivated.connect(lambda _row: self._resume())
        box.addWidget(self.table, 1)
        buttons = QHBoxLayout()
        buttons.addWidget(button("Discard", kind="Danger", on_click=self._discard))
        buttons.addStretch(1)
        buttons.addWidget(button("Close", on_click=self.reject))
        buttons.addWidget(button("Pick up", kind="Primary", on_click=self._resume))
        box.addLayout(buttons)

    def _resume(self) -> None:
        row = self.table.current()
        if row is None:
            return
        self.chosen_id = int(row["id"])
        self.accept()

    def _discard(self) -> None:
        row = self.table.current()
        if row is None or not confirm(self, f"Throw away the held bill “{row['label']}”?"):
            return
        self.context.sales.discard_held(int(row["id"]))
        self.table.set_rows(self.context.sales.held_carts())
