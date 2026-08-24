import pytest

from pharmacy_desktop.core.errors import ValidationError
from pharmacy_desktop.core.money import to_paisa


def test_receiving_the_same_batch_twice_merges_it(app, product):
    product_id = int(product["id"])
    app.inventory.add_stock(
        product_id=product_id, quantity=50, batch_no="B-1", expiry_date="2030-12-31"
    )
    batches = app.inventory.batches_for(product_id)
    assert len(batches) == 1
    assert batches[0]["quantity"] == 150


def test_expiry_typed_as_month_and_year_becomes_the_last_day(app, product):
    batch_id = app.inventory.add_stock(
        product_id=int(product["id"]), quantity=5, batch_no="B-9", expiry_date="02/2028"
    )
    assert app.inventory.get_batch(batch_id)["expiry_date"] == "2028-02-29"


def test_a_nonsense_expiry_is_refused(app, product):
    with pytest.raises(ValidationError):
        app.inventory.add_stock(
            product_id=int(product["id"]), quantity=5, batch_no="X", expiry_date="soon"
        )


def test_adjustment_writes_a_traceable_row(app, product):
    batch_id = int(app.inventory.batches_for(int(product["id"]))[0]["id"])
    app.inventory.adjust(
        batch_id=batch_id,
        quantity=-6,
        reason="Damaged / broken",
        note="Bottle broke",
        user=app.auth.current_user,
    )
    assert app.inventory.stock_on_hand(int(product["id"])) == 94
    entry = app.inventory.adjustments()[0]
    assert entry["quantity"] == -6
    assert entry["reason"] == "Damaged / broken"
    assert entry["username"] == "admin"


def test_an_adjustment_cannot_push_a_batch_negative(app, product):
    batch_id = int(app.inventory.batches_for(int(product["id"]))[0]["id"])
    with pytest.raises(ValidationError):
        app.inventory.adjust(batch_id=batch_id, quantity=-101, reason="Lost / stolen")


def test_expired_stock_shows_up_and_can_be_written_off_in_one_go(app, product):
    product_id = int(product["id"])
    app.inventory.add_stock(
        product_id=product_id, quantity=20, batch_no="OLD", expiry_date="2020-01-01"
    )
    assert len(app.inventory.expired()) == 1
    assert app.inventory.sellable_on_hand(product_id) == 100
    result = app.inventory.write_off_expired(user=app.auth.current_user)
    assert result == {"batches": 1, "units": 20, "cost_value": 0}
    assert app.inventory.expired() == []
    assert app.inventory.stock_on_hand(product_id) == 100


def test_expiring_soon_uses_the_window_it_is_given(app, product):
    from datetime import date, timedelta

    soon = (date.today() + timedelta(days=40)).isoformat()
    app.inventory.add_stock(
        product_id=int(product["id"]), quantity=10, batch_no="NEAR", expiry_date=soon
    )
    assert len(app.inventory.expiring_soon(days=90)) == 1
    assert app.inventory.expiring_soon(days=30) == []


def test_low_stock_and_out_of_stock_lists(app, product):
    product_id = int(product["id"])
    batch_id = int(app.inventory.batches_for(product_id)[0]["id"])
    assert app.inventory.low_stock() == []
    app.inventory.adjust(batch_id=batch_id, quantity=-85, reason="Stock count correction")
    assert [row["name"] for row in app.inventory.low_stock()] == ["Panadol 500mg"]
    app.inventory.adjust(batch_id=batch_id, quantity=-15, reason="Stock count correction")
    assert [row["name"] for row in app.inventory.out_of_stock()] == ["Panadol 500mg"]


def test_stock_value_counts_cost_and_retail(app, product):
    value = app.inventory.stock_value()
    assert value["units"] == 100
    assert value["cost_value"] == to_paisa("800.00")
    assert value["retail_value"] == to_paisa("1000.00")


def test_a_batch_that_has_been_sold_from_cannot_be_deleted(app, product):
    cart = app.sales.new_cart()
    app.sales.add_to_cart(cart, product, 1)
    app.sales.complete_sale(cart, user=app.auth.current_user, paid_amount=cart.net_amount)
    batch_id = int(app.inventory.batches_for(int(product["id"]))[0]["id"])
    with pytest.raises(ValidationError):
        app.inventory.delete_batch(batch_id)
