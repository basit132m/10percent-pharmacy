"""Settings — shop details, selling rules, receipts, backup and demo data."""

from __future__ import annotations

from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
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
from .. import printing
from ..widgets.common import (
    MutedLabel,
    SectionTitle,
    button,
    confirm,
    error,
    info,
    warn,
)
from ..widgets.table import Col, DataTable, DATETIME, INT
from .base import Page

RECEIPT_FORMATS = [
    ("Thermal roll — 80 mm", printing.THERMAL),
    ("Half sheet — A5", printing.A5),
    ("Full sheet — A4", printing.A4),
]


class SettingsPage(Page):
    title = "Settings"
    subtitle = "Shop details, selling rules and backups"

    def build(self) -> None:
        self.header.add_action(button("Save changes", kind="Primary", on_click=self._save))

        self.tabs = QTabWidget()
        self.tabs.addTab(self._shop_tab(), "Pharmacy details")
        self.tabs.addTab(self._selling_tab(), "Selling rules")
        self.tabs.addTab(self._receipt_tab(), "Receipts & documents")
        self.tabs.addTab(self._backup_tab(), "Backup & data")
        self.body.addWidget(self.tabs, 1)

    # ------------------------------------------------------------------ tabs
    def _shop_tab(self) -> QWidget:
        page = QWidget()
        form = QFormLayout(page)
        form.setSpacing(9)
        self.pharmacy_name = QLineEdit()
        self.tagline = QLineEdit()
        self.address = QPlainTextEdit()
        self.address.setMaximumHeight(70)
        self.phone = QLineEdit()
        self.email = QLineEdit()
        self.licence = QLineEdit()
        self.ntn = QLineEdit()
        form.addRow("Pharmacy name", self.pharmacy_name)
        form.addRow("Tagline", self.tagline)
        form.addRow("Address", self.address)
        form.addRow("Phone", self.phone)
        form.addRow("Email", self.email)
        form.addRow("Drug licence no.", self.licence)
        form.addRow("NTN / tax number", self.ntn)
        form.addRow("", MutedLabel("These appear at the top of every printed receipt."))
        return page

    def _selling_tab(self) -> QWidget:
        page = QWidget()
        form = QFormLayout(page)
        form.setSpacing(9)
        self.discount = QDoubleSpinBox()
        self.discount.setRange(0, 100)
        self.discount.setDecimals(2)
        self.discount.setSuffix(" %")
        self.max_discount = QDoubleSpinBox()
        self.max_discount.setRange(0, 100)
        self.max_discount.setSuffix(" %")
        self.round_off = QCheckBox("Round every bill to the nearest rupee")
        self.negative_stock = QCheckBox("Allow selling when the shelf shows zero")
        self.negative_stock.setToolTip(
            "Leave this off. Turn it on only while the stock figures are still being "
            "corrected, otherwise the stock report cannot be trusted."
        )
        self.expiry_days = QSpinBox()
        self.expiry_days.setRange(7, 730)
        self.expiry_days.setSuffix(" days")
        self.reorder_default = QSpinBox()
        self.reorder_default.setRange(0, 100000)
        form.addRow("Standard discount", self.discount)
        form.addRow("Most a manager may give", self.max_discount)
        form.addRow("", self.round_off)
        form.addRow("", self.negative_stock)
        form.addRow("Warn about expiry", self.expiry_days)
        form.addRow("Default reorder level", self.reorder_default)
        form.addRow(
            "",
            MutedLabel(
                "The standard discount is applied to every line at the counter. "
                "Individual medicines can be excluded on their own page."
            ),
        )
        return page

    def _receipt_tab(self) -> QWidget:
        page = QWidget()
        form = QFormLayout(page)
        form.setSpacing(9)
        self.receipt_format = QComboBox()
        for label, value in RECEIPT_FORMATS:
            self.receipt_format.addItem(label, value)
        self.print_after_sale = QCheckBox("Print the receipt as soon as a bill is saved")
        self.show_savings = QCheckBox("Print “You saved …” on the receipt")
        self.footer = QPlainTextEdit()
        self.footer.setMaximumHeight(70)
        self.invoice_prefix = QLineEdit()
        self.purchase_prefix = QLineEdit()
        self.return_prefix = QLineEdit()
        form.addRow("Receipt size", self.receipt_format)
        form.addRow("", self.print_after_sale)
        form.addRow("", self.show_savings)
        form.addRow("Footer message", self.footer)
        form.addRow("Invoice number prefix", self.invoice_prefix)
        form.addRow("Purchase number prefix", self.purchase_prefix)
        form.addRow("Return number prefix", self.return_prefix)
        form.addRow("", button("Print a test receipt", on_click=self._test_receipt))
        return page

    def _backup_tab(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setSpacing(10)
        layout.addWidget(SectionTitle("Automatic backups"))
        options = QFormLayout()
        self.auto_backup = QCheckBox("Take a backup every time the program closes")
        self.keep_copies = QSpinBox()
        self.keep_copies.setRange(1, 500)
        options.addRow("", self.auto_backup)
        options.addRow("Copies to keep", self.keep_copies)
        layout.addLayout(options)
        layout.addWidget(
            MutedLabel(
                f"Backups are kept in <code>{config.backup_dir()}</code>. "
                "Copy that folder to a USB stick every week — a backup on the same "
                "computer does not survive a broken hard disk."
            )
        )

        tools = QHBoxLayout()
        tools.addWidget(button("Back up now", kind="Primary", on_click=self._backup_now))
        tools.addWidget(button("Copy backup to…", on_click=self._backup_to))
        tools.addWidget(button("Restore from a backup…", kind="Danger", on_click=self._restore))
        tools.addStretch(1)
        layout.addLayout(tools)

        self.backup_table = DataTable(
            [
                Col("name", "Backup file", stretch=True),
                Col("created_at", "Taken", DATETIME),
                Col("size_kb", "Size (KB)", INT),
            ]
        )
        layout.addWidget(self.backup_table, 1)

        layout.addWidget(SectionTitle("Sample data"))
        layout.addWidget(
            MutedLabel(
                "Load 40 common medicines, two supplier bills and a few days of sales so "
                "you can try every screen. Use it on a fresh installation only."
            )
        )
        demo_row = QHBoxLayout()
        demo_row.addWidget(button("Load sample data", on_click=self._load_demo))
        demo_row.addStretch(1)
        layout.addLayout(demo_row)
        return page

    # ------------------------------------------------------------------ data
    def reload(self) -> None:
        settings = self.context.settings
        self.pharmacy_name.setText(settings.get("pharmacy_name"))
        self.tagline.setText(settings.get("pharmacy_tagline"))
        self.address.setPlainText(settings.get("pharmacy_address"))
        self.phone.setText(settings.get("pharmacy_phone"))
        self.email.setText(settings.get("pharmacy_email"))
        self.licence.setText(settings.get("license_no"))
        self.ntn.setText(settings.get("ntn"))

        self.discount.setValue(settings.discount_percent)
        self.max_discount.setValue(settings.get_float("max_discount_percent", 25))
        self.round_off.setChecked(settings.get_bool("round_off_totals", True))
        self.negative_stock.setChecked(settings.get_bool("allow_negative_stock", False))
        self.expiry_days.setValue(settings.get_int("warn_expiry_days", 90))
        self.reorder_default.setValue(settings.get_int("default_reorder_level", 10))

        index = self.receipt_format.findData(settings.get("receipt_format"))
        self.receipt_format.setCurrentIndex(max(index, 0))
        self.print_after_sale.setChecked(settings.get_bool("print_after_sale", True))
        self.show_savings.setChecked(settings.get_bool("show_savings_on_receipt", True))
        self.footer.setPlainText(settings.get("receipt_footer"))
        self.invoice_prefix.setText(settings.get("invoice_prefix"))
        self.purchase_prefix.setText(settings.get("purchase_prefix"))
        self.return_prefix.setText(settings.get("sale_return_prefix"))

        self.auto_backup.setChecked(settings.get_bool("auto_backup_on_exit", True))
        self.keep_copies.setValue(settings.get_int("backup_copies_to_keep", 20))
        self.backup_table.set_rows(self.context.backups.list_backups())

    def _save(self) -> None:
        self.context.settings.set_many(
            {
                "pharmacy_name": self.pharmacy_name.text().strip() or "Pharmacy",
                "pharmacy_tagline": self.tagline.text(),
                "pharmacy_address": self.address.toPlainText(),
                "pharmacy_phone": self.phone.text(),
                "pharmacy_email": self.email.text(),
                "license_no": self.licence.text(),
                "ntn": self.ntn.text(),
                "default_discount_percent": self.discount.value(),
                "max_discount_percent": self.max_discount.value(),
                "round_off_totals": self.round_off.isChecked(),
                "allow_negative_stock": self.negative_stock.isChecked(),
                "warn_expiry_days": self.expiry_days.value(),
                "default_reorder_level": self.reorder_default.value(),
                "receipt_format": self.receipt_format.currentData(),
                "print_after_sale": self.print_after_sale.isChecked(),
                "show_savings_on_receipt": self.show_savings.isChecked(),
                "receipt_footer": self.footer.toPlainText(),
                "invoice_prefix": self.invoice_prefix.text().strip(),
                "purchase_prefix": self.purchase_prefix.text().strip(),
                "sale_return_prefix": self.return_prefix.text().strip(),
                "auto_backup_on_exit": self.auto_backup.isChecked(),
                "backup_copies_to_keep": self.keep_copies.value(),
            }
        )
        self.context.audit.log("settings.update", user=self.user)
        info(self, "Settings saved.")
        self.notify_change()

    # --------------------------------------------------------------- actions
    def _test_receipt(self) -> None:
        sale = self.context.db.query_one("SELECT id FROM sales ORDER BY id DESC LIMIT 1")
        if sale is None:
            warn(self, "Make one sale first — the test print uses the last bill.")
            return
        sale_id = int(sale["id"])
        content = printing.receipt_html(
            self.context.settings,
            self.context.sales.get_sale(sale_id),
            self.context.sales.sale_items(sale_id),
            page_format=self.receipt_format.currentData(),
            copy_label="TEST PRINT",
        )
        printing.preview_html(self, content, page_format=self.receipt_format.currentData())

    def _backup_now(self) -> None:
        try:
            path = self.context.backups.create("manual")
        except PharmacyError as exc:
            error(self, str(exc))
            return
        info(self, f"Backup saved:\n{path}")
        self.reload()

    def _backup_to(self) -> None:
        folder = QFileDialog.getExistingDirectory(self, "Choose a folder (a USB stick works)")
        if not folder:
            return
        try:
            path = self.context.backups.copy_to(folder)
        except PharmacyError as exc:
            error(self, str(exc))
            return
        info(self, f"Backup copied to:\n{path}")

    def _restore(self) -> None:
        row = self.backup_table.current()
        suggested = str(row["path"]) if row is not None else str(config.backup_dir())
        path, _filter = QFileDialog.getOpenFileName(
            self, "Choose a backup file", suggested, "Backup file (*.db)"
        )
        if not path:
            return
        if not confirm(
            self,
            "Restoring replaces everything currently in the program with the contents "
            "of that backup.\n\nA copy of the present data is kept next to the database "
            "first, but any sale made since the backup was taken will be gone.\n\nGo ahead?",
            danger=True,
        ):
            return
        try:
            self.context.backups.restore(path)
        except PharmacyError as exc:
            error(self, str(exc))
            return
        info(
            self,
            "The backup has been restored. Please close and reopen the program so every "
            "screen reads the restored data.",
        )
        self.notify_change()

    def _load_demo(self) -> None:
        if self.context.db.scalar("SELECT COUNT(*) FROM products"):
            if not confirm(
                self,
                "There are already medicines in the list. Sample data will be added on "
                "top of them. Continue?",
                danger=True,
            ):
                return
        from ...core.demo import seed_demo

        result = seed_demo(self.context)
        info(
            self,
            f"Loaded {result['products']} medicines, {result['suppliers']} suppliers, "
            f"{result['customers']} customers and {result['sales']} sales.",
        )
        self.notify_change()
