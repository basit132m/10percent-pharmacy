import pytest

from pharmacy_desktop.core.errors import ValidationError
from pharmacy_desktop.core.money import to_paisa


def test_ten_percent_comes_off_automatically(app, product):
    cart = app.sales.new_cart()
    app.sales.add_to_cart(cart, product, 5)
    line = cart.lines[0]
    assert line.discount_percent == 10.0
    assert line.gross == to_paisa("50.00")
    assert line.discount_amount == to_paisa("5.00")
    assert cart.net_amount == to_paisa("45.00")
    assert cart.savings == to_paisa("5.00")


def test_discount_percent_is_a_setting_not_a_constant(app, product):
    app.settings.set("default_discount_percent", "15")
    cart = app.sales.new_cart()
    app.sales.add_to_cart(cart, product, 2)
    assert cart.discount_amount == to_paisa("3.00")


def test_a_product_marked_not_eligible_gets_no_discount(app, product):
    app.catalog.update_product(int(product["id"]), {**dict(product), "discount_eligible": 0})
    cart = app.sales.new_cart()
    app.sales.add_to_cart(cart, app.catalog.get(int(product["id"])), 3)
    assert cart.discount_amount == 0
    assert cart.net_amount == to_paisa("30.00")


def test_round_off_lands_on_whole_rupees(app, product):
    app.catalog.update_product(
        int(product["id"]), {**dict(product), "sale_price": to_paisa("3.33")}
    )
    fresh = app.catalog.get(int(product["id"]))
    cart = app.sales.new_cart()
    app.sales.add_to_cart(cart, fresh, 1, unit_price=to_paisa("3.33"))
    assert cart.subtotal == to_paisa("3.00")  # 3.33 less 10% = 2.997, rounded to 3.00
    assert cart.net_amount % 100 == 0


def test_stock_leaves_the_shelf_when_the_bill_is_saved(app, product):
    cart = app.sales.new_cart()
    app.sales.add_to_cart(cart, product, 30)
    sale_id = app.sales.complete_sale(
        cart, user=app.auth.current_user, paid_amount=cart.net_amount
    )
    assert app.inventory.stock_on_hand(int(product["id"])) == 70
    sale = app.sales.get_sale(sale_id)
    assert sale["invoice_no"].startswith("INV-")
    assert sale["net_amount"] == to_paisa("270.00")
    assert sale["cost_amount"] == to_paisa("240.00")


def test_selling_more_than_is_on_the_shelf_is_refused(app, product):
    cart = app.sales.new_cart()
    with pytest.raises(ValidationError):
        app.sales.add_to_cart(cart, product, 500)


def test_the_batch_expiring_first_is_sold_first(app, product):
    product_id = int(product["id"])
    app.inventory.add_stock(
        product_id=product_id,
        quantity=40,
        batch_no="B-SOON",
        expiry_date="2027-01-31",
        purchase_price=to_paisa("8.00"),
        sale_price=to_paisa("10.00"),
    )
    cart = app.sales.new_cart()
    app.sales.add_to_cart(cart, product, 50)
    assert [(line.batch_no, line.quantity) for line in cart.lines] == [
        ("B-SOON", 40),
        ("B-1", 10),
    ]


def test_expired_batches_are_never_sold(app, product):
    product_id = int(product["id"])
    app.db.execute(
        "UPDATE batches SET expiry_date = '2020-01-01' WHERE product_id = ?", (product_id,)
    )
    cart = app.sales.new_cart()
    with pytest.raises(ValidationError):
        app.sales.add_to_cart(cart, app.catalog.get(product_id), 1)


def test_change_is_worked_out_for_the_customer(app, product):
    cart = app.sales.new_cart()
    app.sales.add_to_cart(cart, product, 10)  # 100 less 10% = 90
    sale_id = app.sales.complete_sale(
        cart, user=app.auth.current_user, paid_amount=to_paisa("500")
    )
    assert app.sales.get_sale(sale_id)["change_amount"] == to_paisa("410.00")


def test_an_unpaid_bill_needs_a_named_customer(app, product):
    cart = app.sales.new_cart()
    app.sales.add_to_cart(cart, product, 10)
    with pytest.raises(ValidationError):
        app.sales.complete_sale(cart, user=app.auth.current_user, paid_amount=0)


def test_credit_sale_lands_on_the_customer_ledger(app, product):
    customer_id = app.parties.create("customer", {"name": "Muhammad Aslam"})
    cart = app.sales.new_cart()
    cart.customer_id = customer_id
    cart.customer_name = "Muhammad Aslam"
    app.sales.add_to_cart(cart, product, 10)
    app.sales.complete_sale(
        cart, user=app.auth.current_user, paid_amount=to_paisa("40"), payment_method="Credit"
    )
    assert app.parties.balance(customer_id) == to_paisa("50.00")
    app.parties.record_payment(customer_id, amount=to_paisa("50"), direction="in")
    assert app.parties.balance(customer_id) == 0


def test_a_bill_can_be_held_and_picked_up_again(app, product):
    cart = app.sales.new_cart()
    app.sales.add_to_cart(cart, product, 3)
    cart.customer_name = "Waiting outside"
    held_id = app.sales.hold_cart(cart, "Counter 2", user=app.auth.current_user)
    assert len(app.sales.held_carts()) == 1
    resumed = app.sales.resume_cart(held_id)
    assert resumed.customer_name == "Waiting outside"
    assert resumed.net_amount == cart.net_amount
    assert app.sales.held_carts() == []


def test_returning_goods_puts_them_back_and_refunds_the_discounted_price(app, product):
    cart = app.sales.new_cart()
    app.sales.add_to_cart(cart, product, 10)
    sale_id = app.sales.complete_sale(
        cart, user=app.auth.current_user, paid_amount=cart.net_amount
    )
    item = app.sales.sale_items(sale_id)[0]
    app.sales.create_return(
        sale_id,
        [{"sale_item_id": int(item["id"]), "quantity": 4}],
        user=app.auth.current_user,
        reason="Wrong strength",
    )
    assert app.inventory.stock_on_hand(int(product["id"])) == 94
    assert app.sales.get_sale(sale_id)["status"] == "part-returned"
    assert app.sales.list_returns()[0]["total_amount"] == to_paisa("36.00")


def test_the_same_unit_cannot_be_returned_twice(app, product):
    cart = app.sales.new_cart()
    app.sales.add_to_cart(cart, product, 2)
    sale_id = app.sales.complete_sale(
        cart, user=app.auth.current_user, paid_amount=cart.net_amount
    )
    item_id = int(app.sales.sale_items(sale_id)[0]["id"])
    app.sales.create_return(
        sale_id, [{"sale_item_id": item_id, "quantity": 2}], user=app.auth.current_user
    )
    with pytest.raises(ValidationError):
        app.sales.create_return(
            sale_id, [{"sale_item_id": item_id, "quantity": 1}], user=app.auth.current_user
        )


def test_cancelling_an_invoice_returns_the_stock(app, product):
    cart = app.sales.new_cart()
    app.sales.add_to_cart(cart, product, 25)
    sale_id = app.sales.complete_sale(
        cart, user=app.auth.current_user, paid_amount=cart.net_amount
    )
    app.sales.delete_sale(sale_id, user=app.auth.current_user)
    assert app.inventory.stock_on_hand(int(product["id"])) == 100


def test_invoice_numbers_run_in_sequence(app, product):
    numbers = []
    for _ in range(3):
        cart = app.sales.new_cart()
        app.sales.add_to_cart(cart, product, 1)
        sale_id = app.sales.complete_sale(
            cart, user=app.auth.current_user, paid_amount=cart.net_amount
        )
        numbers.append(app.sales.get_sale(sale_id)["invoice_no"])
    assert numbers == ["INV-00001", "INV-00002", "INV-00003"]
