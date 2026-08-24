from pharmacy_desktop.core import dates
from pharmacy_desktop.core.money import to_paisa


def _sell(app, product, quantity, **kwargs):
    cart = app.sales.new_cart()
    app.sales.add_to_cart(cart, product, quantity)
    return app.sales.complete_sale(
        cart, user=app.auth.current_user, paid_amount=cart.net_amount, **kwargs
    )


def test_dashboard_adds_up_the_day(app, product):
    _sell(app, product, 10)  # 100 gross, 10 discount, 90 net, 80 cost
    summary = app.reports.dashboard()
    assert summary["today"]["bills"] == 1
    assert summary["today"]["net"] == to_paisa("90.00")
    assert summary["today"]["discount"] == to_paisa("10.00")
    assert summary["today"]["profit"] == to_paisa("10.00")
    assert summary["cash_today"] == to_paisa("90.00")
    assert summary["stock_value"] == to_paisa("720.00")
    assert summary["products"] == 1


def test_sales_summary_totals_match_the_invoices(app, product):
    _sell(app, product, 4)
    _sell(app, product, 6)
    today = dates.today_iso()
    report = app.reports.run("sales_summary", today, today)
    assert report.totals["bills"] == 2
    assert report.totals["gross"] == to_paisa("100.00")
    assert report.totals["discount"] == to_paisa("10.00")
    assert report.totals["net"] == to_paisa("90.00")


def test_discount_report_shows_the_effective_rate(app, product):
    _sell(app, product, 10)
    today = dates.today_iso()
    report = app.reports.run("discount_report", today, today)
    assert report.totals["rate"] == 10.0


def test_profit_report_uses_the_cost_of_the_batch_sold(app, product):
    _sell(app, product, 10)
    today = dates.today_iso()
    report = app.reports.run("profit_report", today, today)
    assert report.totals["revenue"] == to_paisa("90.00")
    assert report.totals["cost"] == to_paisa("80.00")
    assert report.totals["profit"] == to_paisa("10.00")


def test_every_registered_report_runs(app, product):
    _sell(app, product, 3)
    date_from, date_to = dates.date_range("month")
    for key, label, _needs_dates in app.reports.available():
        report = app.reports.run(key, date_from, date_to)
        assert report.title
        assert report.columns, f"{label} has no columns"


def test_a_report_exports_to_csv(app, product, tmp_path):
    _sell(app, product, 5)
    today = dates.today_iso()
    report = app.reports.run("invoice_register", today, today)
    path = report.export_csv(tmp_path / "register.csv")
    text = path.read_text(encoding="utf-8-sig")
    assert "Invoice register" in text
    assert "INV-00001" in text
    assert "45.00" in text  # 5 x 10.00 less 10%


def test_stock_valuation_and_reorder_list(app, product):
    valuation = app.reports.run("stock_valuation")
    assert valuation.totals["cost_value"] == to_paisa("800.00")
    batch_id = int(app.inventory.batches_for(int(product["id"]))[0]["id"])
    app.inventory.adjust(batch_id=batch_id, quantity=-90, reason="Stock count correction")
    reorder = app.reports.run("low_stock_report")
    assert reorder.rows[0]["shortfall"] == 10


def test_day_book_separates_money_in_from_money_out(app, product):
    _sell(app, product, 10)
    supplier = app.parties.create("supplier", {"name": "Al-Madina"})
    app.parties.record_payment(supplier, amount=to_paisa("500"), direction="out")
    today = dates.today_iso()
    report = app.reports.run("day_book", today, today)
    assert report.totals["amount_in"] == to_paisa("90.00")
    assert report.totals["amount_out"] == to_paisa("500.00")
