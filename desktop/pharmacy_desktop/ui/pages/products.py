"""Medicines — the master list, its editor, and bulk import/export."""

from __future__ import annotations

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLineEdit,
    QPlainTextEdit,
    QSpinBox,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from ...core import config
from ...core.errors import PharmacyError
from ...core.money import fmt
from ...core.services.catalog import DOSAGE_FORMS
from ..widgets.common import (
    MoneyEdit,
    MutedLabel,
    SearchBox,
    SectionTitle,
    button,
    confirm,
    error,
    info,
    warn,
)
from ..widgets.table import BOOL, Col, DataTable, DATE, INT, MONEY
from .base import Page


class ProductsPage(Page):
    title = "Medicines"
    subtitle = "Every item the pharmacy sells"

    def build(self) -> None:
        may_edit = self.can("catalog.manage")
        if may_edit:
            self.header.add_action(
                button("Add medicine", kind="Primary", shortcut="Ctrl+N", on_click=self._add)
            )
            self.header.add_action(button("Import from file…", on_click=self._import))
        self.header.add_action(button("Export to Excel/CSV", on_click=self._export))

        filters = QHBoxLayout()
        self.search = SearchBox("Search by name, generic, company or barcode…")
        self.search.textChanged.connect(lambda _t: self._debounce.start())
        filters.addWidget(self.search, 3)

        self.category = QComboBox()
        self.category.currentIndexChanged.connect(lambda _i: self.reload())
        filters.addWidget(self.category, 1)

        self.stock_filter = QComboBox()
        for label, value in [
            ("All stock levels", "all"),
            ("In stock", "in"),
            ("Low / at reorder level", "low"),
            ("Out of stock", "out"),
        ]:
            self.stock_filter.addItem(label, value)
        self.stock_filter.currentIndexChanged.connect(lambda _i: self.reload())
        filters.addWidget(self.stock_filter, 1)

        self.show_inactive = QCheckBox("Include inactive")
        self.show_inactive.stateChanged.connect(lambda _s: self.reload())
        filters.addWidget(self.show_inactive)
        self.body.addLayout(filters)

        self.table = DataTable(
            [
                Col("name", "Medicine", stretch=True),
                Col("generic_name", "Generic"),
                Col("manufacturer_name", "Company"),
                Col("form", "Form"),
                Col("strength", "Strength"),
                Col("pack_size", "Pack", INT),
                Col("stock_quantity", "In stock", INT),
                Col("reorder_level", "Reorder at", INT),
                Col("purchase_price", "Cost", MONEY),
                Col("sale_price", "Retail", MONEY),
                Col("nearest_expiry", "First expiry", DATE),
                Col("rack", "Rack"),
                Col("prescription_required", "Rx", BOOL),
            ]
        )
        self.table.row_style = self._tone
        self.table.rowActivated.connect(lambda _row: self._edit())
        self.body.addWidget(self.table, 1)

        tools = QHBoxLayout()
        self.count_label = MutedLabel("")
        tools.addWidget(self.count_label)
        tools.addStretch(1)
        if may_edit:
            tools.addWidget(button("Edit (Enter)", on_click=self._edit))
            tools.addWidget(button("Receive stock…", on_click=self._add_stock))
            tools.addWidget(button("Turn on/off", on_click=self._toggle_active))
            tools.addWidget(button("Delete", kind="Danger", on_click=self._delete))
            tools.addWidget(button("Categories & companies…", on_click=self._manage_lookups))
        self.body.addLayout(tools)

        self._debounce = QTimer(self)
        self._debounce.setSingleShot(True)
        self._debounce.setInterval(180)
        self._debounce.timeout.connect(self.reload)

    def focus_default(self) -> None:
        self.search.setFocus()

    @staticmethod
    def _tone(row) -> str:
        if not row["is_active"]:
            return "muted"
        if int(row["stock_quantity"] or 0) <= 0:
            return "danger"
        if row["reorder_level"] and int(row["stock_quantity"]) <= int(row["reorder_level"]):
            return "warning"
        return ""

    # ---------------------------------------------------------------- reload
    def reload(self) -> None:
        selected = self.category.currentData()
        if self.category.count() == 0:
            self.category.addItem("All categories", None)
            for row in self.context.catalog.categories():
                self.category.addItem(row["name"], int(row["id"]))
        rows = self.context.catalog.list_products(
            self.search.text(),
            category_id=selected,
            only_active=not self.show_inactive.isChecked(),
            stock_filter=self.stock_filter.currentData() or "all",
        )
        self.table.set_rows(rows)
        value = sum(int(row["stock_quantity"] or 0) * int(row["purchase_price"]) for row in rows)
        self.count_label.setText(
            f"{len(rows)} medicine(s) shown · stock value at cost {fmt(value, symbol=True)}"
        )

    # --------------------------------------------------------------- actions
    def _selected(self):
        row = self.table.current()
        if row is None:
            warn(self, "Choose a medicine from the list first.")
        return row

    def _add(self) -> None:
        if ProductDialog(self.context, parent=self).exec() == QDialog.Accepted:
            self.notify_change()

    def _edit(self) -> None:
        row = self._selected()
        if row is None:
            return
        if not self.can("catalog.manage"):
            ProductDialog(self.context, row, parent=self, read_only=True).exec()
            return
        if ProductDialog(self.context, row, parent=self).exec() == QDialog.Accepted:
            self.notify_change()

    def _add_stock(self) -> None:
        row = self._selected()
        if row is None:
            return
        from .stock import ReceiveStockDialog

        if ReceiveStockDialog(self.context, int(row["id"]), parent=self).exec() == QDialog.Accepted:
            self.notify_change()

    def _toggle_active(self) -> None:
        row = self._selected()
        if row is None:
            return
        active = not row["is_active"]
        self.context.catalog.set_active(int(row["id"]), active)
        self.reload()

    def _delete(self) -> None:
        row = self._selected()
        if row is None:
            return
        if not confirm(self, f"Delete “{row['name']}” from the medicine list?", danger=True):
            return
        try:
            self.context.catalog.delete_product(int(row["id"]))
        except PharmacyError as exc:
            error(self, str(exc))
            return
        self.notify_change()

    def _manage_lookups(self) -> None:
        LookupDialog(self.context, self).exec()
        self.category.clear()
        self.reload()

    # ----------------------------------------------------------- import/export
    def _export(self) -> None:
        path, _filter = QFileDialog.getSaveFileName(
            self,
            "Save the medicine list",
            str(config.export_dir() / "medicines.csv"),
            "Spreadsheet (*.csv)",
        )
        if not path:
            return
        self.context.catalog.export_csv(path, self.table.rows())
        info(self, f"Saved to:\n{path}\n\nThis file opens in Excel.")

    def _import(self) -> None:
        dialog = ImportDialog(self.context, self)
        if dialog.exec() == QDialog.Accepted:
            self.notify_change()


class ProductDialog(QDialog):
    """Add or change one medicine."""

    def __init__(self, context, row=None, parent=None, *, read_only: bool = False):
        super().__init__(parent)
        self.context = context
        self.row = row
        self.read_only = read_only
        self.setWindowTitle(row["name"] if row is not None else "New medicine")
        self.setMinimumWidth(640)
        box = QVBoxLayout(self)
        box.setSpacing(12)

        tabs = QTabWidget()
        tabs.addTab(self._identity_tab(), "Medicine")
        tabs.addTab(self._pricing_tab(), "Pricing & stock")
        box.addWidget(tabs)

        buttons = QHBoxLayout()
        buttons.addStretch(1)
        buttons.addWidget(button("Close" if read_only else "Cancel", on_click=self.reject))
        if not read_only:
            buttons.addWidget(button("Save", kind="Primary", on_click=self._save))
        box.addLayout(buttons)
        self._load()

    # ------------------------------------------------------------------ tabs
    def _identity_tab(self) -> QWidget:
        page = QWidget()
        form = QFormLayout(page)
        form.setSpacing(9)
        self.name = QLineEdit()
        self.name.setPlaceholderText("Brand name as printed on the pack, e.g. Panadol 500mg")
        self.generic = QLineEdit()
        self.generic.setPlaceholderText("Salt / formula, e.g. Paracetamol")
        self.company = QComboBox()
        self.company.setEditable(True)
        self.category = QComboBox()
        self.category.setEditable(True)
        self.form_field = QComboBox()
        self.form_field.setEditable(True)
        self.form_field.addItems(DOSAGE_FORMS)
        self.strength = QLineEdit()
        self.strength.setPlaceholderText("e.g. 500mg, 125mg/5ml")
        self.barcode = QLineEdit()
        self.barcode.setPlaceholderText("Scan the pack barcode here (optional)")
        self.code = QLineEdit()
        self.code.setPlaceholderText("Your own short code (optional)")
        self.rack = QLineEdit()
        self.rack.setPlaceholderText("Where it sits, e.g. B-3")
        self.prescription = QCheckBox("Prescription only — warn at the counter")
        self.discountable = QCheckBox("Give the standard discount on this item")
        self.discountable.setChecked(True)
        self.notes = QPlainTextEdit()
        self.notes.setMaximumHeight(70)

        form.addRow("Name *", self.name)
        form.addRow("Generic name", self.generic)
        form.addRow("Company", self.company)
        form.addRow("Category", self.category)
        form.addRow("Form", self.form_field)
        form.addRow("Strength", self.strength)
        form.addRow("Barcode", self.barcode)
        form.addRow("Item code", self.code)
        form.addRow("Rack / shelf", self.rack)
        form.addRow("", self.prescription)
        form.addRow("", self.discountable)
        form.addRow("Notes", self.notes)
        return page

    def _pricing_tab(self) -> QWidget:
        page = QWidget()
        form = QFormLayout(page)
        form.setSpacing(9)
        self.pack_size = QSpinBox()
        self.pack_size.setRange(1, 100000)
        self.pack_size.setValue(1)
        self.unit_label = QComboBox()
        self.unit_label.setEditable(True)
        self.unit_label.addItems(
            ["Tablet", "Capsule", "Bottle", "Sachet", "Vial", "Tube", "Piece", "Pack", "Unit"]
        )
        self.cost = MoneyEdit()
        self.retail = MoneyEdit()
        self.tax = QLineEdit("0")
        self.reorder = QSpinBox()
        self.reorder.setRange(0, 1000000)
        self.reorder.setValue(self.context.settings.get_int("default_reorder_level", 10))

        form.addRow("Units in one pack", self.pack_size)
        form.addRow("Sold as", self.unit_label)
        form.addRow("Cost price (per unit)", self.cost)
        form.addRow("Retail price (per unit)", self.retail)
        form.addRow("Tax %", self.tax)
        form.addRow("Reorder level", self.reorder)
        hint = MutedLabel(
            "Prices are per single unit — if a strip of 10 tablets costs Rs 27.50, "
            "enter 2.75 as the cost. The counter screen sells in units."
        )
        form.addRow("", hint)

        self.margin_hint = MutedLabel("")
        self.cost.textChanged.connect(self._update_margin)
        self.retail.textChanged.connect(self._update_margin)
        form.addRow("", self.margin_hint)

        if self.row is not None:
            stock = MutedLabel(
                f"In stock now: {self.row['stock_quantity']} "
                f"{(self.row['unit_label'] or 'unit').lower()}(s) across "
                f"{len(self.context.inventory.batches_for(int(self.row['id'])))} batch(es). "
                "Use “Receive stock…” to add more."
            )
            form.addRow("", stock)
        return page

    def _update_margin(self) -> None:
        cost, retail = self.cost.paisa(), self.retail.paisa()
        if not cost or not retail:
            self.margin_hint.setText("")
            return
        margin = retail - cost
        percent = margin * 100 / cost if cost else 0
        after_discount = retail - round(retail * self.context.settings.discount_percent / 100)
        self.margin_hint.setText(
            f"Margin {fmt(margin, symbol=True)} ({percent:.1f}%). "
            f"After the standard {self.context.settings.discount_percent:g}% discount the "
            f"customer pays {fmt(after_discount, symbol=True)} and the shop keeps "
            f"{fmt(after_discount - cost, symbol=True)}."
        )

    # ------------------------------------------------------------------ data
    def _load(self) -> None:
        for widget, rows, key in (
            (self.company, self.context.catalog.manufacturers(), "manufacturer_name"),
            (self.category, self.context.catalog.categories(), "category_name"),
        ):
            widget.addItem("")
            for row in rows:
                widget.addItem(row["name"])
        if self.row is None:
            self._update_margin()
            return
        row = self.row
        self.name.setText(row["name"])
        self.generic.setText(row["generic_name"] or "")
        self.company.setCurrentText(row["manufacturer_name"] or "")
        self.category.setCurrentText(row["category_name"] or "")
        self.form_field.setCurrentText(row["form"] or "")
        self.strength.setText(row["strength"] or "")
        self.barcode.setText(row["barcode"] or "")
        self.code.setText(row["code"] or "")
        self.rack.setText(row["rack"] or "")
        self.prescription.setChecked(bool(row["prescription_required"]))
        self.discountable.setChecked(bool(row["discount_eligible"]))
        self.notes.setPlainText(row["notes"] or "")
        self.pack_size.setValue(int(row["pack_size"]))
        self.unit_label.setCurrentText(row["unit_label"])
        self.cost.set_paisa(int(row["purchase_price"]))
        self.retail.set_paisa(int(row["sale_price"]))
        self.tax.setText(str(row["tax_percent"]))
        self.reorder.setValue(int(row["reorder_level"]))
        self._update_margin()
        if self.read_only:
            for widget in self.findChildren(QWidget):
                if isinstance(
                    widget, (QLineEdit, QComboBox, QSpinBox, QCheckBox, QPlainTextEdit, MoneyEdit)
                ):
                    widget.setEnabled(False)

    def _values(self) -> dict:
        return {
            "name": self.name.text(),
            "generic_name": self.generic.text().strip() or None,
            "manufacturer_id": self.context.catalog.manufacturer_id(self.company.currentText()),
            "category_id": self.context.catalog.category_id(self.category.currentText()),
            "form": self.form_field.currentText().strip() or None,
            "strength": self.strength.text().strip() or None,
            "barcode": self.barcode.text(),
            "code": self.code.text(),
            "rack": self.rack.text().strip() or None,
            "prescription_required": 1 if self.prescription.isChecked() else 0,
            "discount_eligible": 1 if self.discountable.isChecked() else 0,
            "notes": self.notes.toPlainText().strip() or None,
            "pack_size": self.pack_size.value(),
            "unit_label": self.unit_label.currentText().strip() or "Unit",
            "purchase_price": self.cost.paisa(),
            "sale_price": self.retail.paisa(),
            "tax_percent": float(self.tax.text() or 0),
            "reorder_level": self.reorder.value(),
        }

    def _save(self) -> None:
        try:
            values = self._values()
            if self.row is None:
                self.context.catalog.create_product(values)
            else:
                self.context.catalog.update_product(int(self.row["id"]), values)
        except (PharmacyError, ValueError) as exc:
            error(self, str(exc))
            return
        self.accept()


class LookupDialog(QDialog):
    """Rename or remove categories and companies."""

    def __init__(self, context, parent=None):
        super().__init__(parent)
        self.context = context
        self.setWindowTitle("Categories & companies")
        self.setMinimumSize(560, 440)
        box = QVBoxLayout(self)
        tabs = QTabWidget()
        self.category_table = DataTable([Col("name", "Category", stretch=True)])
        self.company_table = DataTable([Col("name", "Company", stretch=True)])
        for table, label in ((self.category_table, "Categories"), (self.company_table, "Companies")):
            page = QWidget()
            layout = QVBoxLayout(page)
            layout.addWidget(table, 1)
            tools = QHBoxLayout()
            tools.addStretch(1)
            tools.addWidget(button("Rename…", on_click=lambda _c=False, t=table: self._rename(t)))
            tools.addWidget(
                button("Delete", kind="Danger", on_click=lambda _c=False, t=table: self._delete(t))
            )
            layout.addLayout(tools)
            tabs.addTab(page, label)
        box.addWidget(tabs, 1)
        box.addWidget(button("Close", on_click=self.accept))
        self._reload()

    def _reload(self) -> None:
        self.category_table.set_rows(self.context.catalog.categories())
        self.company_table.set_rows(self.context.catalog.manufacturers())

    def _rename(self, table) -> None:
        from PySide6.QtWidgets import QInputDialog

        row = table.current()
        if row is None:
            return
        name, ok = QInputDialog.getText(self, "Rename", "New name:", text=row["name"])
        if not ok or not name.strip():
            return
        try:
            if table is self.category_table:
                self.context.catalog.rename_category(int(row["id"]), name)
            else:
                self.context.catalog.rename_manufacturer(int(row["id"]), name)
        except PharmacyError as exc:
            error(self, str(exc))
        self._reload()

    def _delete(self, table) -> None:
        row = table.current()
        if row is None or not confirm(self, f"Delete “{row['name']}”?"):
            return
        if table is self.category_table:
            self.context.catalog.delete_category(int(row["id"]))
        else:
            self.context.catalog.delete_manufacturer(int(row["id"]))
        self._reload()


class ImportDialog(QDialog):
    """Bring the medicine list in from a spreadsheet."""

    def __init__(self, context, parent=None):
        super().__init__(parent)
        self.context = context
        self.setWindowTitle("Import medicines from a file")
        self.setMinimumWidth(560)
        box = QVBoxLayout(self)
        box.setSpacing(12)
        box.addWidget(SectionTitle("Import from a CSV spreadsheet"))
        box.addWidget(
            MutedLabel(
                "Save your list from Excel as CSV. The file needs a <b>name</b> column; "
                "everything else is optional. Rows are matched on barcode, then item code, "
                "then name — so running the same file twice updates instead of duplicating. "
                "Add an <b>opening_quantity</b> column (with batch_no and expiry_date) to "
                "load stock at the same time."
            )
        )
        self.path = QLineEdit()
        self.path.setPlaceholderText("Choose a .csv file…")
        picker = QHBoxLayout()
        picker.addWidget(self.path, 1)
        picker.addWidget(button("Browse…", on_click=self._browse))
        box.addLayout(picker)
        self.update_existing = QCheckBox("Update medicines that are already in the list")
        self.update_existing.setChecked(True)
        box.addWidget(self.update_existing)

        buttons = QHBoxLayout()
        buttons.addWidget(button("Download a blank template", on_click=self._template))
        buttons.addStretch(1)
        buttons.addWidget(button("Cancel", on_click=self.reject))
        buttons.addWidget(button("Import", kind="Primary", on_click=self._import))
        box.addLayout(buttons)

    def _browse(self) -> None:
        path, _filter = QFileDialog.getOpenFileName(
            self, "Choose a CSV file", str(config.export_dir()), "Spreadsheet (*.csv *.txt)"
        )
        if path:
            self.path.setText(path)

    def _template(self) -> None:
        path, _filter = QFileDialog.getSaveFileName(
            self,
            "Save template",
            str(config.export_dir() / "medicines-template.csv"),
            "Spreadsheet (*.csv)",
        )
        if not path:
            return
        self.context.catalog.write_import_template(path)
        info(self, f"Template saved to:\n{path}")

    def _import(self) -> None:
        if not self.path.text().strip():
            warn(self, "Choose a file first.")
            return
        try:
            result = self.context.catalog.import_csv(
                self.path.text().strip(), update_existing=self.update_existing.isChecked()
            )
        except PharmacyError as exc:
            error(self, str(exc))
            return
        message = f"{result['created']} added, {result['updated']} updated."
        if result["errors"]:
            preview = "\n".join(result["errors"][:12])
            more = (
                f"\n…and {len(result['errors']) - 12} more"
                if len(result["errors"]) > 12
                else ""
            )
            message += f"\n\n{len(result['errors'])} row(s) were skipped:\n{preview}{more}"
        info(self, message)
        self.accept()
