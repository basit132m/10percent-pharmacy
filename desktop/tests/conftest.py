import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from pharmacy_desktop.core.context import AppContext  # noqa: E402
from pharmacy_desktop.core.money import to_paisa  # noqa: E402


@pytest.fixture()
def app(tmp_path, monkeypatch):
    monkeypatch.setenv("PHARMACY_DATA_DIR", str(tmp_path))
    context = AppContext(tmp_path / "test.db")
    context.auth.login("admin", "admin123")
    yield context
    context.close(backup=False)


@pytest.fixture()
def product(app):
    """A medicine with 100 units in stock at Rs 10.00 retail, Rs 8.00 cost."""
    product_id = app.catalog.create_product(
        {
            "name": "Panadol 500mg",
            "generic_name": "Paracetamol",
            "pack_size": 10,
            "unit_label": "Tablet",
            "purchase_price": to_paisa("8.00"),
            "sale_price": to_paisa("10.00"),
            "reorder_level": 20,
        }
    )
    app.inventory.add_stock(
        product_id=product_id,
        quantity=100,
        batch_no="B-1",
        expiry_date="2030-12-31",
        purchase_price=to_paisa("8.00"),
        sale_price=to_paisa("10.00"),
    )
    return app.catalog.get(product_id)
