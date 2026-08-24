import pytest

from pharmacy_desktop.core.errors import ValidationError
from pharmacy_desktop.core.money import to_paisa


def test_customer_ledger_runs_a_balance(app, product):
    customer = app.parties.create(
        "customer", {"name": "Ayesha Bibi", "phone": "0345-1112223", "opening_balance": to_paisa("200")}
    )
    cart = app.sales.new_cart()
    cart.customer_id = customer
    app.sales.add_to_cart(cart, product, 10)
    app.sales.complete_sale(
        cart, user=app.auth.current_user, paid_amount=0, payment_method="Credit"
    )
    app.parties.record_payment(customer, amount=to_paisa("100"), direction="in")
    ledger = app.parties.ledger(customer)
    assert [row["description"] for row in ledger] == [
        "Opening balance",
        "Invoice INV-00001",
        "Payment received (Cash)",
    ]
    assert ledger[-1]["balance"] == to_paisa("190.00")
    assert app.parties.balance(customer) == to_paisa("190.00")


def test_supplier_balance_is_shown_as_a_payable(app):
    supplier = app.parties.create(
        "supplier", {"name": "Punjab Drug House", "opening_balance": to_paisa("5000")}
    )
    assert app.parties.balance(supplier) == -to_paisa("5000")
    report = app.reports.run("payables")
    assert report.rows[0]["balance"] == to_paisa("5000")
    assert report.totals["balance"] == to_paisa("5000")


def test_an_account_with_history_cannot_be_deleted(app):
    customer = app.parties.create("customer", {"name": "Rana Medical"})
    app.parties.record_payment(customer, amount=to_paisa("50"), direction="in")
    with pytest.raises(ValidationError):
        app.parties.delete(customer)
    app.parties.set_active(customer, False)
    assert app.parties.list_parties("customer") == []


def test_backup_and_restore_round_trip(app, product, tmp_path):
    cart = app.sales.new_cart()
    app.sales.add_to_cart(cart, product, 5)
    app.sales.complete_sale(cart, user=app.auth.current_user, paid_amount=cart.net_amount)
    backup = app.backups.create("beforetest")
    assert backup.exists()

    # Carry on trading, then roll back to the backup.
    cart = app.sales.new_cart()
    app.sales.add_to_cart(cart, product, 5)
    app.sales.complete_sale(cart, user=app.auth.current_user, paid_amount=cart.net_amount)
    assert len(app.sales.list_sales()) == 2

    app.backups.restore(backup)
    assert len(app.sales.list_sales()) == 1
    assert app.inventory.stock_on_hand(int(product["id"])) == 95


def test_restoring_a_file_that_is_not_a_backup_is_refused(app, tmp_path):
    junk = tmp_path / "holiday-photo.db"
    junk.write_bytes(b"not a database")
    with pytest.raises(ValidationError):
        app.backups.restore(junk)


def test_old_backups_are_pruned(app):
    for index in range(5):
        app.backups.create(f"copy{index}")
    assert len(app.backups.list_backups()) == 5
    app.backups.prune(keep=2)
    assert len(app.backups.list_backups()) == 2


def test_demo_data_loads_and_balances(app):
    from pharmacy_desktop.core.demo import seed_demo

    result = seed_demo(app, days=4, seed=3)
    assert result["products"] == 40
    assert result["sales"] > 10
    summary = app.reports.dashboard()
    assert summary["stock_value"] > 0
    assert summary["month"]["net"] > 0
