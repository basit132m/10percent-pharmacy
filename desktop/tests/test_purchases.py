import pytest

from pharmacy_desktop.core.errors import ValidationError
from pharmacy_desktop.core.money import to_paisa
from pharmacy_desktop.core.services.purchases import PurchaseDraft, PurchaseLine


@pytest.fixture()
def supplier(app):
    return app.parties.create("supplier", {"name": "Al-Madina Pharma", "phone": "0300-1234567"})


def _draft(app, supplier_id, product, **kwargs):
    draft = PurchaseDraft(supplier_id=supplier_id, supplier_bill_no="B-77")
    draft.lines.append(
        PurchaseLine(
            product_id=int(product["id"]),
            product_name=product["name"],
            quantity=kwargs.get("quantity", 100),
            unit_cost=kwargs.get("unit_cost", to_paisa("8.00")),
            batch_no=kwargs.get("batch_no", "NEW-1"),
            expiry_date=kwargs.get("expiry_date", "2029-06-30"),
            bonus_quantity=kwargs.get("bonus_quantity", 0),
            unit_sale_price=kwargs.get("unit_sale_price", to_paisa("10.00")),
            discount_percent=kwargs.get("discount_percent", 0.0),
        )
    )
    return draft


def test_receiving_a_bill_puts_stock_on_the_shelf_and_money_on_the_ledger(
    app, product, supplier
):
    draft = _draft(app, supplier, product)
    purchase_id = app.purchases.create_purchase(
        draft, user=app.auth.current_user, paid_amount=to_paisa("300")
    )
    purchase = app.purchases.get_purchase(purchase_id)
    assert purchase["net_amount"] == to_paisa("800.00")
    assert app.inventory.stock_on_hand(int(product["id"])) == 200
    # We owe the supplier 800 less the 300 paid: balance is negative (payable).
    assert app.parties.balance(supplier) == -to_paisa("500.00")


def test_bonus_units_lower_the_cost_per_unit(app, product, supplier):
    draft = _draft(app, supplier, product, quantity=100, bonus_quantity=20)
    app.purchases.create_purchase(draft, user=app.auth.current_user)
    batch = [
        row for row in app.inventory.batches_for(int(product["id"])) if row["batch_no"] == "NEW-1"
    ][0]
    assert batch["quantity"] == 120
    assert batch["purchase_price"] == to_paisa("6.67")  # 800.00 spread over 120 units


def test_a_trade_discount_reduces_the_bill(app, product, supplier):
    draft = _draft(app, supplier, product, discount_percent=10)
    app.purchases.create_purchase(draft, user=app.auth.current_user)
    assert app.purchases.list_purchases()[0]["net_amount"] == to_paisa("720.00")


def test_paying_more_than_the_bill_is_refused(app, product, supplier):
    draft = _draft(app, supplier, product)
    with pytest.raises(ValidationError):
        app.purchases.create_purchase(
            draft, user=app.auth.current_user, paid_amount=to_paisa("900")
        )


def test_selling_price_from_the_bill_updates_the_medicine(app, product, supplier):
    draft = _draft(app, supplier, product, unit_sale_price=to_paisa("12.50"))
    app.purchases.create_purchase(draft, user=app.auth.current_user)
    assert app.catalog.get(int(product["id"]))["sale_price"] == to_paisa("12.50")


def test_a_wrongly_entered_bill_can_be_deleted_until_it_is_sold_from(app, product, supplier):
    draft = _draft(app, supplier, product)
    purchase_id = app.purchases.create_purchase(draft, user=app.auth.current_user)
    app.purchases.delete_purchase(purchase_id, user=app.auth.current_user)
    assert app.inventory.stock_on_hand(int(product["id"])) == 100
    assert app.parties.balance(supplier) == 0


def test_a_bill_partly_sold_cannot_be_deleted(app, product, supplier):
    draft = _draft(app, supplier, product, batch_no="ONLY", quantity=10)
    purchase_id = app.purchases.create_purchase(draft, user=app.auth.current_user)
    app.db.execute("UPDATE batches SET quantity = 0 WHERE batch_no = 'B-1'")
    cart = app.sales.new_cart()
    app.sales.add_to_cart(cart, app.catalog.get(int(product["id"])), 3)
    app.sales.complete_sale(cart, user=app.auth.current_user, paid_amount=cart.net_amount)
    with pytest.raises(ValidationError):
        app.purchases.delete_purchase(purchase_id, user=app.auth.current_user)


def test_returning_stock_to_the_supplier_reduces_what_we_owe(app, product, supplier):
    draft = _draft(app, supplier, product)
    app.purchases.create_purchase(draft, user=app.auth.current_user)
    batch = [
        row for row in app.inventory.batches_for(int(product["id"])) if row["batch_no"] == "NEW-1"
    ][0]
    app.purchases.return_to_supplier(
        supplier,
        [{"batch_id": int(batch["id"]), "quantity": 25}],
        user=app.auth.current_user,
        reason="Damaged carton",
    )
    assert app.inventory.stock_on_hand(int(product["id"])) == 175
    assert app.parties.balance(supplier) == -to_paisa("600.00")
