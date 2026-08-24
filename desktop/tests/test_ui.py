"""Headless checks that the screens build, react and print.

These run offscreen (no display needed), which is enough to catch the mistakes
that actually happen when wiring Qt: a bad signal name, a missing column, a
dialog that cannot be constructed.
"""

from __future__ import annotations

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

pytest.importorskip("PySide6")

import shiboken6  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from pharmacy_desktop.core.money import to_paisa  # noqa: E402
from pharmacy_desktop.ui import printing, theme  # noqa: E402
from pharmacy_desktop.ui.main_window import PAGES, MainWindow  # noqa: E402


@pytest.fixture(scope="session")
def qt_app():
    app = QApplication.instance() or QApplication([])
    theme.apply(app)
    yield app
    # Qt has to be taken down while its Python wrappers are still alive. Left to
    # the interpreter's own shutdown, the C++ QApplication outlives objects it
    # still points at and the process dies with a segfault *after* the tests
    # have passed.
    app.closeAllWindows()
    app.processEvents()
    shiboken6.delete(app)


@pytest.fixture()
def window(qt_app, app, product, monkeypatch):
    # The start-up reminder is a modal box; it would block a headless run.
    monkeypatch.setattr(MainWindow, "_show_startup_alerts", lambda self: None)
    win = MainWindow(app)
    win.resize(1400, 900)
    yield win
    win.close()
    # The window holds pages that hold the database; destroy it now, before the
    # AppContext fixture closes that database underneath it.
    shiboken6.delete(win)
    qt_app.processEvents()


def test_every_screen_builds_and_refreshes(window, qt_app):
    for _label, key, _factory, _permission, _shortcut in PAGES:
        window.show_page(key)
        qt_app.processEvents()
        assert key in window.pages
        window.pages[key].refresh(force=True)


def test_dashboard_shows_the_days_takings(window, app, product, qt_app):
    cart = app.sales.new_cart()
    app.sales.add_to_cart(cart, product, 10)
    app.sales.complete_sale(cart, user=app.auth.current_user, paid_amount=cart.net_amount)
    window.show_page("dashboard")
    page = window.pages["dashboard"]
    page.refresh(force=True)
    assert "90.00" in page.cards["sales_today"]._value.text()
    assert "10.00" in page.cards["savings_today"]._value.text()


def test_counter_screen_builds_a_bill(window, app, product, qt_app):
    window.show_page("pos")
    page = window.pages["pos"]
    page.search.setText("Panadol")
    page._run_search()
    qt_app.processEvents()
    assert page.results.rowCount() == 1

    page.quantity.setValue(4)
    page._add_highlighted()
    assert len(page.cart.lines) == 1
    assert page.cart.net_amount == to_paisa("36.00")
    assert "36.00" in page.total_labels["net"].text()

    page.cart_table.selectRow(0)
    page._bump(1)
    assert page.cart.lines[0].quantity == 5
    page._remove_line()
    assert page.cart.is_empty


def test_counter_screen_refuses_more_than_the_shelf_holds(window, app, product, monkeypatch):
    warnings = []
    monkeypatch.setattr("pharmacy_desktop.ui.pages.pos.warn", lambda *args: warnings.append(args))
    window.show_page("pos")
    page = window.pages["pos"]
    page.search.setText("Panadol")
    page._run_search()
    page.quantity.setValue(500)
    page._add_highlighted()
    assert page.cart.is_empty
    assert warnings, "the cashier should have been told the stock is not there"


def test_stock_screen_lists_batches_and_flags_expiry(window, app, product):
    app.inventory.add_stock(
        product_id=int(product["id"]), quantity=5, batch_no="OLD", expiry_date="2020-01-01"
    )
    window.show_page("stock")
    page = window.pages["stock"]
    page.view.setCurrentIndex(2)  # "Already expired"
    page.reload()
    assert page.table.rowCount() == 1
    assert page.table.current()["batch_no"] == "OLD"


def test_reports_screen_runs_each_report(window, qt_app):
    window.show_page("reports")
    page = window.pages["reports"]
    for index in range(page.list.count()):
        page.list.setCurrentRow(index)
        qt_app.processEvents()
        assert page.current_report is not None
        assert page.result_title.text()


def test_receipt_prints_to_pdf(app, product, tmp_path, qt_app):
    cart = app.sales.new_cart()
    app.sales.add_to_cart(cart, product, 3)
    sale_id = app.sales.complete_sale(
        cart, user=app.auth.current_user, paid_amount=to_paisa("100")
    )
    for page_format in (printing.THERMAL, printing.A5, printing.A4):
        content = printing.receipt_html(
            app.settings,
            app.sales.get_sale(sale_id),
            app.sales.sale_items(sale_id),
            page_format=page_format,
        )
        assert "Ten Percent Discount Pharmacy" in content
        assert "You saved" in content
        path = printing.save_pdf(content, tmp_path / f"{page_format}.pdf", page_format=page_format)
        assert path.exists() and path.stat().st_size > 800


def test_report_sheet_prints_to_pdf(app, product, tmp_path, qt_app):
    from pharmacy_desktop.core import dates

    cart = app.sales.new_cart()
    app.sales.add_to_cart(cart, product, 2)
    app.sales.complete_sale(cart, user=app.auth.current_user, paid_amount=cart.net_amount)
    report = app.reports.run("sales_summary", *dates.date_range("month"))
    content = printing.report_html(app.settings, report)
    path = printing.save_pdf(content, tmp_path / "report.pdf")
    assert path.exists() and path.stat().st_size > 800
