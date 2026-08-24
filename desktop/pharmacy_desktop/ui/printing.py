"""Printing: customer receipts, invoice copies and report sheets.

Documents are built as small HTML pages and handed to Qt's print engine, which
means the same markup can go to an 80 mm thermal roll, to an A4/A5 sheet, or to
a PDF file — no printer driver assumptions, and nothing to install.
"""

from __future__ import annotations

import html
from pathlib import Path

from PySide6.QtCore import QMarginsF, QSizeF
from PySide6.QtGui import QPageLayout, QPageSize, QTextDocument
from PySide6.QtPrintSupport import QPrintDialog, QPrinter, QPrintPreviewDialog

from ..core import dates
from ..core.money import fmt
from . import theme

THERMAL = "thermal80"
A5 = "a5"
A4 = "a4"


# --------------------------------------------------------------------- pages
def _page_layout(page_format: str) -> QPageLayout:
    if page_format == THERMAL:
        size = QPageSize(QSizeF(80, 297), QPageSize.Millimeter, "Roll80", QPageSize.ExactMatch)
        margins = QMarginsF(3, 4, 3, 4)
    elif page_format == A5:
        size = QPageSize(QPageSize.A5)
        margins = QMarginsF(10, 10, 10, 10)
    else:
        size = QPageSize(QPageSize.A4)
        margins = QMarginsF(12, 12, 12, 12)
    return QPageLayout(size, QPageLayout.Portrait, margins, QPageLayout.Millimeter)


def _document(content: str, page_format: str) -> QTextDocument:
    document = QTextDocument()
    document.setDefaultStyleSheet(_stylesheet(page_format))
    document.setHtml(content)
    if page_format == THERMAL:
        document.setTextWidth(280)
    return document


def _stylesheet(page_format: str) -> str:
    if page_format == THERMAL:
        return """
            body { font-family: 'Segoe UI', Arial, sans-serif; font-size: 8.5pt; }
            .shop { font-size: 12pt; font-weight: bold; text-align: center; }
            .tag  { font-size: 8pt; text-align: center; }
            .meta { font-size: 7.5pt; }
            table { width: 100%; border-collapse: collapse; }
            th { font-size: 7.5pt; text-align: left; border-bottom: 1px solid #000; }
            td { font-size: 8pt; padding: 1px 0; }
            .r { text-align: right; }
            .c { text-align: center; }
            .total { font-size: 11pt; font-weight: bold; }
            .save { font-size: 9pt; font-weight: bold; text-align: center; }
            .foot { font-size: 7.5pt; text-align: center; }
        """
    return f"""
        body {{ font-family: 'Segoe UI', Arial, sans-serif; font-size: 10pt;
                color: {theme.INK}; }}
        .shop {{ font-size: 17pt; font-weight: bold; color: {theme.GREEN}; }}
        .tag  {{ font-size: 10pt; color: {theme.GOLD}; font-weight: bold; }}
        .meta {{ font-size: 9pt; color: #444; }}
        .title {{ font-size: 12pt; font-weight: bold; }}
        table {{ width: 100%; border-collapse: collapse; }}
        th {{ background: #EEF2F5; text-align: left; padding: 5px 6px;
              border-bottom: 1px solid #99A; font-size: 9pt; }}
        td {{ padding: 4px 6px; border-bottom: 1px solid #E2E7EC; font-size: 9.5pt; }}
        .r {{ text-align: right; }}
        .c {{ text-align: center; }}
        .total {{ font-size: 13pt; font-weight: bold; }}
        .save {{ font-size: 11pt; font-weight: bold; color: {theme.GREEN}; }}
        .foot {{ font-size: 8.5pt; color: #555; text-align: center; }}
    """


# ------------------------------------------------------------------ receipts
def receipt_html(settings, sale, items, *, page_format: str = THERMAL, copy_label: str = "") -> str:
    """Build the customer's bill. ``sale`` and ``items`` are database rows."""
    esc = html.escape
    shop = esc(settings.get("pharmacy_name"))
    tagline = esc(settings.get("pharmacy_tagline"))
    address = esc(settings.get("pharmacy_address"))
    phone = esc(settings.get("pharmacy_phone"))
    licence = esc(settings.get("license_no"))
    narrow = page_format == THERMAL

    head = [
        f'<div class="shop">{shop}</div>',
        f'<div class="tag">{tagline}</div>' if tagline else "",
        f'<div class="meta c">{address}</div>' if address else "",
        f'<div class="meta c">Phone: {phone}</div>' if phone else "",
        f'<div class="meta c">Drug licence: {licence}</div>' if licence else "",
    ]

    customer = sale["party_name"] if _has(sale, "party_name") else None
    customer = customer or sale["customer_name"] or "Walk-in customer"
    meta_rows = [
        ("Invoice", esc(str(sale["invoice_no"]))),
        ("Date", dates.fmt_datetime(sale["sale_date"])),
        ("Customer", esc(str(customer))),
    ]
    if sale["doctor_name"]:
        meta_rows.append(("Doctor", esc(str(sale["doctor_name"]))))
    if _has(sale, "cashier_name") and sale["cashier_name"]:
        meta_rows.append(("Served by", esc(str(sale["cashier_name"]))))
    meta = "".join(
        f'<tr><td class="meta">{label}</td><td class="meta r">{value}</td></tr>'
        for label, value in meta_rows
    )

    lines = []
    for index, item in enumerate(items, start=1):
        name = esc(str(item["product_name"]))
        expiry = dates.fmt_date(item["expiry_date"], "")
        batch = esc(str(item["batch_no"] or ""))
        detail = " · ".join(part for part in (f"Batch {batch}" if batch and batch != "-" else "",
                                              f"Exp {expiry}" if expiry else "") if part)
        if narrow:
            lines.append(
                f'<tr><td colspan="4">{index}. {name}'
                + (f'<br/><span class="meta">{detail}</span>' if detail else "")
                + "</td></tr>"
                f'<tr><td class="c">{item["quantity"]}</td>'
                f'<td class="r">{fmt(item["unit_price"])}</td>'
                f'<td class="r">-{fmt(item["discount_amount"])}</td>'
                f'<td class="r">{fmt(item["line_total"])}</td></tr>'
            )
        else:
            lines.append(
                f"<tr><td>{index}</td><td>{name}"
                + (f'<br/><span class="meta">{detail}</span>' if detail else "")
                + f'</td><td class="c">{item["quantity"]}</td>'
                f'<td class="r">{fmt(item["unit_price"])}</td>'
                f'<td class="r">{fmt(item["discount_amount"])}</td>'
                f'<td class="r">{fmt(item["line_total"])}</td></tr>'
            )

    header_row = (
        '<tr><th class="c">Qty</th><th class="r">Rate</th><th class="r">Disc</th>'
        '<th class="r">Amount</th></tr>'
        if narrow
        else '<tr><th>#</th><th>Medicine</th><th class="c">Qty</th><th class="r">Rate</th>'
        '<th class="r">Discount</th><th class="r">Amount</th></tr>'
    )

    def total_row(label: str, value: str, *, css: str = "") -> str:
        span = 3 if narrow else 5
        return (
            f'<tr><td class="r{css and " " + css}" colspan="{span}">{label}</td>'
            f'<td class="r {css}">{value}</td></tr>'
        )

    totals = [total_row("Sub total", fmt(sale["gross_amount"]))]
    if sale["discount_amount"]:
        totals.append(total_row("Discount", "-" + fmt(sale["discount_amount"])))
    if sale["tax_amount"]:
        totals.append(total_row("Tax", fmt(sale["tax_amount"])))
    if sale["round_off"]:
        totals.append(total_row("Round off", fmt(sale["round_off"])))
    totals.append(total_row("TOTAL", fmt(sale["net_amount"]), css="total"))
    totals.append(total_row(f"Paid ({esc(str(sale['payment_method']))})", fmt(sale["paid_amount"])))
    if sale["change_amount"]:
        totals.append(total_row("Change", fmt(sale["change_amount"])))
    due = int(sale["net_amount"]) - int(sale["paid_amount"])
    if due > 0:
        totals.append(total_row("Balance due", fmt(due)))

    savings = ""
    if sale["discount_amount"] and settings.get_bool("show_savings_on_receipt", True):
        savings = (
            f'<div class="save">You saved {fmt(sale["discount_amount"], symbol=True)} today</div>'
        )

    footer = esc(settings.get("receipt_footer"))
    label = f'<div class="c meta">{esc(copy_label)}</div>' if copy_label else ""
    return f"""
      <div>
        {''.join(head)}
        {label}
        <hr/>
        <table>{meta}</table>
        <hr/>
        <table>{header_row}{''.join(lines)}</table>
        <hr/>
        <table>{''.join(totals)}</table>
        {savings}
        <hr/>
        <div class="foot">{footer}</div>
        <div class="foot">Medicines are not returnable without this receipt.</div>
      </div>
    """


def purchase_html(settings, purchase, items) -> str:
    """A goods-received note for the supplier bill just entered."""
    esc = html.escape
    rows = "".join(
        f"<tr><td>{index}</td><td>{esc(str(item['product_name']))}</td>"
        f"<td class='c'>{esc(str(item['batch_no'] or ''))}</td>"
        f"<td class='c'>{dates.fmt_date(item['expiry_date'], '—')}</td>"
        f"<td class='r'>{item['quantity']}</td>"
        f"<td class='r'>{item['bonus_quantity']}</td>"
        f"<td class='r'>{fmt(item['unit_cost'])}</td>"
        f"<td class='r'>{fmt(item['line_total'])}</td></tr>"
        for index, item in enumerate(items, start=1)
    )
    due = int(purchase["net_amount"]) - int(purchase["paid_amount"])
    return f"""
      <div class="shop">{esc(settings.get('pharmacy_name'))}</div>
      <div class="meta">{esc(settings.get('pharmacy_address'))}</div>
      <br/>
      <div class="title">Goods received note — {esc(str(purchase['reference_no']))}</div>
      <table>
        <tr><td class="meta">Supplier</td>
            <td class="meta">{esc(str(purchase['supplier_name'] or '—'))}</td>
            <td class="meta r">Supplier bill</td>
            <td class="meta r">{esc(str(purchase['supplier_bill_no'] or '—'))}</td></tr>
        <tr><td class="meta">Date</td>
            <td class="meta">{dates.fmt_date(purchase['purchase_date'])}</td>
            <td class="meta r">Entered by</td>
            <td class="meta r">{esc(str(purchase['username'] or '—'))}</td></tr>
      </table>
      <br/>
      <table>
        <tr><th>#</th><th>Medicine</th><th class="c">Batch</th><th class="c">Expiry</th>
            <th class="r">Qty</th><th class="r">Bonus</th><th class="r">Cost</th>
            <th class="r">Amount</th></tr>
        {rows}
        <tr><td colspan="7" class="r">Gross</td>
            <td class="r">{fmt(purchase['gross_amount'])}</td></tr>
        <tr><td colspan="7" class="r">Discount</td>
            <td class="r">-{fmt(purchase['discount_amount'])}</td></tr>
        <tr><td colspan="7" class="r total">Net payable</td>
            <td class="r total">{fmt(purchase['net_amount'])}</td></tr>
        <tr><td colspan="7" class="r">Paid</td>
            <td class="r">{fmt(purchase['paid_amount'])}</td></tr>
        <tr><td colspan="7" class="r">Balance</td><td class="r">{fmt(due)}</td></tr>
      </table>
    """


def report_html(settings, report) -> str:
    """Render any :class:`ReportResult` as a printable sheet."""
    from ..core.services import reports as report_module

    esc = html.escape
    header = "".join(f"<th>{esc(column.label)}</th>" for column in report.columns)
    body = []
    for row in report.rows:
        cells = []
        for column in report.columns:
            value = row.get(column.key)
            if column.kind == report_module.MONEY:
                cells.append(f'<td class="r">{fmt(int(value or 0))}</td>')
            elif column.kind in (report_module.INT,):
                cells.append(f'<td class="r">{int(value or 0):,}</td>')
            elif column.kind == report_module.PERCENT:
                cells.append(f'<td class="r">{float(value or 0):.2f}%</td>')
            elif column.kind == report_module.DATE:
                cells.append(f'<td class="c">{dates.fmt_date(value, "—")}</td>')
            elif column.kind == report_module.DATETIME:
                cells.append(f'<td class="c">{dates.fmt_datetime(value, "—")}</td>')
            else:
                cells.append(f"<td>{esc(str(value if value is not None else ''))}</td>")
        body.append("<tr>" + "".join(cells) + "</tr>")
    totals = ""
    if report.totals:
        cells = []
        for index, column in enumerate(report.columns):
            if index == 0:
                cells.append("<td><b>TOTAL</b></td>")
                continue
            value = report.totals.get(column.key)
            if value is None:
                cells.append("<td></td>")
            elif column.kind == report_module.MONEY:
                cells.append(f'<td class="r"><b>{fmt(int(value))}</b></td>')
            elif column.kind == report_module.PERCENT:
                cells.append(f'<td class="r"><b>{float(value):.2f}%</b></td>')
            elif column.kind == report_module.INT:
                cells.append(f'<td class="r"><b>{int(value):,}</b></td>')
            else:
                cells.append(f"<td><b>{esc(str(value))}</b></td>")
        totals = "<tr>" + "".join(cells) + "</tr>"
    return f"""
      <div class="shop">{esc(settings.get('pharmacy_name'))}</div>
      <div class="tag">{esc(settings.get('pharmacy_tagline'))}</div>
      <br/>
      <div class="title">{esc(report.title)}</div>
      <div class="meta">{esc(report.subtitle)}</div>
      <br/>
      <table><tr>{header}</tr>{''.join(body)}{totals}</table>
      <br/>
      <div class="foot">Printed {dates.fmt_datetime(dates.now_iso())}</div>
    """


# ------------------------------------------------------------------ output
def print_html(parent, content: str, *, page_format: str = A4, ask: bool = True) -> bool:
    printer = QPrinter(QPrinter.HighResolution)
    printer.setPageLayout(_page_layout(page_format))
    if ask:
        dialog = QPrintDialog(printer, parent)
        dialog.setWindowTitle("Print")
        if dialog.exec() != QPrintDialog.Accepted:
            return False
    _document(content, page_format).print_(printer)
    return True


def preview_html(parent, content: str, *, page_format: str = A4) -> None:
    printer = QPrinter(QPrinter.HighResolution)
    printer.setPageLayout(_page_layout(page_format))
    dialog = QPrintPreviewDialog(printer, parent)
    dialog.setWindowTitle("Print preview")
    dialog.resize(920, 780)
    dialog.paintRequested.connect(lambda target: _document(content, page_format).print_(target))
    dialog.exec()


def save_pdf(content: str, path: str | Path, *, page_format: str = A4) -> Path:
    path = Path(path)
    printer = QPrinter(QPrinter.HighResolution)
    printer.setOutputFormat(QPrinter.PdfFormat)
    printer.setOutputFileName(str(path))
    printer.setPageLayout(_page_layout(page_format))
    _document(content, page_format).print_(printer)
    return path


def _has(row, key: str) -> bool:
    try:
        return key in row.keys()
    except AttributeError:
        return hasattr(row, key)
