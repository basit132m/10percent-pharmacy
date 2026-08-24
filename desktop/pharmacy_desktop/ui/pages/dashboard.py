"""Dashboard — what the owner wants to see the moment the program opens."""

from __future__ import annotations

from PySide6.QtWidgets import QGridLayout, QHBoxLayout, QWidget

from ...core import dates
from ...core.money import fmt
from .. import theme
from ..widgets.common import Card, KpiCard, SectionTitle, button
from ..widgets.table import Col, DataTable, DATE, DATETIME, INT, MONEY
from .base import Page


class DashboardPage(Page):
    title = "Dashboard"
    subtitle = "Today at a glance"

    def build(self) -> None:
        self.header.add_action(
            button("New sale (F2)", kind="Accent", on_click=lambda: self._go("pos"))
        )
        self.header.add_action(button("Refresh (F5)", on_click=lambda: self.refresh(force=True)))

        self.cards: dict[str, KpiCard] = {}
        grid = QGridLayout()
        grid.setSpacing(12)
        definitions = [
            ("sales_today", "Sales today", theme.GREEN, "pos"),
            ("savings_today", "Discount given today", theme.GOLD, None),
            ("profit_today", "Gross profit today", theme.INK, "reports"),
            ("cash_today", "Cash & card taken today", theme.INK, None),
            ("month", "Sales this month", theme.GREEN, "reports"),
            ("stock_value", "Stock value at cost", theme.INK, "stock"),
            ("receivable", "Customers owe us", theme.INFO, "parties"),
            ("payable", "We owe suppliers", theme.DANGER, "parties"),
        ]
        for index, (key, label, colour, target) in enumerate(definitions):
            card = KpiCard(label, "—", "", accent=colour)
            if target:
                card.clicked.connect(lambda page=target: self._go(page))
            self.cards[key] = card
            grid.addWidget(card, index // 4, index % 4)
        self.body.addLayout(grid)

        alerts = QGridLayout()
        alerts.setSpacing(12)
        for index, (key, label, colour) in enumerate(
            [
                ("low_stock", "Medicines to reorder", theme.WARNING),
                ("expiring", "Batches expiring soon", theme.WARNING),
                ("expired", "Expired batches on shelf", theme.DANGER),
                ("out_of_stock", "Out of stock", theme.DANGER),
            ]
        ):
            card = KpiCard(label, "0", "", accent=colour)
            card.clicked.connect(lambda page="stock": self._go(page))
            self.cards[key] = card
            alerts.addWidget(card, 0, index)
        self.body.addLayout(alerts)

        tables = QHBoxLayout()
        tables.setSpacing(12)
        tables.addWidget(self._reorder_card(), 1)
        tables.addWidget(self._expiry_card(), 1)
        self.body.addLayout(tables, 1)

        self.body.addWidget(self._recent_card(), 1)

    # ----------------------------------------------------------------- cards
    def _reorder_card(self) -> QWidget:
        card = Card()
        card.body.addWidget(SectionTitle("Running low — order these"))
        self.low_table = DataTable(
            [
                Col("name", "Medicine", stretch=True),
                Col("manufacturer_name", "Company"),
                Col("stock_quantity", "In stock", INT),
                Col("reorder_level", "Reorder at", INT),
            ],
            row_height=30,
        )
        self.low_table.row_style = lambda row: "danger" if not row["stock_quantity"] else "warning"
        card.body.addWidget(self.low_table)
        return card

    def _expiry_card(self) -> QWidget:
        card = Card()
        card.body.addWidget(SectionTitle("Expiring soon — move or return these"))
        self.expiry_table = DataTable(
            [
                Col("product_name", "Medicine", stretch=True),
                Col("batch_no", "Batch"),
                Col("expiry_date", "Expiry", DATE),
                Col("days_to_expiry", "Days left", INT),
                Col("quantity", "Units", INT),
            ],
            row_height=30,
        )
        self.expiry_table.row_style = lambda row: (
            "danger" if (row["days_to_expiry"] or 0) <= 30 else "warning"
        )
        card.body.addWidget(self.expiry_table)
        return card

    def _recent_card(self) -> QWidget:
        card = Card()
        heading = QHBoxLayout()
        heading.addWidget(SectionTitle("Latest bills"))
        heading.addStretch(1)
        heading.addWidget(button("See all sales (F8)", on_click=lambda: self._go("sales")))
        card.body.addLayout(heading)
        self.recent_table = DataTable(
            [
                Col("invoice_no", "Invoice"),
                Col("sale_date", "Time", DATETIME),
                Col("customer", "Customer", stretch=True),
                Col("payment_method", "Payment"),
                Col("discount_amount", "Discount", MONEY),
                Col("net_amount", "Total", MONEY),
            ],
            row_height=30,
        )
        card.body.addWidget(self.recent_table)
        return card

    # ---------------------------------------------------------------- reload
    def reload(self) -> None:
        summary = self.context.reports.dashboard()
        today = summary["today"]
        month = summary["month"]
        self.cards["sales_today"].set_value(
            fmt(today["net"], symbol=True), f"{today['bills']} bill(s) today"
        )
        self.cards["savings_today"].set_value(
            fmt(today["discount"], symbol=True), "saved by our customers"
        )
        self.cards["profit_today"].set_value(
            fmt(today["profit"], symbol=True), "after cost of medicines"
        )
        self.cards["cash_today"].set_value(
            fmt(summary["cash_today"], symbol=True), "excluding credit sales"
        )
        self.cards["month"].set_value(
            fmt(month["net"], symbol=True),
            f"{month['bills']} bills · profit {fmt(month['profit'], symbol=True)}",
        )
        self.cards["stock_value"].set_value(
            fmt(summary["stock_value"], symbol=True),
            f"{summary['stock_units']:,} units · {summary['products']} medicines",
        )
        self.cards["receivable"].set_value(fmt(summary["receivable"], symbol=True), "credit book")
        self.cards["payable"].set_value(fmt(summary["payable"], symbol=True), "supplier bills")
        self.cards["low_stock"].set_value(str(summary["low_stock"]), "at or below reorder level")
        self.cards["expiring"].set_value(
            str(summary["expiring"]),
            f"within {self.context.settings.get_int('warn_expiry_days', 90)} days",
        )
        self.cards["expired"].set_value(str(summary["expired"]), "remove from the shelf")
        self.cards["out_of_stock"].set_value(str(summary["out_of_stock"]), "nothing left to sell")

        self.low_table.set_rows(self.context.inventory.low_stock(limit=12))
        self.expiry_table.set_rows(
            self.context.inventory.expiring_soon(
                days=self.context.settings.get_int("warn_expiry_days", 90), limit=12
            )
        )
        recent = []
        for row in self.context.sales.list_sales(limit=10):
            entry = dict(row)
            entry["customer"] = row["party_name"] or row["customer_name"] or "Walk-in customer"
            recent.append(entry)
        self.recent_table.set_rows(recent)
        self.header.set_subtitle(
            f"{dates.fmt_date(dates.today_iso())} · standard discount "
            f"{self.context.settings.discount_percent:g}%"
        )

    def _go(self, page: str) -> None:
        if self.window_ref is not None:
            self.window_ref.show_page(page)
