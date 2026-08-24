"""Reporting.

Every report comes back in the same shape — a title, typed columns and rows —
so one screen can display them all, print them all and export them all to CSV
without knowing what it is looking at.
"""

from __future__ import annotations

import csv
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

from .. import dates
from ..db import Database
from ..money import to_rupees

# Column kinds the report screen knows how to format.
TEXT, INT, MONEY, PERCENT, DATE, DATETIME = "text", "int", "money", "percent", "date", "datetime"


@dataclass
class Column:
    key: str
    label: str
    kind: str = TEXT


@dataclass
class ReportResult:
    title: str
    columns: list[Column]
    rows: list[dict]
    totals: dict = field(default_factory=dict)
    subtitle: str = ""

    def export_csv(self, path: str | Path) -> Path:
        path = Path(path)
        with path.open("w", newline="", encoding="utf-8-sig") as handle:
            writer = csv.writer(handle)
            writer.writerow([self.title])
            if self.subtitle:
                writer.writerow([self.subtitle])
            writer.writerow([])
            writer.writerow([column.label for column in self.columns])
            for row in self.rows:
                writer.writerow(
                    [
                        to_rupees(row.get(column.key) or 0)
                        if column.kind == MONEY
                        else row.get(column.key, "")
                        for column in self.columns
                    ]
                )
            if self.totals:
                writer.writerow([])
                writer.writerow(
                    [
                        "TOTAL"
                        if index == 0
                        else (
                            to_rupees(self.totals.get(column.key) or 0)
                            if column.kind == MONEY
                            else self.totals.get(column.key, "")
                        )
                        for index, column in enumerate(self.columns)
                    ]
                )
        return path


class ReportService:
    def __init__(self, db: Database, settings=None):
        self.db = db
        self.settings = settings

    # ------------------------------------------------------------- dashboard
    def dashboard(self) -> dict:
        today = dates.today_iso()
        month_start = dates.month_start().strftime(dates.ISO)
        warn_days = self.settings.get_int("warn_expiry_days", 90) if self.settings else 90

        def sales_totals(date_from: str) -> dict:
            row = self.db.query_one(
                """SELECT COUNT(*) AS bills,
                          COALESCE(SUM(net_amount), 0)      AS net,
                          COALESCE(SUM(discount_amount), 0) AS discount,
                          COALESCE(SUM(cost_amount), 0)     AS cost
                   FROM sales WHERE date(sale_date) >= ?""",
                (date_from,),
            )
            return {
                "bills": int(row["bills"]),
                "net": int(row["net"]),
                "discount": int(row["discount"]),
                "profit": int(row["net"]) - int(row["cost"]),
            }

        cash_today = int(
            self.db.scalar(
                "SELECT COALESCE(SUM(paid_amount - change_amount), 0) FROM sales "
                "WHERE date(sale_date) = ? AND payment_method <> 'Credit'",
                (today,),
            )
        )
        stock = self.db.query_one(
            "SELECT COALESCE(SUM(quantity), 0) AS units, "
            "COALESCE(SUM(quantity * purchase_price), 0) AS cost_value FROM batches "
            "WHERE quantity > 0"
        )
        counts = self.db.query_one(
            f"""SELECT
                (SELECT COUNT(*) FROM products p LEFT JOIN product_stock s
                   ON s.product_id = p.id
                  WHERE p.is_active = 1 AND p.reorder_level > 0
                    AND COALESCE(s.quantity, 0) <= p.reorder_level)      AS low_stock,
                (SELECT COUNT(*) FROM products p LEFT JOIN product_stock s
                   ON s.product_id = p.id
                  WHERE p.is_active = 1 AND COALESCE(s.quantity, 0) <= 0) AS out_of_stock,
                (SELECT COUNT(*) FROM batches WHERE quantity > 0 AND expiry_date IS NOT NULL
                    AND expiry_date >= date('now')
                    AND expiry_date <= date('now', '+{int(warn_days)} days')) AS expiring,
                (SELECT COUNT(*) FROM batches WHERE quantity > 0 AND expiry_date IS NOT NULL
                    AND expiry_date < date('now'))                        AS expired,
                (SELECT COUNT(*) FROM products WHERE is_active = 1)        AS products
            """
        )
        from .parties import PartyService  # local import keeps the module graph flat

        party_service = PartyService(self.db)
        return {
            "today": sales_totals(today),
            "month": sales_totals(month_start),
            "cash_today": cash_today,
            "stock_units": int(stock["units"]),
            "stock_value": int(stock["cost_value"]),
            "low_stock": int(counts["low_stock"]),
            "out_of_stock": int(counts["out_of_stock"]),
            "expiring": int(counts["expiring"]),
            "expired": int(counts["expired"]),
            "products": int(counts["products"]),
            "receivable": party_service.total_outstanding("customer"),
            "payable": party_service.total_outstanding("supplier"),
        }

    def sales_trend(self, days: int = 14) -> list:
        return self.db.query(
            """SELECT date(sale_date) AS day,
                      COUNT(*) AS bills,
                      COALESCE(SUM(net_amount), 0) AS net
               FROM sales
               WHERE date(sale_date) >= date('now', ? || ' days')
               GROUP BY day ORDER BY day""",
            (f"-{int(days) - 1}",),
        )

    # --------------------------------------------------------------- reports
    def sales_summary(self, date_from: str, date_to: str) -> ReportResult:
        rows = [
            dict(row)
            for row in self.db.query(
                """SELECT date(sale_date) AS day, COUNT(*) AS bills,
                          COALESCE(SUM(gross_amount), 0)    AS gross,
                          COALESCE(SUM(discount_amount), 0) AS discount,
                          COALESCE(SUM(tax_amount), 0)      AS tax,
                          COALESCE(SUM(net_amount), 0)      AS net,
                          COALESCE(SUM(net_amount - cost_amount), 0) AS profit
                   FROM sales WHERE date(sale_date) BETWEEN ? AND ?
                   GROUP BY day ORDER BY day""",
                (date_from, date_to),
            )
        ]
        return ReportResult(
            title="Sales summary",
            subtitle=_range_label(date_from, date_to),
            columns=[
                Column("day", "Date", DATE),
                Column("bills", "Bills", INT),
                Column("gross", "Gross", MONEY),
                Column("discount", "Discount given", MONEY),
                Column("tax", "Tax", MONEY),
                Column("net", "Net sales", MONEY),
                Column("profit", "Gross profit", MONEY),
            ],
            rows=rows,
            totals=_sum_rows(rows, ("bills", "gross", "discount", "tax", "net", "profit")),
        )

    def sales_by_product(self, date_from: str, date_to: str) -> ReportResult:
        rows = [
            dict(row)
            for row in self.db.query(
                """SELECT si.product_name AS product,
                          SUM(si.quantity - si.returned_quantity) AS units,
                          COALESCE(SUM((si.quantity - si.returned_quantity)
                                * si.unit_price), 0) AS gross,
                          COALESCE(SUM(si.discount_amount), 0) AS discount,
                          COALESCE(SUM((si.quantity - si.returned_quantity)
                                * (si.unit_price - si.unit_cost)), 0) AS margin
                   FROM sale_items si JOIN sales s ON s.id = si.sale_id
                   WHERE date(s.sale_date) BETWEEN ? AND ?
                   GROUP BY si.product_name
                   HAVING units > 0
                   ORDER BY gross DESC""",
                (date_from, date_to),
            )
        ]
        return ReportResult(
            title="Sales by medicine",
            subtitle=_range_label(date_from, date_to),
            columns=[
                Column("product", "Medicine"),
                Column("units", "Units sold", INT),
                Column("gross", "Value (before discount)", MONEY),
                Column("discount", "Discount", MONEY),
                Column("margin", "Margin", MONEY),
            ],
            rows=rows,
            totals=_sum_rows(rows, ("units", "gross", "discount", "margin")),
        )

    def sales_by_user(self, date_from: str, date_to: str) -> ReportResult:
        rows = [
            dict(row)
            for row in self.db.query(
                """SELECT COALESCE(u.full_name, 'Unknown') AS cashier,
                          COUNT(*) AS bills,
                          COALESCE(SUM(s.net_amount), 0) AS net,
                          COALESCE(SUM(s.discount_amount), 0) AS discount
                   FROM sales s LEFT JOIN users u ON u.id = s.user_id
                   WHERE date(s.sale_date) BETWEEN ? AND ?
                   GROUP BY cashier ORDER BY net DESC""",
                (date_from, date_to),
            )
        ]
        return ReportResult(
            title="Sales by counter staff",
            subtitle=_range_label(date_from, date_to),
            columns=[
                Column("cashier", "Staff member"),
                Column("bills", "Bills", INT),
                Column("discount", "Discount given", MONEY),
                Column("net", "Net sales", MONEY),
            ],
            rows=rows,
            totals=_sum_rows(rows, ("bills", "discount", "net")),
        )

    def invoice_register(self, date_from: str, date_to: str) -> ReportResult:
        rows = [
            dict(row)
            for row in self.db.query(
                """SELECT s.invoice_no, s.sale_date,
                          COALESCE(p.name, s.customer_name, 'Walk-in') AS customer,
                          s.payment_method, s.gross_amount, s.discount_amount,
                          s.net_amount, s.paid_amount,
                          (s.net_amount - s.paid_amount) AS due, s.status
                   FROM sales s LEFT JOIN parties p ON p.id = s.customer_id
                   WHERE date(s.sale_date) BETWEEN ? AND ?
                   ORDER BY s.id""",
                (date_from, date_to),
            )
        ]
        return ReportResult(
            title="Invoice register",
            subtitle=_range_label(date_from, date_to),
            columns=[
                Column("invoice_no", "Invoice"),
                Column("sale_date", "Date & time", DATETIME),
                Column("customer", "Customer"),
                Column("payment_method", "Payment"),
                Column("gross_amount", "Gross", MONEY),
                Column("discount_amount", "Discount", MONEY),
                Column("net_amount", "Net", MONEY),
                Column("paid_amount", "Paid", MONEY),
                Column("due", "Due", MONEY),
                Column("status", "Status"),
            ],
            rows=rows,
            totals=_sum_rows(
                rows, ("gross_amount", "discount_amount", "net_amount", "paid_amount", "due")
            ),
        )

    def discount_report(self, date_from: str, date_to: str) -> ReportResult:
        rows = [
            dict(row)
            for row in self.db.query(
                """SELECT date(sale_date) AS day, COUNT(*) AS bills,
                          COALESCE(SUM(gross_amount), 0) AS gross,
                          COALESCE(SUM(discount_amount), 0) AS discount,
                          CASE WHEN SUM(gross_amount) > 0
                               THEN ROUND(SUM(discount_amount) * 100.0
                                          / SUM(gross_amount), 2)
                               ELSE 0 END AS rate
                   FROM sales WHERE date(sale_date) BETWEEN ? AND ?
                   GROUP BY day ORDER BY day""",
                (date_from, date_to),
            )
        ]
        totals = _sum_rows(rows, ("bills", "gross", "discount"))
        totals["rate"] = (
            round(totals["discount"] * 100.0 / totals["gross"], 2) if totals.get("gross") else 0
        )
        return ReportResult(
            title="Customer savings (discount given)",
            subtitle=_range_label(date_from, date_to),
            columns=[
                Column("day", "Date", DATE),
                Column("bills", "Bills", INT),
                Column("gross", "Value before discount", MONEY),
                Column("discount", "Discount given", MONEY),
                Column("rate", "Effective %", PERCENT),
            ],
            rows=rows,
            totals=totals,
        )

    def profit_report(self, date_from: str, date_to: str) -> ReportResult:
        rows = [
            dict(row)
            for row in self.db.query(
                """SELECT date(s.sale_date) AS day,
                          COALESCE(SUM(si.line_total - si.tax_amount), 0) AS revenue,
                          COALESCE(SUM(si.unit_cost * si.quantity), 0)    AS cost,
                          COALESCE(SUM(si.line_total - si.tax_amount
                                       - si.unit_cost * si.quantity), 0)  AS profit
                   FROM sale_items si JOIN sales s ON s.id = si.sale_id
                   WHERE date(s.sale_date) BETWEEN ? AND ?
                   GROUP BY day ORDER BY day""",
                (date_from, date_to),
            )
        ]
        for row in rows:
            row["margin"] = (
                round(row["profit"] * 100.0 / row["revenue"], 2) if row["revenue"] else 0
            )
        totals = _sum_rows(rows, ("revenue", "cost", "profit"))
        totals["margin"] = (
            round(totals["profit"] * 100.0 / totals["revenue"], 2) if totals["revenue"] else 0
        )
        return ReportResult(
            title="Profit report",
            subtitle=_range_label(date_from, date_to) + " — cost taken from the batch sold",
            columns=[
                Column("day", "Date", DATE),
                Column("revenue", "Revenue (after discount, before tax)", MONEY),
                Column("cost", "Cost of goods", MONEY),
                Column("profit", "Gross profit", MONEY),
                Column("margin", "Margin", PERCENT),
            ],
            rows=rows,
            totals=totals,
        )

    def purchase_report(self, date_from: str, date_to: str) -> ReportResult:
        rows = [
            dict(row)
            for row in self.db.query(
                """SELECT pu.purchase_date, pu.reference_no, pu.supplier_bill_no,
                          COALESCE(p.name, '—') AS supplier,
                          pu.gross_amount, pu.discount_amount, pu.net_amount,
                          pu.paid_amount, (pu.net_amount - pu.paid_amount) AS due
                   FROM purchases pu LEFT JOIN parties p ON p.id = pu.supplier_id
                   WHERE pu.purchase_date BETWEEN ? AND ?
                   ORDER BY pu.purchase_date, pu.id""",
                (date_from, date_to),
            )
        ]
        return ReportResult(
            title="Purchase register",
            subtitle=_range_label(date_from, date_to),
            columns=[
                Column("purchase_date", "Date", DATE),
                Column("reference_no", "Reference"),
                Column("supplier_bill_no", "Supplier bill"),
                Column("supplier", "Supplier"),
                Column("gross_amount", "Gross", MONEY),
                Column("discount_amount", "Discount", MONEY),
                Column("net_amount", "Net", MONEY),
                Column("paid_amount", "Paid", MONEY),
                Column("due", "Balance", MONEY),
            ],
            rows=rows,
            totals=_sum_rows(
                rows, ("gross_amount", "discount_amount", "net_amount", "paid_amount", "due")
            ),
        )

    def stock_valuation(self, *_args) -> ReportResult:
        rows = [
            dict(row)
            for row in self.db.query(
                """SELECT p.name AS product, COALESCE(m.name, '') AS manufacturer,
                          COALESCE(SUM(b.quantity), 0) AS units,
                          COALESCE(SUM(b.quantity * b.purchase_price), 0) AS cost_value,
                          COALESCE(SUM(b.quantity * CASE WHEN b.sale_price > 0
                                THEN b.sale_price ELSE p.sale_price END), 0) AS retail_value
                   FROM products p
                   LEFT JOIN batches b ON b.product_id = p.id AND b.quantity > 0
                   LEFT JOIN manufacturers m ON m.id = p.manufacturer_id
                   GROUP BY p.id HAVING units > 0
                   ORDER BY cost_value DESC"""
            )
        ]
        for row in rows:
            row["potential_margin"] = row["retail_value"] - row["cost_value"]
        return ReportResult(
            title="Stock valuation",
            subtitle=f"As on {dates.fmt_date(dates.today_iso())}",
            columns=[
                Column("product", "Medicine"),
                Column("manufacturer", "Company"),
                Column("units", "Units", INT),
                Column("cost_value", "Value at cost", MONEY),
                Column("retail_value", "Value at retail", MONEY),
                Column("potential_margin", "Potential margin", MONEY),
            ],
            rows=rows,
            totals=_sum_rows(rows, ("units", "cost_value", "retail_value", "potential_margin")),
        )

    def expiry_report(self, *_args, days: int = 180) -> ReportResult:
        rows = [
            dict(row)
            for row in self.db.query(
                """SELECT p.name AS product, b.batch_no, b.expiry_date, b.quantity,
                          (b.quantity * b.purchase_price) AS cost_value,
                          CAST(julianday(b.expiry_date) - julianday(date('now'))
                               AS INTEGER) AS days_left
                   FROM batches b JOIN products p ON p.id = b.product_id
                   WHERE b.quantity > 0 AND b.expiry_date IS NOT NULL
                     AND b.expiry_date <= date('now', ? || ' days')
                   ORDER BY b.expiry_date""",
                (f"+{int(days)}",),
            )
        ]
        return ReportResult(
            title=f"Expiry watch — next {days} days (expired included)",
            subtitle=f"As on {dates.fmt_date(dates.today_iso())}",
            columns=[
                Column("product", "Medicine"),
                Column("batch_no", "Batch"),
                Column("expiry_date", "Expiry", DATE),
                Column("days_left", "Days left", INT),
                Column("quantity", "Units", INT),
                Column("cost_value", "Value at cost", MONEY),
            ],
            rows=rows,
            totals=_sum_rows(rows, ("quantity", "cost_value")),
        )

    def low_stock_report(self, *_args) -> ReportResult:
        rows = [
            dict(row)
            for row in self.db.query(
                """SELECT p.name AS product, COALESCE(m.name, '') AS manufacturer,
                          COALESCE(s.quantity, 0) AS units, p.reorder_level,
                          MAX(p.reorder_level - COALESCE(s.quantity, 0), 0) AS shortfall,
                          (MAX(p.reorder_level - COALESCE(s.quantity, 0), 0)
                             * p.purchase_price) AS order_value
                   FROM products p
                   LEFT JOIN product_stock s ON s.product_id = p.id
                   LEFT JOIN manufacturers m ON m.id = p.manufacturer_id
                   WHERE p.is_active = 1 AND p.reorder_level > 0
                     AND COALESCE(s.quantity, 0) <= p.reorder_level
                   ORDER BY shortfall DESC, p.name"""
            )
        ]
        return ReportResult(
            title="Reorder list (at or below reorder level)",
            subtitle=f"As on {dates.fmt_date(dates.today_iso())}",
            columns=[
                Column("product", "Medicine"),
                Column("manufacturer", "Company"),
                Column("units", "In stock", INT),
                Column("reorder_level", "Reorder level", INT),
                Column("shortfall", "Short by", INT),
                Column("order_value", "Cost to refill", MONEY),
            ],
            rows=rows,
            totals=_sum_rows(rows, ("shortfall", "order_value")),
        )

    def receivables(self, *_args) -> ReportResult:
        return self._balances("customer")

    def payables(self, *_args) -> ReportResult:
        return self._balances("supplier")

    def _balances(self, party_type: str) -> ReportResult:
        from .parties import PartyService

        service = PartyService(self.db)
        sign = 1 if party_type == "customer" else -1
        rows = [
            {
                "name": row["name"],
                "phone": row["phone"] or "",
                "balance": sign * int(row["balance"]),
            }
            for row in service.outstanding(party_type)
        ]
        label = "Customer balances (money owed to us)" if party_type == "customer" else (
            "Supplier balances (money we owe)"
        )
        return ReportResult(
            title=label,
            subtitle=f"As on {dates.fmt_date(dates.today_iso())}",
            columns=[
                Column("name", "Name"),
                Column("phone", "Phone"),
                Column("balance", "Balance", MONEY),
            ],
            rows=rows,
            totals=_sum_rows(rows, ("balance",)),
        )

    def day_book(self, date_from: str, date_to: str) -> ReportResult:
        """Money in and out, the way a cash drawer is reconciled at closing."""
        rows: list[dict] = []
        for row in self.db.query(
            """SELECT date(sale_date) AS day, payment_method AS head,
                      COALESCE(SUM(paid_amount - change_amount), 0) AS amount_in
               FROM sales WHERE date(sale_date) BETWEEN ? AND ?
               GROUP BY day, payment_method""",
            (date_from, date_to),
        ):
            rows.append(
                {
                    "day": row["day"],
                    "head": f"Counter sales — {row['head']}",
                    "amount_in": int(row["amount_in"]),
                    "amount_out": 0,
                }
            )
        for row in self.db.query(
            """SELECT date(paid_at) AS day, direction, method,
                      COALESCE(SUM(amount), 0) AS amount
               FROM payments WHERE date(paid_at) BETWEEN ? AND ?
               GROUP BY day, direction, method""",
            (date_from, date_to),
        ):
            incoming = row["direction"] == "in"
            rows.append(
                {
                    "day": row["day"],
                    "head": (
                        f"Customer payment — {row['method']}"
                        if incoming
                        else f"Supplier payment — {row['method']}"
                    ),
                    "amount_in": int(row["amount"]) if incoming else 0,
                    "amount_out": 0 if incoming else int(row["amount"]),
                }
            )
        rows.sort(key=lambda row: (row["day"], row["head"]))
        totals = _sum_rows(rows, ("amount_in", "amount_out"))
        totals["head"] = "Net movement: " + f"{(totals['amount_in'] - totals['amount_out'])/100:,.2f}"
        return ReportResult(
            title="Day book (cash & bank movement)",
            subtitle=_range_label(date_from, date_to),
            columns=[
                Column("day", "Date", DATE),
                Column("head", "Head"),
                Column("amount_in", "Money in", MONEY),
                Column("amount_out", "Money out", MONEY),
            ],
            rows=rows,
            totals=totals,
        )

    def returns_report(self, date_from: str, date_to: str) -> ReportResult:
        rows = [
            dict(row)
            for row in self.db.query(
                """SELECT r.return_date, r.return_no, s.invoice_no,
                          COALESCE(s.customer_name, 'Walk-in') AS customer,
                          r.total_amount, COALESCE(r.reason, '') AS reason
                   FROM sale_returns r JOIN sales s ON s.id = r.sale_id
                   WHERE date(r.return_date) BETWEEN ? AND ?
                   ORDER BY r.id""",
                (date_from, date_to),
            )
        ]
        return ReportResult(
            title="Sale returns",
            subtitle=_range_label(date_from, date_to),
            columns=[
                Column("return_date", "Date", DATETIME),
                Column("return_no", "Return no"),
                Column("invoice_no", "Against invoice"),
                Column("customer", "Customer"),
                Column("reason", "Reason"),
                Column("total_amount", "Refunded", MONEY),
            ],
            rows=rows,
            totals=_sum_rows(rows, ("total_amount",)),
        )

    def stock_movement(self, date_from: str, date_to: str) -> ReportResult:
        rows = [
            dict(row)
            for row in self.db.query(
                """SELECT a.created_at, p.name AS product, COALESCE(b.batch_no, '') AS batch,
                          a.quantity, a.reason, COALESCE(u.username, '') AS username
                   FROM stock_adjustments a
                   JOIN products p ON p.id = a.product_id
                   LEFT JOIN batches b ON b.id = a.batch_id
                   LEFT JOIN users u ON u.id = a.user_id
                   WHERE date(a.created_at) BETWEEN ? AND ?
                   ORDER BY a.id DESC""",
                (date_from, date_to),
            )
        ]
        return ReportResult(
            title="Stock adjustments",
            subtitle=_range_label(date_from, date_to),
            columns=[
                Column("created_at", "When", DATETIME),
                Column("product", "Medicine"),
                Column("batch", "Batch"),
                Column("quantity", "Change", INT),
                Column("reason", "Reason"),
                Column("username", "By"),
            ],
            rows=rows,
            totals=_sum_rows(rows, ("quantity",)),
        )

    # ---------------------------------------------------------------- registry
    def available(self) -> list[tuple[str, str, bool]]:
        """``(key, label, needs_date_range)`` for every report on offer."""
        return [
            ("sales_summary", "Sales summary (day by day)", True),
            ("invoice_register", "Invoice register", True),
            ("sales_by_product", "Sales by medicine", True),
            ("sales_by_user", "Sales by counter staff", True),
            ("discount_report", "Customer savings (10% discount)", True),
            ("profit_report", "Profit report", True),
            ("returns_report", "Sale returns", True),
            ("purchase_report", "Purchase register", True),
            ("day_book", "Day book (cash & bank)", True),
            ("stock_movement", "Stock adjustments", True),
            ("stock_valuation", "Stock valuation", False),
            ("low_stock_report", "Reorder list", False),
            ("expiry_report", "Expiry watch", False),
            ("receivables", "Customer balances", False),
            ("payables", "Supplier balances", False),
        ]

    def run(self, key: str, date_from: str = "", date_to: str = "") -> ReportResult:
        method: Callable[..., ReportResult] | None = getattr(self, key, None)
        if method is None:
            raise ValueError(f"Unknown report: {key}")
        return method(date_from, date_to)


def _sum_rows(rows: list[dict], keys: tuple[str, ...]) -> dict[str, Any]:
    return {key: sum(int(row.get(key) or 0) for row in rows) for key in keys}


def _range_label(date_from: str, date_to: str) -> str:
    if not date_from and not date_to:
        return ""
    return f"{dates.fmt_date(date_from)} to {dates.fmt_date(date_to)}"
